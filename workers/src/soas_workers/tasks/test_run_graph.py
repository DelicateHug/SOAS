"""Test-run a VisualPython2 graph in a sandboxed subprocess without persisting a compiled script."""

import json
import os
import subprocess
import sys
import tempfile
import threading
import time
from datetime import datetime, timezone

import redis

from soas_workers.celery_app import app
from soas_workers.config import config
from soas_workers.db import get_case_incident_ids, get_sensitive_incident_variable_names, update_execution_complete, update_execution_status


@app.task(name="soas.test_run_graph", bind=True, max_retries=0)
def test_run_graph(
    self,
    execution_id: str,
    automation_id: str,
    graph_json: dict,
    parameters: dict,
    incident_id: str | None = None,
    timeout_seconds: int = 300,
    user_role_ids: list[str] | None = None,
    api_token: str | None = None,
    triggering_user_id: str | None = None,
    resume_segment: int | None = None,
):
    """Compile a VP2 graph on-the-fly and execute it in a sandboxed subprocess.

    Unlike ``run_automation`` this task does **not** require a pre-compiled
    script on disk.  It compiles the graph JSON in-process, writes the result
    to a temporary file, and runs it as a subprocess — streaming output over
    Redis pubsub for the frontend.
    """

    # ------------------------------------------------------------------
    # 1. Mark execution as running
    # ------------------------------------------------------------------
    update_execution_status(
        execution_id, "running", worker_id=self.request.hostname
    )

    r = redis.from_url(config.REDIS_URL)
    pubsub_channel = f"execution:{execution_id}:output"

    # ------------------------------------------------------------------
    # 2. Compile graph_json using VP2
    # ------------------------------------------------------------------
    try:
        from visualpython2.serialization.graph_serializer import GraphSerializer
        from visualpython2.compiler.code_generator import CodeGenerator

        sensitive_vars = get_sensitive_incident_variable_names()
        serializer = GraphSerializer()
        graph = serializer.deserialize(graph_json)
        result = CodeGenerator(graph, debug_mode=True, sensitive_var_names=sensitive_vars).generate()

        if not result.success:
            error_msg = "; ".join(result.errors) if result.errors else "Compilation failed"
            r.publish(
                pubsub_channel,
                json.dumps({
                    "type": "compile_error",
                    "errors": result.errors,
                }),
            )
            update_execution_complete(
                execution_id,
                status="failed",
                error_message=error_msg,
            )
            return {"success": False, "errors": result.errors}

        compiled_code = result.code

    except ImportError as exc:
        error_msg = f"VisualPython2 compiler not available: {exc}"
        r.publish(
            pubsub_channel,
            json.dumps({"type": "compile_error", "errors": [error_msg]}),
        )
        update_execution_complete(
            execution_id,
            status="failed",
            error_message=error_msg,
        )
        return {"success": False, "errors": [error_msg]}

    except Exception as exc:
        error_msg = f"Compilation error: {exc}"
        r.publish(
            pubsub_channel,
            json.dumps({"type": "compile_error", "errors": [str(exc)]}),
        )
        update_execution_complete(
            execution_id,
            status="failed",
            error_message=error_msg,
        )
        return {"success": False, "errors": [str(exc)]}

    # ------------------------------------------------------------------
    # 3. Prepend runtime bridge code (SOAS vars + incident vars)
    # ------------------------------------------------------------------

    # 3a. SOAS application-level variables + shared secrets
    # For test runs, load all SOAS vars (user is already authenticated).
    # Fall back to role-based if role_ids are provided and return results.
    try:
        from visualpython2.soas_vars.runtime_bridge import generate_soas_bridge_code
        from soas_workers.db import get_all_soas_vars, get_soas_vars_for_roles, get_writable_soas_vars_for_roles, get_shared_secrets_for_roles, get_sensitive_shared_secret_names

        role_ids = user_role_ids or []
        soas_vars = get_soas_vars_for_roles(role_ids) if role_ids else {}
        # Fallback: if role-based returned nothing, load all vars for test runs
        if not soas_vars:
            soas_vars = get_all_soas_vars()
        writable_vars = get_writable_soas_vars_for_roles(role_ids) if role_ids else []
        # For test runs, also allow writing all vars
        if not writable_vars:
            writable_vars = list(soas_vars.keys())
        # Merge shared secrets into SOAS vars (accessible via get_soas_var)
        sens_shared: set[str] = set()
        if role_ids:
            shared_secrets = get_shared_secrets_for_roles(role_ids)
            if shared_secrets:
                soas_vars.update(shared_secrets)
                sens_shared = get_sensitive_shared_secret_names(role_ids)
        soas_bridge = generate_soas_bridge_code(soas_vars, writable_vars, sensitive_names=sens_shared)
        compiled_code = soas_bridge + compiled_code
    except ImportError:
        pass  # SOAS vars bridge not available

    # 3a-ii. User secrets (per-user encrypted secrets with per-user DEK)
    try:
        from visualpython2.user_secrets.runtime_bridge import generate_user_secrets_bridge_code
        from soas_workers.db import get_user_secrets_for_user, get_sensitive_user_secret_names

        if triggering_user_id:
            user_secrets = get_user_secrets_for_user(triggering_user_id)
            if user_secrets:
                sens_user = get_sensitive_user_secret_names(triggering_user_id)
                compiled_code = generate_user_secrets_bridge_code(user_secrets, sensitive_names=sens_user) + compiled_code
    except ImportError:
        pass

    # 3a-iii. Team variables — resolved from the automation's team
    team_id = None
    try:
        from visualpython2.team_vars.runtime_bridge import generate_team_vars_bridge_code
        from soas_workers.db import get_automation_team_id, get_team_vars_for_roles, get_writable_team_vars_for_roles, get_all_team_vars, get_sensitive_team_variable_names

        team_id = get_automation_team_id(automation_id)
        if team_id:
            role_ids = user_role_ids or []
            team_vars = get_team_vars_for_roles(team_id, role_ids) if role_ids else {}
            if not team_vars:
                team_vars = get_all_team_vars(team_id)
            writable_team_vars = get_writable_team_vars_for_roles(team_id, role_ids) if role_ids else []
            if not writable_team_vars:
                writable_team_vars = list(team_vars.keys())
            sens_team = get_sensitive_team_variable_names(team_id)
            compiled_code = generate_team_vars_bridge_code(team_vars, writable_team_vars, sensitive_names=sens_team) + compiled_code
    except ImportError:
        pass

    # Stub for get_team_var when no bridge was generated
    if "get_team_var" not in compiled_code:
        stub = (
            "# --- Team Variable Stubs ---\n"
            "def get_team_var(name, default=None):\n"
            "    return default\n"
            "def set_team_var(name, value):\n"
            "    raise PermissionError(f'No team context for variable: {name}')\n"
            "# --- End Team Variable Stubs ---\n\n"
        )
        compiled_code = stub + compiled_code

    # Stub for get_user_secret when no bridge was generated
    if "get_user_secret" not in compiled_code:
        stub = (
            "# --- User Secrets Stub ---\n"
            "def get_user_secret(name, default=None):\n"
            "    return default\n"
            "# --- End User Secrets Stub ---\n\n"
        )
        compiled_code = stub + compiled_code

    # 3b. Resolve incident group for group bridge functions
    case_id = parameters.get("case_id")
    group_incident_ids: list[str] | None = None

    if case_id:
        group_incident_ids = get_case_incident_ids(case_id)
        if not incident_id and group_incident_ids:
            incident_id = group_incident_ids[0]
    elif incident_id:
        group_incident_ids = [incident_id]

    # 3c. Incident variables — real bridge or fallback stubs
    has_incident_bridge = False
    if incident_id:
        try:
            from visualpython2.incident_vars.runtime_bridge import (
                generate_incident_bridge_code,
            )

            bridge_code = generate_incident_bridge_code(
                incident_id,
                group_incident_ids=group_incident_ids,
                sensitive_var_names=get_sensitive_incident_variable_names(),
            )
            compiled_code = bridge_code + "\n" + compiled_code
            has_incident_bridge = True
        except ImportError:
            pass  # Bridge not available

    if not has_incident_bridge:
        stub_bridge = (
            "# --- Incident Variable Stubs (no incident context) ---\n"
            "def get_incident_var(name, default=None):\n"
            "    return default\n"
            "def set_incident_var(name, value):\n"
            "    pass\n"
            "def get_incident_data():\n"
            "    return {}\n"
            "def get_group_incidents():\n"
            "    return []\n"
            "def get_group_incident(index):\n"
            "    raise IndexError(f'Incident index {index} out of range (group size: 0)')\n"
            "def get_group_incident_count():\n"
            "    return 0\n"
            "# --- End Stubs ---\n\n"
        )
        compiled_code = stub_bridge + compiled_code

    # ------------------------------------------------------------------
    # 4. Write compiled code to a temp file and execute with live streaming
    # ------------------------------------------------------------------
    env = os.environ.copy()
    env["SOAS_PARAMS"] = json.dumps(parameters)
    env["SOAS_EXECUTION_ID"] = execution_id
    env["SOAS_AUTOMATION_ID"] = automation_id
    env["SOAS_INTERACTIVE"] = "1"
    env["REDIS_URL"] = config.REDIS_URL
    if incident_id:
        env["SOAS_INCIDENT_ID"] = incident_id
    if case_id:
        env["SOAS_CASE_ID"] = case_id
    if team_id:
        env["SOAS_TEAM_ID"] = team_id
    if resume_segment is not None:
        env["SOAS_RESUME_SEGMENT"] = str(resume_segment)
    # Sub-automation support: inject API credentials and runtime module path
    env["SOAS_API_URL"] = config.SOAS_API_URL
    env["SOAS_API_TOKEN"] = api_token or config.SOAS_API_TOKEN
    call_depth = int(env.get("SOAS_CALL_DEPTH", "0"))
    env["SOAS_CALL_DEPTH"] = str(call_depth + 1)
    # Make soas_runtime importable from the subprocess
    # Docker: VP2 is at /opt/vp2/visualpython2/; local dev: relative path from source
    docker_runtime = "/opt/vp2/visualpython2/runtime"
    local_runtime = os.path.normpath(
        os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "VisualPython2", "src", "visualpython2", "runtime")
    )
    runtime_dir = docker_runtime if os.path.isdir(docker_runtime) else local_runtime
    env["PYTHONPATH"] = runtime_dir + os.pathsep + env.get("PYTHONPATH", "")

    os.makedirs(config.SANDBOX_WORKDIR, exist_ok=True)

    start_time = time.monotonic()
    stdout_lines: list[str] = []
    stderr_lines: list[str] = []

    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".py",
            dir=config.SANDBOX_WORKDIR,
            delete=False,
        ) as tmp:
            tmp.write(compiled_code)
            tmp_path = tmp.name

        # Create a temp file for debug trace output
        debug_file_path = tmp_path.replace(".py", "_debug.json")
        env["SOAS_DEBUG_FILE"] = debug_file_path

        try:
            proc = subprocess.Popen(
                [sys.executable, "-u", tmp_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=env,
                cwd=config.SANDBOX_WORKDIR,
            )

            # Stream stdout and stderr in separate threads
            def read_stdout():
                assert proc.stdout is not None
                for line in iter(proc.stdout.readline, ""):
                    if not line:
                        break
                    stripped = line.rstrip("\n")
                    stdout_lines.append(stripped)
                    r.publish(
                        pubsub_channel,
                        json.dumps({"type": "output", "stream": "stdout", "text": stripped}),
                    )
                proc.stdout.close()

            def read_stderr():
                assert proc.stderr is not None
                for line in iter(proc.stderr.readline, ""):
                    if not line:
                        break
                    stripped = line.rstrip("\n")
                    stderr_lines.append(stripped)
                    r.publish(
                        pubsub_channel,
                        json.dumps({"type": "output", "stream": "stderr", "text": stripped}),
                    )
                proc.stderr.close()

            t_out = threading.Thread(target=read_stdout, daemon=True)
            t_err = threading.Thread(target=read_stderr, daemon=True)
            t_out.start()
            t_err.start()

            # Wait for process with timeout
            timed_out = False
            try:
                proc.wait(timeout=timeout_seconds)
            except subprocess.TimeoutExpired:
                timed_out = True
                proc.kill()
                proc.wait()

            t_out.join(timeout=5)
            t_err.join(timeout=5)

            duration_ms = int((time.monotonic() - start_time) * 1000)

            if timed_out:
                r.publish(
                    pubsub_channel,
                    json.dumps({"type": "complete", "status": "timed_out"}),
                )
                update_execution_complete(
                    execution_id,
                    status="timed_out",
                    error_message=f"Execution timed out after {timeout_seconds}s",
                    stdout="\n".join(stdout_lines)[:50000] or None,
                    stderr="\n".join(stderr_lines)[:50000] or None,
                    duration_ms=duration_ms,
                )
                return {"success": False, "error": "timeout"}

            # Exit code 42 = checkpoint: waiting for user input.
            # Save context and free the worker slot.
            if proc.returncode == 42:
                accumulated = json.dumps({
                    "stdout": "\n".join(stdout_lines),
                    "stderr": "\n".join(stderr_lines),
                })
                r.set(
                    f"execution:{execution_id}:accumulated_output",
                    accumulated,
                    ex=3600,
                )
                resume_ctx = json.dumps({
                    "automation_id": automation_id,
                    "graph_json": graph_json,
                    "parameters": parameters,
                    "incident_id": incident_id,
                    "timeout_seconds": timeout_seconds,
                    "user_role_ids": user_role_ids,
                    "api_token": api_token,
                    "triggering_user_id": triggering_user_id,
                })
                r.set(
                    f"execution:{execution_id}:resume_context",
                    resume_ctx,
                    ex=3600,
                )
                update_execution_status(execution_id, "waiting_for_input")
                return {
                    "success": True,
                    "waiting_for_input": True,
                    "exit_code": 42,
                    "duration_ms": duration_ms,
                }

            # Normal completion or failure
            final_status = "completed" if proc.returncode == 0 else "failed"

            # Read debug trace data (best-effort)
            result_data = None
            try:
                if os.path.exists(debug_file_path):
                    with open(debug_file_path, "r") as f:
                        content = f.read()
                    if content.strip():
                        node_trace = json.loads(content)
                        result_data = {
                            "debug": {
                                "graph_data": graph_json,
                                "node_trace": node_trace,
                            }
                        }
            except Exception:
                pass  # Debug data is best-effort
            finally:
                try:
                    os.unlink(debug_file_path)
                except OSError:
                    pass

            # Merge accumulated output from previous segments
            prev_stdout = ""
            prev_stderr = ""
            try:
                acc_key = f"execution:{execution_id}:accumulated_output"
                acc_raw = r.get(acc_key)
                if acc_raw:
                    acc = json.loads(acc_raw if isinstance(acc_raw, str) else acc_raw.decode())
                    prev_stdout = acc.get("stdout", "")
                    prev_stderr = acc.get("stderr", "")
                    r.delete(acc_key)
            except Exception:
                pass

            full_stdout = (prev_stdout + "\n" + "\n".join(stdout_lines)).strip()
            full_stderr = (prev_stderr + "\n" + "\n".join(stderr_lines)).strip()

            # Update DB first so the frontend can fetch the final record
            update_execution_complete(
                execution_id,
                status=final_status,
                stdout=full_stdout[:50000] or None,
                stderr=full_stderr[:50000] or None,
                exit_code=proc.returncode,
                duration_ms=duration_ms,
                result_data=result_data,
            )

            # Clean up resume context
            r.delete(f"execution:{execution_id}:resume_context")

            # Then publish completion notification
            r.publish(
                pubsub_channel,
                json.dumps({
                    "type": "complete",
                    "status": final_status,
                    "exit_code": proc.returncode,
                }),
            )

            return {
                "success": proc.returncode == 0,
                "exit_code": proc.returncode,
                "duration_ms": duration_ms,
            }

        finally:
            # Clean up temp file
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

    except Exception as e:
        duration_ms = int((time.monotonic() - start_time) * 1000)
        update_execution_complete(
            execution_id,
            status="failed",
            error_message=str(e),
            duration_ms=duration_ms,
        )
        return {"success": False, "error": str(e)}

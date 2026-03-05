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

    # 3a. SOAS application-level variables
    # For test runs, load all SOAS vars (user is already authenticated).
    # Fall back to role-based if role_ids are provided and return results.
    try:
        from visualpython2.soas_vars.runtime_bridge import generate_soas_bridge_code
        from soas_workers.db import get_all_soas_vars, get_soas_vars_for_roles, get_writable_soas_vars_for_roles

        role_ids = user_role_ids or []
        soas_vars = get_soas_vars_for_roles(role_ids) if role_ids else {}
        # Fallback: if role-based returned nothing, load all vars for test runs
        if not soas_vars:
            soas_vars = get_all_soas_vars()
        writable_vars = get_writable_soas_vars_for_roles(role_ids) if role_ids else []
        # For test runs, also allow writing all vars
        if not writable_vars:
            writable_vars = list(soas_vars.keys())
        soas_bridge = generate_soas_bridge_code(soas_vars, writable_vars)
        compiled_code = soas_bridge + compiled_code
    except ImportError:
        pass  # SOAS vars bridge not available

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

        # Collect sensitive values for stdout/stderr scrubbing
        _scrub_values: list[str] = []
        if incident_id:
            _sens_names = get_sensitive_incident_variable_names()
            if _sens_names:
                for _iid in (group_incident_ids or [incident_id]):
                    for _name in _sens_names:
                        _raw = r.hget(f"incident:{_iid}:data", _name)
                        if _raw:
                            try:
                                _decoded = json.loads(_raw if isinstance(_raw, str) else _raw.decode())
                                s = str(_decoded) if _decoded is not None else ""
                                if len(s) >= 3:
                                    _scrub_values.append(s)
                            except Exception:
                                pass
        _scrub_values.sort(key=len, reverse=True)

        def _scrub_line(line: str) -> str:
            for v in _scrub_values:
                line = line.replace(v, "***")
            return line

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
                    stripped = _scrub_line(line.rstrip("\n"))
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
                    stripped = _scrub_line(line.rstrip("\n"))
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

            # Wait for process with input-aware timeout: time spent waiting
            # for user input (pending_input Redis key exists) does not count.
            deadline = time.monotonic() + timeout_seconds
            timed_out = False
            pending_key = f"execution:{execution_id}:pending_input"

            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    timed_out = True
                    break
                try:
                    proc.wait(timeout=min(remaining, 2))
                    break  # Process completed
                except subprocess.TimeoutExpired:
                    # If waiting for user input, pause the timeout countdown
                    if r.exists(pending_key):
                        deadline += 2  # Add back the 2s we just waited

            if timed_out:
                proc.kill()
                proc.wait()
                t_out.join(timeout=2)
                t_err.join(timeout=2)
                duration_ms = int((time.monotonic() - start_time) * 1000)
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

            t_out.join(timeout=5)
            t_err.join(timeout=5)

            duration_ms = int((time.monotonic() - start_time) * 1000)
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

            # Update DB first so the frontend can fetch the final record
            update_execution_complete(
                execution_id,
                status=final_status,
                stdout="\n".join(stdout_lines)[:50000] or None,
                stderr="\n".join(stderr_lines)[:50000] or None,
                exit_code=proc.returncode,
                duration_ms=duration_ms,
                result_data=result_data,
            )

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

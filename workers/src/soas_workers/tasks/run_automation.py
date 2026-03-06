"""Execute compiled automation scripts in a sandboxed subprocess."""

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
from soas_workers.db import (
    get_automation_graph_data,
    get_automation_timeout,
    get_case_incident_ids,
    get_connection,
    get_execution_incident_id,
    get_script_path,
    get_sensitive_incident_variable_names,
    update_execution_complete,
    update_execution_status,
)


def _stream_pipe(pipe, stream_name: str, r, channel: str):
    """Read lines from a subprocess pipe and publish them to Redis."""
    try:
        for line in iter(pipe.readline, ""):
            if not line:
                break
            r.publish(
                channel,
                json.dumps({
                    "type": "output",
                    "stream": stream_name,
                    "text": line.rstrip("\n"),
                }),
            )
    except Exception:
        pass
    finally:
        pipe.close()


@app.task(name="soas.run_automation", bind=True, max_retries=0)
def run_automation(self, execution_id: str, automation_id: str, parameters: dict, user_role_ids: list[str] | None = None, api_token: str | None = None):
    """Execute a compiled automation script in a sandboxed subprocess."""
    # Update status to running
    update_execution_status(
        execution_id, "running", worker_id=self.request.hostname
    )

    script_path = get_script_path(automation_id)
    if not script_path:
        update_execution_complete(
            execution_id, "failed", error_message="Script not found"
        )
        return {"success": False, "error": "Script not found"}

    full_path = os.path.join(config.AUTOMATIONS_DIR, script_path)
    if not os.path.exists(full_path):
        update_execution_complete(
            execution_id, "failed", error_message=f"Script file missing: {script_path}"
        )
        return {"success": False, "error": "Script file missing"}

    # Build runtime bridge code to prepend to the compiled script.
    # Always inject at least stub functions so nodes like Get Incident Var
    # don't crash with NameError when run outside an incident context.
    incident_id = get_execution_incident_id(execution_id)
    tmp_bridge_path = None
    bridge_prefix = ""
    has_incident_bridge = False

    # Resolve incident group: case runs get all linked incidents, single
    # incident runs get a group of size 1.
    case_id = parameters.get("case_id")
    group_incident_ids: list[str] | None = None

    if case_id:
        group_incident_ids = get_case_incident_ids(case_id)
        if not incident_id and group_incident_ids:
            incident_id = group_incident_ids[0]
    elif incident_id:
        group_incident_ids = [incident_id]

    # Resolve triggering user for SOAS vars and user secrets
    triggering_user_id = None
    try:
        from soas_workers.db import get_user_role_ids

        role_ids = user_role_ids or []
        if not role_ids:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT triggered_by FROM execution_logs WHERE id = %s::uuid",
                        (execution_id,),
                    )
                    row = cur.fetchone()
                    if row and row["triggered_by"]:
                        triggering_user_id = str(row["triggered_by"])
                        role_ids = get_user_role_ids(triggering_user_id)
        else:
            # Still need user ID for user secrets even if role_ids were passed
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT triggered_by FROM execution_logs WHERE id = %s::uuid",
                        (execution_id,),
                    )
                    row = cur.fetchone()
                    if row and row["triggered_by"]:
                        triggering_user_id = str(row["triggered_by"])
    except ImportError:
        role_ids = []

    # SOAS application-level variables + shared secrets
    try:
        from visualpython2.soas_vars.runtime_bridge import generate_soas_bridge_code
        from soas_workers.db import get_soas_vars_for_roles, get_writable_soas_vars_for_roles, get_shared_secrets_for_roles, get_sensitive_shared_secret_names

        if role_ids:
            soas_vars = get_soas_vars_for_roles(role_ids)
            writable_vars = get_writable_soas_vars_for_roles(role_ids)
            # Merge shared secrets into SOAS vars (accessible via get_soas_var)
            shared_secrets = get_shared_secrets_for_roles(role_ids)
            sens_shared: set[str] = set()
            if shared_secrets:
                soas_vars.update(shared_secrets)
                sens_shared = get_sensitive_shared_secret_names(role_ids)
            bridge_prefix += generate_soas_bridge_code(soas_vars, writable_vars, sensitive_names=sens_shared)
    except ImportError:
        pass

    # User secrets (per-user encrypted secrets with per-user DEK)
    try:
        from visualpython2.user_secrets.runtime_bridge import generate_user_secrets_bridge_code
        from soas_workers.db import get_user_secrets_for_user, get_sensitive_user_secret_names

        if triggering_user_id:
            user_secrets = get_user_secrets_for_user(triggering_user_id)
            if user_secrets:
                sens_user = get_sensitive_user_secret_names(triggering_user_id)
                bridge_prefix += generate_user_secrets_bridge_code(user_secrets, sensitive_names=sens_user)
    except ImportError:
        pass

    # Stub for get_user_secret when no bridge was generated
    if "get_user_secret" not in bridge_prefix:
        bridge_prefix += (
            "# --- User Secrets Stub ---\n"
            "def get_user_secret(name, default=None):\n"
            "    return default\n"
            "# --- End User Secrets Stub ---\n\n"
        )

    # Incident variables — real bridge when incident context exists
    if incident_id:
        try:
            from visualpython2.incident_vars.runtime_bridge import (
                generate_incident_bridge_code,
            )
            bridge_prefix += generate_incident_bridge_code(
                incident_id,
                group_incident_ids=group_incident_ids,
                sensitive_var_names=get_sensitive_incident_variable_names(),
            )
            has_incident_bridge = True
        except ImportError:
            pass

    # Fallback stubs when no real incident bridge was injected
    if not has_incident_bridge:
        bridge_prefix += (
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

    # Write combined script to temp file
    if bridge_prefix:
        with open(full_path, "r") as f:
            original_code = f.read()
        combined_code = bridge_prefix + "\n" + original_code
        os.makedirs(config.SANDBOX_WORKDIR, exist_ok=True)
        tmp = tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", dir=config.SANDBOX_WORKDIR, delete=False,
        )
        tmp.write(combined_code)
        tmp.close()
        tmp_bridge_path = tmp.name
        full_path = tmp_bridge_path

    timeout = get_automation_timeout(automation_id)

    # Set up environment for the subprocess
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

    # Debug trace file for per-node I/O capture
    os.makedirs(config.SANDBOX_WORKDIR, exist_ok=True)
    debug_tmp = tempfile.NamedTemporaryFile(
        mode="w", suffix="_debug.json", dir=config.SANDBOX_WORKDIR, delete=False,
    )
    debug_file_path = debug_tmp.name
    debug_tmp.close()
    env["SOAS_DEBUG_FILE"] = debug_file_path

    # Set up Redis pubsub for real-time output
    r = redis.from_url(config.REDIS_URL)
    pubsub_channel = f"execution:{execution_id}:output"

    start_time = time.monotonic()
    stdout_lines: list[str] = []
    stderr_lines: list[str] = []

    try:
        proc = subprocess.Popen(
            [sys.executable, "-u", full_path],
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

        # Wait for process with input-aware timeout: time spent waiting
        # for user input (pending_input Redis key exists) does not count.
        deadline = time.monotonic() + timeout
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
                error_message=f"Execution timed out after {timeout}s",
                stdout="\n".join(stdout_lines)[:50000] or None,
                stderr="\n".join(stderr_lines)[:50000] or None,
                duration_ms=duration_ms,
            )
            return {"success": False, "error": "timeout"}

        t_out.join(timeout=5)
        t_err.join(timeout=5)

        duration_ms = int((time.monotonic() - start_time) * 1000)
        final_status = "completed" if proc.returncode == 0 else "failed"

        # Read debug trace file for per-node I/O data
        result_data = None
        try:
            if os.path.exists(debug_file_path):
                with open(debug_file_path, "r") as f:
                    content = f.read()
                if content.strip():
                    node_trace = json.loads(content)
                    graph_data = get_automation_graph_data(automation_id)
                    if graph_data:
                        result_data = {
                            "debug": {
                                "graph_data": graph_data,
                                "node_trace": node_trace,
                            }
                        }
        except Exception:
            pass

        # Publish completion
        r.publish(
            pubsub_channel,
            json.dumps({"type": "complete", "status": final_status, "exit_code": proc.returncode}),
        )

        update_execution_complete(
            execution_id,
            status=final_status,
            stdout="\n".join(stdout_lines)[:50000] or None,
            stderr="\n".join(stderr_lines)[:50000] or None,
            exit_code=proc.returncode,
            duration_ms=duration_ms,
            result_data=result_data,
        )

        return {
            "success": proc.returncode == 0,
            "exit_code": proc.returncode,
            "duration_ms": duration_ms,
        }

    except Exception as e:
        duration_ms = int((time.monotonic() - start_time) * 1000)
        update_execution_complete(
            execution_id,
            status="failed",
            error_message=str(e),
            duration_ms=duration_ms,
        )
        return {"success": False, "error": str(e)}

    finally:
        # Clean up temp files
        if tmp_bridge_path:
            try:
                os.unlink(tmp_bridge_path)
            except OSError:
                pass
        try:
            os.unlink(debug_file_path)
        except OSError:
            pass

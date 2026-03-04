"""Runtime helper for compiled automation scripts.

Provides run_automation() for calling sub-automations via the SOAS API.
Uses only stdlib modules so it works in sandboxed subprocesses.
"""

import json
import os
import time
import urllib.error
import urllib.request


_API_URL = os.environ.get("SOAS_API_URL", "http://localhost:8000/api/v1")
_API_TOKEN = os.environ.get("SOAS_API_TOKEN", "")

# Track call depth to prevent circular automation calls
_CALL_DEPTH = int(os.environ.get("SOAS_CALL_DEPTH", "0"))
_MAX_CALL_DEPTH = 10


def _api_request(method: str, path: str, body: dict | None = None) -> dict:
    """Make an authenticated request to the SOAS API."""
    url = f"{_API_URL.rstrip('/')}{path}"
    data = json.dumps(body).encode("utf-8") if body else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    if _API_TOKEN:
        req.add_header("Authorization", f"Bearer {_API_TOKEN}")

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(
            f"SOAS API error {e.code} on {method} {path}: {error_body}"
        ) from e


def run_automation(
    automation_id: str,
    parameters: dict | None = None,
    synchronous: bool = True,
    poll_interval: float = 2.0,
    timeout: float = 600.0,
) -> dict:
    """Execute another automation as a sub-automation.

    Args:
        automation_id: UUID of the target automation.
        parameters: Parameters dict to pass to the child automation.
        synchronous: If True, wait for completion and return output.
                     If False, return immediately with execution_id.
        poll_interval: Seconds between status polls (sync mode).
        timeout: Max seconds to wait for completion (sync mode).

    Returns:
        dict with keys: execution_id, success, output, error
    """
    if _CALL_DEPTH >= _MAX_CALL_DEPTH:
        return {
            "execution_id": None,
            "success": False,
            "output": None,
            "error": f"Maximum sub-automation call depth ({_MAX_CALL_DEPTH}) exceeded. "
                     "Check for circular automation references.",
        }

    # Propagate incremented call depth to child via parameters
    execute_body = {"parameters": parameters or {}}

    # Pass incident context if available
    incident_id = os.environ.get("SOAS_INCIDENT_ID")
    if incident_id:
        execute_body["incident_id"] = incident_id

    try:
        result = _api_request(
            "POST", f"/automations/{automation_id}/execute", execute_body
        )
    except RuntimeError as e:
        return {
            "execution_id": None,
            "success": False,
            "output": None,
            "error": str(e),
        }

    execution_id = result.get("execution_id")

    if not synchronous:
        return {
            "execution_id": execution_id,
            "success": None,
            "output": None,
            "error": None,
        }

    # Synchronous mode: poll until terminal status
    start = time.monotonic()
    while time.monotonic() - start < timeout:
        time.sleep(poll_interval)
        try:
            status_resp = _api_request("GET", f"/executions/{execution_id}")
        except RuntimeError as e:
            return {
                "execution_id": execution_id,
                "success": False,
                "output": None,
                "error": f"Failed to poll execution status: {e}",
            }

        status = status_resp.get("status", "")
        if status in ("completed", "failed", "timed_out"):
            child_stdout = status_resp.get("stdout", "") or ""
            child_stderr = status_resp.get("stderr", "") or ""
            child_error = status_resp.get("error_message", "") if status != "completed" else None

            # Stream child output to parent stdout so it appears in the
            # combined test-run output.
            import sys
            if child_stdout:
                for line in child_stdout.rstrip("\n").split("\n"):
                    print(f"[sub:{execution_id[:8]}] {line}", flush=True)
            if child_stderr:
                for line in child_stderr.rstrip("\n").split("\n"):
                    print(f"[sub:{execution_id[:8]}] {line}", file=sys.stderr, flush=True)
            if status != "completed":
                print(f"[sub:{execution_id[:8]}] FAILED: {child_error or status}", file=sys.stderr, flush=True)

            return {
                "execution_id": execution_id,
                "success": status == "completed",
                "output": child_stdout,
                "error": child_error,
            }

    return {
        "execution_id": execution_id,
        "success": False,
        "output": None,
        "error": f"Timed out waiting for child automation after {timeout}s",
    }

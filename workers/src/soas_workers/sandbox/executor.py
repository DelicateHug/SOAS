"""Subprocess-based script execution with isolation."""

import json
import os
import subprocess
import sys
from dataclasses import dataclass


@dataclass
class ExecutionResult:
    success: bool
    stdout: str
    stderr: str
    exit_code: int
    duration_ms: int


def execute_script(
    script_path: str,
    parameters: dict | None = None,
    timeout: int = 300,
    working_dir: str = "/tmp/sandbox",
) -> ExecutionResult:
    """Execute a Python script in a subprocess with isolation."""
    import time

    os.makedirs(working_dir, exist_ok=True)

    env = os.environ.copy()
    if parameters:
        env["SOAS_PARAMS"] = json.dumps(parameters)

    start = time.monotonic()

    try:
        result = subprocess.run(
            [sys.executable, script_path],
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
            cwd=working_dir,
        )

        duration_ms = int((time.monotonic() - start) * 1000)

        return ExecutionResult(
            success=result.returncode == 0,
            stdout=result.stdout[:50000],
            stderr=result.stderr[:50000],
            exit_code=result.returncode,
            duration_ms=duration_ms,
        )

    except subprocess.TimeoutExpired:
        duration_ms = int((time.monotonic() - start) * 1000)
        return ExecutionResult(
            success=False,
            stdout="",
            stderr=f"Execution timed out after {timeout}s",
            exit_code=-1,
            duration_ms=duration_ms,
        )

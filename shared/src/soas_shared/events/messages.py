"""Celery task message schemas - defines the contract between backend and workers."""

from typing import Any
from uuid import UUID

from pydantic import BaseModel


class CompileGraphMessage(BaseModel):
    automation_id: str
    graph_json: dict[str, Any]


class RunAutomationMessage(BaseModel):
    execution_id: str
    automation_id: str
    script_path: str
    parameters: dict[str, Any] = {}
    timeout_seconds: int = 300


class ExecutionUpdate(BaseModel):
    execution_id: str
    status: str
    worker_id: str | None = None
    stdout: str | None = None
    stderr: str | None = None
    exit_code: int | None = None
    error_message: str | None = None
    result_data: dict[str, Any] | None = None
    duration_ms: int | None = None

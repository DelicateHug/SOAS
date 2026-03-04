"""Execution log schemas."""

from datetime import datetime
from typing import Any
from uuid import UUID

from soas_shared.constants import ExecutionStatus
from soas_shared.schemas.common import BaseSchema
from soas_shared.schemas.user import UserBrief


class ExecutionLogRead(BaseSchema):
    id: UUID
    automation_id: UUID
    automation_name: str | None = None
    triggered_by: UserBrief
    incident_id: UUID | None = None
    case_id: UUID | None = None
    status: ExecutionStatus
    worker_id: str | None = None
    parameters: dict[str, Any] = {}
    stdout: str | None = None
    stderr: str | None = None
    result_data: dict[str, Any] | None = None
    exit_code: int | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    duration_ms: int | None = None
    error_message: str | None = None
    created_at: datetime


class ExecutionListItem(BaseSchema):
    id: UUID
    automation_id: UUID
    automation_name: str | None = None
    triggered_by: UserBrief
    status: ExecutionStatus
    celery_task_id: str | None = None
    worker_id: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    duration_ms: int | None = None
    created_at: datetime

"""Version control schemas."""

from datetime import datetime
from typing import Any
from uuid import UUID

from soas_shared.schemas.common import BaseSchema
from soas_shared.schemas.user import UserBrief


class VersionRead(BaseSchema):
    id: UUID
    version_number: int
    name: str | None = None
    description: str | None = None
    created_by: UserBrief
    created_at: datetime


class VersionCreate(BaseSchema):
    name: str | None = None
    description: str | None = None


class VersionUpdate(BaseSchema):
    name: str | None = None
    description: str | None = None


class AutomationVersionRead(VersionRead):
    """Automation version with full snapshot data."""
    automation_id: UUID
    graph_data: dict[str, Any] | None = None
    parameters: list[Any] | None = None
    timeout_seconds: int | None = None
    tags: list[str] | None = None
    trigger_tags: list[str] | None = None
    is_trigger_enabled: bool | None = None
    documentation: str | None = None


class CodeBlockVersionRead(VersionRead):
    """Code library block version with snapshot data."""
    block_id: UUID
    code: str
    language: str | None = None
    input_ports: list[Any] | None = None
    output_ports: list[Any] | None = None
    tags: list[str] | None = None


class ScheduledJobVersionRead(VersionRead):
    """Scheduled job version with snapshot data."""
    job_id: UUID
    schedule_type: str | None = None
    cron_expression: str | None = None
    interval_seconds: int | None = None
    calendar_config: dict[str, Any] | None = None
    timezone: str | None = None
    parameters: dict[str, Any] | None = None

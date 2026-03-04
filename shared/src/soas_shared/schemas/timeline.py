"""Timeline entry schemas."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import Field

from soas_shared.constants import TimelineEntryType
from soas_shared.schemas.common import BaseSchema
from soas_shared.schemas.user import UserBrief


class TimelineCreate(BaseSchema):
    entry_type: TimelineEntryType = TimelineEntryType.COMMENT
    content: str = Field(min_length=1)
    details: dict[str, Any] = {}


class TimelineEntryRead(BaseSchema):
    id: UUID
    incident_id: UUID | None = None
    case_id: UUID | None = None
    entry_type: TimelineEntryType
    content: str
    details: dict[str, Any] = {}
    is_evidence: bool = False
    created_by: UserBrief | None = None
    created_at: datetime

"""Incident note schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import Field

from soas_shared.schemas.common import BaseSchema
from soas_shared.schemas.user import UserBrief


class IncidentNoteCreate(BaseSchema):
    content: str = Field(min_length=1)


class IncidentNoteUpdate(BaseSchema):
    content: str | None = Field(default=None, min_length=1)


class IncidentNoteRead(BaseSchema):
    id: UUID
    incident_id: UUID
    content: str
    is_evidence: bool = False
    created_by: UserBrief
    updated_by: UserBrief | None = None
    created_at: datetime
    updated_at: datetime

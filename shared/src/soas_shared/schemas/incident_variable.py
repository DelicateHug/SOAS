"""Schemas for incident variable definitions (keys only, no values)."""

from datetime import datetime
from uuid import UUID

from soas_shared.schemas.common import BaseSchema


class IncidentVariableCreate(BaseSchema):
    name: str
    description: str | None = None
    default_enabled: bool = True


class IncidentVariableUpdate(BaseSchema):
    description: str | None = None
    default_enabled: bool | None = None


class IncidentVariableRead(BaseSchema):
    id: UUID
    name: str
    description: str | None = None
    default_enabled: bool = True
    created_by: UUID
    created_at: datetime
    updated_at: datetime

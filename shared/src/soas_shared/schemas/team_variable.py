"""Schemas for team-scoped variables."""

from datetime import datetime
from typing import Any
from uuid import UUID

from soas_shared.schemas.common import BaseSchema


class TeamVariableCreate(BaseSchema):
    name: str
    description: str | None = None
    value: Any = None
    is_secret: bool = False


class TeamVariableUpdate(BaseSchema):
    description: str | None = None
    value: Any = None
    is_secret: bool | None = None


class TeamVariableRead(BaseSchema):
    id: UUID
    team_id: UUID
    name: str
    description: str | None = None
    value: Any = None
    is_secret: bool = False
    created_by: UUID | None = None
    updated_by: UUID | None = None
    created_at: datetime
    updated_at: datetime


class TeamVariablePermissionEntry(BaseSchema):
    role_id: UUID
    role_name: str | None = None
    can_read: bool = True
    can_write: bool = False


class TeamVariablePermissionUpdate(BaseSchema):
    permissions: list[TeamVariablePermissionEntry]

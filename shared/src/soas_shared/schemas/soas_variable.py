"""Schemas for SOAS application-level variables."""

from datetime import datetime
from typing import Any
from uuid import UUID

from soas_shared.schemas.common import BaseSchema


class SOASVariableCreate(BaseSchema):
    name: str
    description: str | None = None
    value: Any = None
    is_secret: bool = False


class SOASVariableUpdate(BaseSchema):
    description: str | None = None
    value: Any = None
    is_secret: bool | None = None


class SOASVariableRead(BaseSchema):
    id: UUID
    name: str
    description: str | None = None
    value: Any = None
    is_secret: bool = False
    created_by: UUID
    updated_by: UUID | None = None
    created_at: datetime
    updated_at: datetime


class SOASVariablePermissionEntry(BaseSchema):
    role_id: UUID
    role_name: str | None = None
    can_read: bool = True
    can_write: bool = False


class SOASVariablePermissionUpdate(BaseSchema):
    permissions: list[SOASVariablePermissionEntry]

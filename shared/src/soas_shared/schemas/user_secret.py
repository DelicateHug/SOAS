"""Schemas for per-user secrets."""

from datetime import datetime
from uuid import UUID

from soas_shared.schemas.common import BaseSchema


class UserSecretCreate(BaseSchema):
    name: str
    description: str | None = None
    value: str
    sensitive: bool = False


class UserSecretUpdate(BaseSchema):
    description: str | None = None
    value: str | None = None


class UserSecretRead(BaseSchema):
    id: UUID
    name: str
    description: str | None = None
    sensitive: bool = False
    is_shared: bool = False
    created_at: datetime
    updated_at: datetime


class UserSecretReadWithValue(UserSecretRead):
    value: str


class UserSecretAdminRead(BaseSchema):
    id: UUID
    user_id: UUID
    username: str | None = None
    name: str
    description: str | None = None
    sensitive: bool = False
    is_shared: bool = False
    created_at: datetime
    updated_at: datetime


class UserSecretShareRequest(BaseSchema):
    role_ids: list[UUID]


class SharedSecretPermissionRead(BaseSchema):
    role_id: UUID
    role_name: str | None = None
    can_read: bool = True


class SharedSecretRead(BaseSchema):
    """A user secret shared with roles, visible in SOAS variables context."""
    id: UUID
    name: str
    description: str | None = None
    sensitive: bool = False
    owner_username: str
    value: str | None = None  # None if sensitive
    source: str = "shared_secret"

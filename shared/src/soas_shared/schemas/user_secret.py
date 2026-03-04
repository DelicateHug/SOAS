"""Schemas for per-user secrets."""

from datetime import datetime
from uuid import UUID

from soas_shared.schemas.common import BaseSchema


class UserSecretCreate(BaseSchema):
    name: str
    description: str | None = None
    value: str


class UserSecretUpdate(BaseSchema):
    description: str | None = None
    value: str | None = None


class UserSecretRead(BaseSchema):
    id: UUID
    name: str
    description: str | None = None
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
    created_at: datetime
    updated_at: datetime

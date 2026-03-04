"""User schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import EmailStr, Field

from soas_shared.schemas.common import BaseReadSchema, BaseSchema


class UserCreate(BaseSchema):
    username: str = Field(min_length=3, max_length=100)
    email: EmailStr
    display_name: str = Field(min_length=1, max_length=200)
    password: str = Field(min_length=8, max_length=128)


class AdminUserCreate(BaseSchema):
    """Schema for admin-created users (password is auto-generated)."""
    username: str = Field(min_length=3, max_length=100)
    email: EmailStr
    display_name: str = Field(min_length=1, max_length=200)


class UserRead(BaseReadSchema):
    username: str
    email: str
    display_name: str
    is_active: bool
    is_mfa_enabled: bool
    must_reset_password: bool = False
    last_login_at: datetime | None = None
    roles: list[str] = []


class AdminUserCreateResponse(BaseReadSchema):
    """Response for admin-created users, includes the temporary password."""
    username: str
    email: str
    display_name: str
    is_active: bool
    is_mfa_enabled: bool
    must_reset_password: bool = True
    temporary_password: str
    roles: list[str] = []


class UserUpdate(BaseSchema):
    display_name: str | None = None
    email: EmailStr | None = None
    is_active: bool | None = None


class UserBrief(BaseSchema):
    id: UUID
    username: str
    display_name: str

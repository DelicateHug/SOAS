"""User schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import EmailStr, Field, field_validator

from soas_shared.schemas.common import BaseReadSchema, BaseSchema


class UserCreate(BaseSchema):
    username: str = Field(min_length=3, max_length=100)
    email: EmailStr
    display_name: str = Field(min_length=1, max_length=200)
    password: str = Field(min_length=8, max_length=128)

    @field_validator("username", "display_name")
    @classmethod
    def strip_text_fields(cls, v: str) -> str:
        return v.strip()

    @field_validator("email")
    @classmethod
    def strip_email(cls, v: str) -> str:
        return v.strip().lower()


class AdminUserCreate(BaseSchema):
    """Schema for admin-created users (password is auto-generated)."""
    username: str = Field(min_length=3, max_length=100)
    email: EmailStr
    display_name: str = Field(min_length=1, max_length=200)

    @field_validator("username", "display_name")
    @classmethod
    def strip_text_fields(cls, v: str) -> str:
        return v.strip()

    @field_validator("email")
    @classmethod
    def strip_email(cls, v: str) -> str:
        return v.strip().lower()


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


class AdminPasswordResetResponse(BaseSchema):
    """Response for admin password reset."""
    temporary_password: str


class UserUpdate(BaseSchema):
    display_name: str | None = None
    email: EmailStr | None = None
    is_active: bool | None = None


class UserBrief(BaseSchema):
    id: UUID
    username: str
    display_name: str

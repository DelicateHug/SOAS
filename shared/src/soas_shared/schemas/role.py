"""Role and permission schemas."""

from uuid import UUID

from pydantic import Field

from soas_shared.schemas.common import BaseReadSchema, BaseSchema


class PermissionRead(BaseSchema):
    id: UUID
    resource: str
    action: str
    description: str | None = None


class RoleCreate(BaseSchema):
    name: str = Field(min_length=1, max_length=100)
    display_name: str = Field(min_length=1, max_length=200)
    description: str | None = None
    permission_ids: list[UUID] = []


class RoleRead(BaseReadSchema):
    name: str
    display_name: str
    description: str | None = None
    is_system: bool
    permissions: list[PermissionRead] = []


class RoleUpdate(BaseSchema):
    display_name: str | None = None
    description: str | None = None
    permission_ids: list[UUID] | None = None


class UserRoleAssign(BaseSchema):
    role_id: UUID


class UserRoleRead(BaseSchema):
    user_id: UUID
    role_id: UUID
    role_name: str
    role_display_name: str

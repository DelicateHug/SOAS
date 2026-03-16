"""Team and team membership schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import Field

from soas_shared.schemas.common import BaseReadSchema, BaseSchema


class TeamCreate(BaseSchema):
    name: str = Field(min_length=1, max_length=100, pattern=r"^[a-z0-9][a-z0-9\-]*$")
    display_name: str = Field(min_length=1, max_length=200)
    description: str | None = None


class TeamUpdate(BaseSchema):
    display_name: str | None = None
    description: str | None = None


class TeamRead(BaseReadSchema):
    name: str
    display_name: str
    description: str | None = None
    is_default: bool
    member_count: int = 0


class TeamBrief(BaseSchema):
    id: UUID
    name: str
    display_name: str


class TeamMemberAdd(BaseSchema):
    user_id: UUID
    role_ids: list[UUID] = Field(min_length=1)
    team_role: str = Field(default="member", pattern=r"^(owner|member)$")


class TeamMemberUpdate(BaseSchema):
    role_ids: list[UUID] | None = None
    team_role: str | None = Field(default=None, pattern=r"^(owner|member)$")


class RoleBrief(BaseSchema):
    id: UUID
    name: str
    display_name: str


class TeamMemberRead(BaseSchema):
    user_id: UUID
    username: str
    display_name: str
    roles: list[RoleBrief] = []
    team_role: str
    joined_at: datetime


class TeamJWTClaim(BaseSchema):
    """Team membership info embedded in JWT token."""
    id: UUID
    name: str
    roles: list[str] = []
    team_role: str

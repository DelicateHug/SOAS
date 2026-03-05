"""Change request schemas for dev/prod draft workflow."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class ChangeRequestCreate(BaseModel):
    entity_type: str = Field(..., max_length=50)
    entity_id: UUID | None = None
    action: str = Field(..., pattern="^(create|update|delete)$")
    title: str = Field(..., max_length=255)
    snapshot: dict
    diff_summary: dict | None = None


class ChangeRequestReview(BaseModel):
    comment: str | None = None


class UserBrief(BaseModel):
    id: UUID
    display_name: str

    class Config:
        from_attributes = True


class ChangeRequestItem(BaseModel):
    id: UUID
    entity_type: str
    entity_id: UUID | None
    action: str
    title: str
    status: str
    diff_summary: dict | None
    review_comment: str | None
    git_branch: str | None = None
    git_sha: str | None = None
    target_tier: str = "dev"
    created_by: UUID
    creator: UserBrief | None = None
    reviewed_by: UUID | None
    reviewer: UserBrief | None = None
    created_at: datetime
    updated_at: datetime
    reviewed_at: datetime | None

    class Config:
        from_attributes = True


class ChangeRequestDetail(ChangeRequestItem):
    snapshot: dict


class ChangeRequestListResponse(BaseModel):
    data: list[ChangeRequestItem]
    total: int
    page: int
    per_page: int


# ---------------------------------------------------------------------------
# Branch versioning schemas
# ---------------------------------------------------------------------------


class EntityVersionResponse(BaseModel):
    entity_type: str
    entity_id: str | None
    tier: str  # "user", "dev", "prod"
    snapshot: dict | None


class PushToDevRequest(BaseModel):
    force: bool = False


class PushToDevResult(BaseModel):
    status: str  # "merged", "up-to-date", "conflict"
    conflicts: list[str] = []
    sha: str | None = None


class PromotionResult(BaseModel):
    status: str
    conflicts: list[str] = []
    sha: str | None = None


class BranchInfo(BaseModel):
    name: str
    sha: str | None
    is_user: bool
    is_dev: bool
    is_prod: bool


class DevChangesItem(BaseModel):
    file_path: str
    entity_type: str | None = None

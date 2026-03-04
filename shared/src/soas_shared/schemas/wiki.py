"""Wiki page schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import Field

from soas_shared.schemas.common import BaseReadSchema, BaseSchema
from soas_shared.schemas.user import UserBrief


# --- Create / Update ---


class WikiPageCreate(BaseSchema):
    title: str = Field(min_length=1, max_length=500)
    slug: str | None = None  # Auto-generated from title if not provided
    content: str | None = None
    parent_id: UUID | None = None
    tags: list[str] = []
    status: str = "published"
    icon: str | None = None


class WikiPageUpdate(BaseSchema):
    title: str | None = Field(default=None, min_length=1, max_length=500)
    slug: str | None = None
    content: str | None = None
    parent_id: UUID | None = None
    sort_order: int | None = None
    tags: list[str] | None = None
    status: str | None = None
    icon: str | None = None
    change_summary: str | None = Field(default=None, max_length=500)


# --- Read ---


class WikiPageRead(BaseReadSchema):
    title: str
    slug: str
    content: str | None = None
    parent_id: UUID | None = None
    sort_order: int
    tags: list[str] = []
    status: str
    version: int
    icon: str | None = None
    created_by: UserBrief
    updated_by: UserBrief | None = None
    child_count: int = 0


class WikiPageListItem(BaseReadSchema):
    title: str
    slug: str
    parent_id: UUID | None = None
    sort_order: int
    tags: list[str] = []
    status: str
    version: int
    icon: str | None = None
    created_by: UserBrief
    updated_by: UserBrief | None = None
    child_count: int = 0


# --- Tree ---


class WikiPageTreeNode(BaseSchema):
    """Recursive tree structure for sidebar navigation."""

    id: UUID
    title: str
    slug: str
    icon: str | None = None
    sort_order: int
    status: str
    children: list["WikiPageTreeNode"] = []


# --- Breadcrumb ---


class WikiPageBreadcrumb(BaseSchema):
    id: UUID
    title: str
    slug: str


# --- Version History ---


class WikiPageVersionRead(BaseSchema):
    id: UUID
    page_id: UUID
    version_number: int
    title: str | None = None
    content: str | None = None
    tags: list[str] | None = None
    change_summary: str | None = None
    created_by: UserBrief
    created_at: datetime


# --- Permissions ---


class WikiPagePermissionRead(BaseSchema):
    page_id: UUID
    role_id: UUID
    role_name: str
    can_read: bool
    can_edit: bool


class WikiPagePermissionSet(BaseSchema):
    role_id: UUID
    can_read: bool = True
    can_edit: bool = False


# --- Search ---


class WikiSearchResult(BaseSchema):
    id: UUID
    title: str
    slug: str
    snippet: str
    tags: list[str] = []
    updated_at: datetime

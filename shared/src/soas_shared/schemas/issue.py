"""Issue schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import Field

from soas_shared.constants import IssueLinkTargetType, IssueStatus
from soas_shared.schemas.common import BaseReadSchema, BaseSchema
from soas_shared.schemas.user import UserBrief


# --- Graph Annotation ---


class GraphAnnotation(BaseSchema):
    x: float
    y: float
    width: float = 200
    height: float = 100
    automation_version: int
    node_id: str | None = None


# --- Issue Links ---


class IssueLinkCreate(BaseSchema):
    target_type: IssueLinkTargetType
    target_id: UUID


class IssueLinkRead(BaseSchema):
    id: UUID
    target_type: IssueLinkTargetType
    target_id: UUID
    target_name: str | None = None


# --- Issue Notes ---


class IssueNoteCreate(BaseSchema):
    content: str = Field(min_length=1)


class IssueNoteUpdate(BaseSchema):
    content: str | None = Field(default=None, min_length=1)


class IssueNoteRead(BaseSchema):
    id: UUID
    issue_id: UUID
    content: str
    is_evidence: bool = False
    created_by: UserBrief
    updated_by: UserBrief | None = None
    created_at: datetime
    updated_at: datetime


# --- Checklist Items ---


class IssueChecklistItemCreate(BaseSchema):
    content: str = Field(min_length=1, max_length=500)
    sort_order: int = 0


class IssueChecklistItemUpdate(BaseSchema):
    content: str | None = Field(default=None, min_length=1, max_length=500)
    is_checked: bool | None = None
    sort_order: int | None = None


class IssueChecklistItemRead(BaseSchema):
    id: UUID
    content: str
    is_checked: bool
    sort_order: int
    created_by: UserBrief
    created_at: datetime


# --- Core Issue ---


class IssueCreate(BaseSchema):
    title: str = Field(min_length=1, max_length=500)
    description: str | None = None
    assigned_to: UUID | None = None
    graph_annotation: GraphAnnotation | None = None
    links: list[IssueLinkCreate] = []


class IssueUpdate(BaseSchema):
    title: str | None = Field(default=None, min_length=1, max_length=500)
    description: str | None = None
    status: IssueStatus | None = None
    assigned_to: UUID | None = None
    graph_annotation: GraphAnnotation | None = None


class IssueRead(BaseReadSchema):
    title: str
    description: str | None = None
    status: IssueStatus
    assigned_to: UserBrief | None = None
    created_by: UserBrief
    closed_at: datetime | None = None
    graph_annotation: GraphAnnotation | None = None
    links: list[IssueLinkRead] = []
    note_count: int = 0
    checklist_total: int = 0
    checklist_checked: int = 0


class IssueListItem(BaseReadSchema):
    title: str
    status: IssueStatus
    assigned_to: UserBrief | None = None
    created_by: UserBrief
    link_count: int = 0
    note_count: int = 0
    checklist_total: int = 0
    checklist_checked: int = 0


class GraphIssueItem(BaseReadSchema):
    """Lightweight issue payload for graph-editor overlays."""

    title: str
    description: str | None = None
    status: IssueStatus
    assigned_to: UserBrief | None = None
    graph_annotation: GraphAnnotation

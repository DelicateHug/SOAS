"""Incident schemas."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import Field

from soas_shared.constants import IncidentRole, IncidentSeverity, IncidentStatus
from soas_shared.schemas.common import BaseReadSchema, BaseSchema
from soas_shared.schemas.user import UserBrief


class IncidentCreate(BaseSchema):
    title: str = Field(min_length=1, max_length=500)
    summary: str | None = None
    severity: IncidentSeverity = IncidentSeverity.MEDIUM
    source: str | None = None
    source_ref: str | None = None
    tags: list[str] = []
    metadata: dict[str, Any] = {}
    raw_event: dict[str, Any] | None = None


class IncidentRead(BaseReadSchema):
    title: str
    summary: str | None = None
    severity: IncidentSeverity
    status: IncidentStatus
    source: str | None = None
    source_ref: str | None = None
    lead: UserBrief | None = None
    created_by: UserBrief
    detected_at: datetime | None = None
    resolved_at: datetime | None = None
    closed_at: datetime | None = None
    tags: list[str] = []
    metadata: dict[str, Any] = {}
    raw_event: dict[str, Any] | None = None
    assignment_count: int = 0
    case_id: UUID | None = None
    group_ids: list[UUID] = []


class IncidentUpdate(BaseSchema):
    title: str | None = None
    summary: str | None = None
    severity: IncidentSeverity | None = None
    source: str | None = None
    source_ref: str | None = None
    tags: list[str] | None = None
    metadata: dict[str, Any] | None = None
    raw_event: dict[str, Any] | None = None


class IncidentTransition(BaseSchema):
    new_status: IncidentStatus
    comment: str | None = None


class IncidentAssign(BaseSchema):
    user_id: UUID
    role_in_incident: IncidentRole = IncidentRole.RESPONDER


class IncidentAssignmentRead(BaseSchema):
    id: UUID
    user: UserBrief
    role_in_incident: IncidentRole
    assigned_at: datetime


class IncidentListItem(BaseReadSchema):
    title: str
    severity: IncidentSeverity
    status: IncidentStatus
    lead: UserBrief | None = None
    created_by: UserBrief
    detected_at: datetime | None = None
    tags: list[str] = []
    assignment_count: int = 0
    group_ids: list[UUID] = []

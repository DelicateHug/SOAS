"""Case schemas."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import Field

from soas_shared.constants import CaseStatus
from soas_shared.schemas.common import BaseReadSchema, BaseSchema
from soas_shared.schemas.incident import IncidentListItem
from soas_shared.schemas.user import UserBrief


class CaseCreate(BaseSchema):
    title: str = Field(min_length=1, max_length=500)
    description: str | None = None
    priority: int = Field(default=3, ge=1, le=5)
    tags: list[str] = []
    metadata: dict[str, Any] = {}
    team_id: UUID | None = None


class CaseRead(BaseReadSchema):
    title: str
    description: str | None = None
    status: CaseStatus
    priority: int
    lead: UserBrief | None = None
    created_by: UserBrief
    closed_at: datetime | None = None
    tags: list[str] = []
    metadata: dict[str, Any] = {}
    incident_count: int = 0
    incidents: list[IncidentListItem] = []
    team_id: UUID | None = None


class CaseUpdate(BaseSchema):
    title: str | None = None
    description: str | None = None
    status: CaseStatus | None = None
    priority: int | None = Field(default=None, ge=1, le=5)
    lead_id: UUID | None = None
    tags: list[str] | None = None
    metadata: dict[str, Any] | None = None
    cascade_status: bool = False


class CaseLinkIncident(BaseSchema):
    incident_id: UUID


class CaseListItem(BaseReadSchema):
    title: str
    status: CaseStatus
    priority: int
    lead: UserBrief | None = None
    created_by: UserBrief
    tags: list[str] = []
    incident_count: int = 0
    team_id: UUID | None = None


class CaseGroupedItem(BaseReadSchema):
    """A group (case) with its nested incidents for the grouped view."""

    title: str
    description: str | None = None
    status: CaseStatus
    priority: int
    lead: UserBrief | None = None
    created_by: UserBrief
    tags: list[str] = []
    incidents: list[IncidentListItem] = []
    team_id: UUID | None = None

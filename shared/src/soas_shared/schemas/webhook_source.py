"""Webhook source schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import Field

from soas_shared.schemas.common import BaseReadSchema, BaseSchema


class WebhookSourceCreate(BaseSchema):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = None
    icon: str | None = None


class WebhookSourceUpdate(BaseSchema):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    icon: str | None = None


class SourceAutomationCreate(BaseSchema):
    automation_id: UUID
    is_enabled: bool = True
    run_order: int = 0


class SourceAutomationUpdate(BaseSchema):
    run_order: int | None = None
    is_enabled: bool | None = None


class SourceAutomationRead(BaseSchema):
    id: UUID
    source_id: UUID
    automation_id: UUID
    automation_name: str
    is_enabled: bool
    run_order: int
    created_at: datetime


class WebhookSourceRead(BaseReadSchema):
    name: str
    description: str | None = None
    icon: str | None = None
    automations: list[SourceAutomationRead] = []


class WebhookSourceListItem(BaseSchema):
    id: UUID
    name: str
    description: str | None = None
    icon: str | None = None
    automation_count: int = 0
    created_at: datetime

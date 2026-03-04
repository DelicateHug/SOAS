"""Webhook schemas."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import Field

from soas_shared.schemas.common import BaseReadSchema, BaseSchema
from soas_shared.schemas.user import UserBrief


class WebhookCreate(BaseSchema):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = None
    source_type: str = Field(default="custom", max_length=100)
    source_id: UUID | None = None
    default_severity: str = Field(default="medium", max_length=20)
    default_tags: list[str] = []
    rate_limit_per_minute: int = Field(default=60, ge=1, le=10000)


class WebhookUpdate(BaseSchema):
    name: str | None = None
    description: str | None = None
    source_type: str | None = None
    source_id: UUID | None = None
    is_enabled: bool | None = None
    default_severity: str | None = None
    default_tags: list[str] | None = None
    rate_limit_per_minute: int | None = Field(default=None, ge=1, le=10000)


class WebhookRead(BaseReadSchema):
    name: str
    description: str | None = None
    secret_token: str
    source_type: str
    source_id: UUID | None = None
    source_name: str | None = None
    is_enabled: bool
    default_severity: str
    default_tags: list[str] = []
    rate_limit_per_minute: int
    ingest_url: str | None = None
    last_received_at: datetime | None = None
    total_received: int = 0
    created_by: UserBrief


class WebhookListItem(BaseSchema):
    id: UUID
    name: str
    source_type: str
    is_enabled: bool
    last_received_at: datetime | None = None
    total_received: int = 0
    created_at: datetime


class WebhookLogRead(BaseSchema):
    id: UUID
    webhook_id: UUID
    status: str
    request_body: dict[str, Any] = {}
    normalized_data: dict[str, Any] | None = None
    incident_id: UUID | None = None
    error_message: str | None = None
    processing_time_ms: int | None = None
    remote_ip: str | None = None
    created_at: datetime

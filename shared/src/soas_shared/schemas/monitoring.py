"""Monitoring, alerting, and quorum schemas."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import Field

from soas_shared.schemas.common import BaseSchema, BaseReadSchema
from soas_shared.schemas.user import UserBrief


# --- Component Health ---


class ComponentHealth(BaseSchema):
    component_type: str
    component_id: str
    status: str
    metrics: dict[str, Any] = {}
    last_check_at: datetime | None = None


class SystemHealthOverview(BaseSchema):
    overall_status: str
    components: list[ComponentHealth]
    uptime_seconds: float
    timestamp: datetime


# --- Health Metric Snapshots ---


class HealthMetricSnapshotRead(BaseSchema):
    id: UUID
    component_type: str
    component_id: str
    status: str
    metrics: dict[str, Any]
    recorded_at: datetime


# --- Alert Rules ---


class AlertRuleCreate(BaseSchema):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = None
    component_type: str
    metric_key: str = Field(min_length=1, max_length=100)
    condition: str = Field(pattern=r"^(gt|lt|gte|lte|eq|ne)$")
    threshold: float
    severity: str = "warning"
    is_enabled: bool = True
    cooldown_seconds: int = Field(default=300, ge=30)


class AlertRuleUpdate(BaseSchema):
    name: str | None = None
    description: str | None = None
    metric_key: str | None = None
    condition: str | None = None
    threshold: float | None = None
    severity: str | None = None
    is_enabled: bool | None = None
    cooldown_seconds: int | None = None


class AlertRuleRead(BaseReadSchema):
    name: str
    description: str | None
    component_type: str
    metric_key: str
    condition: str
    threshold: float
    severity: str
    is_enabled: bool
    cooldown_seconds: int
    created_by: UUID


# --- Alerts ---


class AlertRead(BaseSchema):
    id: UUID
    rule_id: UUID | None
    component_type: str
    component_id: str
    severity: str
    title: str
    message: str
    metric_value: float | None
    status: str
    acknowledged_by: UserBrief | None = None
    acknowledged_at: datetime | None
    resolved_at: datetime | None
    created_at: datetime


# --- Monitoring Agents ---


class MonitoringAgentRead(BaseSchema):
    id: UUID
    name: str
    description: str | None
    component_type: str
    check_interval_seconds: int
    is_enabled: bool
    last_check_at: datetime | None
    last_status: str | None
    consecutive_failures: int
    is_alive: bool
    created_at: datetime
    updated_at: datetime


class MonitoringAgentUpdate(BaseSchema):
    is_enabled: bool | None = None


# --- Quorum ---


class QuorumMember(BaseSchema):
    instance_id: str
    hostname: str
    started_at: datetime
    last_heartbeat: datetime
    is_alive: bool


class QuorumStatus(BaseSchema):
    has_quorum: bool
    active_members: int
    total_members: int
    quorum_threshold: int
    members: list[QuorumMember]

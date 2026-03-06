"""Monitoring, alerting, quorum, and agent management endpoints."""

from datetime import datetime, timedelta, timezone
from uuid import UUID

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from soas_backend.api.deps import get_current_user, get_redis, require_permission, require_role
from soas_backend.database import get_db
from soas_backend.models.user import User
from soas_backend.services.alerting_service import AlertingService
from soas_backend.services.monitoring_service import MonitoringService
from soas_backend.services.quorum_service import QuorumService
from soas_shared.schemas.common import PaginatedResponse, PaginationMeta
from soas_shared.schemas.monitoring import (
    AlertRead,
    AlertRuleCreate,
    AlertRuleRead,
    AlertRuleUpdate,
    MonitoringAgentUpdate,
)

router = APIRouter(prefix="/monitoring", tags=["monitoring"])


# ---------------------------------------------------------------------------
# Overview (combined endpoint to reduce frontend polling)
# ---------------------------------------------------------------------------


@router.get("/overview")
async def monitoring_overview(
    minutes: int = Query(10, ge=1, le=1440),
    _: dict = Depends(require_permission("monitoring", "read")),
    db: AsyncSession = Depends(get_db),
    r: aioredis.Redis = Depends(get_redis),
):
    """Combined health + alert summary + quorum in a single response.

    Health is aggregated over the last ``minutes`` (default 10) from stored
    snapshots rather than showing a single point-in-time check.
    """
    monitoring_svc = MonitoringService(db, r)
    alerting_svc = AlertingService(db, r)
    quorum_svc = QuorumService(r)
    return {
        "health": await monitoring_svc.get_aggregated_health(minutes),
        "alert_summary": await alerting_svc.get_active_alert_count(),
        "quorum": await quorum_svc.get_quorum_status(),
    }


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------


@router.get("/health")
async def system_health(
    _: dict = Depends(require_permission("monitoring", "read")),
    db: AsyncSession = Depends(get_db),
    r: aioredis.Redis = Depends(get_redis),
):
    """Get overall system health with all component statuses."""
    svc = MonitoringService(db, r)
    return await svc.get_system_health()


@router.get("/health/{component_type}")
async def component_health(
    component_type: str,
    _: dict = Depends(require_permission("monitoring", "read")),
    db: AsyncSession = Depends(get_db),
    r: aioredis.Redis = Depends(get_redis),
):
    """Get health for a specific component type."""
    svc = MonitoringService(db, r)
    return await svc.get_component_health(component_type)


@router.get("/metrics/{component_type}")
async def historical_metrics(
    component_type: str,
    component_id: str | None = None,
    hours: int = Query(24, ge=1, le=168),
    _: dict = Depends(require_permission("monitoring", "read")),
    db: AsyncSession = Depends(get_db),
    r: aioredis.Redis = Depends(get_redis),
):
    """Get historical metrics for time-series charts."""
    svc = MonitoringService(db, r)
    end = datetime.now(timezone.utc)
    start = end - timedelta(hours=hours)
    return await svc.get_historical_metrics(component_type, component_id, start, end)


# ---------------------------------------------------------------------------
# Alerts
# ---------------------------------------------------------------------------


@router.get("/alerts")
async def list_alerts(
    alert_status: str | None = Query(None, alias="status"),
    severity: str | None = None,
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=1, le=100),
    _: dict = Depends(require_permission("monitoring", "read")),
    db: AsyncSession = Depends(get_db),
    r: aioredis.Redis = Depends(get_redis),
):
    """List alerts with optional filters."""
    svc = AlertingService(db, r)
    alerts, total = await svc.get_alerts(alert_status, severity, page, per_page)
    total_pages = (total + per_page - 1) // per_page if total > 0 else 1
    return {
        "data": [
            {
                "id": str(a.id),
                "rule_id": str(a.rule_id) if a.rule_id else None,
                "component_type": a.component_type,
                "component_id": a.component_id,
                "severity": a.severity,
                "title": a.title,
                "message": a.message,
                "metric_value": a.metric_value,
                "status": a.status,
                "acknowledged_by": None,
                "acknowledged_at": a.acknowledged_at.isoformat() if a.acknowledged_at else None,
                "resolved_at": a.resolved_at.isoformat() if a.resolved_at else None,
                "created_at": a.created_at.isoformat(),
            }
            for a in alerts
        ],
        "meta": {
            "total": total,
            "page": page,
            "per_page": per_page,
            "total_pages": total_pages,
        },
    }


@router.post("/alerts/{alert_id}/acknowledge")
async def acknowledge_alert(
    alert_id: UUID,
    current_user: User = Depends(get_current_user),
    _: dict = Depends(require_permission("monitoring", "admin")),
    db: AsyncSession = Depends(get_db),
    r: aioredis.Redis = Depends(get_redis),
):
    """Acknowledge an active alert."""
    svc = AlertingService(db, r)
    alert = await svc.acknowledge_alert(alert_id, current_user.id)
    if not alert:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert not found")
    return {"message": "Alert acknowledged", "alert_id": str(alert.id)}


@router.post("/alerts/{alert_id}/resolve")
async def resolve_alert(
    alert_id: UUID,
    _: dict = Depends(require_permission("monitoring", "admin")),
    db: AsyncSession = Depends(get_db),
    r: aioredis.Redis = Depends(get_redis),
):
    """Resolve an alert."""
    svc = AlertingService(db, r)
    alert = await svc.resolve_alert(alert_id)
    if not alert:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert not found")
    return {"message": "Alert resolved", "alert_id": str(alert.id)}


@router.get("/alerts/summary")
async def alert_summary(
    _: dict = Depends(require_permission("monitoring", "read")),
    db: AsyncSession = Depends(get_db),
    r: aioredis.Redis = Depends(get_redis),
):
    """Get active alert counts by severity."""
    svc = AlertingService(db, r)
    return await svc.get_active_alert_count()


# ---------------------------------------------------------------------------
# Alert Rules
# ---------------------------------------------------------------------------


@router.get("/alert-rules")
async def list_alert_rules(
    component_type: str | None = None,
    _: dict = Depends(require_permission("monitoring", "admin")),
    db: AsyncSession = Depends(get_db),
    r: aioredis.Redis = Depends(get_redis),
):
    """List all alert rules."""
    svc = AlertingService(db, r)
    rules = await svc.get_rules(component_type)
    return [
        {
            "id": str(rule.id),
            "name": rule.name,
            "description": rule.description,
            "component_type": rule.component_type,
            "metric_key": rule.metric_key,
            "condition": rule.condition,
            "threshold": rule.threshold,
            "severity": rule.severity,
            "is_enabled": rule.is_enabled,
            "cooldown_seconds": rule.cooldown_seconds,
            "created_by": str(rule.created_by),
            "created_at": rule.created_at.isoformat(),
            "updated_at": rule.updated_at.isoformat(),
        }
        for rule in rules
    ]


@router.post("/alert-rules", status_code=201)
async def create_alert_rule(
    body: AlertRuleCreate,
    current_user: User = Depends(get_current_user),
    _: dict = Depends(require_permission("monitoring", "admin")),
    db: AsyncSession = Depends(get_db),
    r: aioredis.Redis = Depends(get_redis),
):
    """Create a new alert rule."""
    svc = AlertingService(db, r)
    rule = await svc.create_rule(body.model_dump(), current_user.id)
    return {
        "id": str(rule.id),
        "name": rule.name,
        "component_type": rule.component_type,
        "metric_key": rule.metric_key,
        "condition": rule.condition,
        "threshold": rule.threshold,
        "severity": rule.severity,
        "is_enabled": rule.is_enabled,
        "cooldown_seconds": rule.cooldown_seconds,
        "created_at": rule.created_at.isoformat(),
    }


@router.patch("/alert-rules/{rule_id}")
async def update_alert_rule(
    rule_id: UUID,
    body: AlertRuleUpdate,
    _: dict = Depends(require_permission("monitoring", "admin")),
    db: AsyncSession = Depends(get_db),
    r: aioredis.Redis = Depends(get_redis),
):
    """Update an alert rule."""
    svc = AlertingService(db, r)
    rule = await svc.update_rule(rule_id, body.model_dump(exclude_unset=True))
    if not rule:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert rule not found")
    return {
        "id": str(rule.id),
        "name": rule.name,
        "component_type": rule.component_type,
        "metric_key": rule.metric_key,
        "condition": rule.condition,
        "threshold": rule.threshold,
        "severity": rule.severity,
        "is_enabled": rule.is_enabled,
        "cooldown_seconds": rule.cooldown_seconds,
        "updated_at": rule.updated_at.isoformat(),
    }


@router.delete("/alert-rules/{rule_id}", status_code=204)
async def delete_alert_rule(
    rule_id: UUID,
    _: dict = Depends(require_permission("monitoring", "admin")),
    db: AsyncSession = Depends(get_db),
    r: aioredis.Redis = Depends(get_redis),
):
    """Delete an alert rule."""
    svc = AlertingService(db, r)
    deleted = await svc.delete_rule(rule_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert rule not found")


# ---------------------------------------------------------------------------
# Monitoring Agents (meta-monitoring)
# ---------------------------------------------------------------------------


@router.get("/agents")
async def list_monitoring_agents(
    _: dict = Depends(require_permission("monitoring", "read")),
    db: AsyncSession = Depends(get_db),
    r: aioredis.Redis = Depends(get_redis),
):
    """List all monitoring agents with alive status."""
    svc = MonitoringService(db, r)
    return await svc.get_all_agents()


@router.patch("/agents/{agent_id}")
async def update_monitoring_agent(
    agent_id: UUID,
    body: MonitoringAgentUpdate,
    _: dict = Depends(require_permission("monitoring", "admin")),
    db: AsyncSession = Depends(get_db),
    r: aioredis.Redis = Depends(get_redis),
):
    """Enable or disable a monitoring agent."""
    svc = MonitoringService(db, r)
    if body.is_enabled is not None:
        await svc.update_agent(agent_id, body.is_enabled)
    return {"message": "Agent updated"}


# ---------------------------------------------------------------------------
# Quorum
# ---------------------------------------------------------------------------


@router.get("/quorum")
async def quorum_status(
    _: dict = Depends(require_permission("monitoring", "read")),
    r: aioredis.Redis = Depends(get_redis),
):
    """Get backend quorum status."""
    svc = QuorumService(r)
    return await svc.get_quorum_status()


# ---------------------------------------------------------------------------
# In-Memory Request Log
# ---------------------------------------------------------------------------


@router.get("/request-log/stats")
async def request_log_stats(
    _: dict = Depends(require_permission("monitoring", "read")),
):
    """Get request/error buffer counts."""
    from soas_backend.middleware.request_log import get_stats
    return get_stats()


@router.get("/request-log/errors")
async def request_log_errors(
    limit: int = Query(50, ge=1, le=500),
    _: dict = Depends(require_permission("monitoring", "read")),
):
    """Get recent error records from the in-memory buffer."""
    from soas_backend.middleware.request_log import get_errors
    errors = get_errors()
    return [
        {
            "request_id": r.request_id,
            "method": r.method,
            "path": r.path,
            "status_code": r.status_code,
            "duration_ms": r.duration_ms,
            "timestamp": r.timestamp,
            "detail": r.detail,
        }
        for r in errors[-limit:]
    ]


@router.get("/request-log/requests")
async def request_log_requests(
    limit: int = Query(100, ge=1, le=2000),
    _: dict = Depends(require_role("admin")),
):
    """Get recent request records from the in-memory buffer (admin only)."""
    from soas_backend.middleware.request_log import get_requests
    requests = get_requests()
    return [
        {
            "request_id": r.request_id,
            "method": r.method,
            "path": r.path,
            "status_code": r.status_code,
            "duration_ms": r.duration_ms,
            "timestamp": r.timestamp,
        }
        for r in requests[-limit:]
    ]


@router.post("/request-log/clear")
async def request_log_clear(
    _: dict = Depends(require_role("admin")),
):
    """Manually clear both request log buffers."""
    from soas_backend.middleware.request_log import cleanup_if_healthy
    cleared = cleanup_if_healthy()
    if not cleared:
        return {"message": "Buffers not cleared — errors still present", "cleared": False}
    return {"message": "Both buffers cleared", "cleared": True}

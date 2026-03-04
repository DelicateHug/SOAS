"""Dashboard statistics and activity feed endpoints."""

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from soas_backend.api.deps import require_permission
from soas_backend.database import get_db
from soas_backend.models.automation import Automation
from soas_backend.models.case import Case
from soas_backend.models.execution import ExecutionLog
from soas_backend.models.incident import Incident
from soas_backend.models.timeline import TimelineEntry
from soas_backend.services.execution_service import ExecutionService
from soas_shared.schemas.timeline import TimelineEntryRead
from soas_shared.schemas.user import UserBrief

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/stats")
async def dashboard_stats(
    _: dict = Depends(require_permission("dashboard", "read")),
    db: AsyncSession = Depends(get_db),
):
    # Incident counts by status and severity in two grouped queries
    incident_status_counts: dict[str, int] = {}
    result = await db.execute(
        select(Incident.status, func.count(Incident.id)).group_by(Incident.status)
    )
    for status, count in result.all():
        incident_status_counts[status] = count

    incident_severity_counts: dict[str, int] = {}
    result = await db.execute(
        select(Incident.severity, func.count(Incident.id)).group_by(Incident.severity)
    )
    for severity, count in result.all():
        incident_severity_counts[severity] = count

    # Derive totals from status counts (avoids 2 extra queries)
    closed_statuses = {"closed", "resolved", "false_positive"}
    total_incidents = sum(incident_status_counts.values())
    open_count = sum(
        c for s, c in incident_status_counts.items() if s not in closed_statuses
    )

    # Open cases + active automations in a single query
    counts_row = (
        await db.execute(
            select(
                select(func.count(Case.id))
                .where(Case.status.notin_(["closed", "archived"]))
                .correlate(None)
                .scalar_subquery()
                .label("open_cases"),
                select(func.count(Automation.id))
                .where(Automation.status == "active")
                .correlate(None)
                .scalar_subquery()
                .label("active_automations"),
            )
        )
    ).one()
    open_cases = counts_row.open_cases or 0
    active_automations = counts_row.active_automations or 0

    # MTTR (mean time to resolution) for last 30 days
    thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)
    mttr_result = await db.execute(
        select(
            func.avg(
                func.extract("epoch", Incident.resolved_at - Incident.created_at)
            )
        ).where(
            Incident.resolved_at.isnot(None),
            Incident.created_at >= thirty_days_ago,
        )
    )
    avg_resolution_seconds = mttr_result.scalar()
    mttr_hours = round(avg_resolution_seconds / 3600, 1) if avg_resolution_seconds else None

    # Execution stats
    exec_svc = ExecutionService(db)
    execution_stats = await exec_svc.get_stats()

    # Incidents created per day (last 7 days)
    seven_days_ago = datetime.now(timezone.utc) - timedelta(days=7)
    daily_incidents = []
    result = await db.execute(
        select(
            func.date_trunc("day", Incident.created_at).label("day"),
            func.count(Incident.id),
        )
        .where(Incident.created_at >= seven_days_ago)
        .group_by("day")
        .order_by("day")
    )
    for day, count in result.all():
        daily_incidents.append({"date": day.isoformat(), "count": count})

    return {
        "incidents": {
            "open": open_count,
            "total": total_incidents,
            "by_status": incident_status_counts,
            "by_severity": incident_severity_counts,
            "daily": daily_incidents,
            "mttr_hours": mttr_hours,
        },
        "cases": {
            "open": open_cases,
        },
        "automations": {
            "active": active_automations,
        },
        "executions": execution_stats,
    }


@router.get("/activity", response_model=list[TimelineEntryRead])
async def recent_activity(
    limit: int = Query(20, ge=1, le=100),
    _: dict = Depends(require_permission("dashboard", "read")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(TimelineEntry)
        .options(selectinload(TimelineEntry.creator))
        .order_by(TimelineEntry.created_at.desc())
        .limit(limit)
    )
    entries = result.scalars().all()

    def _user_brief(user) -> UserBrief | None:
        if user is None:
            return None
        return UserBrief(id=user.id, username=user.username, display_name=user.display_name)

    return [
        TimelineEntryRead(
            id=e.id,
            incident_id=e.incident_id,
            case_id=e.case_id,
            entry_type=e.entry_type,
            content=e.content,
            details=e.details,
            created_by=_user_brief(e.creator),
            created_at=e.created_at,
        )
        for e in entries
    ]

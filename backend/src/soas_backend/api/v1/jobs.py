"""Scheduled job CRUD endpoints."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from soas_backend.api.deps import get_current_user, require_permission
from soas_backend.database import get_db
from soas_backend.models.user import User
from soas_backend.services.scheduled_job_service import ScheduledJobService
from soas_backend.services.version_service import VersionService
from soas_shared.schemas.version import VersionCreate, VersionRead, VersionUpdate
from soas_shared.schemas.common import PaginatedResponse, PaginationMeta
from soas_shared.schemas.scheduled_job import (
    ScheduledJobCreate,
    ScheduledJobListItem,
    ScheduledJobRead,
    ScheduledJobUpdate,
)
from soas_shared.schemas.user import UserBrief

router = APIRouter(prefix="/jobs", tags=["jobs"])


def _user_brief(user) -> UserBrief | None:
    if user is None:
        return None
    return UserBrief(id=user.id, username=user.username, display_name=user.display_name)


def _job_to_read(job) -> ScheduledJobRead:
    return ScheduledJobRead(
        id=job.id,
        automation_id=job.automation_id,
        automation_name=job.automation.name if job.automation else "Unknown",
        name=job.name,
        description=job.description,
        schedule_type=job.schedule_type,
        cron_expression=job.cron_expression,
        interval_seconds=job.interval_seconds,
        calendar_config=job.calendar_config,
        timezone=job.timezone,
        parameters=job.parameters or {},
        is_enabled=job.is_enabled,
        start_date=job.start_date,
        end_date=job.end_date,
        last_run_at=job.last_run_at,
        next_run_at=job.next_run_at,
        run_count=job.run_count,
        created_by=_user_brief(job.creator),
        created_at=job.created_at,
        updated_at=job.updated_at,
    )


def _job_to_list_item(job) -> ScheduledJobListItem:
    return ScheduledJobListItem(
        id=job.id,
        automation_id=job.automation_id,
        automation_name=job.automation.name if job.automation else "Unknown",
        name=job.name,
        description=job.description,
        schedule_type=job.schedule_type,
        cron_expression=job.cron_expression,
        interval_seconds=job.interval_seconds,
        calendar_config=job.calendar_config,
        timezone=job.timezone,
        is_enabled=job.is_enabled,
        last_run_at=job.last_run_at,
        next_run_at=job.next_run_at,
        run_count=job.run_count,
        start_date=job.start_date,
        end_date=job.end_date,
        created_by=_user_brief(job.creator),
        created_at=job.created_at,
        updated_at=job.updated_at,
    )


@router.get("", response_model=PaginatedResponse[ScheduledJobListItem])
async def list_jobs(
    enabled: bool | None = Query(None),
    automation_id: UUID | None = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=1, le=100),
    _: dict = Depends(require_permission("job", "read")),
    db: AsyncSession = Depends(get_db),
):
    svc = ScheduledJobService(db)
    jobs, total = await svc.list_jobs(enabled=enabled, automation_id=automation_id, page=page, per_page=per_page)

    return PaginatedResponse(
        data=[_job_to_list_item(j) for j in jobs],
        meta=PaginationMeta(
            total=total,
            page=page,
            per_page=per_page,
            total_pages=(total + per_page - 1) // per_page if total else 0,
        ),
    )


@router.post("", response_model=ScheduledJobRead, status_code=status.HTTP_201_CREATED)
async def create_job(
    body: ScheduledJobCreate,
    current_user: User = Depends(get_current_user),
    _: dict = Depends(require_permission("job", "create")),
    db: AsyncSession = Depends(get_db),
):
    svc = ScheduledJobService(db)
    try:
        job = await svc.create(
            automation_id=body.automation_id,
            name=body.name,
            description=body.description,
            schedule_type=body.schedule_type,
            cron_expression=body.cron_expression,
            interval_seconds=body.interval_seconds,
            calendar_config=body.calendar_config.model_dump() if body.calendar_config else None,
            timezone_str=body.timezone,
            parameters=body.parameters,
            start_date=body.start_date,
            end_date=body.end_date,
            created_by=current_user.id,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    job = await svc.get(job.id)
    return _job_to_read(job)


@router.get("/{job_id}", response_model=ScheduledJobRead)
async def get_job(
    job_id: UUID,
    _: dict = Depends(require_permission("job", "read")),
    db: AsyncSession = Depends(get_db),
):
    svc = ScheduledJobService(db)
    job = await svc.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Scheduled job not found")
    return _job_to_read(job)


@router.patch("/{job_id}", response_model=ScheduledJobRead)
async def update_job(
    job_id: UUID,
    body: ScheduledJobUpdate,
    _: dict = Depends(require_permission("job", "update")),
    db: AsyncSession = Depends(get_db),
):
    svc = ScheduledJobService(db)
    try:
        job = await svc.update(
            job_id,
            name=body.name,
            description=body.description,
            schedule_type=body.schedule_type,
            cron_expression=body.cron_expression,
            interval_seconds=body.interval_seconds,
            calendar_config=body.calendar_config.model_dump() if body.calendar_config else None,
            timezone_str=body.timezone,
            parameters=body.parameters,
            start_date=body.start_date,
            end_date=body.end_date,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    if not job:
        raise HTTPException(status_code=404, detail="Scheduled job not found")
    return _job_to_read(job)


@router.post("/{job_id}/enable", response_model=ScheduledJobRead)
async def enable_job(
    job_id: UUID,
    _: dict = Depends(require_permission("job", "update")),
    db: AsyncSession = Depends(get_db),
):
    svc = ScheduledJobService(db)
    job = await svc.toggle_enabled(job_id, enabled=True)
    if not job:
        raise HTTPException(status_code=404, detail="Scheduled job not found")
    return _job_to_read(job)


@router.post("/{job_id}/disable", response_model=ScheduledJobRead)
async def disable_job(
    job_id: UUID,
    _: dict = Depends(require_permission("job", "update")),
    db: AsyncSession = Depends(get_db),
):
    svc = ScheduledJobService(db)
    job = await svc.toggle_enabled(job_id, enabled=False)
    if not job:
        raise HTTPException(status_code=404, detail="Scheduled job not found")
    return _job_to_read(job)


@router.delete("/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_job(
    job_id: UUID,
    current_user: User = Depends(get_current_user),
    _: dict = Depends(require_permission("job", "delete")),
    db: AsyncSession = Depends(get_db),
):
    svc = ScheduledJobService(db)
    deleted = await svc.delete(job_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Scheduled job not found")
    # Phase 7: audit trail
    try:
        from soas_backend.services.job_tick_service import JobTickService
        await JobTickService(db).record(
            job_id=job_id, decision="deleted", actor_id=current_user.id
        )
    except Exception:
        pass


# ------------------------------------------------------------------
# Phase 7: job ticks audit + run-now
# ------------------------------------------------------------------


@router.get("/{job_id}/ticks")
async def list_job_ticks(
    job_id: UUID,
    limit: int = Query(100, ge=1, le=500),
    _: dict = Depends(require_permission("job", "read")),
    db: AsyncSession = Depends(get_db),
):
    """Return the most recent scheduler decisions for this job (job_ticks)."""
    from soas_backend.services.job_tick_service import JobTickService
    rows = await JobTickService(db).recent(job_id, limit=limit)
    return [
        {
            "id": str(r.id),
            "decision": r.decision,
            "reason": r.reason,
            "execution_id": str(r.execution_id) if r.execution_id else None,
            "actor_id": str(r.actor_id) if r.actor_id else None,
            "extra": r.extra,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]


@router.post("/{job_id}/run-now")
async def run_job_now(
    job_id: UUID,
    current_user: User = Depends(get_current_user),
    _: dict = Depends(require_permission("job", "update")),
    db: AsyncSession = Depends(get_db),
):
    """Trigger an off-schedule execution of the job's automation immediately."""
    svc = ScheduledJobService(db)
    job = await svc.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Scheduled job not found")
    # Audit
    try:
        from soas_backend.services.job_tick_service import JobTickService
        await JobTickService(db).record(
            job_id=job_id,
            decision="run_now",
            reason=f"Triggered by {current_user.username}",
            actor_id=current_user.id,
        )
    except Exception:
        pass
    # Bump next_run_at to now so the scheduled-jobs beat task picks it up
    # on the next tick (within 60s). Conservative — keeps the firing path
    # identical to normal schedule firing, including ExecutionLog creation.
    from datetime import datetime, timezone
    job.next_run_at = datetime.now(timezone.utc)
    await db.flush()
    return {
        "job_id": str(job_id),
        "next_run_at": job.next_run_at.isoformat(),
        "note": "Will fire on the next scheduler tick (≤60s).",
    }


def _version_read(v) -> VersionRead:
    return VersionRead(
        id=v.id,
        version_number=v.version_number,
        name=v.name,
        description=v.description,
        created_by=_user_brief(v.creator),
        created_at=v.created_at,
    )


# ------------------------------------------------------------------
# Version control endpoints
# ------------------------------------------------------------------


@router.get("/{job_id}/versions", response_model=list[VersionRead])
async def list_job_versions(
    job_id: UUID,
    _: dict = Depends(require_permission("job", "read")),
    db: AsyncSession = Depends(get_db),
):
    svc = VersionService(db)
    versions = await svc.list_job_versions(job_id)
    return [_version_read(v) for v in versions]


@router.post("/{job_id}/versions", response_model=VersionRead, status_code=status.HTTP_201_CREATED)
async def create_job_version(
    job_id: UUID,
    body: VersionCreate,
    current_user: User = Depends(get_current_user),
    _: dict = Depends(require_permission("job", "update")),
    db: AsyncSession = Depends(get_db),
):
    job_svc = ScheduledJobService(db)
    job = await job_svc.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Scheduled job not found")

    svc = VersionService(db)
    version = await svc.create_job_version(
        job, current_user.id, name=body.name, description=body.description
    )
    return _version_read(version)


@router.patch("/{job_id}/versions/{version_number}", response_model=VersionRead)
async def update_job_version(
    job_id: UUID,
    version_number: int,
    body: VersionUpdate,
    _: dict = Depends(require_permission("job", "update")),
    db: AsyncSession = Depends(get_db),
):
    svc = VersionService(db)
    version = await svc.update_job_version_meta(
        job_id, version_number, name=body.name, description=body.description
    )
    if not version:
        raise HTTPException(status_code=404, detail="Version not found")
    return _version_read(version)


@router.post("/{job_id}/versions/{version_number}/restore", response_model=ScheduledJobRead)
async def restore_job_version(
    job_id: UUID,
    version_number: int,
    _: dict = Depends(require_permission("job", "update")),
    db: AsyncSession = Depends(get_db),
):
    job_svc = ScheduledJobService(db)
    job = await job_svc.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Scheduled job not found")

    svc = VersionService(db)
    job = await svc.restore_job_version(job, version_number)
    if not job:
        raise HTTPException(status_code=404, detail="Version not found")

    # Re-fetch with relationships
    job = await job_svc.get(job_id)
    return _job_to_read(job)

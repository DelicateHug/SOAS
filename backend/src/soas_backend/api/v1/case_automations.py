"""Case automation views and manual run endpoints."""

from uuid import UUID

from soas_backend.celery_proxy import get_celery
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from soas_backend.api.deps import get_current_user, get_redis_pool, require_permission
from soas_backend.database import get_db
from soas_backend.models.automation import Automation
from soas_backend.models.case import Case, CaseIncident
from soas_backend.models.case_file import CaseFile
from soas_backend.models.case_note import CaseNote
from soas_backend.models.execution import ExecutionLog
from soas_backend.models.timeline import TimelineEntry
from soas_backend.models.user import User
from soas_backend.services.incident_cache import IncidentCacheService
from soas_shared.schemas.user import UserBrief

router = APIRouter(tags=["case-automations"])


def _user_brief(user) -> UserBrief | None:
    if user is None:
        return None
    return UserBrief(id=user.id, username=user.username, display_name=user.display_name)


@router.get("/cases/{case_id}/automations")
async def list_case_automations(
    case_id: UUID,
    _: dict = Depends(require_permission("case", "read")),
    db: AsyncSession = Depends(get_db),
):
    """List automation executions for this case."""
    result = await db.execute(
        select(ExecutionLog)
        .where(ExecutionLog.case_id == case_id)
        .options(selectinload(ExecutionLog.automation))
        .order_by(ExecutionLog.created_at.desc())
    )
    executions = result.scalars().all()

    return [
        {
            "id": str(ex.id),
            "automation_id": str(ex.automation_id),
            "automation_name": ex.automation.name if ex.automation else "Unknown",
            "status": ex.status,
            "triggered_by": str(ex.triggered_by),
            "parameters": ex.parameters or {},
            "started_at": ex.started_at.isoformat() if ex.started_at else None,
            "completed_at": ex.completed_at.isoformat() if ex.completed_at else None,
            "duration_ms": ex.duration_ms,
            "created_at": ex.created_at.isoformat() if ex.created_at else None,
            "is_evidence": ex.is_evidence,
        }
        for ex in executions
    ]


@router.post("/cases/{case_id}/automations/{execution_id}/evidence")
async def toggle_execution_evidence(
    case_id: UUID,
    execution_id: UUID,
    current_user: User = Depends(get_current_user),
    _: dict = Depends(require_permission("case", "read")),
    db: AsyncSession = Depends(get_db),
):
    """Toggle evidence status on a case automation execution."""
    result = await db.execute(
        select(ExecutionLog)
        .where(ExecutionLog.id == execution_id, ExecutionLog.case_id == case_id)
        .options(selectinload(ExecutionLog.automation))
    )
    execution = result.scalar_one_or_none()
    if not execution:
        raise HTTPException(status_code=404, detail="Execution not found")

    execution.is_evidence = not execution.is_evidence
    await db.flush()

    action = "marked as evidence" if execution.is_evidence else "unmarked as evidence"
    automation_name = execution.automation.name if execution.automation else "Unknown"
    db.add(TimelineEntry(
        case_id=case_id,
        entry_type="evidence",
        content=f"Automation execution {action}: {automation_name}",
        details={
            "execution_id": str(execution.id),
            "automation_name": automation_name,
            "is_evidence": execution.is_evidence,
        },
        created_by=current_user.id,
    ))
    await db.flush()

    return {"id": str(execution.id), "is_evidence": execution.is_evidence}


@router.post("/cases/{case_id}/automations/{automation_id}/run", status_code=status.HTTP_202_ACCEPTED)
async def run_automation_on_case(
    case_id: UUID,
    automation_id: UUID,
    current_user: User = Depends(get_current_user),
    _: dict = Depends(require_permission("automation", "execute")),
    db: AsyncSession = Depends(get_db),
):
    """Manually trigger an automation in this case's context."""
    case_result = await db.execute(select(Case).where(Case.id == case_id))
    case = case_result.scalar_one_or_none()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    auto_result = await db.execute(select(Automation).where(Automation.id == automation_id))
    automation = auto_result.scalar_one_or_none()
    if not automation:
        raise HTTPException(status_code=404, detail="Automation not found")
    if automation.status != "active":
        raise HTTPException(status_code=400, detail="Automation is not active")
    if not automation.script_path:
        raise HTTPException(status_code=400, detail="Automation has no compiled script")

    # Query all linked incidents ordered by linked_at ASC
    ci_result = await db.execute(
        select(CaseIncident)
        .where(CaseIncident.case_id == case_id)
        .options(selectinload(CaseIncident.incident))
        .order_by(CaseIncident.linked_at.asc())
    )
    case_incidents = ci_result.scalars().all()

    # Cache each linked incident to Redis so the runtime bridge can access them
    r = await get_redis_pool()
    cache = IncidentCacheService(r)
    ordered_incident_ids: list[str] = []
    for ci in case_incidents:
        inc = ci.incident
        metadata = inc.metadata_ or {}
        incident_data = {
            "id": str(inc.id),
            "title": inc.title,
            "summary": inc.summary,
            "severity": inc.severity,
            "status": inc.status,
            "source": inc.source,
            "source_ref": inc.source_ref,
            "tags": inc.tags or [],
            "metadata": metadata,
            **metadata,
        }
        await cache.cache_incident(inc.id, incident_data)
        ordered_incident_ids.append(str(inc.id))

    # Store ordered incident ID list in Redis for the worker
    order_key = f"case:{case_id}:incident_order"
    pipe = r.pipeline(transaction=True)
    pipe.delete(order_key)
    if ordered_incident_ids:
        pipe.rpush(order_key, *ordered_incident_ids)
    pipe.expire(order_key, 3600)
    await pipe.execute()

    # Set incident_id to first linked incident for backward-compatible get_incident_var/data
    first_incident_id = UUID(ordered_incident_ids[0]) if ordered_incident_ids else None

    execution = ExecutionLog(
        automation_id=automation.id,
        triggered_by=current_user.id,
        case_id=case_id,
        incident_id=first_incident_id,
        parameters={"manual_run": True},
        status="pending",
    )
    db.add(execution)
    await db.flush()

    celery = get_celery()
    task = celery.send_task(
        "soas.run_automation",
        args=[
            str(execution.id),
            str(automation.id),
            {"manual_run": True, "case_id": str(case_id)},
        ],
    )
    execution.celery_task_id = task.id
    execution.status = "queued"
    await db.flush()

    timeline_entry = TimelineEntry(
        case_id=case_id,
        entry_type="automation_run",
        content=f"Automation '{automation.name}' manually triggered by {current_user.display_name}",
        details={"automation_id": str(automation.id), "execution_id": str(execution.id)},
        created_by=current_user.id,
    )
    db.add(timeline_entry)
    await db.flush()

    return {
        "execution_id": str(execution.id),
        "automation_id": str(automation.id),
        "celery_task_id": task.id,
        "status": "queued",
    }


@router.get("/cases/{case_id}/evidence")
async def get_case_evidence(
    case_id: UUID,
    _: dict = Depends(require_permission("case", "read")),
    db: AsyncSession = Depends(get_db),
):
    """Aggregated evidence view: notes, files, and timeline entries marked as evidence."""
    notes_result = await db.execute(
        select(CaseNote)
        .where(CaseNote.case_id == case_id, CaseNote.is_evidence == True)  # noqa: E712
        .options(selectinload(CaseNote.creator))
        .order_by(CaseNote.created_at.desc())
    )
    notes = notes_result.scalars().all()

    files_result = await db.execute(
        select(CaseFile)
        .where(CaseFile.case_id == case_id, CaseFile.is_evidence == True)  # noqa: E712
        .options(selectinload(CaseFile.uploader))
        .order_by(CaseFile.created_at.desc())
    )
    files = files_result.scalars().all()

    timeline_result = await db.execute(
        select(TimelineEntry)
        .where(TimelineEntry.case_id == case_id, TimelineEntry.is_evidence == True)  # noqa: E712
        .options(selectinload(TimelineEntry.creator))
        .order_by(TimelineEntry.created_at.desc())
    )
    timeline_entries = timeline_result.scalars().all()

    # Evidence executions
    exec_result = await db.execute(
        select(ExecutionLog)
        .where(ExecutionLog.case_id == case_id, ExecutionLog.is_evidence == True)  # noqa: E712
        .options(selectinload(ExecutionLog.automation), selectinload(ExecutionLog.user))
        .order_by(ExecutionLog.created_at.desc())
    )
    evidence_executions = exec_result.scalars().all()

    return {
        "notes": [
            {
                "id": str(n.id),
                "type": "note",
                "content": n.content,
                "created_by": _user_brief(n.creator),
                "created_at": n.created_at.isoformat(),
            }
            for n in notes
        ],
        "files": [
            {
                "id": str(f.id),
                "type": "file",
                "filename": f.filename,
                "content_type": f.content_type,
                "file_size": f.file_size,
                "uploaded_by": _user_brief(f.uploader),
                "created_at": f.created_at.isoformat(),
            }
            for f in files
        ],
        "executions": [
            {
                "id": str(ex.id),
                "type": "execution",
                "automation_name": ex.automation.name if ex.automation else "Unknown",
                "status": ex.status,
                "triggered_by": _user_brief(ex.user),
                "duration_ms": ex.duration_ms,
                "created_at": ex.created_at.isoformat(),
            }
            for ex in evidence_executions
        ],
        "timeline_entries": [
            {
                "id": str(e.id),
                "type": "timeline",
                "entry_type": e.entry_type,
                "content": e.content,
                "created_by": _user_brief(e.creator),
                "created_at": e.created_at.isoformat(),
            }
            for e in timeline_entries
        ],
    }

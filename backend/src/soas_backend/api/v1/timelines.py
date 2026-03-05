"""Timeline endpoints."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from soas_backend.api.deps import get_current_user, require_permission
from soas_backend.database import get_db
from soas_backend.models.case_note import CaseNote
from soas_backend.models.execution import ExecutionLog
from soas_backend.models.incident_note import IncidentNote
from soas_backend.models.timeline import TimelineEntry
from soas_backend.models.user import User
from soas_shared.schemas.timeline import TimelineCreate, TimelineEntryRead
from soas_shared.schemas.user import UserBrief

router = APIRouter(tags=["timelines"])


def _user_brief(user) -> UserBrief | None:
    if user is None:
        return None
    return UserBrief(id=user.id, username=user.username, display_name=user.display_name)


@router.get("/incidents/{incident_id}/timeline", response_model=list[TimelineEntryRead])
async def get_incident_timeline(
    incident_id: UUID,
    limit: int = Query(50, ge=1, le=200),
    _: dict = Depends(require_permission("timeline", "read")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(TimelineEntry)
        .options(selectinload(TimelineEntry.creator))
        .where(TimelineEntry.incident_id == incident_id)
        .order_by(TimelineEntry.created_at.desc())
        .limit(limit)
    )
    entries = result.scalars().all()
    return [
        TimelineEntryRead(
            id=e.id,
            incident_id=e.incident_id,
            case_id=e.case_id,
            entry_type=e.entry_type,
            content=e.content,
            details=e.details,
            is_evidence=e.is_evidence,
            created_by=_user_brief(e.creator),
            created_at=e.created_at,
        )
        for e in entries
    ]


@router.post("/incidents/{incident_id}/timeline", response_model=TimelineEntryRead, status_code=201)
async def add_incident_comment(
    incident_id: UUID,
    body: TimelineCreate,
    current_user: User = Depends(get_current_user),
    _: dict = Depends(require_permission("timeline", "create")),
    db: AsyncSession = Depends(get_db),
):
    entry = TimelineEntry(
        incident_id=incident_id,
        entry_type=body.entry_type,
        content=body.content,
        details=body.details,
        created_by=current_user.id,
    )
    db.add(entry)
    await db.flush()

    return TimelineEntryRead(
        id=entry.id,
        incident_id=entry.incident_id,
        case_id=entry.case_id,
        entry_type=entry.entry_type,
        content=entry.content,
        details=entry.details,
        is_evidence=entry.is_evidence,
        created_by=UserBrief(
            id=current_user.id,
            username=current_user.username,
            display_name=current_user.display_name,
        ),
        created_at=entry.created_at,
    )


@router.post("/incidents/{incident_id}/timeline/{entry_id}/evidence", response_model=TimelineEntryRead)
async def toggle_timeline_evidence(
    incident_id: UUID,
    entry_id: UUID,
    current_user: User = Depends(get_current_user),
    _: dict = Depends(require_permission("timeline", "create")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(TimelineEntry)
        .options(selectinload(TimelineEntry.creator))
        .where(TimelineEntry.id == entry_id, TimelineEntry.incident_id == incident_id)
    )
    entry = result.scalar_one_or_none()
    if not entry:
        raise HTTPException(status_code=404, detail="Timeline entry not found")

    entry.is_evidence = not entry.is_evidence

    if entry.details and entry.details.get("note_id"):
        note_result = await db.execute(
            select(IncidentNote).where(IncidentNote.id == UUID(entry.details["note_id"]))
        )
        linked_note = note_result.scalar_one_or_none()
        if linked_note:
            linked_note.is_evidence = entry.is_evidence

    # Also toggle linked execution if present
    if entry.details and entry.details.get("execution_id"):
        exec_result = await db.execute(
            select(ExecutionLog).where(ExecutionLog.id == UUID(entry.details["execution_id"]))
        )
        linked_exec = exec_result.scalar_one_or_none()
        if linked_exec:
            linked_exec.is_evidence = entry.is_evidence

    # Create audit trail entry
    action = "marked as evidence" if entry.is_evidence else "unmarked as evidence"
    db.add(TimelineEntry(
        incident_id=incident_id,
        entry_type="evidence_marked",
        content=f"Manually {action}: {entry.content}",
        details={
            "source_entry_id": str(entry.id),
            "source_type": entry.entry_type,
            "is_evidence": entry.is_evidence,
        },
        created_by=current_user.id,
    ))

    await db.flush()

    return TimelineEntryRead(
        id=entry.id,
        incident_id=entry.incident_id,
        case_id=entry.case_id,
        entry_type=entry.entry_type,
        content=entry.content,
        details=entry.details,
        is_evidence=entry.is_evidence,
        created_by=_user_brief(entry.creator),
        created_at=entry.created_at,
    )


@router.post("/cases/{case_id}/timeline", response_model=TimelineEntryRead, status_code=201)
async def add_case_comment(
    case_id: UUID,
    body: TimelineCreate,
    current_user: User = Depends(get_current_user),
    _: dict = Depends(require_permission("timeline", "create")),
    db: AsyncSession = Depends(get_db),
):
    entry = TimelineEntry(
        case_id=case_id,
        entry_type=body.entry_type,
        content=body.content,
        details=body.details,
        created_by=current_user.id,
    )
    db.add(entry)
    await db.flush()

    return TimelineEntryRead(
        id=entry.id,
        incident_id=entry.incident_id,
        case_id=entry.case_id,
        entry_type=entry.entry_type,
        content=entry.content,
        details=entry.details,
        is_evidence=entry.is_evidence,
        created_by=UserBrief(
            id=current_user.id,
            username=current_user.username,
            display_name=current_user.display_name,
        ),
        created_at=entry.created_at,
    )


@router.post("/cases/{case_id}/timeline/{entry_id}/evidence", response_model=TimelineEntryRead)
async def toggle_case_timeline_evidence(
    case_id: UUID,
    entry_id: UUID,
    current_user: User = Depends(get_current_user),
    _: dict = Depends(require_permission("timeline", "create")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(TimelineEntry)
        .options(selectinload(TimelineEntry.creator))
        .where(TimelineEntry.id == entry_id, TimelineEntry.case_id == case_id)
    )
    entry = result.scalar_one_or_none()
    if not entry:
        raise HTTPException(status_code=404, detail="Timeline entry not found")

    entry.is_evidence = not entry.is_evidence

    if entry.details and entry.details.get("note_id"):
        note_result = await db.execute(
            select(CaseNote).where(CaseNote.id == UUID(entry.details["note_id"]))
        )
        linked_note = note_result.scalar_one_or_none()
        if linked_note:
            linked_note.is_evidence = entry.is_evidence

    # Also toggle linked execution if present
    if entry.details and entry.details.get("execution_id"):
        exec_result = await db.execute(
            select(ExecutionLog).where(ExecutionLog.id == UUID(entry.details["execution_id"]))
        )
        linked_exec = exec_result.scalar_one_or_none()
        if linked_exec:
            linked_exec.is_evidence = entry.is_evidence

    # Create audit trail entry
    action = "marked as evidence" if entry.is_evidence else "unmarked as evidence"
    db.add(TimelineEntry(
        case_id=case_id,
        entry_type="evidence_marked",
        content=f"Manually {action}: {entry.content}",
        details={
            "source_entry_id": str(entry.id),
            "source_type": entry.entry_type,
            "is_evidence": entry.is_evidence,
        },
        created_by=current_user.id,
    ))

    await db.flush()

    return TimelineEntryRead(
        id=entry.id,
        incident_id=entry.incident_id,
        case_id=entry.case_id,
        entry_type=entry.entry_type,
        content=entry.content,
        details=entry.details,
        is_evidence=entry.is_evidence,
        created_by=_user_brief(entry.creator),
        created_at=entry.created_at,
    )


@router.get("/cases/{case_id}/timeline", response_model=list[TimelineEntryRead])
async def get_case_timeline(
    case_id: UUID,
    limit: int = Query(50, ge=1, le=200),
    _: dict = Depends(require_permission("timeline", "read")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(TimelineEntry)
        .options(selectinload(TimelineEntry.creator))
        .where(TimelineEntry.case_id == case_id)
        .order_by(TimelineEntry.created_at.desc())
        .limit(limit)
    )
    entries = result.scalars().all()
    return [
        TimelineEntryRead(
            id=e.id,
            incident_id=e.incident_id,
            case_id=e.case_id,
            entry_type=e.entry_type,
            content=e.content,
            details=e.details,
            is_evidence=e.is_evidence,
            created_by=_user_brief(e.creator),
            created_at=e.created_at,
        )
        for e in entries
    ]

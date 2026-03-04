"""Incident note CRUD endpoints."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from soas_backend.api.deps import get_current_user, require_permission
from soas_backend.database import get_db
from soas_backend.models.user import User
from soas_backend.services.incident_note_service import IncidentNoteService
from soas_shared.schemas.incident_note import IncidentNoteCreate, IncidentNoteRead, IncidentNoteUpdate
from soas_shared.schemas.user import UserBrief

router = APIRouter(tags=["incident-notes"])


def _user_brief(user) -> UserBrief | None:
    if user is None:
        return None
    return UserBrief(id=user.id, username=user.username, display_name=user.display_name)


def _note_to_read(note) -> IncidentNoteRead:
    return IncidentNoteRead(
        id=note.id,
        incident_id=note.incident_id,
        content=note.content,
        is_evidence=note.is_evidence,
        created_by=_user_brief(note.creator),
        updated_by=_user_brief(note.updater),
        created_at=note.created_at,
        updated_at=note.updated_at,
    )


@router.get("/incidents/{incident_id}/notes", response_model=list[IncidentNoteRead])
async def list_incident_notes(
    incident_id: UUID,
    _: dict = Depends(require_permission("incident_note", "read")),
    db: AsyncSession = Depends(get_db),
):
    svc = IncidentNoteService(db)
    notes = await svc.list_notes(incident_id)
    return [_note_to_read(n) for n in notes]


@router.post(
    "/incidents/{incident_id}/notes",
    response_model=IncidentNoteRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_incident_note(
    incident_id: UUID,
    body: IncidentNoteCreate,
    current_user: User = Depends(get_current_user),
    _: dict = Depends(require_permission("incident_note", "create")),
    db: AsyncSession = Depends(get_db),
):
    svc = IncidentNoteService(db)
    note = await svc.create(
        incident_id=incident_id,
        content=body.content,
        created_by=current_user.id,
    )
    return _note_to_read(note)


@router.patch("/incidents/{incident_id}/notes/{note_id}", response_model=IncidentNoteRead)
async def update_incident_note(
    incident_id: UUID,
    note_id: UUID,
    body: IncidentNoteUpdate,
    current_user: User = Depends(get_current_user),
    _: dict = Depends(require_permission("incident_note", "update")),
    db: AsyncSession = Depends(get_db),
):
    svc = IncidentNoteService(db)
    note = await svc.get(note_id)
    if not note or note.incident_id != incident_id:
        raise HTTPException(status_code=404, detail="Note not found")

    update_fields = body.model_dump(exclude_unset=True)
    note = await svc.update(note_id, updated_by=current_user.id, **update_fields)
    return _note_to_read(note)


@router.delete(
    "/incidents/{incident_id}/notes/{note_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_incident_note(
    incident_id: UUID,
    note_id: UUID,
    _: dict = Depends(require_permission("incident_note", "delete")),
    db: AsyncSession = Depends(get_db),
):
    svc = IncidentNoteService(db)
    note = await svc.get(note_id)
    if not note or note.incident_id != incident_id:
        raise HTTPException(status_code=404, detail="Note not found")
    await svc.delete(note_id)
    return None


@router.post("/incidents/{incident_id}/notes/{note_id}/evidence", response_model=IncidentNoteRead)
async def toggle_note_evidence(
    incident_id: UUID,
    note_id: UUID,
    _: dict = Depends(require_permission("incident_note", "update")),
    db: AsyncSession = Depends(get_db),
):
    svc = IncidentNoteService(db)
    note = await svc.get(note_id)
    if not note or note.incident_id != incident_id:
        raise HTTPException(status_code=404, detail="Note not found")

    note = await svc.toggle_evidence(note_id)
    return _note_to_read(note)

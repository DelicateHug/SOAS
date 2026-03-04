"""Case note CRUD endpoints."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from soas_backend.api.deps import get_current_user, require_permission
from soas_backend.database import get_db
from soas_backend.models.user import User
from soas_backend.services.case_note_service import CaseNoteService
from soas_shared.schemas.case_note import CaseNoteCreate, CaseNoteRead, CaseNoteUpdate
from soas_shared.schemas.user import UserBrief

router = APIRouter(tags=["case-notes"])


def _user_brief(user) -> UserBrief | None:
    if user is None:
        return None
    return UserBrief(id=user.id, username=user.username, display_name=user.display_name)


def _note_to_read(note) -> CaseNoteRead:
    return CaseNoteRead(
        id=note.id,
        case_id=note.case_id,
        content=note.content,
        is_evidence=note.is_evidence,
        created_by=_user_brief(note.creator),
        updated_by=_user_brief(note.updater),
        created_at=note.created_at,
        updated_at=note.updated_at,
    )


@router.get("/cases/{case_id}/notes", response_model=list[CaseNoteRead])
async def list_case_notes(
    case_id: UUID,
    _: dict = Depends(require_permission("case_note", "read")),
    db: AsyncSession = Depends(get_db),
):
    svc = CaseNoteService(db)
    notes = await svc.list_notes(case_id)
    return [_note_to_read(n) for n in notes]


@router.post(
    "/cases/{case_id}/notes",
    response_model=CaseNoteRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_case_note(
    case_id: UUID,
    body: CaseNoteCreate,
    current_user: User = Depends(get_current_user),
    _: dict = Depends(require_permission("case_note", "create")),
    db: AsyncSession = Depends(get_db),
):
    svc = CaseNoteService(db)
    note = await svc.create(
        case_id=case_id,
        content=body.content,
        created_by=current_user.id,
    )
    return _note_to_read(note)


@router.patch("/cases/{case_id}/notes/{note_id}", response_model=CaseNoteRead)
async def update_case_note(
    case_id: UUID,
    note_id: UUID,
    body: CaseNoteUpdate,
    current_user: User = Depends(get_current_user),
    _: dict = Depends(require_permission("case_note", "update")),
    db: AsyncSession = Depends(get_db),
):
    svc = CaseNoteService(db)
    note = await svc.get(note_id)
    if not note or note.case_id != case_id:
        raise HTTPException(status_code=404, detail="Note not found")

    update_fields = body.model_dump(exclude_unset=True)
    note = await svc.update(note_id, updated_by=current_user.id, **update_fields)
    return _note_to_read(note)


@router.delete(
    "/cases/{case_id}/notes/{note_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_case_note(
    case_id: UUID,
    note_id: UUID,
    _: dict = Depends(require_permission("case_note", "delete")),
    db: AsyncSession = Depends(get_db),
):
    svc = CaseNoteService(db)
    note = await svc.get(note_id)
    if not note or note.case_id != case_id:
        raise HTTPException(status_code=404, detail="Note not found")
    await svc.delete(note_id)
    return None


@router.post("/cases/{case_id}/notes/{note_id}/evidence", response_model=CaseNoteRead)
async def toggle_note_evidence(
    case_id: UUID,
    note_id: UUID,
    _: dict = Depends(require_permission("case_note", "update")),
    db: AsyncSession = Depends(get_db),
):
    svc = CaseNoteService(db)
    note = await svc.get(note_id)
    if not note or note.case_id != case_id:
        raise HTTPException(status_code=404, detail="Note not found")

    note = await svc.toggle_evidence(note_id)
    return _note_to_read(note)

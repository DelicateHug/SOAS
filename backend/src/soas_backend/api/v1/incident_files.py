"""Incident file upload/download endpoints."""

from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from soas_backend.api.deps import get_current_user, get_db, require_permission
from soas_backend.models.timeline import TimelineEntry
from soas_backend.models.user import User
from soas_backend.services.app_setting_service import AppSettingService
from soas_backend.services.incident_file_service import IncidentFileService
from soas_shared.schemas.incident_file import IncidentFileRead
from soas_shared.schemas.user import UserBrief

router = APIRouter(tags=["incident-files"])

MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB

PRIVILEGED_DELETE_ROLES = {"admin", "soc_manager"}


def _user_brief(user) -> UserBrief | None:
    if user is None:
        return None
    return UserBrief(id=user.id, username=user.username, display_name=user.display_name)


def _can_delete(file_uploaded_by: UUID, current_user_id: UUID, jwt_roles: list[str]) -> bool:
    """Check if the current user can delete this file."""
    is_owner = file_uploaded_by == current_user_id
    is_privileged = bool(PRIVILEGED_DELETE_ROLES & set(jwt_roles))
    return is_owner or is_privileged


def _file_to_read(
    f,
    *,
    current_user_id: UUID | None = None,
    jwt_roles: list[str] | None = None,
) -> IncidentFileRead:
    can_del = False
    if current_user_id is not None and jwt_roles is not None:
        can_del = _can_delete(f.uploaded_by, current_user_id, jwt_roles)
    return IncidentFileRead(
        id=f.id,
        incident_id=f.incident_id,
        filename=f.filename,
        content_type=f.content_type,
        file_size=f.file_size,
        description=f.description,
        is_evidence=f.is_evidence,
        uploaded_by=_user_brief(f.uploader),
        created_at=f.created_at,
        expires_at=f.expires_at,
        can_delete=can_del,
    )


@router.get("/incidents/{incident_id}/files", response_model=list[IncidentFileRead])
async def list_incident_files(
    incident_id: UUID,
    current_user: User = Depends(get_current_user),
    payload: dict = Depends(require_permission("incident_file", "read")),
    db: AsyncSession = Depends(get_db),
):
    svc = IncidentFileService(db)
    files = await svc.list_files(incident_id)
    jwt_roles = payload.get("roles", [])
    return [
        _file_to_read(f, current_user_id=current_user.id, jwt_roles=jwt_roles)
        for f in files
    ]


@router.post(
    "/incidents/{incident_id}/files",
    response_model=IncidentFileRead,
    status_code=status.HTTP_201_CREATED,
)
async def upload_incident_file(
    incident_id: UUID,
    file: UploadFile = File(...),
    description: str | None = Form(None),
    current_user: User = Depends(get_current_user),
    payload: dict = Depends(require_permission("incident_file", "upload")),
    db: AsyncSession = Depends(get_db),
):
    contents = await file.read()
    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds maximum size of {MAX_FILE_SIZE // (1024*1024)} MB",
        )

    setting_svc = AppSettingService(db)
    ttl_days = await setting_svc.get_file_ttl_days()

    svc = IncidentFileService(db)
    record = await svc.upload(
        incident_id=incident_id,
        filename=file.filename or "unnamed",
        content_type=file.content_type or "application/octet-stream",
        file_bytes=contents,
        uploaded_by=current_user.id,
        description=description,
        ttl_days=ttl_days,
    )

    db.add(TimelineEntry(
        incident_id=incident_id,
        entry_type="evidence",
        content=f"File uploaded: {record.filename}",
        details={"file_id": str(record.id), "filename": record.filename, "content_type": record.content_type},
        created_by=current_user.id,
    ))
    await db.flush()

    jwt_roles = payload.get("roles", [])
    return _file_to_read(record, current_user_id=current_user.id, jwt_roles=jwt_roles)


@router.get("/incidents/{incident_id}/files/{file_id}/download")
async def download_incident_file(
    incident_id: UUID,
    file_id: UUID,
    _: dict = Depends(require_permission("incident_file", "read")),
    db: AsyncSession = Depends(get_db),
):
    svc = IncidentFileService(db)
    record = await svc.get(file_id)
    if not record or record.incident_id != incident_id:
        raise HTTPException(status_code=404, detail="File not found")

    file_path = svc.get_file_path(record)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found on disk")

    return FileResponse(
        path=str(file_path),
        filename=record.filename,
        media_type=record.content_type,
    )


@router.delete(
    "/incidents/{incident_id}/files/{file_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_incident_file(
    incident_id: UUID,
    file_id: UUID,
    current_user: User = Depends(get_current_user),
    payload: dict = Depends(require_permission("incident_file", "delete")),
    db: AsyncSession = Depends(get_db),
):
    svc = IncidentFileService(db)
    record = await svc.get(file_id)
    if not record or record.incident_id != incident_id:
        raise HTTPException(status_code=404, detail="File not found")

    jwt_roles: list[str] = payload.get("roles", [])
    if not _can_delete(record.uploaded_by, current_user.id, jwt_roles):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the uploader, admin, or soc_manager can delete files",
        )

    await svc.delete(file_id)
    return None


@router.post("/incidents/{incident_id}/files/{file_id}/evidence", response_model=IncidentFileRead)
async def toggle_file_evidence(
    incident_id: UUID,
    file_id: UUID,
    current_user: User = Depends(get_current_user),
    payload: dict = Depends(require_permission("incident_file", "read")),
    db: AsyncSession = Depends(get_db),
):
    svc = IncidentFileService(db)
    record = await svc.get(file_id)
    if not record or record.incident_id != incident_id:
        raise HTTPException(status_code=404, detail="File not found")

    record = await svc.toggle_evidence(file_id)

    action = "marked as evidence" if record.is_evidence else "unmarked as evidence"
    db.add(TimelineEntry(
        incident_id=incident_id,
        entry_type="evidence",
        content=f"File {action}: {record.filename}",
        details={"file_id": str(record.id), "filename": record.filename, "is_evidence": record.is_evidence},
        created_by=current_user.id,
    ))
    await db.flush()

    jwt_roles = payload.get("roles", [])
    return _file_to_read(record, current_user_id=current_user.id, jwt_roles=jwt_roles)

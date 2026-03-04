"""Case CRUD endpoints."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from soas_backend.api.deps import get_current_user, require_permission
from soas_backend.database import get_db
from soas_backend.models.user import User
from soas_backend.services.case_service import CaseService
from soas_shared.schemas.case import (
    CaseCreate,
    CaseGroupedItem,
    CaseLinkIncident,
    CaseListItem,
    CaseRead,
    CaseUpdate,
)
from soas_shared.schemas.common import PaginatedResponse, PaginationMeta
from soas_shared.schemas.incident import IncidentListItem
from soas_shared.schemas.user import UserBrief

router = APIRouter(prefix="/cases", tags=["cases"])


def _user_brief(user) -> UserBrief | None:
    if user is None:
        return None
    return UserBrief(id=user.id, username=user.username, display_name=user.display_name)


@router.get("", response_model=PaginatedResponse[CaseListItem])
async def list_cases(
    case_status: str | None = Query(None, alias="status"),
    priority: int | None = Query(None, ge=1, le=5),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=1, le=100),
    _: dict = Depends(require_permission("case", "read")),
    db: AsyncSession = Depends(get_db),
):
    svc = CaseService(db)
    cases, total = await svc.list_cases(case_status, page, per_page, priority=priority)

    return PaginatedResponse(
        data=[
            CaseListItem(
                id=c.id,
                title=c.title,
                status=c.status,
                priority=c.priority,
                lead=_user_brief(c.lead),
                created_by=_user_brief(c.creator),
                tags=c.tags or [],
                incident_count=len(c.case_incidents),
                created_at=c.created_at,
                updated_at=c.updated_at,
            )
            for c in cases
        ],
        meta=PaginationMeta(
            total=total,
            page=page,
            per_page=per_page,
            total_pages=(total + per_page - 1) // per_page if total else 0,
        ),
    )


@router.get("/grouped", response_model=PaginatedResponse[CaseGroupedItem])
async def list_cases_grouped(
    case_status: str | None = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
    _: dict = Depends(require_permission("case", "read")),
    db: AsyncSession = Depends(get_db),
):
    """Return groups (cases) with their nested incidents."""
    svc = CaseService(db)
    cases, total = await svc.list_cases_with_incidents(case_status, page, per_page)

    return PaginatedResponse(
        data=[
            CaseGroupedItem(
                id=c.id,
                title=c.title,
                description=c.description,
                status=c.status,
                priority=c.priority,
                lead=_user_brief(c.lead),
                created_by=_user_brief(c.creator),
                tags=c.tags or [],
                created_at=c.created_at,
                updated_at=c.updated_at,
                incidents=[
                    IncidentListItem(
                        id=ci.incident.id,
                        title=ci.incident.title,
                        severity=ci.incident.severity,
                        status=ci.incident.status,
                        lead=_user_brief(ci.incident.lead),
                        created_by=_user_brief(ci.incident.creator),
                        detected_at=ci.incident.detected_at,
                        tags=ci.incident.tags or [],
                        created_at=ci.incident.created_at,
                        updated_at=ci.incident.updated_at,
                    )
                    for ci in c.case_incidents
                ],
            )
            for c in cases
        ],
        meta=PaginationMeta(
            total=total,
            page=page,
            per_page=per_page,
            total_pages=(total + per_page - 1) // per_page if total else 0,
        ),
    )


@router.post("", response_model=CaseRead, status_code=status.HTTP_201_CREATED)
async def create_case(
    body: CaseCreate,
    current_user: User = Depends(get_current_user),
    _: dict = Depends(require_permission("case", "create")),
    db: AsyncSession = Depends(get_db),
):
    svc = CaseService(db)
    case = await svc.create(
        title=body.title,
        created_by=current_user.id,
        description=body.description,
        priority=body.priority,
        tags=body.tags,
        metadata=body.metadata,
    )
    case = await svc.get(case.id)
    return CaseRead(
        id=case.id,
        title=case.title,
        description=case.description,
        status=case.status,
        priority=case.priority,
        lead=_user_brief(case.lead),
        created_by=_user_brief(case.creator),
        closed_at=case.closed_at,
        tags=case.tags or [],
        metadata=case.metadata_,
        incident_count=len(case.case_incidents),
        created_at=case.created_at,
        updated_at=case.updated_at,
    )


@router.get("/{case_id}", response_model=CaseRead)
async def get_case(
    case_id: UUID,
    _: dict = Depends(require_permission("case", "read")),
    db: AsyncSession = Depends(get_db),
):
    svc = CaseService(db)
    case = await svc.get_with_incidents(case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    return CaseRead(
        id=case.id,
        title=case.title,
        description=case.description,
        status=case.status,
        priority=case.priority,
        lead=_user_brief(case.lead),
        created_by=_user_brief(case.creator),
        closed_at=case.closed_at,
        tags=case.tags or [],
        metadata=case.metadata_,
        incident_count=len(case.case_incidents),
        incidents=[
            IncidentListItem(
                id=ci.incident.id,
                title=ci.incident.title,
                severity=ci.incident.severity,
                status=ci.incident.status,
                lead=_user_brief(ci.incident.lead),
                created_by=_user_brief(ci.incident.creator),
                detected_at=ci.incident.detected_at,
                tags=ci.incident.tags or [],
                created_at=ci.incident.created_at,
                updated_at=ci.incident.updated_at,
            )
            for ci in case.case_incidents
        ],
        created_at=case.created_at,
        updated_at=case.updated_at,
    )


@router.patch("/{case_id}", response_model=CaseRead)
async def update_case(
    case_id: UUID,
    body: CaseUpdate,
    current_user: User = Depends(get_current_user),
    _: dict = Depends(require_permission("case", "update")),
    db: AsyncSession = Depends(get_db),
):
    svc = CaseService(db)

    kwargs: dict = {"user_id": current_user.id}
    provided = body.model_fields_set
    if "title" in provided:
        kwargs["title"] = body.title
    if "description" in provided:
        kwargs["description"] = body.description
    if "status" in provided:
        kwargs["status"] = body.status.value
        kwargs["cascade_status"] = body.cascade_status
    if "priority" in provided:
        kwargs["priority"] = body.priority
    if "lead_id" in provided:
        kwargs["lead_id"] = body.lead_id
    if "tags" in provided:
        kwargs["tags"] = body.tags
    if "metadata" in provided:
        kwargs["metadata"] = body.metadata

    try:
        await svc.update(case_id, **kwargs)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    case = await svc.get_with_incidents(case_id)
    return CaseRead(
        id=case.id,
        title=case.title,
        description=case.description,
        status=case.status,
        priority=case.priority,
        lead=_user_brief(case.lead),
        created_by=_user_brief(case.creator),
        closed_at=case.closed_at,
        tags=case.tags or [],
        metadata=case.metadata_,
        incident_count=len(case.case_incidents),
        incidents=[
            IncidentListItem(
                id=ci.incident.id,
                title=ci.incident.title,
                severity=ci.incident.severity,
                status=ci.incident.status,
                lead=_user_brief(ci.incident.lead),
                created_by=_user_brief(ci.incident.creator),
                detected_at=ci.incident.detected_at,
                tags=ci.incident.tags or [],
                created_at=ci.incident.created_at,
                updated_at=ci.incident.updated_at,
            )
            for ci in case.case_incidents
        ],
        created_at=case.created_at,
        updated_at=case.updated_at,
    )


@router.post("/{case_id}/incidents", status_code=status.HTTP_201_CREATED)
async def link_incident(
    case_id: UUID,
    body: CaseLinkIncident,
    current_user: User = Depends(get_current_user),
    _: dict = Depends(require_permission("case", "update")),
    db: AsyncSession = Depends(get_db),
):
    svc = CaseService(db)
    await svc.link_incident(case_id, body.incident_id, current_user.id)
    return {"message": "Incident linked to case"}


@router.delete(
    "/{case_id}/incidents/{incident_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def unlink_incident(
    case_id: UUID,
    incident_id: UUID,
    _: dict = Depends(require_permission("case", "update")),
    db: AsyncSession = Depends(get_db),
):
    svc = CaseService(db)
    removed = await svc.unlink_incident(case_id, incident_id)
    if not removed:
        raise HTTPException(status_code=404, detail="Link not found")

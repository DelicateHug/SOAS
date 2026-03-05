"""Incident variable definition endpoints - registry of variable names for dropdown selection."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from soas_backend.api.deps import get_current_user, require_permission
from soas_backend.database import get_db
from soas_backend.models.user import User
from soas_backend.services.incident_variable_service import IncidentVariableService
from soas_shared.schemas.common import PaginatedResponse, PaginationMeta
from soas_shared.schemas.incident_variable import (
    IncidentVariableCreate,
    IncidentVariableRead,
    IncidentVariableUpdate,
)

router = APIRouter(prefix="/incident-variables", tags=["incident-variables"])


def _to_read(v) -> IncidentVariableRead:
    return IncidentVariableRead(
        id=v.id,
        name=v.name,
        description=v.description,
        default_enabled=v.default_enabled,
        sensitive=v.sensitive,
        created_by=v.created_by,
        created_at=v.created_at,
        updated_at=v.updated_at,
    )


@router.get("", response_model=PaginatedResponse[IncidentVariableRead])
async def list_variables(
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=1, le=100),
    _: dict = Depends(require_permission("incident_variable", "read")),
    db: AsyncSession = Depends(get_db),
):
    svc = IncidentVariableService(db)
    variables, total = await svc.list_variables(page, per_page)
    return PaginatedResponse(
        data=[_to_read(v) for v in variables],
        meta=PaginationMeta(
            total=total,
            page=page,
            per_page=per_page,
            total_pages=(total + per_page - 1) // per_page if total else 0,
        ),
    )


@router.post("", response_model=IncidentVariableRead, status_code=201)
async def create_variable(
    body: IncidentVariableCreate,
    current_user: User = Depends(get_current_user),
    _: dict = Depends(require_permission("incident_variable", "create")),
    db: AsyncSession = Depends(get_db),
):
    svc = IncidentVariableService(db)

    existing = await svc.get_by_name(body.name)
    if existing:
        raise HTTPException(status_code=409, detail=f"Variable '{body.name}' already exists")

    variable = await svc.create(
        name=body.name,
        description=body.description,
        default_enabled=body.default_enabled,
        sensitive=body.sensitive,
        created_by=current_user.id,
    )
    return _to_read(variable)


@router.patch("/{variable_id}", response_model=IncidentVariableRead)
async def update_variable(
    variable_id: UUID,
    body: IncidentVariableUpdate,
    _: dict = Depends(require_permission("incident_variable", "update")),
    db: AsyncSession = Depends(get_db),
):
    svc = IncidentVariableService(db)

    kwargs: dict = {}
    if body.description is not None:
        kwargs["description"] = body.description
    if body.default_enabled is not None:
        kwargs["default_enabled"] = body.default_enabled
    if body.sensitive is not None:
        kwargs["sensitive"] = body.sensitive

    variable = await svc.update(variable_id, **kwargs)
    if not variable:
        raise HTTPException(status_code=404, detail="Variable not found")
    return _to_read(variable)


@router.delete("/{variable_id}", status_code=204)
async def delete_variable(
    variable_id: UUID,
    _: dict = Depends(require_permission("incident_variable", "delete")),
    db: AsyncSession = Depends(get_db),
):
    svc = IncidentVariableService(db)
    deleted = await svc.delete_variable(variable_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Variable not found")

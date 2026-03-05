"""SOAS application-level variable endpoints."""

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from sqlalchemy import select

from soas_backend.api.deps import get_current_user, require_permission
from soas_backend.database import get_db
from soas_backend.models.role import UserRole
from soas_backend.models.user import User
from soas_backend.services.soas_variable_service import SOASVariableService
from soas_backend.services.user_secret_service import UserSecretService
from soas_shared.schemas.common import PaginatedResponse, PaginationMeta
from soas_shared.schemas.soas_variable import (
    SOASVariableCreate,
    SOASVariablePermissionEntry,
    SOASVariablePermissionUpdate,
    SOASVariableRead,
    SOASVariableUpdate,
)

router = APIRouter(prefix="/soas-variables", tags=["soas-variables"])


def _to_read(v, mask_secret: bool = False) -> SOASVariableRead:
    return SOASVariableRead(
        id=v.id,
        name=v.name,
        description=v.description,
        value="***" if (v.is_secret and mask_secret) else v.value,
        is_secret=v.is_secret,
        created_by=v.created_by,
        updated_by=v.updated_by,
        created_at=v.created_at,
        updated_at=v.updated_at,
    )


@router.get("", response_model=PaginatedResponse[SOASVariableRead])
async def list_variables(
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=1, le=100),
    include_shared: bool = Query(True),
    current_user: User = Depends(get_current_user),
    _: dict = Depends(require_permission("soas_variable", "read")),
    db: AsyncSession = Depends(get_db),
):
    svc = SOASVariableService(db)
    variables, total = await svc.list_variables(page, per_page)
    data = [_to_read(v) for v in variables]

    # Append shared secrets visible to current user's roles
    if include_shared:
        role_result = await db.execute(
            select(UserRole.role_id).where(UserRole.user_id == current_user.id)
        )
        role_ids = [row[0] for row in role_result.all()]
        if role_ids:
            secret_svc = UserSecretService(db)
            shared = await secret_svc.get_shared_for_roles(role_ids)
            for item in shared:
                data.append(SOASVariableRead(
                    id=item["id"],
                    name=item["name"],
                    description=item["description"],
                    value=item["value"],
                    is_secret=item["sensitive"],
                    created_by=None,
                    created_at=datetime.min,
                    updated_at=datetime.min,
                    source="shared_secret",
                    owner_username=item["owner_username"],
                ))
            total += len(shared)

    return PaginatedResponse(
        data=data,
        meta=PaginationMeta(
            total=total,
            page=page,
            per_page=per_page,
            total_pages=(total + per_page - 1) // per_page if total else 0,
        ),
    )


@router.post("", response_model=SOASVariableRead, status_code=201)
async def create_variable(
    body: SOASVariableCreate,
    current_user: User = Depends(get_current_user),
    _: dict = Depends(require_permission("soas_variable", "create")),
    db: AsyncSession = Depends(get_db),
):
    svc = SOASVariableService(db)

    existing = await svc.get_by_name(body.name)
    if existing:
        raise HTTPException(status_code=409, detail=f"Variable '{body.name}' already exists")

    variable = await svc.create(
        name=body.name,
        value=body.value,
        description=body.description,
        is_secret=body.is_secret,
        created_by=current_user.id,
    )
    return _to_read(variable)


@router.get("/{variable_id}", response_model=SOASVariableRead)
async def get_variable(
    variable_id: UUID,
    _: dict = Depends(require_permission("soas_variable", "read")),
    db: AsyncSession = Depends(get_db),
):
    svc = SOASVariableService(db)
    variable = await svc.get(variable_id)
    if not variable:
        raise HTTPException(status_code=404, detail="Variable not found")
    return _to_read(variable)


@router.patch("/{variable_id}", response_model=SOASVariableRead)
async def update_variable(
    variable_id: UUID,
    body: SOASVariableUpdate,
    current_user: User = Depends(get_current_user),
    _: dict = Depends(require_permission("soas_variable", "update")),
    db: AsyncSession = Depends(get_db),
):
    svc = SOASVariableService(db)

    kwargs: dict = {"updated_by": current_user.id}
    if body.value is not None:
        kwargs["value"] = body.value
    if body.description is not None:
        kwargs["description"] = body.description
    if body.is_secret is not None:
        kwargs["is_secret"] = body.is_secret

    variable = await svc.update(variable_id, **kwargs)
    if not variable:
        raise HTTPException(status_code=404, detail="Variable not found")
    return _to_read(variable)


@router.delete("/{variable_id}", status_code=204)
async def delete_variable(
    variable_id: UUID,
    _: dict = Depends(require_permission("soas_variable", "delete")),
    db: AsyncSession = Depends(get_db),
):
    svc = SOASVariableService(db)
    deleted = await svc.delete_variable(variable_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Variable not found")


@router.get("/{variable_id}/permissions", response_model=list[SOASVariablePermissionEntry])
async def get_variable_permissions(
    variable_id: UUID,
    _: dict = Depends(require_permission("soas_variable", "read")),
    db: AsyncSession = Depends(get_db),
):
    svc = SOASVariableService(db)
    variable = await svc.get(variable_id)
    if not variable:
        raise HTTPException(status_code=404, detail="Variable not found")

    perms = await svc.get_permissions(variable_id)
    return [
        SOASVariablePermissionEntry(
            role_id=p.role_id,
            role_name=p.role.name if p.role else None,
            can_read=p.can_read,
            can_write=p.can_write,
        )
        for p in perms
    ]


@router.patch("/{variable_id}/permissions")
async def set_variable_permissions(
    variable_id: UUID,
    body: SOASVariablePermissionUpdate,
    current_user: User = Depends(get_current_user),
    _: dict = Depends(require_permission("soas_variable", "update")),
    db: AsyncSession = Depends(get_db),
):
    svc = SOASVariableService(db)
    variable = await svc.get(variable_id)
    if not variable:
        raise HTTPException(status_code=404, detail="Variable not found")

    await svc.set_permissions(
        variable_id,
        [p.model_dump() for p in body.permissions],
        granted_by=current_user.id,
    )
    return {"message": "Permissions updated"}

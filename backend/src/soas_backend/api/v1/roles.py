"""Role and permission management endpoints."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from soas_backend.api.deps import get_current_user, require_permission
from soas_backend.database import get_db
from soas_backend.models.user import User
from soas_backend.services.rbac_service import RBACService
from soas_shared.schemas.role import (
    PermissionRead,
    RoleCreate,
    RoleRead,
    RoleUpdate,
    UserRoleAssign,
)

router = APIRouter(prefix="/roles", tags=["roles"])


@router.get("", response_model=list[RoleRead])
async def list_roles(
    _: dict = Depends(require_permission("role", "read")),
    db: AsyncSession = Depends(get_db),
):
    rbac = RBACService(db)
    roles = await rbac.get_all_roles()
    return [
        RoleRead(
            id=r.id,
            name=r.name,
            display_name=r.display_name,
            description=r.description,
            is_system=r.is_system,
            created_at=r.created_at,
            updated_at=r.updated_at,
            permissions=[
                PermissionRead(
                    id=rp.permission.id,
                    resource=rp.permission.resource,
                    action=rp.permission.action,
                    description=rp.permission.description,
                )
                for rp in r.role_permissions
            ],
        )
        for r in roles
    ]


@router.get("/permissions", response_model=list[PermissionRead])
async def list_permissions(
    _: dict = Depends(require_permission("role", "read")),
    db: AsyncSession = Depends(get_db),
):
    rbac = RBACService(db)
    perms = await rbac.get_all_permissions()
    return [
        PermissionRead(
            id=p.id,
            resource=p.resource,
            action=p.action,
            description=p.description,
        )
        for p in perms
    ]


@router.post("", response_model=RoleRead, status_code=status.HTTP_201_CREATED)
async def create_role(
    body: RoleCreate,
    _: dict = Depends(require_permission("role", "create")),
    db: AsyncSession = Depends(get_db),
):
    rbac = RBACService(db)
    role = await rbac.create_role(
        name=body.name,
        display_name=body.display_name,
        description=body.description,
        permission_ids=body.permission_ids,
    )
    return RoleRead(
        id=role.id,
        name=role.name,
        display_name=role.display_name,
        description=role.description,
        is_system=role.is_system,
        created_at=role.created_at,
        updated_at=role.updated_at,
        permissions=[],
    )


@router.patch("/{role_id}", response_model=RoleRead)
async def update_role(
    role_id: UUID,
    body: RoleUpdate,
    _: dict = Depends(require_permission("role", "update")),
    db: AsyncSession = Depends(get_db),
):
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload
    from soas_backend.models.role import Role, RolePermission

    result = await db.execute(
        select(Role)
        .options(selectinload(Role.role_permissions).selectinload(RolePermission.permission))
        .where(Role.id == role_id)
    )
    role = result.scalar_one_or_none()
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")

    if role.is_system and body.display_name is None and body.permission_ids is None:
        raise HTTPException(status_code=400, detail="Cannot modify system role name")

    if body.display_name is not None:
        role.display_name = body.display_name
    if body.description is not None:
        role.description = body.description
    if body.permission_ids is not None:
        rbac = RBACService(db)
        await rbac.update_role_permissions(role_id, body.permission_ids)

    await db.flush()

    return RoleRead(
        id=role.id,
        name=role.name,
        display_name=role.display_name,
        description=role.description,
        is_system=role.is_system,
        created_at=role.created_at,
        updated_at=role.updated_at,
        permissions=[
            PermissionRead(
                id=rp.permission.id,
                resource=rp.permission.resource,
                action=rp.permission.action,
                description=rp.permission.description,
            )
            for rp in role.role_permissions
        ],
    )


@router.post("/users/{user_id}/roles", status_code=status.HTTP_201_CREATED)
async def assign_role(
    user_id: UUID,
    body: UserRoleAssign,
    current_user: User = Depends(get_current_user),
    _: dict = Depends(require_permission("role", "update")),
    db: AsyncSession = Depends(get_db),
):
    rbac = RBACService(db)
    await rbac.assign_role_to_user(user_id, body.role_id, assigned_by=current_user.id)
    return {"message": "Role assigned"}


@router.delete("/users/{user_id}/roles/{role_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_role(
    user_id: UUID,
    role_id: UUID,
    _: dict = Depends(require_permission("role", "update")),
    db: AsyncSession = Depends(get_db),
):
    rbac = RBACService(db)
    removed = await rbac.remove_role_from_user(user_id, role_id)
    if not removed:
        raise HTTPException(status_code=404, detail="Role assignment not found")

"""Role and permission management endpoints."""

import uuid
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from soas_backend.api.deps import get_current_user, require_permission
from soas_backend.database import get_db
from soas_backend.models.role import Role
from soas_backend.models.user import User
from soas_backend.services.change_request_service import ChangeRequestService
from soas_backend.services.rbac_service import RBACService
from soas_backend.services.audit import audit
from soas_shared.schemas.change_request import ChangeRequestDetail, UserBrief
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
@audit(
    "role.created",
    target_kind="role",
    extract_target=lambda r: getattr(r, "id", None),
    extract_label=lambda r: getattr(r, "name", None),
)
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


def _cr_to_detail(cr) -> ChangeRequestDetail:
    return ChangeRequestDetail(
        id=cr.id,
        entity_type=cr.entity_type,
        entity_id=cr.entity_id,
        action=cr.action,
        title=cr.title,
        status=cr.status,
        snapshot=cr.snapshot,
        diff_summary=cr.diff_summary,
        review_comment=cr.review_comment,
        git_branch=cr.git_branch,
        git_sha=cr.git_sha,
        target_tier=cr.target_tier,
        created_by=cr.created_by,
        creator=None,
        reviewed_by=cr.reviewed_by,
        reviewer=None,
        created_at=cr.created_at,
        updated_at=cr.updated_at,
        reviewed_at=cr.reviewed_at,
    )


@router.post("/users/{user_id}/roles", response_model=ChangeRequestDetail, status_code=status.HTTP_201_CREATED)
async def assign_role(
    user_id: UUID,
    body: UserRoleAssign,
    current_user: User = Depends(get_current_user),
    _: dict = Depends(require_permission("role", "update")),
    db: AsyncSession = Depends(get_db),
):
    role = (await db.execute(select(Role).where(Role.id == body.role_id))).scalar_one_or_none()
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
    target_user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")

    # Deterministic entity_id per (target_user, role) pair to allow one pending CR per slot
    entity_id = uuid.uuid5(uuid.NAMESPACE_URL, f"user_role:{user_id}:{body.role_id}")

    svc = ChangeRequestService(db)
    try:
        cr = await svc.upsert_draft(
            user_id=current_user.id,
            entity_type="user_role",
            entity_id=entity_id,
            action="create",
            title=f"Assign role '{role.display_name}' to {target_user.display_name}",
            snapshot={
                "user_id": str(user_id),
                "role_id": str(body.role_id),
                "role_name": role.name,
                "role_display_name": role.display_name,
                "target_username": target_user.username,
            },
            username=current_user.username,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return _cr_to_detail(cr)


@router.delete("/users/{user_id}/roles/{role_id}", response_model=ChangeRequestDetail)
async def remove_role(
    user_id: UUID,
    role_id: UUID,
    current_user: User = Depends(get_current_user),
    _: dict = Depends(require_permission("role", "update")),
    db: AsyncSession = Depends(get_db),
):
    role = (await db.execute(select(Role).where(Role.id == role_id))).scalar_one_or_none()
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
    target_user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")

    entity_id = uuid.uuid5(uuid.NAMESPACE_URL, f"user_role:{user_id}:{role_id}")

    svc = ChangeRequestService(db)
    try:
        cr = await svc.upsert_draft(
            user_id=current_user.id,
            entity_type="user_role",
            entity_id=entity_id,
            action="delete",
            title=f"Remove role '{role.display_name}' from {target_user.display_name}",
            snapshot={
                "user_id": str(user_id),
                "role_id": str(role_id),
                "role_name": role.name,
                "role_display_name": role.display_name,
                "target_username": target_user.username,
            },
            username=current_user.username,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return _cr_to_detail(cr)

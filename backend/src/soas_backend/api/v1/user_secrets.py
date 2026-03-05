"""Per-user secret endpoints with sharing support."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from soas_backend.api.deps import get_current_user, require_permission
from soas_backend.database import get_db
from soas_backend.models.role import UserRole
from soas_backend.models.user import User
from soas_backend.services.user_secret_service import UserSecretService
from soas_shared.schemas.common import PaginatedResponse, PaginationMeta
from soas_shared.schemas.user_secret import (
    SharedSecretPermissionRead,
    SharedSecretRead,
    UserSecretAdminRead,
    UserSecretCreate,
    UserSecretRead,
    UserSecretReadWithValue,
    UserSecretShareRequest,
    UserSecretUpdate,
)

router = APIRouter(prefix="/user-secrets", tags=["user-secrets"])


def _to_read(s) -> UserSecretRead:
    return UserSecretRead(
        id=s.id,
        name=s.name,
        description=s.description,
        sensitive=s.sensitive,
        is_shared=s.is_shared,
        created_at=s.created_at,
        updated_at=s.updated_at,
    )


# ---------------------------------------------------------------------------
# Admin endpoints (MUST be before /{secret_id} to avoid path conflicts)
# ---------------------------------------------------------------------------


@router.get("/admin/all", response_model=PaginatedResponse[UserSecretAdminRead])
async def admin_list_all_secrets(
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=1, le=100),
    _: dict = Depends(require_permission("user_secret", "admin_list")),
    db: AsyncSession = Depends(get_db),
):
    svc = UserSecretService(db)
    secrets, total = await svc.list_all_admin(page, per_page)
    return PaginatedResponse(
        data=[
            UserSecretAdminRead(
                id=s.id,
                user_id=s.user_id,
                username=s.owner.username if s.owner else None,
                name=s.name,
                description=s.description,
                sensitive=s.sensitive,
                is_shared=s.is_shared,
                created_at=s.created_at,
                updated_at=s.updated_at,
            )
            for s in secrets
        ],
        meta=PaginationMeta(
            total=total,
            page=page,
            per_page=per_page,
            total_pages=(total + per_page - 1) // per_page if total else 0,
        ),
    )


@router.delete("/admin/{secret_id}", status_code=204)
async def admin_delete_secret(
    secret_id: UUID,
    _: dict = Depends(require_permission("user_secret", "admin_delete")),
    db: AsyncSession = Depends(get_db),
):
    svc = UserSecretService(db)
    deleted = await svc.delete_secret(secret_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Secret not found")


# ---------------------------------------------------------------------------
# Shared secrets visible to current user's roles
# ---------------------------------------------------------------------------


@router.get("/shared", response_model=list[SharedSecretRead])
async def list_shared_secrets(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List shared secrets visible to the current user's roles."""
    result = await db.execute(
        select(UserRole.role_id).where(UserRole.user_id == current_user.id)
    )
    role_ids = [row[0] for row in result.all()]

    svc = UserSecretService(db)
    items = await svc.get_shared_for_roles(role_ids)
    return [
        SharedSecretRead(
            id=item["id"],
            name=item["name"],
            description=item["description"],
            sensitive=item["sensitive"],
            owner_username=item["owner_username"],
            value=item["value"],
        )
        for item in items
    ]


# ---------------------------------------------------------------------------
# User-facing endpoints (own secrets only)
# ---------------------------------------------------------------------------


@router.get("", response_model=PaginatedResponse[UserSecretRead])
async def list_my_secrets(
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = UserSecretService(db)
    secrets, total = await svc.list_for_user(current_user.id, page, per_page)
    return PaginatedResponse(
        data=[_to_read(s) for s in secrets],
        meta=PaginationMeta(
            total=total,
            page=page,
            per_page=per_page,
            total_pages=(total + per_page - 1) // per_page if total else 0,
        ),
    )


@router.post("", response_model=UserSecretRead, status_code=201)
async def create_secret(
    body: UserSecretCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = UserSecretService(db)
    existing = await svc.get_by_name_for_user(current_user.id, body.name)
    if existing:
        raise HTTPException(status_code=409, detail=f"Secret '{body.name}' already exists")

    secret = await svc.create(
        user_id=current_user.id,
        name=body.name,
        value=body.value,
        description=body.description,
        sensitive=body.sensitive,
    )
    return _to_read(secret)


@router.get("/{secret_id}", response_model=UserSecretRead)
async def get_secret(
    secret_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = UserSecretService(db)
    secret = await svc.get(secret_id)
    if not secret or secret.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Secret not found")
    return _to_read(secret)


@router.get("/{secret_id}/value", response_model=UserSecretReadWithValue)
async def get_secret_value(
    secret_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Explicitly retrieve the decrypted value. Only the owning user can call this."""
    svc = UserSecretService(db)
    secret = await svc.get(secret_id)
    if not secret or secret.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Secret not found")

    if secret.sensitive:
        raise HTTPException(
            status_code=403,
            detail="This secret is sensitive and its value cannot be retrieved",
        )

    return UserSecretReadWithValue(
        id=secret.id,
        name=secret.name,
        description=secret.description,
        sensitive=secret.sensitive,
        is_shared=secret.is_shared,
        created_at=secret.created_at,
        updated_at=secret.updated_at,
        value=await svc.decrypt_single(secret),
    )


@router.patch("/{secret_id}", response_model=UserSecretRead)
async def update_secret(
    secret_id: UUID,
    body: UserSecretUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = UserSecretService(db)
    secret = await svc.get(secret_id)
    if not secret or secret.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Secret not found")

    kwargs: dict = {}
    if body.value is not None:
        kwargs["value"] = body.value
    if body.description is not None:
        kwargs["description"] = body.description

    updated = await svc.update(secret_id, **kwargs)
    if not updated:
        raise HTTPException(status_code=404, detail="Secret not found")
    return _to_read(updated)


@router.delete("/{secret_id}", status_code=204)
async def delete_secret(
    secret_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = UserSecretService(db)
    secret = await svc.get(secret_id)
    if not secret or secret.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Secret not found")
    await svc.delete_secret(secret_id)


# ---------------------------------------------------------------------------
# Sharing endpoints
# ---------------------------------------------------------------------------


@router.post("/{secret_id}/share", status_code=200)
async def share_secret(
    secret_id: UUID,
    body: UserSecretShareRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Share a secret with specific roles."""
    svc = UserSecretService(db)
    secret = await svc.get(secret_id)
    if not secret or secret.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Secret not found")

    await svc.share_secret(secret_id, body.role_ids)
    return {"message": "Secret shared successfully"}


@router.delete("/{secret_id}/share", status_code=200)
async def unshare_secret(
    secret_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Remove sharing from a secret."""
    svc = UserSecretService(db)
    secret = await svc.get(secret_id)
    if not secret or secret.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Secret not found")

    await svc.unshare_secret(secret_id)
    return {"message": "Secret unshared successfully"}


@router.patch("/{secret_id}/share", status_code=200)
async def update_share(
    secret_id: UUID,
    body: UserSecretShareRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update which roles a shared secret is accessible to."""
    svc = UserSecretService(db)
    secret = await svc.get(secret_id)
    if not secret or secret.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Secret not found")

    if not secret.is_shared:
        raise HTTPException(status_code=400, detail="Secret is not shared. Use POST to share first.")

    await svc.update_share_permissions(secret_id, body.role_ids)
    return {"message": "Share permissions updated"}


@router.get("/{secret_id}/share", response_model=list[SharedSecretPermissionRead])
async def get_share_permissions(
    secret_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get current sharing roles for a secret."""
    svc = UserSecretService(db)
    secret = await svc.get(secret_id)
    if not secret or secret.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Secret not found")

    perms = await svc.get_share_permissions(secret_id)
    return [
        SharedSecretPermissionRead(
            role_id=p.role_id,
            role_name=p.role.name if p.role else None,
            can_read=p.can_read,
        )
        for p in perms
    ]

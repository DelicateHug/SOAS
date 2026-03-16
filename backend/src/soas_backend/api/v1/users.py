"""Admin user management endpoints."""

import secrets
import string
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from soas_backend.api.deps import get_current_user, require_permission
from soas_backend.auth.password import hash_password
from soas_backend.database import get_db
from soas_backend.models.role import UserRole
from soas_backend.models.user import User
from soas_shared.schemas.common import PaginatedResponse, PaginationMeta
from soas_shared.schemas.user import AdminPasswordResetResponse, AdminUserCreate, AdminUserCreateResponse, UserRead, UserUpdate


def _generate_secure_password(length: int = 20) -> str:
    """Generate a cryptographically secure random password."""
    alphabet = string.ascii_letters + string.digits + string.punctuation
    # Ensure at least one of each category
    password = [
        secrets.choice(string.ascii_uppercase),
        secrets.choice(string.ascii_lowercase),
        secrets.choice(string.digits),
        secrets.choice(string.punctuation),
    ]
    password += [secrets.choice(alphabet) for _ in range(length - 4)]
    # Shuffle to avoid predictable positions
    result = list(password)
    secrets.SystemRandom().shuffle(result)
    return "".join(result)

router = APIRouter(prefix="/admin/users", tags=["admin"])


@router.post("", response_model=AdminUserCreateResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    body: AdminUserCreate,
    _: dict = Depends(require_permission("user", "create")),
    db: AsyncSession = Depends(get_db),
):
    temporary_password = _generate_secure_password()
    user = User(
        username=body.username,
        email=body.email,
        display_name=body.display_name,
        password_hash=hash_password(temporary_password),
        must_reset_password=True,
    )
    db.add(user)
    try:
        await db.flush()
    except Exception as e:
        if "unique" in str(e).lower():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Username or email already exists",
            )
        raise

    return AdminUserCreateResponse(
        id=user.id,
        username=user.username,
        email=user.email,
        display_name=user.display_name,
        is_active=user.is_active,
        is_mfa_enabled=user.is_mfa_enabled,
        must_reset_password=True,
        temporary_password=temporary_password,
        created_at=user.created_at,
        updated_at=user.updated_at,
        roles=[],
    )


@router.get("", response_model=PaginatedResponse[UserRead])
async def list_users(
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=1, le=100),
    _: dict = Depends(require_permission("user", "read")),
    db: AsyncSession = Depends(get_db),
):
    query = select(User).options(
        selectinload(User.user_roles).selectinload(UserRole.role)
    )

    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0

    query = query.order_by(User.created_at.desc())
    query = query.offset((page - 1) * per_page).limit(per_page)

    result = await db.execute(query)
    users = result.scalars().all()

    return PaginatedResponse(
        data=[
            UserRead(
                id=u.id,
                username=u.username,
                email=u.email,
                display_name=u.display_name,
                is_active=u.is_active,
                is_mfa_enabled=u.is_mfa_enabled,
                must_reset_password=u.must_reset_password,
                last_login_at=u.last_login_at,
                created_at=u.created_at,
                updated_at=u.updated_at,
                roles=[ur.role.display_name for ur in u.user_roles],
            )
            for u in users
        ],
        meta=PaginationMeta(
            total=total,
            page=page,
            per_page=per_page,
            total_pages=(total + per_page - 1) // per_page if total else 0,
        ),
    )


@router.get("/{user_id}", response_model=UserRead)
async def get_user(
    user_id: UUID,
    _: dict = Depends(require_permission("user", "read")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(User)
        .options(selectinload(User.user_roles).selectinload(UserRole.role))
        .where(User.id == user_id)
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return UserRead(
        id=user.id,
        username=user.username,
        email=user.email,
        display_name=user.display_name,
        is_active=user.is_active,
        is_mfa_enabled=user.is_mfa_enabled,
        must_reset_password=user.must_reset_password,
        last_login_at=user.last_login_at,
        created_at=user.created_at,
        updated_at=user.updated_at,
        roles=[ur.role.display_name for ur in user.user_roles],
    )


@router.patch("/{user_id}", response_model=UserRead)
async def update_user(
    user_id: UUID,
    body: UserUpdate,
    _: dict = Depends(require_permission("user", "update")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(User)
        .options(selectinload(User.user_roles).selectinload(UserRole.role))
        .where(User.id == user_id)
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if body.display_name is not None:
        user.display_name = body.display_name
    if body.email is not None:
        user.email = body.email
    if body.is_active is not None:
        user.is_active = body.is_active

    await db.flush()

    return UserRead(
        id=user.id,
        username=user.username,
        email=user.email,
        display_name=user.display_name,
        is_active=user.is_active,
        is_mfa_enabled=user.is_mfa_enabled,
        must_reset_password=user.must_reset_password,
        last_login_at=user.last_login_at,
        created_at=user.created_at,
        updated_at=user.updated_at,
        roles=[ur.role.display_name for ur in user.user_roles],
    )


@router.post("/{user_id}/reset-password", response_model=AdminPasswordResetResponse)
async def reset_user_password(
    user_id: UUID,
    current_user: User = Depends(get_current_user),
    _: dict = Depends(require_permission("user", "update")),
    db: AsyncSession = Depends(get_db),
):
    """Admin resets a user's password, generating a new temporary one."""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="Use change-password to reset your own password")

    temporary_password = _generate_secure_password()
    user.password_hash = hash_password(temporary_password)
    user.must_reset_password = True
    await db.flush()

    return AdminPasswordResetResponse(temporary_password=temporary_password)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def deactivate_user(
    user_id: UUID,
    current_user: User = Depends(get_current_user),
    _: dict = Depends(require_permission("user", "delete")),
    db: AsyncSession = Depends(get_db),
):
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot deactivate yourself")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.is_active = False
    await db.flush()

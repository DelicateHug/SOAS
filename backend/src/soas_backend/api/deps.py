"""FastAPI dependency injection - auth, RBAC, and shared resources."""

from collections.abc import AsyncGenerator
from uuid import UUID

import redis.asyncio as aioredis
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from soas_backend.auth.jwt import decode_access_token
from soas_backend.config import settings
from soas_backend.database import get_db
from soas_backend.models.user import User

security = HTTPBearer()

# ---------------------------------------------------------------------------
# Redis
# ---------------------------------------------------------------------------

_redis_pool: aioredis.Redis | None = None


async def get_redis_pool() -> aioredis.Redis:
    """Return the shared Redis pool (for use outside of FastAPI dependency injection)."""
    global _redis_pool
    if _redis_pool is None:
        _redis_pool = aioredis.from_url(
            settings.redis_url,
            decode_responses=False,
            max_connections=50,
        )
    return _redis_pool


async def get_redis() -> AsyncGenerator[aioredis.Redis, None]:
    """Yield an async Redis connection from the shared connection pool."""
    yield await get_redis_pool()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Extract and validate the current user from the JWT token."""
    token = credentials.credentials
    payload = decode_access_token(token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )

    result = await db.execute(
        select(User)
        .options(selectinload(User.user_roles))
        .where(User.id == UUID(user_id))
    )
    user = result.scalar_one_or_none()

    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )

    return user


def require_permission(resource: str, action: str):
    """FastAPI dependency that enforces RBAC on a route.

    Usage:
        @router.get("/incidents", dependencies=[Depends(require_permission("incident", "read"))])
    """

    async def _check(
        credentials: HTTPAuthorizationCredentials = Depends(security),
    ) -> dict:
        token = credentials.credentials
        payload = decode_access_token(token)
        if payload is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token",
            )

        # Admin role bypasses all permission checks
        roles: list[str] = payload.get("roles", [])
        if "admin" in roles:
            return payload

        permissions: list[str] = payload.get("permissions", [])
        required = f"{resource}:{action}"

        if required not in permissions:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Missing permission: {required}",
            )

        return payload

    return _check


def require_role(*role_names: str):
    """FastAPI dependency that enforces role membership via JWT roles claim.

    Usage:
        @router.get("/settings", dependencies=[Depends(require_role("admin", "soc_manager"))])
    """

    async def _check(
        credentials: HTTPAuthorizationCredentials = Depends(security),
    ) -> dict:
        token = credentials.credentials
        payload = decode_access_token(token)
        if payload is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token",
            )

        jwt_roles: list[str] = payload.get("roles", [])
        if not set(jwt_roles) & set(role_names):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires one of roles: {', '.join(role_names)}",
            )

        return payload

    return _check


# ---------------------------------------------------------------------------
# Deployment mode guard
# ---------------------------------------------------------------------------


async def require_dev_mode(
    db: AsyncSession = Depends(get_db),
) -> None:
    """Block write operations when the platform is in production mode.

    In production mode, entities are read-only. Changes must come via git sync.
    Add this dependency to any route that modifies data.
    """
    from soas_backend.services.app_setting_service import AppSettingService
    svc = AppSettingService(db)
    mode = await svc.get_value("deployment_mode", "development")
    if mode == "production":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Platform is in production mode. Editing is restricted — changes must be applied via git sync.",
        )

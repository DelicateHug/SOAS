"""FastAPI dependency injection - auth, RBAC, and shared resources."""

from collections.abc import AsyncGenerator
from typing import Any
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
from soas_backend.models.role import Permission, Role, RolePermission, UserRole
from soas_backend.models.user import User

security = HTTPBearer()


# ---------------------------------------------------------------------------
# Service-token + JWT bearer resolver
# ---------------------------------------------------------------------------
#
# Routes accept both transient JWTs (interactive users) and long-lived service tokens
# (MCP clients, CI). To keep RBAC behaviour identical, service tokens are resolved into a
# synthetic JWT-payload-shaped dict containing the underlying user's roles and permissions
# at request time. This means a service token "inherits" exactly what its user has, so
# revoking a role on the user immediately tightens the token's powers — no JWT re-issue
# needed.
#
# Service tokens carry the prefix `sst_`. Anything else is treated as a JWT.


def _is_service_token(raw: str) -> bool:
    return bool(raw) and raw.startswith("sst_")


async def _payload_from_service_token(
    raw: str,
    db: AsyncSession,
) -> tuple[dict[str, Any], User] | None:
    """Validate a service token and return a (jwt-shaped payload, user) tuple."""
    # Local import keeps the deps module light and avoids a circular import at module load.
    from soas_backend.services.service_token_service import ServiceTokenService

    svc = ServiceTokenService(db)
    result = await svc.validate(raw)
    if result is None:
        return None
    token, user = result

    # Resolve roles + permissions for the underlying user.
    roles_q = await db.execute(
        select(Role.name)
        .join(UserRole, UserRole.role_id == Role.id)
        .where(UserRole.user_id == user.id)
    )
    role_names = [r[0] for r in roles_q.all()]

    perms_q = await db.execute(
        select(Permission.resource, Permission.action)
        .join(RolePermission, RolePermission.permission_id == Permission.id)
        .join(UserRole, UserRole.role_id == RolePermission.role_id)
        .where(UserRole.user_id == user.id)
    )
    permissions: set[str] = set()
    for resource, action in perms_q.all():
        permissions.add(f"{resource}:{action}")

    # If the token has explicit scopes, restrict permissions to that intersection.
    # Empty scopes = inherit everything. Admin role always wins (matches JWT behaviour).
    if token.scopes and "admin" not in role_names:
        permissions &= set(token.scopes)

    payload = {
        "sub": str(user.id),
        "username": user.username,
        "roles": role_names,
        "permissions": sorted(permissions),
        "teams": [],
        # Marker so downstream code (audit log, etc.) can tell this was a service token.
        "auth_type": "service_token",
        "token_id": str(token.id),
        "token_name": token.name,
    }

    # Touch usage timestamp out-of-band; never block the request on this.
    try:
        await svc.touch(token.id)
    except Exception:
        pass

    return payload, user

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
    """Extract and validate the current user from a JWT or service token."""
    raw = credentials.credentials

    if _is_service_token(raw):
        st_result = await _payload_from_service_token(raw, db)
        if st_result is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or revoked service token",
            )
        _payload, user = st_result
        return user

    payload = decode_access_token(raw)
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


async def _resolve_payload(
    credentials: HTTPAuthorizationCredentials,
    db: AsyncSession,
) -> dict[str, Any]:
    """Return a JWT-shaped payload for either a JWT or a service token, or raise 401."""
    raw = credentials.credentials

    if _is_service_token(raw):
        st_result = await _payload_from_service_token(raw, db)
        if st_result is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or revoked service token",
            )
        payload, _user = st_result
        return payload

    payload = decode_access_token(raw)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )
    return payload


async def get_user_teams(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]] | None:
    """Extract team memberships from JWT or service token.

    Returns list of team dicts for normal users, or None for admins (meaning all teams).
    """
    payload = await _resolve_payload(credentials, db)

    roles: list[str] = payload.get("roles", [])
    if "admin" in roles:
        return None  # Admin sees all teams

    return payload.get("teams", [])


def require_permission(resource: str, action: str):
    """FastAPI dependency that enforces RBAC on a route.

    Accepts both JWT bearer tokens (interactive users) and service tokens (`sst_…`),
    sharing the same permission model. Admin role bypasses all checks.
    """

    async def _check(
        credentials: HTTPAuthorizationCredentials = Depends(security),
        db: AsyncSession = Depends(get_db),
    ) -> dict:
        payload = await _resolve_payload(credentials, db)

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
    """FastAPI dependency that enforces role membership.

    Accepts both JWT and service tokens.
    """

    async def _check(
        credentials: HTTPAuthorizationCredentials = Depends(security),
        db: AsyncSession = Depends(get_db),
    ) -> dict:
        payload = await _resolve_payload(credentials, db)

        principal_roles: list[str] = payload.get("roles", [])
        if not set(principal_roles) & set(role_names):
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

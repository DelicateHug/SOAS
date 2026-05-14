"""FastAPI dependency injection - auth, RBAC, and shared resources."""

from collections.abc import AsyncGenerator
from typing import Any
from uuid import UUID

import redis.asyncio as aioredis
from fastapi import Depends, HTTPException, Request, status
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


async def _pick_default_team_id(
    db: AsyncSession,
    user_id: UUID,
    user_teams: list[dict[str, Any]] | None,
) -> UUID | None:
    """Pick the team to stamp on a newly-created entity when the request omits one.

    Order of preference:
      1. The user's first team membership (from JWT for non-admins).
      2. For admins (whose JWT says ``teams=None``), look up actual memberships
         in the DB so admin-created rows are also team-stamped.
      3. The team named ``default`` (created by the bootstrap CLI / migration 042).
    Returns ``None`` if no team exists at all — caller stores ``NULL``.
    """
    if user_teams:
        return UUID(user_teams[0]["id"])

    from soas_backend.models.team import Team, TeamMembership

    # Admin path: read membership directly
    rs = await db.execute(
        select(TeamMembership.team_id)
        .where(TeamMembership.user_id == user_id)
        .limit(1)
    )
    tid = rs.scalar_one_or_none()
    if tid is not None:
        return tid

    # Last resort: the named default team
    rs = await db.execute(select(Team.id).where(Team.name == "default"))
    return rs.scalar_one_or_none()


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


# ---------------------------------------------------------------------------
# Phase 12: hybrid auth (cert verifies transport, JWT identifies user, CAE re-check)
# ---------------------------------------------------------------------------


async def get_authenticated_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Resolve the calling user with three layers of evidence.

    1. JWT/service token (existing logic) — identifies the user.
    2. Continuous Access Evaluation (CAE) — re-checks revocation on
       every request. SOAS-issued JWTs hit a Redis revoked-jti set;
       OIDC users get a short-cached call back to Entra.
    3. Client cert via X-Forwarded-Client-Cert (when SOAS_TRUST_XFCC=1
       and auth_cert_login_enabled=true) — must match the JWT's `sub`.

    Routes that previously used `get_current_user` can switch to this
    dep at their own pace. The old dep stays in place.
    """
    from soas_backend.auth.cert import parse_xfcc_header, trust_enabled
    from soas_backend.services.app_setting_service import AppSettingService
    from soas_backend.services.cae_service import CAEService

    raw = credentials.credentials

    # JWT or service token → payload + user
    if _is_service_token(raw):
        st_result = await _payload_from_service_token(raw, db)
        if st_result is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or revoked service token",
            )
        payload, user = st_result
    else:
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

    # CAE — service tokens bypass; everyone else re-validates.
    if payload.get("auth_type") != "service_token":
        try:
            redis = await get_redis_pool()
            cae = CAEService(db, redis)
            result_cae = await cae.evaluate(payload)
            if not result_cae.valid:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail=f"Token revoked: {result_cae.reason or 'unknown'}",
                    headers={"X-Cae-Revoked": "true"},
                )
        except HTTPException:
            raise
        except Exception:
            # CAE failure mode is configured by auth_cae_strict
            settings_svc = AppSettingService(db)
            strict = (await settings_svc.get_value("auth_cae_strict", "true") or "true").lower() == "true"
            if strict:
                raise HTTPException(status_code=503, detail="CAE check unavailable")

    # Client-cert binding (only when the gateway is trusted)
    if trust_enabled():
        settings_svc = AppSettingService(db)
        cert_required = (await settings_svc.get_value("auth_cert_login_enabled", "true") or "true").lower() == "true"
        if cert_required:
            xfcc = request.headers.get("x-forwarded-client-cert")
            peers = parse_xfcc_header(xfcc)
            if not peers:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Client cert required",
                )
            # Look up the cert by fingerprint; must belong to the same user.
            from soas_backend.services.cert_authority_service import CertAuthorityService

            ca = CertAuthorityService(db)
            cert_row = None
            for p in peers:
                cert_row = await ca.lookup_by_fingerprint(p.fingerprint_sha256)
                if cert_row is not None:
                    break
            if cert_row is None or cert_row.revoked_at is not None:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Client cert not recognised or revoked",
                )
            if cert_row.user_id != user.id:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Client cert does not match JWT subject",
                )

    # Stash for downstream consumers (e.g. @audit decorator)
    try:
        request.state.user = user
        request.state.jwt_payload = payload
    except Exception:
        pass
    return user


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

"""FastAPI dependency injection - auth, RBAC, and shared resources."""

import logging as _logging
from collections.abc import AsyncGenerator
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

import redis.asyncio as aioredis
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from soas_backend.auth.jwt import decode_access_token
from soas_backend.auth import request_signature as reqsig
from soas_backend.config import settings
from soas_backend.database import get_db
from soas_backend.models.app_session import AppSession
from soas_backend.models.app_token import AppToken
from soas_backend.models.role import Permission, Role, RolePermission, UserRole
from soas_backend.models.user import User

# `auto_error=False` lets unauthenticated requests fall through to the cookie-based path
# rather than 401-ing immediately on a missing Authorization header. Service tokens and
# legacy JWT bearers still work when the header IS present.
security = HTTPBearer(auto_error=False)

SESSION_COOKIE_NAME = "soas_session"
# Browser-session idle timeout. If the client hasn't pinged /auth/session/heartbeat (or
# made any other authenticated call) in this many minutes, the server revokes the
# session. Heartbeat interval is 5 minutes, so the client can miss 6 in a row before
# the session dies — covers network blips and Sleep/Wake cycles up to that bound.
IDLE_TIMEOUT_MINUTES = 30


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
    *,
    on_behalf_of: str | None = None,
) -> tuple[dict[str, Any], User] | None:
    """Validate a service token and return a (jwt-shaped payload, user) tuple.

    When `on_behalf_of` (a user id string) is supplied, the resulting payload is scoped
    to *that* user's roles and permissions rather than the service token's underlying
    user. The service token must still be valid — this prevents anyone without the
    bearer from impersonating a user, while letting trusted MCP gateways scope per-call
    permissions to the actual analyst.
    """
    # Local import keeps the deps module light and avoids a circular import at module load.
    from soas_backend.services.service_token_service import ServiceTokenService

    svc = ServiceTokenService(db)
    result = await svc.validate(raw)
    if result is None:
        return None
    token, token_user = result

    target_user: User = token_user
    obo_marker: dict[str, str] = {}

    if on_behalf_of:
        try:
            obo_uuid = UUID(on_behalf_of)
        except (ValueError, TypeError):
            return None
        obo_q = await db.execute(select(User).where(User.id == obo_uuid))
        obo = obo_q.scalar_one_or_none()
        if obo is None or not obo.is_active:
            return None
        target_user = obo
        obo_marker["on_behalf_of"] = str(obo.id)

    # Resolve roles + permissions for the effective user (token holder, or OBO).
    roles_q = await db.execute(
        select(Role.name)
        .join(UserRole, UserRole.role_id == Role.id)
        .where(UserRole.user_id == target_user.id)
    )
    role_names = [r[0] for r in roles_q.all()]

    perms_q = await db.execute(
        select(Permission.resource, Permission.action)
        .join(RolePermission, RolePermission.permission_id == Permission.id)
        .join(UserRole, UserRole.role_id == RolePermission.role_id)
        .where(UserRole.user_id == target_user.id)
    )
    permissions: set[str] = set()
    for resource, action in perms_q.all():
        permissions.add(f"{resource}:{action}")

    # If the token has explicit scopes, restrict permissions to that intersection.
    # Empty scopes = inherit everything. Admin role always wins (matches JWT behaviour).
    if token.scopes and "admin" not in role_names:
        permissions &= set(token.scopes)

    payload = {
        "sub": str(target_user.id),
        "username": target_user.username,
        "roles": role_names,
        "permissions": sorted(permissions),
        "teams": [],
        # Marker so downstream code (audit log, etc.) can tell this was a service token.
        "auth_type": "service_token",
        "token_id": str(token.id),
        "token_name": token.name,
        **obo_marker,
    }

    # Touch usage timestamp out-of-band; never block the request on this.
    try:
        await svc.touch(token.id)
    except Exception:
        pass

    return payload, target_user

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


# ---------------------------------------------------------------------------
# Cookie + HMAC-signature auth path
# ---------------------------------------------------------------------------
#
# Interactive users (browsers) authenticate via an httpOnly cookie that carries
# `<session_id>.<b64_session_key>`. Every request also presents an HMAC of the canonical
# request string in the `X-SOAS-Signature` header, signed with the session key. The server
# loads the AppSession by id, checks IP binding + signature + timestamp + expiry, and only
# then resolves the user.
#
# Service tokens (sst_ / sat_ raw bearer in the Authorization header) keep their existing
# path so MCP/CI clients are unaffected.


def _parse_session_cookie(cookie: str | None) -> tuple[UUID, str] | None:
    if not cookie or "." not in cookie:
        return None
    sid_str, _, key_b64 = cookie.partition(".")
    try:
        return UUID(sid_str), key_b64
    except (ValueError, AttributeError):
        return None


def _client_ip(request: Request) -> str | None:
    """Pick the right client IP. Honour X-Forwarded-For only when the proxy is trusted."""
    if (settings.__dict__.get("trust_xfcc") or
            (getattr(settings, "soas_trust_xff", None) is True)):
        xff = request.headers.get("x-forwarded-for")
        if xff:
            return xff.split(",")[0].strip()
    if request.client:
        return request.client.host
    return None


async def _payload_from_app_session(
    request: Request,
    db: AsyncSession,
) -> tuple[dict[str, Any], User] | None:
    """Validate the session cookie + signature, returning a JWT-shaped payload + user.

    Returns None when there is no cookie at all (caller should then try Bearer). Raises
    HTTPException on a present-but-invalid session (so attackers don't fall through and
    we can revoke immediately).
    """
    from soas_backend.services.app_session_service import AppSessionService
    from soas_backend.services.security_event_service import SecurityEventService

    cookie = request.cookies.get(SESSION_COOKIE_NAME)
    parsed = _parse_session_cookie(cookie)
    if parsed is None:
        return None
    session_id, presented_key_b64 = parsed

    # Load session + paired app token
    result = await db.execute(
        select(AppSession)
        .where(AppSession.id == session_id)
        .options(selectinload(AppSession.user), selectinload(AppSession.app_token))
    )
    session = result.scalar_one_or_none()
    if session is None or session.revoked_at is not None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session not found or revoked",
        )

    sess_svc = AppSessionService(db)
    sec = SecurityEventService(db)

    # The cookie value must match the wrapped key on file. This guards against an attacker
    # who steals only the session_id half (since both halves are required to sign).
    try:
        stored_key_b64 = sess_svc.reveal_key(session)
    except Exception:
        await sess_svc.revoke(session.id, "key_unwrap_failed")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session key corrupted",
        )
    if not reqsig.verify(presented=presented_key_b64, expected=stored_key_b64):
        await sess_svc.revoke(session.id, "key_mismatch")
        await sec.record(
            event_type="auth.session_key_mismatch",
            severity="warn",
            actor_id=session.user_id,
            ip_address=_client_ip(request),
            message="Cookie session key did not match stored key",
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid session",
        )

    # IP binding — hard reject and revoke. The 1:1 session↔token mapping means losing this
    # session also kills the underlying app token unless explicitly preserved.
    ip = _client_ip(request)
    if ip is None or str(session.ip_address) != ip:
        await sess_svc.revoke(session.id, "ip_mismatch")
        await sec.record(
            event_type="auth.session_ip_mismatch",
            severity="warn",
            actor_id=session.user_id,
            ip_address=ip,
            message=f"Expected {session.ip_address}, got {ip}",
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="IP mismatch — please re-authenticate",
        )

    # App token expiry / revocation
    token: AppToken | None = session.app_token
    if token is None:
        await sess_svc.revoke(session.id, "token_missing")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session token missing",
        )
    now = datetime.now(timezone.utc)
    if token.revoked_at is not None or token.expires_at <= now:
        await sess_svc.revoke(session.id, "token_expired")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired — please re-authenticate",
        )

    # Idle-timeout: if we haven't heard from this client in IDLE_TIMEOUT_MINUTES, kill the
    # session. The browser sends a heartbeat every 5 minutes; missing 6 in a row (30 min)
    # means the tab is closed or the user walked away, and we shouldn't trust the cookie
    # if it's later reused. last_seen_at is updated by `sess_svc.touch()` at the bottom of
    # this function on every successful auth check, and explicitly by the heartbeat route.
    last_seen = session.last_seen_at or session.created_at
    if last_seen is not None:
        if last_seen.tzinfo is None:
            last_seen = last_seen.replace(tzinfo=timezone.utc)
        if (now - last_seen).total_seconds() > IDLE_TIMEOUT_MINUTES * 60:
            await sess_svc.revoke(session.id, "idle_timeout")
            await sec.record(
                event_type="auth.session_idle_timeout",
                severity="info",
                actor_id=session.user_id,
                ip_address=ip,
                message=f"Session idle for {(now - last_seen).total_seconds():.0f}s",
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Session idle-timed out — please re-authenticate",
            )

    # Per-request signature
    ts = request.headers.get(reqsig.TIMESTAMP_HEADER)
    sig = request.headers.get(reqsig.SIGNATURE_HEADER)
    _auth_log = _logging.getLogger("soas_backend.auth")
    if not ts or not sig:
        _auth_log.info(
            "session auth: missing signature headers path=%s method=%s have_ts=%s have_sig=%s ip=%s session=%s",
            request.url.path, request.method, bool(ts), bool(sig), ip, str(session.id)[:8],
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing request signature headers",
        )
    if not reqsig.timestamp_in_window(ts):
        _auth_log.info(
            "session auth: stale request path=%s ts=%s session=%s",
            request.url.path, ts, str(session.id)[:8],
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Stale request",
        )
    # Body has already been buffered by FastAPI for the route; pull from the raw scope.
    body = await request.body()
    canonical = reqsig.build_canonical_string(
        method=request.method,
        path=request.url.path,
        query_string=request.url.query,
        timestamp=ts,
        body=body,
    )
    # The session key is base64url(32 random bytes); the client signs with the raw
    # decoded bytes via SubtleCrypto importKey("raw", ...). Match that here.
    from soas_backend.services.app_session_service import session_key_from_b64
    raw_key = session_key_from_b64(stored_key_b64)
    expected_sig = reqsig.sign(canonical, raw_key)
    if not reqsig.verify(presented=sig, expected=expected_sig):
        # Encode canonical with explicit \n markers so the log line is readable.
        _auth_log.warning(
            "session auth: bad signature\n  path=%s method=%s qlen=%d blen=%d\n  canonical=%r\n  expected=%s presented=%s\n  session=%s key_prefix=%s",
            request.url.path, request.method, len(request.url.query or ""), len(body or b""),
            canonical, expected_sig, sig, str(session.id)[:8], stored_key_b64[:8],
        )
        await sec.record(
            event_type="auth.session_bad_signature",
            severity="warn",
            actor_id=session.user_id,
            ip_address=ip,
            message="HMAC signature did not match canonical request",
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid request signature",
        )

    user = session.user
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )

    # Resolve roles + permissions live (so a revoked role tightens access instantly)
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
    permissions = sorted({f"{r}:{a}" for r, a in perms_q.all()})

    payload = {
        "sub": str(user.id),
        "username": user.username,
        "roles": role_names,
        "permissions": permissions,
        "teams": [],
        "auth_type": "app_session",
        "session_id": str(session.id),
        "token_id": str(token.id),
    }

    # Best-effort touch of last_seen_at — never block the request on this.
    try:
        await sess_svc.touch(session.id)
    except Exception:
        pass

    return payload, user


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Extract and validate the current user.

    Tries (in order):
      1. App-session cookie + HMAC signature  (browsers)
      2. Service token / JWT in Authorization header (MCP, CI, legacy clients)
    """
    # Cookie path
    sess_result = await _payload_from_app_session(request, db)
    if sess_result is not None:
        _payload, user = sess_result
        return user

    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )

    raw = credentials.credentials

    if _is_service_token(raw):
        obo = request.headers.get("x-soas-on-behalf-of") if request else None
        st_result = await _payload_from_service_token(raw, db, on_behalf_of=obo)
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
    request: Request,
    credentials: HTTPAuthorizationCredentials | None,
    db: AsyncSession,
) -> dict[str, Any]:
    """Return a JWT-shaped payload from cookie session, service token, or JWT — or raise 401."""
    sess_result = await _payload_from_app_session(request, db)
    if sess_result is not None:
        payload, _user = sess_result
        return payload

    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )

    raw = credentials.credentials

    if _is_service_token(raw):
        obo = request.headers.get("x-soas-on-behalf-of") if request else None
        st_result = await _payload_from_service_token(raw, db, on_behalf_of=obo)
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
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]] | None:
    """Extract team memberships from cookie session, JWT, or service token.

    Returns list of team dicts for normal users, or None for admins (meaning all teams).
    """
    payload = await _resolve_payload(request, credentials, db)

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

    Accepts cookie-based app sessions (browsers), service tokens (`sst_…`, MCP/CI) and
    legacy JWT bearers, all sharing the same permission model. Admin role bypasses checks.
    """

    async def _check(
        request: Request,
        credentials: HTTPAuthorizationCredentials | None = Depends(security),
        db: AsyncSession = Depends(get_db),
    ) -> dict:
        payload = await _resolve_payload(request, credentials, db)

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

    Accepts cookie sessions, service tokens, and JWT bearers.
    """

    async def _check(
        request: Request,
        credentials: HTTPAuthorizationCredentials | None = Depends(security),
        db: AsyncSession = Depends(get_db),
    ) -> dict:
        payload = await _resolve_payload(request, credentials, db)

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
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Resolve the calling user with multiple layers of evidence.

    1. App-session cookie + HMAC signature (browsers) — IP-bound, 6h TTL via the
       paired AppToken. If a cookie is present, this path is authoritative.
    2. JWT / service token (`sst_…`) bearer (MCP, CI, legacy clients) when no cookie.
    3. Continuous Access Evaluation (CAE) — re-checks revocation on every request for
       JWT-authenticated users. Skipped for service tokens and app sessions (whose
       revocation is already DB-checked on every request).
    4. Client cert via X-Forwarded-Client-Cert (when SOAS_TRUST_XFCC=1 and
       auth_cert_login_enabled=true) — must match the resolved user.
    """
    from soas_backend.auth.cert import parse_xfcc_header, trust_enabled
    from soas_backend.services.app_setting_service import AppSettingService
    from soas_backend.services.cae_service import CAEService

    # Cookie path takes precedence — it already does its own IP + signature + expiry checks
    sess_result = await _payload_from_app_session(request, db)
    if sess_result is not None:
        payload, user = sess_result
        try:
            request.state.user = user
            request.state.jwt_payload = payload
        except Exception:
            pass
        return user

    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )

    raw = credentials.credentials

    # JWT or service token → payload + user
    if _is_service_token(raw):
        obo = request.headers.get("x-soas-on-behalf-of") if request else None
        st_result = await _payload_from_service_token(raw, db, on_behalf_of=obo)
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

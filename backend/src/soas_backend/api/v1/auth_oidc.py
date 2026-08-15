"""OIDC (Microsoft Entra) login routes.

Two endpoints:

  GET  /auth/oidc/start         — redirect to Entra's authorize endpoint
  GET  /auth/oidc/callback      — Entra redirects here with ?code=...
                                   we exchange, validate, mint a SOAS JWT

Plus a discovery helper the frontend calls to know whether to show the
"Sign in with Microsoft" button:

  GET  /auth/providers          — { password: bool, oidc: bool, cert: bool }
"""

from __future__ import annotations

import json
import logging
import secrets
import uuid
from typing import Any

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from soas_backend.api.deps import SESSION_COOKIE_NAME, get_redis
from soas_backend.services.app_session_service import AppSessionService
from soas_backend.services.app_token_service import AppTokenService, DEFAULT_TTL_HOURS
from soas_backend.auth.oidc import (
    OIDCConfigError,
    OIDCDisabledError,
    OIDCService,
)
from soas_backend.database import get_db
from soas_backend.models.role import Role, UserRole
from soas_backend.models.user import User
from soas_backend.services.app_setting_service import AppSettingService
from soas_backend.services.security_event_service import SecurityEventService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth-oidc"])

# State + PKCE verifier live in Redis for the duration of the flow.
STATE_TTL_SECONDS = 600


class ProvidersResponse(BaseModel):
    password: bool
    oidc: bool
    cert: bool


@router.get("/providers", response_model=ProvidersResponse)
async def list_providers(db: AsyncSession = Depends(get_db)):
    """Read the auth toggles. Public — no auth required."""
    s = AppSettingService(db)
    return ProvidersResponse(
        password=(await s.get_value("auth_password_enabled", "true") or "true").lower() == "true",
        oidc=(await s.get_value("auth_oidc_enabled", "false") or "false").lower() == "true",
        cert=(await s.get_value("auth_cert_login_enabled", "true") or "true").lower() == "true",
    )


@router.get("/oidc/start")
async def oidc_start(
    next: str = "/dashboard",
    request: Request = None,  # type: ignore[assignment]
    redis: aioredis.Redis = Depends(get_redis),
    db: AsyncSession = Depends(get_db),
):
    svc = OIDCService(db)
    try:
        cfg = await svc.load_config()
    except OIDCDisabledError:
        raise HTTPException(status_code=503, detail="OIDC login is disabled")
    except OIDCConfigError as e:
        raise HTTPException(status_code=503, detail=str(e))

    verifier, challenge = svc.build_pkce_pair()
    state = secrets.token_urlsafe(24)
    await redis.set(
        f"oidc:state:{state}",
        json.dumps({"verifier": verifier, "next": next}),
        ex=STATE_TTL_SECONDS,
    )
    url = await svc.authorize_url(cfg, state=state, code_challenge=challenge)
    return RedirectResponse(url, status_code=status.HTTP_302_FOUND)


@router.get("/oidc/callback")
async def oidc_callback(
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    error_description: str | None = None,
    request: Request = None,  # type: ignore[assignment]
    redis: aioredis.Redis = Depends(get_redis),
    db: AsyncSession = Depends(get_db),
):
    if error:
        await SecurityEventService(db).record(
            event_type="auth.oidc_callback_error",
            severity="warn",
            message=f"{error}: {error_description or ''}",
            ip_address=request.client.host if request and request.client else None,
        )
        raise HTTPException(status_code=400, detail=f"Entra returned: {error}")
    if not code or not state:
        raise HTTPException(status_code=400, detail="Missing code or state")

    raw = await redis.get(f"oidc:state:{state}")
    if not raw:
        raise HTTPException(status_code=400, detail="State expired or unknown")
    await redis.delete(f"oidc:state:{state}")
    flow = json.loads(raw)
    verifier = flow["verifier"]
    next_path = flow.get("next", "/dashboard")

    svc = OIDCService(db)
    try:
        cfg = await svc.load_config()
    except (OIDCDisabledError, OIDCConfigError) as e:
        raise HTTPException(status_code=503, detail=str(e))

    try:
        tokens = await svc.exchange_code(cfg, code=code, code_verifier=verifier)
        claims = await svc.validate_id_token(cfg, tokens.id_token)
    except OIDCConfigError as e:
        await SecurityEventService(db).record(
            event_type="auth.oidc_callback_error",
            severity="warn",
            message=str(e),
            ip_address=request.client.host if request and request.client else None,
        )
        raise HTTPException(status_code=400, detail=str(e))

    oid = claims.get("oid") or claims.get("sub")
    if not oid:
        raise HTTPException(status_code=400, detail="id_token missing subject")
    email = claims.get("email") or claims.get("preferred_username") or f"{oid}@entra.local"
    display_name = claims.get("name") or email
    username = (claims.get("preferred_username") or email).split("@")[0].lower()
    groups = claims.get("groups") or []

    # Provision (or look up) the SOAS user
    rs = await db.execute(select(User).where(User.oidc_subject == oid))
    user = rs.scalar_one_or_none()
    if user is None:
        # Try matching by email (existing local user linking via OIDC)
        rs = await db.execute(select(User).where(User.email == email))
        user = rs.scalar_one_or_none()
    if user is None:
        # New user — provision. Use a random placeholder password hash
        # (login via password is blocked by the auth_provider check).
        from soas_backend.auth.password import hash_password

        user = User(
            username=username,
            email=email,
            display_name=display_name,
            password_hash=hash_password(secrets.token_urlsafe(32)),
            auth_provider="entra",
            oidc_subject=oid,
            is_active=True,
        )
        db.add(user)
        await db.flush()
        await SecurityEventService(db).record(
            event_type="user.created",
            actor_label=username,
            target_kind="user",
            target_id=user.id,
            target_label=username,
            message="Provisioned via OIDC first-login",
        )
    else:
        # Backfill oidc_subject on first sign-in for a linked-by-email user
        if user.oidc_subject is None:
            user.oidc_subject = oid
            user.auth_provider = "entra"
        if user.display_name != display_name:
            user.display_name = display_name
        await db.flush()

    # Apply group → role mappings if any are configured.
    await _apply_group_role_mappings(db, user, groups)

    # Mint a 6h AppToken bound 1:1 to a new AppSession with the originating IP.
    # The session key lives in the cookie (httpOnly+Secure+SameSite=Strict) and the client
    # also gets a one-shot read of it from /auth/session/bootstrap to use for HMAC signing.
    ip = request.client.host if request and request.client else "0.0.0.0"
    ua = request.headers.get("user-agent", "") if request else ""

    _raw_app_token, app_token = await AppTokenService(db).issue(
        user_id=user.id,
        ttl_hours=DEFAULT_TTL_HOURS,
        issued_via="entra",
        oidc_subject=oid,
    )
    b64_session_key, session = await AppSessionService(db).create(
        app_token_id=app_token.id,
        user_id=user.id,
        ip=ip,
        user_agent=ua,
    )

    await SecurityEventService(db).record(
        event_type="auth.oidc_login_success",
        actor_id=user.id,
        actor_label=user.username,
        ip_address=ip,
        extra={
            "oidc_subject": oid,
            "groups": groups,
            "app_token_id": str(app_token.id),
            "session_id": str(session.id),
        },
    )

    # The cookie carries `<session_id>.<b64_session_key>`. The server stores only the
    # encrypted form of the key; the client briefly holds the plaintext so it can sign
    # requests. We mark `oidc=1` in the URL fragment so the frontend knows to call
    # /auth/session/bootstrap to retrieve the signing key.
    cookie_value = f"{session.id}.{b64_session_key}"
    response = RedirectResponse(f"{next_path}#oidc=1", status_code=status.HTTP_302_FOUND)
    # Session-scope cookie: browser drops it on close. AppToken TTL caps it at 6h.
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=cookie_value,
        httponly=True,
        secure=True,
        samesite="strict",
        path="/",
    )
    return response


async def _apply_group_role_mappings(
    db: AsyncSession,
    user: User,
    entra_groups: list[str],
) -> None:
    """Map Entra group object-ids to SOAS roles via app_settings.

    Settings key: `auth_oidc_group_mappings` — JSON dict {entra_oid: role_name}.
    Roles not present in the user's current set are added; we do not
    remove roles assigned by other means here.
    """
    if not entra_groups:
        return
    s = AppSettingService(db)
    raw = await s.get_value("auth_oidc_group_mappings", "{}") or "{}"
    try:
        mapping = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("oidc: invalid auth_oidc_group_mappings JSON; skipping")
        return
    desired_roles: set[str] = set()
    for group_id in entra_groups:
        role_name = mapping.get(group_id)
        if role_name:
            desired_roles.add(role_name)
    if not desired_roles:
        return
    rs = await db.execute(select(Role).where(Role.name.in_(desired_roles)))
    roles = list(rs.scalars().all())
    existing_rs = await db.execute(
        select(UserRole.role_id).where(UserRole.user_id == user.id)
    )
    existing_role_ids = {row[0] for row in existing_rs.all()}
    for role in roles:
        if role.id not in existing_role_ids:
            db.add(UserRole(user_id=user.id, role_id=role.id))
    await db.flush()


async def _user_role_names(db: AsyncSession, user_id: uuid.UUID) -> list[str]:
    rs = await db.execute(
        select(Role.name).join(UserRole, UserRole.role_id == Role.id).where(UserRole.user_id == user_id)
    )
    return [r[0] for r in rs.all()]


async def _user_permissions(db: AsyncSession, user_id: uuid.UUID) -> list[str]:
    from soas_backend.models.role import Permission, RolePermission

    rs = await db.execute(
        select(Permission.resource, Permission.action)
        .join(RolePermission, RolePermission.permission_id == Permission.id)
        .join(UserRole, UserRole.role_id == RolePermission.role_id)
        .where(UserRole.user_id == user_id)
    )
    return sorted({f"{r}:{a}" for r, a in rs.all()})

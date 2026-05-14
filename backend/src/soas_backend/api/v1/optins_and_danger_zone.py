"""User opt-ins for automation execution + consolidated Danger Zone (Phase 6)."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from soas_backend.api.deps import get_current_user, require_role
from soas_backend.database import get_db
from soas_backend.models.asset import UserRunOptin
from soas_backend.models.user import User

router = APIRouter(prefix="/admin", tags=["danger-zone"])


# ----- opt-ins -----


class OptinRead(BaseModel):
    user_id: UUID
    opted_in_at: datetime
    granted_by: UUID | None
    user_display: str | None = None


@router.get("/optins", response_model=list[OptinRead])
async def list_optins(
    _: dict = Depends(require_role("admin", "soc_manager")),
    db: AsyncSession = Depends(get_db),
):
    rs = await db.execute(
        select(UserRunOptin, User.display_name)
        .join(User, User.id == UserRunOptin.user_id)
        .order_by(UserRunOptin.opted_in_at.desc())
    )
    out: list[OptinRead] = []
    for opt, name in rs.all():
        out.append(OptinRead(
            user_id=opt.user_id, opted_in_at=opt.opted_in_at,
            granted_by=opt.granted_by, user_display=name,
        ))
    return out


@router.post("/optins/{user_id}", response_model=OptinRead, status_code=201)
async def grant_optin(
    user_id: UUID,
    current_user: User = Depends(get_current_user),
    _: dict = Depends(require_role("admin", "soc_manager")),
    db: AsyncSession = Depends(get_db),
):
    rs = await db.execute(select(UserRunOptin).where(UserRunOptin.user_id == user_id))
    existing = rs.scalar_one_or_none()
    if existing:
        return OptinRead(user_id=existing.user_id, opted_in_at=existing.opted_in_at, granted_by=existing.granted_by)
    rs = await db.execute(select(User).where(User.id == user_id))
    user = rs.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    optin = UserRunOptin(user_id=user_id, granted_by=current_user.id)
    db.add(optin)
    await db.flush()
    return OptinRead(user_id=optin.user_id, opted_in_at=optin.opted_in_at, granted_by=optin.granted_by, user_display=user.display_name)


@router.delete("/optins/{user_id}", status_code=204)
async def revoke_optin(
    user_id: UUID,
    _: dict = Depends(require_role("admin", "soc_manager")),
    db: AsyncSession = Depends(get_db),
):
    await db.execute(delete(UserRunOptin).where(UserRunOptin.user_id == user_id))


@router.get("/optins/me/status")
async def my_optin_status(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    rs = await db.execute(select(UserRunOptin).where(UserRunOptin.user_id == current_user.id))
    optin = rs.scalar_one_or_none()
    return {"opted_in": optin is not None, "opted_in_at": optin.opted_in_at.isoformat() if optin else None}


# ----- danger zone counters -----


@router.get("/danger-zone/summary")
async def danger_zone_summary(
    _: dict = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    """A quick summary the danger zone page can show — counts of things you might want to nuke."""
    from sqlalchemy import func as sa_func

    from soas_backend.models.execution import ExecutionLog
    from soas_backend.models.incident import Incident
    from soas_backend.models.case import Case
    from soas_backend.models.automation import Automation

    counts: dict[str, int] = {}
    for label, model in (
        ("incidents", Incident),
        ("cases", Case),
        ("automations", Automation),
        ("executions", ExecutionLog),
    ):
        rs = await db.execute(select(sa_func.count()).select_from(model))
        counts[label] = int(rs.scalar() or 0)
    return {"counts": counts}


# ============================================================
# Auth settings (Danger Zone → Authentication panel)
# ============================================================


AUTH_TOGGLE_KEYS = {
    "auth_password_enabled",
    "auth_cert_login_enabled",
    "auth_oidc_enabled",
    "auth_oidc_tenant",
    "auth_oidc_client_id",
    "auth_oidc_redirect_uri",
    "auth_oidc_client_secret",
    "auth_oidc_group_mappings",
    "auth_cae_cache_seconds",
    "auth_cae_strict",
}


@router.get("/danger-zone/auth-settings")
async def get_auth_settings(
    _: dict = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    from soas_backend.services.app_setting_service import AppSettingService

    svc = AppSettingService(db)
    out: dict[str, str] = {}
    for key in AUTH_TOGGLE_KEYS:
        # client_secret is intentionally never returned in cleartext.
        if key == "auth_oidc_client_secret":
            v = await svc.get_value(key, "")
            out[key] = "***" if v else ""
        else:
            out[key] = await svc.get_value(key, "") or ""
    return out


class AuthSettingsUpdate(BaseModel):
    key: str
    value: str


@router.put("/danger-zone/auth-settings")
async def update_auth_setting(
    body: AuthSettingsUpdate,
    current_user: User = Depends(get_current_user),
    _: dict = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    if body.key not in AUTH_TOGGLE_KEYS:
        raise HTTPException(status_code=400, detail="Unknown auth setting key")

    from soas_backend.services.app_setting_service import AppSettingService
    from soas_backend.services.security_event_service import SecurityEventService

    svc = AppSettingService(db)
    prior = await svc.get_value(body.key, "")
    await svc.set(body.key, body.value, updated_by=current_user.id)
    # Audit — redact secret values.
    extra: dict[str, str] = {"key": body.key}
    if body.key != "auth_oidc_client_secret":
        extra["prior"] = prior or ""
        extra["new"] = body.value
    await SecurityEventService(db).record(
        event_type="danger_zone.auth_setting_changed",
        severity="warn",
        actor_id=current_user.id,
        actor_label=current_user.username,
        target_kind="app_setting",
        target_label=body.key,
        extra=extra,
    )
    return {"ok": True}

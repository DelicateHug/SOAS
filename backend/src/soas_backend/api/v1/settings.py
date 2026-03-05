"""App settings API - admin/soc_manager only."""

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from soas_backend.api.deps import get_current_user, get_db, require_role
from soas_backend.models.user import User
from soas_backend.services.app_setting_service import AppSettingService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/settings", tags=["settings"])


class SettingRead(BaseModel):
    key: str
    value: str
    description: str | None = None

    model_config = {"from_attributes": True}


class SettingUpdate(BaseModel):
    value: str


@router.get("", response_model=list[SettingRead])
async def list_settings(
    _: dict = Depends(require_role("admin", "soc_manager")),
    db: AsyncSession = Depends(get_db),
):
    svc = AppSettingService(db)
    return await svc.get_all()


@router.get("/{key}", response_model=SettingRead)
async def get_setting(
    key: str,
    _: dict = Depends(require_role("admin", "soc_manager")),
    db: AsyncSession = Depends(get_db),
):
    svc = AppSettingService(db)
    setting = await svc.get(key)
    if not setting:
        raise HTTPException(status_code=404, detail="Setting not found")
    return setting


@router.put("/{key}", response_model=SettingRead)
async def update_setting(
    key: str,
    body: SettingUpdate,
    current_user: User = Depends(get_current_user),
    _: dict = Depends(require_role("admin", "soc_manager")),
    db: AsyncSession = Depends(get_db),
):
    svc = AppSettingService(db)
    setting = await svc.get(key)
    if not setting:
        raise HTTPException(status_code=404, detail="Setting not found")
    updated = await svc.set(key, body.value, updated_by=current_user.id)
    return updated


# ---------------------------------------------------------------------------
# Deployment mode (accessible to ALL authenticated users for read)
# ---------------------------------------------------------------------------


class DeploymentModeRead(BaseModel):
    mode: str  # "development" or "production"
    is_production: bool


class DeploymentModeUpdate(BaseModel):
    mode: str  # "development" or "production"


@router.get("/deployment-mode/current", response_model=DeploymentModeRead)
async def get_deployment_mode(
    db: AsyncSession = Depends(get_db),
):
    """Get current deployment mode. Accessible to all authenticated users."""
    svc = AppSettingService(db)
    mode = await svc.get_value("deployment_mode", "development")
    return DeploymentModeRead(mode=mode, is_production=mode == "production")


@router.put("/deployment-mode/current", response_model=DeploymentModeRead)
async def set_deployment_mode(
    body: DeploymentModeUpdate,
    current_user: User = Depends(get_current_user),
    _: dict = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    """Switch deployment mode. Admin only.

    When switching to production:
      - Git sync branch is set to 'main'
    When switching to development:
      - Git sync branch is set to 'dev'
    """
    if body.mode not in ("development", "production"):
        raise HTTPException(status_code=400, detail="Mode must be 'development' or 'production'")

    svc = AppSettingService(db)
    await svc.set("deployment_mode", body.mode, updated_by=current_user.id)

    # Auto-switch git sync branch
    new_branch = "main" if body.mode == "production" else "dev"
    await svc.set("git_sync_branch", new_branch, updated_by=current_user.id)
    logger.info("Deployment mode switched to %s (git branch → %s) by %s", body.mode, new_branch, current_user.username)

    return DeploymentModeRead(mode=body.mode, is_production=body.mode == "production")

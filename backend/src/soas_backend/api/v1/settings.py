"""App settings API - admin/soc_manager only."""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from soas_backend.api.deps import get_current_user, get_db, require_role
from soas_backend.models.user import User
from soas_backend.services.app_setting_service import AppSettingService

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

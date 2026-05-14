"""Incident templates admin API (Phase 3)."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from soas_backend.api.deps import get_current_user, require_role
from soas_backend.database import get_db
from soas_backend.models.alert_category import IncidentTemplate
from soas_backend.models.user import User

router = APIRouter(prefix="/incident-templates", tags=["incident-templates"])


class TemplateRead(BaseModel):
    id: UUID
    name: str
    description: str | None
    defaults: dict[str, Any]

    model_config = {"from_attributes": True}


class TemplateCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = None
    defaults: dict[str, Any] = Field(default_factory=dict)


class TemplateUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    defaults: dict[str, Any] | None = None


@router.get("", response_model=list[TemplateRead])
async def list_templates(
    _: dict = Depends(require_role("admin", "soc_manager", "analyst")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(IncidentTemplate).order_by(IncidentTemplate.name.asc()))
    return list(result.scalars().all())


@router.post("", response_model=TemplateRead, status_code=201)
async def create_template(
    body: TemplateCreate,
    current_user: User = Depends(get_current_user),
    _: dict = Depends(require_role("admin", "soc_manager")),
    db: AsyncSession = Depends(get_db),
):
    tmpl = IncidentTemplate(
        name=body.name,
        description=body.description,
        defaults=body.defaults,
        created_by=current_user.id,
    )
    db.add(tmpl)
    await db.flush()
    return tmpl


@router.patch("/{template_id}", response_model=TemplateRead)
async def update_template(
    template_id: UUID,
    body: TemplateUpdate,
    _: dict = Depends(require_role("admin", "soc_manager")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(IncidentTemplate).where(IncidentTemplate.id == template_id))
    tmpl = result.scalar_one_or_none()
    if not tmpl:
        raise HTTPException(status_code=404, detail="Template not found")
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(tmpl, k, v)
    await db.flush()
    return tmpl


@router.delete("/{template_id}", status_code=204)
async def delete_template(
    template_id: UUID,
    _: dict = Depends(require_role("admin", "soc_manager")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(IncidentTemplate).where(IncidentTemplate.id == template_id))
    tmpl = result.scalar_one_or_none()
    if not tmpl:
        raise HTTPException(status_code=404, detail="Template not found")
    await db.delete(tmpl)

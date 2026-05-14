"""Alert categories + rules admin API (Phase 3)."""

from __future__ import annotations

import re
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from soas_backend.api.deps import get_current_user, require_role
from soas_backend.database import get_db
from soas_backend.models.alert_category import AlertCategory, AlertCategoryRule
from soas_backend.models.user import User
from soas_backend.services.classifier_service import ClassifierService

router = APIRouter(prefix="/alert-categories", tags=["alert-categories"])


# -------- schemas --------


class RuleRead(BaseModel):
    id: UUID
    field: str
    pattern: str
    case_sensitive: bool
    is_enabled: bool
    sort_order: int

    model_config = {"from_attributes": True}


class CategoryRead(BaseModel):
    id: UUID
    key: str
    label: str
    description: str | None
    default_severity: str | None
    default_priority: str | None
    default_automation_id: UUID | None
    is_system: bool
    sort_order: int
    rules: list[RuleRead] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class CategoryCreate(BaseModel):
    key: str = Field(min_length=1, max_length=64, pattern=r"^[a-z0-9_]+$")
    label: str = Field(min_length=1, max_length=200)
    description: str | None = None
    default_severity: str | None = None
    default_priority: str | None = None
    default_automation_id: UUID | None = None
    sort_order: int = 100


class CategoryUpdate(BaseModel):
    label: str | None = None
    description: str | None = None
    default_severity: str | None = None
    default_priority: str | None = None
    default_automation_id: UUID | None = None
    sort_order: int | None = None


class RuleCreate(BaseModel):
    field: str = Field(min_length=1, max_length=200)
    pattern: str = Field(min_length=1)
    case_sensitive: bool = False
    is_enabled: bool = True
    sort_order: int = 100


class RuleUpdate(BaseModel):
    field: str | None = None
    pattern: str | None = None
    case_sensitive: bool | None = None
    is_enabled: bool | None = None
    sort_order: int | None = None


# -------- routes --------


@router.get("", response_model=list[CategoryRead])
async def list_categories(
    _: dict = Depends(require_role("admin", "soc_manager")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(AlertCategory)
        .options(selectinload(AlertCategory.rules))
        .order_by(AlertCategory.sort_order.asc())
    )
    return list(result.scalars().all())


@router.post("", response_model=CategoryRead, status_code=201)
async def create_category(
    body: CategoryCreate,
    _: dict = Depends(require_role("admin", "soc_manager")),
    db: AsyncSession = Depends(get_db),
):
    cat = AlertCategory(
        key=body.key,
        label=body.label,
        description=body.description,
        default_severity=body.default_severity,
        default_priority=body.default_priority,
        default_automation_id=body.default_automation_id,
        sort_order=body.sort_order,
    )
    db.add(cat)
    await db.flush()
    ClassifierService.invalidate_cache()
    return CategoryRead(id=cat.id, key=cat.key, label=cat.label, description=cat.description,
                        default_severity=cat.default_severity, default_priority=cat.default_priority,
                        default_automation_id=cat.default_automation_id, is_system=cat.is_system,
                        sort_order=cat.sort_order, rules=[])


@router.patch("/{category_id}", response_model=CategoryRead)
async def update_category(
    category_id: UUID,
    body: CategoryUpdate,
    _: dict = Depends(require_role("admin", "soc_manager")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(AlertCategory).options(selectinload(AlertCategory.rules)).where(AlertCategory.id == category_id)
    )
    cat = result.scalar_one_or_none()
    if not cat:
        raise HTTPException(status_code=404, detail="Category not found")
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(cat, k, v)
    await db.flush()
    ClassifierService.invalidate_cache()
    return cat


@router.delete("/{category_id}", status_code=204)
async def delete_category(
    category_id: UUID,
    _: dict = Depends(require_role("admin", "soc_manager")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(AlertCategory).where(AlertCategory.id == category_id))
    cat = result.scalar_one_or_none()
    if not cat:
        raise HTTPException(status_code=404, detail="Category not found")
    if cat.is_system:
        raise HTTPException(status_code=400, detail="Cannot delete a system category")
    await db.delete(cat)
    ClassifierService.invalidate_cache()


# ----- Rules -----


def _validate_regex(pattern: str) -> None:
    try:
        re.compile(pattern)
    except re.error as e:
        raise HTTPException(status_code=400, detail=f"Invalid regex: {e}")


@router.post("/{category_id}/rules", response_model=RuleRead, status_code=201)
async def add_rule(
    category_id: UUID,
    body: RuleCreate,
    _: dict = Depends(require_role("admin", "soc_manager")),
    db: AsyncSession = Depends(get_db),
):
    _validate_regex(body.pattern)
    rule = AlertCategoryRule(
        category_id=category_id,
        field=body.field,
        pattern=body.pattern,
        case_sensitive=body.case_sensitive,
        is_enabled=body.is_enabled,
        sort_order=body.sort_order,
    )
    db.add(rule)
    await db.flush()
    ClassifierService.invalidate_cache()
    return rule


@router.patch("/rules/{rule_id}", response_model=RuleRead)
async def update_rule(
    rule_id: UUID,
    body: RuleUpdate,
    _: dict = Depends(require_role("admin", "soc_manager")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(AlertCategoryRule).where(AlertCategoryRule.id == rule_id))
    rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    fields = body.model_dump(exclude_unset=True)
    if "pattern" in fields and fields["pattern"]:
        _validate_regex(fields["pattern"])
    for k, v in fields.items():
        setattr(rule, k, v)
    await db.flush()
    ClassifierService.invalidate_cache()
    return rule


@router.delete("/rules/{rule_id}", status_code=204)
async def delete_rule(
    rule_id: UUID,
    _: dict = Depends(require_role("admin", "soc_manager")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(AlertCategoryRule).where(AlertCategoryRule.id == rule_id))
    rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    await db.delete(rule)
    ClassifierService.invalidate_cache()

"""Normalization CRUD endpoints with Redis cache invalidation."""

import logging
from uuid import UUID

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from soas_backend.api.deps import get_current_user, get_redis, require_permission
from soas_backend.database import get_db
from soas_backend.models.user import User
from soas_backend.services.normalization_service import NormalizationService
from soas_shared.schemas.normalization import (
    NormalizationBulkSave,
    NormalizationGroupRead,
    NormalizationRuleCreate,
    NormalizationRuleRead,
    NormalizationRuleUpdate,
    NormalizationTestRequest,
    NormalizationTestResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/normalization", tags=["normalization"])


# --------------------------------------------------------------------------- #
# Helpers                                                                      #
# --------------------------------------------------------------------------- #


def _group_to_read(group) -> NormalizationGroupRead:
    return NormalizationGroupRead(
        id=group.id,
        name=group.name,
        display_name=group.display_name,
        description=group.description,
        icon=group.icon,
        display_order=group.display_order,
    )


def _rule_to_read(rule) -> NormalizationRuleRead:
    group_read = None
    if rule.group:
        group_read = NormalizationGroupRead(
            id=rule.group.id,
            name=rule.group.name,
            display_name=rule.group.display_name,
            description=rule.group.description,
            icon=rule.group.icon,
            display_order=rule.group.display_order,
        )
    return NormalizationRuleRead(
        id=rule.id,
        group_id=rule.group_id,
        group=group_read,
        source_path=rule.source_path,
        target_field=rule.target_field,
        transform_type=rule.transform_type,
        transform_config=rule.transform_config or {},
        is_required=rule.is_required,
        default_value=rule.default_value,
        display_order=rule.display_order,
        is_enabled=rule.is_enabled,
        created_at=rule.created_at,
        updated_at=rule.updated_at,
    )


# --------------------------------------------------------------------------- #
# Groups                                                                       #
# --------------------------------------------------------------------------- #


@router.get("/groups", response_model=list[NormalizationGroupRead])
async def list_groups(
    current_user: User = Depends(get_current_user),
    _: dict = Depends(require_permission("normalization", "read")),
    db: AsyncSession = Depends(get_db),
):
    svc = NormalizationService(db)
    groups = await svc.list_groups()
    return [_group_to_read(g) for g in groups]


# --------------------------------------------------------------------------- #
# Rules                                                                        #
# --------------------------------------------------------------------------- #


@router.get("/rules", response_model=list[NormalizationRuleRead])
async def list_rules(
    current_user: User = Depends(get_current_user),
    _: dict = Depends(require_permission("normalization", "read")),
    db: AsyncSession = Depends(get_db),
):
    svc = NormalizationService(db)
    rules = await svc.list_rules()
    return [_rule_to_read(r) for r in rules]


@router.post("/rules", response_model=NormalizationRuleRead, status_code=status.HTTP_201_CREATED)
async def create_rule(
    body: NormalizationRuleCreate,
    current_user: User = Depends(get_current_user),
    _: dict = Depends(require_permission("normalization", "create")),
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
):
    svc = NormalizationService(db, redis)
    rule = await svc.create_rule(
        group_id=body.group_id,
        source_path=body.source_path,
        target_field=body.target_field,
        transform_type=body.transform_type,
        transform_config=body.transform_config,
        is_required=body.is_required,
        default_value=body.default_value,
        display_order=body.display_order,
        is_enabled=body.is_enabled,
    )

    # Re-fetch to load group relationship
    rules = await svc.list_rules()
    fetched = next((r for r in rules if r.id == rule.id), None)
    if fetched:
        return _rule_to_read(fetched)

    # Fallback: build response without group relationship
    return _rule_to_read(rule)


@router.patch("/rules/{rule_id}", response_model=NormalizationRuleRead)
async def update_rule(
    rule_id: UUID,
    body: NormalizationRuleUpdate,
    current_user: User = Depends(get_current_user),
    _: dict = Depends(require_permission("normalization", "update")),
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
):
    svc = NormalizationService(db, redis)

    # Collect only non-None fields from the update body
    update_fields = {k: v for k, v in body.model_dump().items() if v is not None}

    try:
        rule = await svc.update_rule(rule_id, **update_fields)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    # Re-fetch to load group relationship
    rules = await svc.list_rules()
    fetched = next((r for r in rules if r.id == rule.id), None)
    if fetched:
        return _rule_to_read(fetched)

    return _rule_to_read(rule)


@router.delete("/rules/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_rule(
    rule_id: UUID,
    _: dict = Depends(require_permission("normalization", "delete")),
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
):
    svc = NormalizationService(db, redis)
    try:
        await svc.delete_rule(rule_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# --------------------------------------------------------------------------- #
# Bulk operations                                                              #
# --------------------------------------------------------------------------- #


@router.put("/rules/bulk", response_model=list[NormalizationRuleRead])
async def bulk_save_rules(
    body: NormalizationBulkSave,
    current_user: User = Depends(get_current_user),
    _: dict = Depends(require_permission("normalization", "update")),
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
):
    svc = NormalizationService(db, redis)

    # Convert pydantic models to dicts for the service
    rules_dicts = [r.model_dump() for r in body.rules]
    await svc.bulk_save_rules(rules_dicts)

    # Re-fetch all rules with group relationships loaded
    rules = await svc.list_rules()
    return [_rule_to_read(r) for r in rules]


# --------------------------------------------------------------------------- #
# Test / preview                                                               #
# --------------------------------------------------------------------------- #


@router.post("/test", response_model=NormalizationTestResponse)
async def test_normalization(
    body: NormalizationTestRequest,
    current_user: User = Depends(get_current_user),
    _: dict = Depends(require_permission("normalization", "read")),
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
):
    svc = NormalizationService(db, redis)
    normalized, errors, warnings = await svc.normalize(body.raw_payload)

    return NormalizationTestResponse(
        normalized=normalized,
        errors=errors,
        warnings=warnings,
    )

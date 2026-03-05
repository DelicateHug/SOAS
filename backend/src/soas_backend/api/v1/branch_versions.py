"""API routes for three-tier git branch versioning.

Manages: user draft → push to dev → promote to prod.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from soas_backend.api.deps import get_current_user, get_db, require_permission
from soas_backend.models.user import User
from soas_backend.services.branch_version_service import BranchVersionService
from soas_backend.services.git_ops import GitOpsError
from soas_backend.services.git_serializers import ENTITY_TYPE_TO_SERIALIZER_KEY
from soas_shared.schemas.change_request import (
    BranchInfo,
    DevChangesItem,
    EntityVersionResponse,
    PromotionResult,
    PushToDevRequest,
    PushToDevResult,
)

router = APIRouter(prefix="/branch-versions", tags=["branch-versions"])


def _get_service(db: AsyncSession) -> BranchVersionService:
    return BranchVersionService(db)


# ------------------------------------------------------------------
# Entity version endpoints
# ------------------------------------------------------------------


@router.get("/entity/{entity_type}/{entity_id}", response_model=EntityVersionResponse)
async def get_entity_version(
    entity_type: str,
    entity_id: UUID,
    tier: str | None = Query(None, pattern="^(user|dev|prod)$"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get entity at a specific tier, or the effective version for current user."""
    if entity_type not in ENTITY_TYPE_TO_SERIALIZER_KEY:
        raise HTTPException(status_code=400, detail=f"Unknown entity type: {entity_type}")

    svc = _get_service(db)
    eid = str(entity_id)

    try:
        if tier:
            username = current_user.username if tier == "user" else None
            snapshot = svc.get_entity_at_tier(entity_type, eid, tier, username)
            return EntityVersionResponse(
                entity_type=entity_type,
                entity_id=eid,
                tier=tier,
                snapshot=snapshot,
            )
        else:
            snapshot, source_tier = svc.get_effective_entity(
                current_user.username, entity_type, eid
            )
            return EntityVersionResponse(
                entity_type=entity_type,
                entity_id=eid,
                tier=source_tier,
                snapshot=snapshot,
            )
    except GitOpsError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/entity/{entity_type}/{entity_id}/diff")
async def diff_entity_tiers(
    entity_type: str,
    entity_id: UUID,
    from_tier: str = Query("user", pattern="^(user|dev|prod)$"),
    to_tier: str = Query("dev", pattern="^(user|dev|prod)$"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Compare an entity between two tiers."""
    if entity_type not in ENTITY_TYPE_TO_SERIALIZER_KEY:
        raise HTTPException(status_code=400, detail=f"Unknown entity type: {entity_type}")

    svc = _get_service(db)
    eid = str(entity_id)
    username = current_user.username

    from_snapshot = svc.get_entity_at_tier(entity_type, eid, from_tier, username)
    to_snapshot = svc.get_entity_at_tier(entity_type, eid, to_tier, username)

    return {
        "entity_type": entity_type,
        "entity_id": str(entity_id),
        "from_tier": from_tier,
        "to_tier": to_tier,
        "from_snapshot": from_snapshot,
        "to_snapshot": to_snapshot,
    }


# ------------------------------------------------------------------
# Push to dev
# ------------------------------------------------------------------


@router.post("/push-to-dev", response_model=PushToDevResult)
async def push_to_dev(
    body: PushToDevRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Merge current user's branch into dev."""
    svc = _get_service(db)
    try:
        result = svc.push_to_dev(current_user.username, force=body.force)
        return PushToDevResult(
            status=result.status,
            conflicts=result.conflicts,
            sha=result.sha,
        )
    except GitOpsError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


# ------------------------------------------------------------------
# Promote to prod
# ------------------------------------------------------------------


@router.post("/promote-to-prod", response_model=PromotionResult)
async def promote_to_prod(
    _: dict = Depends(require_permission("change_request", "review")),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Merge dev branch into main (prod).  Admin only."""
    svc = _get_service(db)
    try:
        result = await svc.promote_to_prod()
        return PromotionResult(
            status=result.status,
            conflicts=result.conflicts,
            sha=result.sha,
        )
    except GitOpsError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


# ------------------------------------------------------------------
# Rebase user from dev
# ------------------------------------------------------------------


@router.post("/rebase-from-dev", response_model=PushToDevResult)
async def rebase_from_dev(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update current user's branch with latest dev changes."""
    svc = _get_service(db)
    try:
        result = svc.rebase_user_from_dev(current_user.username)
        return PushToDevResult(
            status=result.status,
            conflicts=result.conflicts,
            sha=result.sha,
        )
    except GitOpsError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


# ------------------------------------------------------------------
# Dev changes (diff dev vs prod)
# ------------------------------------------------------------------


@router.get("/dev/changes", response_model=list[DevChangesItem])
async def list_dev_changes(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List files that differ between dev and prod."""
    svc = _get_service(db)
    try:
        files = svc.diff_dev_prod()
    except GitOpsError:
        files = []

    results = []
    for f in files:
        # Infer entity type from directory
        parts = f.split("/")
        et = None
        if len(parts) >= 2:
            directory = parts[0]
            for etype, skey in ENTITY_TYPE_TO_SERIALIZER_KEY.items():
                from soas_backend.services.git_serializers import _serializer_dir
                if _serializer_dir(etype) == directory:
                    et = etype
                    break
        results.append(DevChangesItem(file_path=f, entity_type=et))
    return results


# ------------------------------------------------------------------
# Branch info
# ------------------------------------------------------------------


@router.get("/branches", response_model=list[BranchInfo])
async def list_branches(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all git branches with metadata."""
    svc = _get_service(db)
    try:
        return [BranchInfo(**b) for b in svc.list_branches()]
    except GitOpsError:
        return []

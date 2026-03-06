"""Change request API routes for dev/prod draft workflow."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from soas_backend.api.deps import get_current_user, get_db, require_permission
from soas_backend.models.user import User
from soas_backend.services.change_request_service import ChangeRequestService
from soas_shared.schemas.change_request import (
    ChangeRequestCreate,
    ChangeRequestDetail,
    ChangeRequestItem,
    ChangeRequestListResponse,
    ChangeRequestReview,
    UserBrief,
)

router = APIRouter(prefix="/change-requests", tags=["change-requests"])


def _to_item(cr, include_snapshot: bool = False) -> ChangeRequestItem | ChangeRequestDetail:
    creator = None
    if cr.creator:
        creator = UserBrief(id=cr.creator.id, display_name=cr.creator.display_name)
    reviewer = None
    if cr.reviewer:
        reviewer = UserBrief(id=cr.reviewer.id, display_name=cr.reviewer.display_name)

    base = dict(
        id=cr.id,
        entity_type=cr.entity_type,
        entity_id=cr.entity_id,
        action=cr.action,
        title=cr.title,
        status=cr.status,
        diff_summary=cr.diff_summary,
        submit_comment=cr.submit_comment,
        review_comment=cr.review_comment,
        git_branch=cr.git_branch,
        git_sha=cr.git_sha,
        git_pr_url=cr.git_pr_url,
        target_tier=cr.target_tier,
        created_by=cr.created_by,
        creator=creator,
        reviewed_by=cr.reviewed_by,
        reviewer=reviewer,
        created_at=cr.created_at,
        updated_at=cr.updated_at,
        reviewed_at=cr.reviewed_at,
    )
    if include_snapshot:
        return ChangeRequestDetail(**base, snapshot=cr.snapshot)
    return ChangeRequestItem(**base)


# ------------------------------------------------------------------
# List endpoints
# ------------------------------------------------------------------


@router.get("/mine", response_model=ChangeRequestListResponse)
async def list_my_change_requests(
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=1, le=100),
    status_filter: str | None = Query(None, alias="status"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List current user's change requests."""
    svc = ChangeRequestService(db)
    items, total = await svc.list_mine(current_user.id, status_filter, page, per_page)
    return ChangeRequestListResponse(
        data=[_to_item(cr) for cr in items],
        total=total,
        page=page,
        per_page=per_page,
    )


@router.get("/pending", response_model=ChangeRequestListResponse)
async def list_pending_change_requests(
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=1, le=100),
    _: dict = Depends(require_permission("change_request", "review")),
    db: AsyncSession = Depends(get_db),
):
    """List all submitted change requests (for reviewers)."""
    svc = ChangeRequestService(db)
    items, total = await svc.list_pending(page, per_page)
    return ChangeRequestListResponse(
        data=[_to_item(cr) for cr in items],
        total=total,
        page=page,
        per_page=per_page,
    )


# ------------------------------------------------------------------
# Active CRs by entity type (for branch-aware overlay)
# ------------------------------------------------------------------


@router.get("/active", response_model=list[ChangeRequestDetail])
async def list_active_by_type(
    entity_type: str = Query(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all active (non-terminal) change requests for a given entity type."""
    svc = ChangeRequestService(db)
    items = await svc.list_active_by_entity_type(entity_type)
    return [_to_item(cr, include_snapshot=True) for cr in items]


# ------------------------------------------------------------------
# Entity-specific lookup
# ------------------------------------------------------------------


@router.get("/entity/{entity_type}/{entity_id}", response_model=ChangeRequestDetail | None)
async def get_active_for_entity(
    entity_type: str,
    entity_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get active draft/submitted CR for a specific entity.

    For shared-draft entity types (e.g. wiki_page), returns the shared draft
    regardless of who created it.  For other entity types, scoped to the
    current user.
    """
    svc = ChangeRequestService(db)
    cr = await svc.get_active_for_entity(current_user.id, entity_type, entity_id)
    if not cr:
        return None
    return _to_item(cr, include_snapshot=True)


# ------------------------------------------------------------------
# CRUD
# ------------------------------------------------------------------


@router.get("/{cr_id}", response_model=ChangeRequestDetail)
async def get_change_request(
    cr_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = ChangeRequestService(db)
    cr = await svc.get(cr_id)
    if not cr:
        raise HTTPException(status_code=404, detail="Change request not found")
    return _to_item(cr, include_snapshot=True)


@router.post("", response_model=ChangeRequestDetail, status_code=status.HTTP_201_CREATED)
async def upsert_draft(
    body: ChangeRequestCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create or update a draft change request."""
    svc = ChangeRequestService(db)
    try:
        cr = await svc.upsert_draft(
            user_id=current_user.id,
            entity_type=body.entity_type,
            entity_id=body.entity_id,
            action=body.action,
            title=body.title,
            snapshot=body.snapshot,
            diff_summary=body.diff_summary,
            username=current_user.username,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return _to_item(cr, include_snapshot=True)


@router.delete("/{cr_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_draft(
    cr_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = ChangeRequestService(db)
    try:
        await svc.delete_draft(cr_id, current_user.id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except PermissionError:
        raise HTTPException(status_code=403, detail="Not your change request")


# ------------------------------------------------------------------
# Lifecycle transitions
# ------------------------------------------------------------------


@router.post("/{cr_id}/push-to-dev", response_model=ChangeRequestItem)
async def push_to_dev(
    cr_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Push a draft change request to the shared dev branch."""
    svc = ChangeRequestService(db)
    try:
        cr = await svc.push_to_dev(cr_id, current_user.id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except PermissionError:
        raise HTTPException(status_code=403, detail="Not your change request")
    return _to_item(cr)


@router.post("/{cr_id}/submit", response_model=ChangeRequestItem)
async def submit_change_request(
    cr_id: UUID,
    body: ChangeRequestReview | None = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = ChangeRequestService(db)
    try:
        cr = await svc.submit(cr_id, current_user.id, comment=body.comment if body else None)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except PermissionError:
        raise HTTPException(status_code=403, detail="Not your change request")
    return _to_item(cr)


@router.post("/{cr_id}/withdraw", response_model=ChangeRequestItem)
async def withdraw_change_request(
    cr_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = ChangeRequestService(db)
    try:
        cr = await svc.withdraw(cr_id, current_user.id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except PermissionError:
        raise HTTPException(status_code=403, detail="Not your change request")
    return _to_item(cr)


@router.post("/{cr_id}/approve", response_model=ChangeRequestItem)
async def approve_change_request(
    cr_id: UUID,
    body: ChangeRequestReview | None = None,
    payload: dict = Depends(require_permission("change_request", "review")),
    db: AsyncSession = Depends(get_db),
):
    reviewer_id = UUID(payload["sub"])
    svc = ChangeRequestService(db)
    try:
        cr = await svc.approve(cr_id, reviewer_id, body.comment if body else None)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return _to_item(cr)


@router.post("/{cr_id}/reject", response_model=ChangeRequestItem)
async def reject_change_request(
    cr_id: UUID,
    body: ChangeRequestReview | None = None,
    payload: dict = Depends(require_permission("change_request", "review")),
    db: AsyncSession = Depends(get_db),
):
    reviewer_id = UUID(payload["sub"])
    svc = ChangeRequestService(db)
    try:
        cr = await svc.reject(cr_id, reviewer_id, body.comment if body else None)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return _to_item(cr)


@router.post("/{cr_id}/apply", response_model=ChangeRequestItem)
async def apply_change_request(
    cr_id: UUID,
    body: ChangeRequestReview | None = None,
    _: dict = Depends(require_permission("change_request", "review")),
    db: AsyncSession = Depends(get_db),
):
    svc = ChangeRequestService(db)
    try:
        cr = await svc.apply(cr_id, comment=body.comment if body else None)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return _to_item(cr)

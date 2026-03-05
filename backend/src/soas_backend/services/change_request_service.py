"""Change request service for dev/prod draft workflow."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from soas_backend.models.change_request import ChangeRequest

logger = logging.getLogger(__name__)

VALID_STATUSES = {"draft", "submitted", "approved", "rejected", "applied", "withdrawn", "pushed_to_dev"}
VALID_ACTIONS = {"create", "update", "delete"}


class ChangeRequestService:
    def __init__(self, db: AsyncSession):
        self.db = db

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    async def list_mine(
        self,
        user_id: UUID,
        status_filter: str | None = None,
        page: int = 1,
        per_page: int = 25,
    ) -> tuple[list[ChangeRequest], int]:
        q = select(ChangeRequest).where(ChangeRequest.created_by == user_id)
        count_q = select(func.count(ChangeRequest.id)).where(ChangeRequest.created_by == user_id)

        if status_filter and status_filter in VALID_STATUSES:
            q = q.where(ChangeRequest.status == status_filter)
            count_q = count_q.where(ChangeRequest.status == status_filter)

        total = (await self.db.execute(count_q)).scalar() or 0
        q = q.order_by(ChangeRequest.updated_at.desc())
        q = q.offset((page - 1) * per_page).limit(per_page)
        result = await self.db.execute(q)
        return list(result.scalars().all()), total

    async def list_pending(
        self,
        page: int = 1,
        per_page: int = 25,
    ) -> tuple[list[ChangeRequest], int]:
        q = select(ChangeRequest).where(ChangeRequest.status == "submitted")
        count_q = select(func.count(ChangeRequest.id)).where(ChangeRequest.status == "submitted")

        total = (await self.db.execute(count_q)).scalar() or 0
        q = q.order_by(ChangeRequest.updated_at.desc())
        q = q.offset((page - 1) * per_page).limit(per_page)
        result = await self.db.execute(q)
        return list(result.scalars().all()), total

    async def get(self, cr_id: UUID) -> ChangeRequest | None:
        result = await self.db.execute(
            select(ChangeRequest).where(ChangeRequest.id == cr_id)
        )
        return result.scalar_one_or_none()

    async def get_active_for_entity(
        self, user_id: UUID, entity_type: str, entity_id: UUID | None
    ) -> ChangeRequest | None:
        """Get the active draft/submitted CR for a specific entity by this user."""
        q = select(ChangeRequest).where(
            ChangeRequest.created_by == user_id,
            ChangeRequest.entity_type == entity_type,
            ChangeRequest.status.in_(["draft", "submitted", "pushed_to_dev"]),
        )
        if entity_id is not None:
            q = q.where(ChangeRequest.entity_id == entity_id)
        else:
            q = q.where(ChangeRequest.entity_id.is_(None))
        result = await self.db.execute(q)
        return result.scalar_one_or_none()

    # ------------------------------------------------------------------
    # Mutations
    # ------------------------------------------------------------------

    async def upsert_draft(
        self,
        user_id: UUID,
        entity_type: str,
        entity_id: UUID | None,
        action: str,
        title: str,
        snapshot: dict,
        diff_summary: dict | None = None,
        username: str | None = None,
    ) -> ChangeRequest:
        """Create or update a draft change request.

        If *username* is provided the snapshot is also committed to the
        user's git branch via ``BranchVersionService``.
        """
        existing = await self.get_active_for_entity(user_id, entity_type, entity_id)

        if existing and existing.status == "submitted":
            raise ValueError("Cannot update a submitted change request. Withdraw it first.")

        # Commit to user's git branch if possible
        git_sha: str | None = None
        git_branch: str | None = None
        if username:
            try:
                from soas_backend.services.branch_version_service import BranchVersionService
                bvs = BranchVersionService(self.db)
                git_sha, git_branch = bvs.save_user_draft(
                    username, entity_type, str(entity_id) if entity_id else None, snapshot
                )
            except Exception:
                logger.warning("Git branch commit failed for %s draft", entity_type, exc_info=True)

        if existing:
            existing.title = title
            existing.snapshot = snapshot
            existing.diff_summary = diff_summary
            existing.action = action
            if git_sha:
                existing.git_sha = git_sha
            if git_branch:
                existing.git_branch = git_branch
            await self.db.flush()
            return existing

        cr = ChangeRequest(
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            title=title,
            snapshot=snapshot,
            diff_summary=diff_summary,
            status="draft",
            created_by=user_id,
            git_branch=git_branch,
            git_sha=git_sha,
        )
        self.db.add(cr)
        await self.db.flush()
        return cr

    async def push_to_dev(self, cr_id: UUID, user_id: UUID, username: str) -> ChangeRequest:
        """Push a draft to the shared dev branch and update status."""
        from soas_backend.services.branch_version_service import BranchVersionService

        cr = await self.get(cr_id)
        if not cr:
            raise ValueError("Change request not found")
        if cr.created_by != user_id:
            raise PermissionError("Not your change request")
        if cr.status != "draft":
            raise ValueError(f"Cannot push a {cr.status} change request to dev")

        bvs = BranchVersionService(self.db)
        result = bvs.push_to_dev(username)

        if result.status == "conflict":
            raise ValueError(f"Merge conflict on files: {', '.join(result.conflicts)}")

        cr.status = "pushed_to_dev"
        if result.sha:
            cr.git_sha = result.sha
        await self.db.flush()
        return cr

    async def submit(self, cr_id: UUID, user_id: UUID) -> ChangeRequest:
        cr = await self.get(cr_id)
        if not cr:
            raise ValueError("Change request not found")
        if cr.created_by != user_id:
            raise PermissionError("Not your change request")
        if cr.status != "draft":
            raise ValueError(f"Cannot submit a {cr.status} change request")
        cr.status = "submitted"
        await self.db.flush()
        return cr

    async def withdraw(self, cr_id: UUID, user_id: UUID) -> ChangeRequest:
        cr = await self.get(cr_id)
        if not cr:
            raise ValueError("Change request not found")
        if cr.created_by != user_id:
            raise PermissionError("Not your change request")
        if cr.status != "submitted":
            raise ValueError(f"Cannot withdraw a {cr.status} change request")
        cr.status = "withdrawn"
        await self.db.flush()
        return cr

    async def approve(self, cr_id: UUID, reviewer_id: UUID, comment: str | None = None) -> ChangeRequest:
        cr = await self.get(cr_id)
        if not cr:
            raise ValueError("Change request not found")
        if cr.status != "submitted":
            raise ValueError(f"Cannot approve a {cr.status} change request")
        cr.status = "approved"
        cr.reviewed_by = reviewer_id
        cr.review_comment = comment
        cr.reviewed_at = datetime.now(timezone.utc)
        await self.db.flush()
        return cr

    async def reject(self, cr_id: UUID, reviewer_id: UUID, comment: str | None = None) -> ChangeRequest:
        cr = await self.get(cr_id)
        if not cr:
            raise ValueError("Change request not found")
        if cr.status != "submitted":
            raise ValueError(f"Cannot reject a {cr.status} change request")
        cr.status = "rejected"
        cr.reviewed_by = reviewer_id
        cr.review_comment = comment
        cr.reviewed_at = datetime.now(timezone.utc)
        await self.db.flush()
        return cr

    async def apply(self, cr_id: UUID) -> ChangeRequest:
        """Apply an approved change request to the live entity."""
        from soas_backend.services.change_request_appliers import APPLIER_REGISTRY

        cr = await self.get(cr_id)
        if not cr:
            raise ValueError("Change request not found")
        if cr.status != "approved":
            raise ValueError(f"Cannot apply a {cr.status} change request")

        applier = APPLIER_REGISTRY.get(cr.entity_type)
        if not applier:
            raise ValueError(f"No applier for entity type: {cr.entity_type}")

        await applier(self.db, cr.snapshot, cr.entity_id, cr.action, cr.created_by)
        cr.status = "applied"
        await self.db.flush()
        return cr

    async def delete_draft(self, cr_id: UUID, user_id: UUID) -> None:
        cr = await self.get(cr_id)
        if not cr:
            raise ValueError("Change request not found")
        if cr.created_by != user_id:
            raise PermissionError("Not your change request")
        if cr.status != "draft":
            raise ValueError("Can only delete draft change requests")
        await self.db.delete(cr)
        await self.db.flush()

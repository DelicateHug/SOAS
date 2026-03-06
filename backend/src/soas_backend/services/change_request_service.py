"""Change request service for dev/prod draft workflow."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from soas_backend.models.change_request import ChangeRequest

logger = logging.getLogger(__name__)

VALID_STATUSES = {"draft", "submitted", "approved", "rejected", "applied", "withdrawn", "pushed_to_dev"}
VALID_ACTIONS = {"create", "update", "delete"}

# Entity types that use a single shared draft (collaborative editing).
# All other entity types use per-user drafts.
SHARED_DRAFT_ENTITY_TYPES = {"wiki_page"}


class ChangeRequestService:
    def __init__(self, db: AsyncSession):
        self.db = db

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def _with_users(self, q):
        return q.options(selectinload(ChangeRequest.creator), selectinload(ChangeRequest.reviewer))

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
        q = self._with_users(q).order_by(ChangeRequest.updated_at.desc())
        q = q.offset((page - 1) * per_page).limit(per_page)
        result = await self.db.execute(q)
        return list(result.scalars().all()), total

    async def list_pending(
        self,
        page: int = 1,
        per_page: int = 25,
    ) -> tuple[list[ChangeRequest], int]:
        q = select(ChangeRequest).where(ChangeRequest.status.in_(["submitted", "approved"]))
        count_q = select(func.count(ChangeRequest.id)).where(ChangeRequest.status.in_(["submitted", "approved"]))

        total = (await self.db.execute(count_q)).scalar() or 0
        q = self._with_users(q).order_by(ChangeRequest.updated_at.desc())
        q = q.offset((page - 1) * per_page).limit(per_page)
        result = await self.db.execute(q)
        return list(result.scalars().all()), total

    async def list_active_by_entity_type(
        self, entity_type: str
    ) -> list[ChangeRequest]:
        """Return all non-terminal change requests for a given entity type."""
        q = select(ChangeRequest).where(
            ChangeRequest.entity_type == entity_type,
            ChangeRequest.status.in_(["draft", "pushed_to_dev", "submitted", "approved"]),
        )
        q = self._with_users(q).order_by(ChangeRequest.updated_at.desc())
        result = await self.db.execute(q)
        return list(result.scalars().all())

    async def get(self, cr_id: UUID) -> ChangeRequest | None:
        result = await self.db.execute(
            self._with_users(select(ChangeRequest).where(ChangeRequest.id == cr_id))
        )
        return result.scalar_one_or_none()

    async def get_active_for_entity(
        self, user_id: UUID, entity_type: str, entity_id: UUID | None
    ) -> ChangeRequest | None:
        """Get the active draft/submitted CR for a specific entity.

        For shared-draft entity types (e.g. wiki_page), returns the shared
        draft regardless of who created it.  For other entity types, scoped
        to the given *user_id*.

        Prioritises drafts so that ``upsert_draft`` can update an existing
        draft even when a separate submitted/approved CR also exists.
        """
        q = select(ChangeRequest).where(
            ChangeRequest.entity_type == entity_type,
            ChangeRequest.status.in_(["draft", "submitted", "approved"]),
        )

        # Per-user filtering only for non-shared entity types
        if entity_type not in SHARED_DRAFT_ENTITY_TYPES:
            q = q.where(ChangeRequest.created_by == user_id)

        if entity_id is not None:
            q = q.where(ChangeRequest.entity_id == entity_id)
        else:
            q = q.where(ChangeRequest.entity_id.is_(None))

        # Prefer drafts first, then most-recently-updated
        q = q.order_by(
            ChangeRequest.status != "draft",
            ChangeRequest.updated_at.desc(),
        )
        result = await self.db.execute(self._with_users(q.limit(1)))
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

        For shared-draft entity types (e.g. wiki_page), any user can update
        the single shared draft.  For other entity types, drafts are per-user.

        If *username* is provided the snapshot is also committed to the
        user's git branch via ``BranchVersionService``.
        """
        existing = await self.get_active_for_entity(user_id, entity_type, entity_id)

        # If the existing CR is already submitted/approved/pushed, start fresh.
        # The old CR continues through its review lifecycle independently.
        if existing and existing.status in ("submitted", "approved", "pushed_to_dev"):
            existing = None

        # Commit to user's git branch if possible
        git_sha: str | None = None
        git_branch: str | None = None
        if username:
            try:
                from soas_backend.services.branch_version_service import BranchVersionService
                bvs = BranchVersionService(self.db)
                git_sha, git_branch = await bvs.save_user_draft(
                    username, entity_type, str(entity_id) if entity_id else None, snapshot,
                    action=action,
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
            return await self.get(existing.id)  # type: ignore[return-value]

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
        return await self.get(cr.id)  # type: ignore[return-value]

    def _can_manage_cr(self, cr: ChangeRequest, user_id: UUID) -> bool:
        """Check if a user can manage (submit/push/withdraw) a change request."""
        if cr.entity_type in SHARED_DRAFT_ENTITY_TYPES:
            return True  # any collaborator can manage shared drafts
        return cr.created_by == user_id

    async def push_to_dev(self, cr_id: UUID, user_id: UUID, force: bool = False) -> ChangeRequest:
        """Push a draft's entity branch to the shared dev branch and update status."""
        from soas_backend.services.branch_version_service import BranchVersionService

        cr = await self.get(cr_id)
        if not cr:
            raise ValueError("Change request not found")
        if not self._can_manage_cr(cr, user_id):
            raise PermissionError("Not your change request")
        if cr.status not in ("draft", "pushed_to_dev"):
            raise ValueError(f"Cannot push a {cr.status} change request to dev")
        if not cr.git_branch:
            raise ValueError("Change request has no associated git branch")

        bvs = BranchVersionService(self.db)
        result = await bvs.push_to_dev(cr.git_branch, force=force)

        if result.status == "conflict":
            raise ValueError(f"Merge conflict on files: {', '.join(result.conflicts)}")

        cr.status = "pushed_to_dev"
        if result.sha:
            cr.git_sha = result.sha
        await self.db.flush()
        return await self.get(cr_id)  # type: ignore[return-value]

    async def submit(self, cr_id: UUID, user_id: UUID, comment: str | None = None) -> ChangeRequest:
        cr = await self.get(cr_id)
        if not cr:
            raise ValueError("Change request not found")
        if not self._can_manage_cr(cr, user_id):
            raise PermissionError("Not your change request")
        if cr.status != "draft":
            raise ValueError(f"Cannot submit a {cr.status} change request")

        # Capture creator name before flush/refresh (avoids lazy-load MissingGreenlet)
        creator_name = cr.creator.display_name if cr.creator else "Unknown"

        cr.status = "submitted"
        if comment:
            cr.submit_comment = comment
        await self.db.flush()

        # Push entity branch to remote so reviewers can see it
        if cr.git_branch:
            try:
                from soas_backend.services.branch_version_service import BranchVersionService
                bvs = BranchVersionService(self.db)
                wt = bvs.ensure_entity_branch(cr.git_branch)
                await bvs._push_remote(wt)
            except Exception:
                logger.warning("Remote push on submit failed for branch %s", cr.git_branch, exc_info=True)

            # Create GitHub PR for tracking/documentation
            try:
                from soas_backend.services.github_service import create_pull_request
                from soas_backend.services.git_sync_service import GitSyncService
                config = await GitSyncService(self.db).get_config()
                if config.remote_url and config.auth_token:
                    pr_body = (
                        f"## Change Request\n\n"
                        f"- **Submitted by:** {creator_name}\n"
                        f"- **Entity type:** {cr.entity_type}\n"
                        f"- **Action:** {cr.action}\n"
                        f"- **Title:** {cr.title}\n"
                    )
                    if comment:
                        pr_body += f"- **Comment:** {comment}\n"
                    if cr.diff_summary:
                        pr_body += f"\n### Diff Summary\n```json\n{cr.diff_summary}\n```\n"
                    pr_body += "\n*Managed by SOAS - review and approve in the SOAS UI.*"

                    pr_info = await create_pull_request(
                        remote_url=config.remote_url,
                        auth_token=config.auth_token,
                        head_branch=cr.git_branch,
                        base_branch="dev",
                        title=f"[{cr.entity_type}] {cr.title}",
                        body=pr_body,
                    )
                    if pr_info:
                        cr.git_pr_url = pr_info["html_url"]
                        await self.db.flush()
            except Exception:
                logger.warning("GitHub PR creation failed for CR %s", cr_id, exc_info=True)

        # Re-fetch with eager-loaded relationships for serialization
        return await self.get(cr_id)  # type: ignore[return-value]

    async def withdraw(self, cr_id: UUID, user_id: UUID) -> ChangeRequest:
        cr = await self.get(cr_id)
        if not cr:
            raise ValueError("Change request not found")
        if not self._can_manage_cr(cr, user_id):
            raise PermissionError("Not your change request")
        if cr.status != "submitted":
            raise ValueError(f"Cannot withdraw a {cr.status} change request")
        cr.status = "withdrawn"
        await self.db.flush()
        return await self.get(cr_id)  # type: ignore[return-value]

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
        return await self.get(cr_id)  # type: ignore[return-value]

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
        return await self.get(cr_id)  # type: ignore[return-value]

    async def apply(self, cr_id: UUID, comment: str | None = None) -> ChangeRequest:
        """Apply an approved change request to the live entity and merge its git branch to dev."""
        from soas_backend.services.change_request_appliers import APPLIER_REGISTRY
        from soas_backend.services.branch_version_service import BranchVersionService

        cr = await self.get(cr_id)
        if not cr:
            raise ValueError("Change request not found")
        if cr.status != "approved":
            raise ValueError(f"Cannot apply a {cr.status} change request")

        # If a comment was provided at apply time, update the review_comment
        if comment:
            cr.review_comment = comment
            await self.db.flush()

        applier = APPLIER_REGISTRY.get(cr.entity_type)
        if not applier:
            raise ValueError(f"No applier for entity type: {cr.entity_type}")

        await applier(self.db, cr.snapshot, cr.entity_id, cr.action, cr.created_by)

        # Merge entity branch → dev, then clean up the branch
        if cr.git_branch:
            bvs = BranchVersionService(self.db)

            # Merge the GitHub PR if one exists
            if cr.git_pr_url:
                try:
                    from soas_backend.services.github_service import (
                        merge_pull_request, extract_pr_number, add_pr_comment,
                    )
                    from soas_backend.services.git_sync_service import GitSyncService
                    config = await GitSyncService(self.db).get_config()
                    pr_number = extract_pr_number(cr.git_pr_url)
                    if pr_number and config.remote_url and config.auth_token:
                        # Add review details as PR comment before merging
                        reviewer_name = cr.reviewer.display_name if cr.reviewer else "Unknown"
                        merge_comment = f"**Approved by:** {reviewer_name}\n"
                        if cr.submit_comment:
                            merge_comment += f"**Submitter comment:** {cr.submit_comment}\n"
                        if cr.review_comment:
                            merge_comment += f"**Review comment:** {cr.review_comment}\n"
                        merge_comment += "\nApplied to live database via SOAS."
                        await add_pr_comment(
                            remote_url=config.remote_url,
                            auth_token=config.auth_token,
                            pr_number=pr_number,
                            body=merge_comment,
                        )
                        await merge_pull_request(
                            remote_url=config.remote_url,
                            auth_token=config.auth_token,
                            pr_number=pr_number,
                        )
                except Exception:
                    logger.warning(
                        "GitHub PR merge failed for CR %s (PR %s)", cr_id, cr.git_pr_url,
                        exc_info=True,
                    )

            # Local merge entity branch → dev
            try:
                await bvs.push_to_dev(cr.git_branch)
            except Exception:
                logger.warning(
                    "Git merge to dev failed for CR %s (branch %s)", cr_id, cr.git_branch,
                    exc_info=True,
                )

            # Clean up: remove worktree, local branch, remote branch
            try:
                await bvs.cleanup_entity_branch(cr.git_branch)
            except Exception:
                logger.warning(
                    "Git branch cleanup failed for CR %s (branch %s)", cr_id, cr.git_branch,
                    exc_info=True,
                )

        cr.status = "applied"
        await self.db.flush()
        return await self.get(cr_id)  # type: ignore[return-value]

    async def delete_draft(self, cr_id: UUID, user_id: UUID) -> None:
        cr = await self.get(cr_id)
        if not cr:
            raise ValueError("Change request not found")
        if not self._can_manage_cr(cr, user_id):
            raise PermissionError("Not your change request")
        if cr.status not in ("draft", "submitted"):
            raise ValueError("Can only delete draft or submitted change requests")
        await self.db.delete(cr)
        await self.db.flush()

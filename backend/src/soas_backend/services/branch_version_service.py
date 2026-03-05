"""Three-tier git branching versioning service.

Manages the flow:  user draft (user/{username} branch)
                 → push to dev (dev branch)
                 → promote to prod (main branch)

Uses git worktrees so each branch has its own filesystem path and
concurrent operations don't conflict.
"""

from __future__ import annotations

import logging
from pathlib import Path
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from soas_backend.services import git_ops
from soas_backend.services.git_ops import MergeResult
from soas_backend.services.git_serializers import (
    export_one,
    read_one,
    read_all_of_type,
    ENTITY_TYPE_TO_SERIALIZER_KEY,
)
from soas_backend.services.change_request_appliers import APPLIER_REGISTRY

logger = logging.getLogger(__name__)

DEFAULT_REPO_PATH = "data/git-sync"
DEFAULT_WORKTREE_BASE = "data/git-sync-worktrees"
PROD_BRANCH = "main"
DEV_BRANCH = "dev"


def _user_branch(username: str) -> str:
    """Git branch name for a user's drafts."""
    return f"user/{username}"


def _user_worktree_name(username: str) -> str:
    """Filesystem-safe directory name for a user worktree."""
    return f"user--{username.replace('/', '--')}"


class BranchVersionService:
    """Orchestrates the three-tier branching workflow."""

    def __init__(self, db: AsyncSession, repo_path: str = DEFAULT_REPO_PATH):
        self.db = db
        self.repo_path = Path(repo_path).resolve()
        self.worktree_base = Path(DEFAULT_WORKTREE_BASE).resolve()

    # ------------------------------------------------------------------
    # Branch / worktree lifecycle
    # ------------------------------------------------------------------

    def _dev_worktree(self) -> Path:
        return self.worktree_base / "dev"

    def _user_worktree(self, username: str) -> Path:
        return self.worktree_base / _user_worktree_name(username)

    def _ensure_repo(self) -> None:
        if not self.repo_path.exists() or not git_ops.is_repo(self.repo_path):
            raise git_ops.GitOpsError(
                "Git sync repository not initialized. Run git sync setup first."
            )

    def ensure_dev_branch(self) -> Path:
        """Create dev branch + worktree if they don't exist.  Returns worktree path."""
        self._ensure_repo()
        git_ops.create_branch(self.repo_path, DEV_BRANCH, PROD_BRANCH)
        wt = self._dev_worktree()
        git_ops.add_worktree(self.repo_path, wt, DEV_BRANCH)
        return wt

    def ensure_user_branch(self, username: str) -> Path:
        """Create user branch + worktree from dev.  Returns worktree path."""
        self._ensure_repo()
        # Dev must exist first
        self.ensure_dev_branch()
        branch = _user_branch(username)
        git_ops.create_branch(self.repo_path, branch, DEV_BRANCH)
        wt = self._user_worktree(username)
        git_ops.add_worktree(self.repo_path, wt, branch)
        return wt

    def cleanup_user_branch(self, username: str) -> None:
        """Remove a user's worktree and branch."""
        wt = self._user_worktree(username)
        if wt.exists():
            git_ops.remove_worktree(self.repo_path, wt)

    # ------------------------------------------------------------------
    # Read entity at a specific tier
    # ------------------------------------------------------------------

    def get_entity_at_tier(
        self,
        entity_type: str,
        entity_id: str,
        tier: str,
        username: str | None = None,
    ) -> dict | None:
        """Read an entity snapshot from a specific tier.

        tier = "prod" → main repo path (main branch)
        tier = "dev"  → dev worktree
        tier = "user" → user/{username} worktree
        """
        if tier == "prod":
            base = self.repo_path
        elif tier == "dev":
            base = self._dev_worktree()
        elif tier == "user" and username:
            base = self._user_worktree(username)
        else:
            return None

        if not base.exists():
            return None
        return read_one(entity_type, entity_id, base)

    def get_effective_entity(
        self,
        username: str,
        entity_type: str,
        entity_id: str,
    ) -> tuple[dict | None, str]:
        """Get the version the user should see: user draft > dev > prod.

        Returns ``(snapshot, source_tier)``.
        """
        # Try user branch first
        user_ver = self.get_entity_at_tier(entity_type, entity_id, "user", username)
        if user_ver is not None:
            return user_ver, "user"

        dev_ver = self.get_entity_at_tier(entity_type, entity_id, "dev")
        if dev_ver is not None:
            return dev_ver, "dev"

        prod_ver = self.get_entity_at_tier(entity_type, entity_id, "prod")
        if prod_ver is not None:
            return prod_ver, "prod"

        return None, "prod"

    def list_entities_at_tier(
        self,
        entity_type: str,
        tier: str,
        username: str | None = None,
    ) -> list[dict]:
        """List all entities of a type at a tier."""
        if tier == "prod":
            base = self.repo_path
        elif tier == "dev":
            base = self._dev_worktree()
        elif tier == "user" and username:
            base = self._user_worktree(username)
        else:
            return []
        if not base.exists():
            return []
        return read_all_of_type(entity_type, base)

    # ------------------------------------------------------------------
    # Save user draft
    # ------------------------------------------------------------------

    def save_user_draft(
        self,
        username: str,
        entity_type: str,
        entity_id: str | None,
        snapshot: dict,
    ) -> tuple[str | None, str]:
        """Write entity to user's branch and commit.

        Returns ``(git_sha, git_branch)``.
        """
        wt = self.ensure_user_branch(username)
        export_one(entity_type, snapshot, wt)
        sha = git_ops.commit_in_path(
            wt, f"Draft: {entity_type} {snapshot.get('name') or snapshot.get('title') or entity_id or 'new'}"
        )
        branch = _user_branch(username)
        return sha, branch

    # ------------------------------------------------------------------
    # Push to dev
    # ------------------------------------------------------------------

    def push_to_dev(self, username: str, force: bool = False) -> MergeResult:
        """Merge user's branch into dev.

        If *force* is True, uses ``-X theirs`` strategy to overwrite dev
        with the user's version on conflict.
        """
        self.ensure_user_branch(username)
        dev_wt = self.ensure_dev_branch()

        strategy = "theirs" if force else None
        branch = _user_branch(username)
        result = git_ops.merge_branch(
            dev_wt,
            branch,
            message=f"Push from {username} to dev",
            strategy_option=strategy,
        )
        return result

    # ------------------------------------------------------------------
    # Promote dev → prod
    # ------------------------------------------------------------------

    async def promote_to_prod(self) -> MergeResult:
        """Merge dev branch into main (prod).

        After merging, imports changed entities from the repo files into
        the live database tables.
        """
        self.ensure_dev_branch()

        result = git_ops.merge_branch(
            self.repo_path,  # main repo is on main branch
            DEV_BRANCH,
            message="Promote dev to prod",
        )

        if result.status == "merged":
            # Import changed entities to live DB
            await self._apply_changes_to_db()

        return result

    async def _apply_changes_to_db(self) -> None:
        """After merging dev → main, import the changed files into live DB.

        Uses the change_request_appliers for each entity type found in the
        diff between the previous and current main HEAD.
        """
        # Get files that changed in the last merge commit
        changed = git_ops.get_changed_files(self.repo_path)
        if not changed:
            return

        # Group by entity type directory
        for filepath in changed:
            parts = filepath.split("/")
            if len(parts) < 2:
                continue
            directory = parts[0]

            # Find which entity type this directory maps to
            entity_type = None
            for et, sk in ENTITY_TYPE_TO_SERIALIZER_KEY.items():
                from soas_backend.services.git_serializers import _serializer_dir
                if _serializer_dir(et) == directory:
                    entity_type = et
                    break

            if not entity_type or entity_type not in APPLIER_REGISTRY:
                continue

            # Read the entity from the prod (main) branch files
            snapshot = read_one(entity_type, "", self.repo_path)
            if snapshot and snapshot.get("id"):
                applier = APPLIER_REGISTRY[entity_type]
                try:
                    entity_id = UUID(snapshot["id"]) if snapshot.get("id") else None
                    await applier(self.db, snapshot, entity_id, "update", None)
                except Exception:
                    logger.exception(
                        "Failed to apply promoted entity %s/%s",
                        entity_type, snapshot.get("id"),
                    )
        await self.db.flush()

    # ------------------------------------------------------------------
    # Rebase user from dev
    # ------------------------------------------------------------------

    def rebase_user_from_dev(self, username: str) -> MergeResult:
        """Merge dev into user branch so user picks up latest dev changes."""
        wt = self.ensure_user_branch(username)
        return git_ops.merge_branch(
            wt, DEV_BRANCH, message=f"Rebase {username} from dev"
        )

    # ------------------------------------------------------------------
    # Diff helpers
    # ------------------------------------------------------------------

    def diff_dev_prod(self) -> list[str]:
        """List files that differ between dev and prod."""
        if not self.repo_path.exists():
            return []
        return git_ops.diff_branches(self.repo_path, PROD_BRANCH, DEV_BRANCH)

    def diff_user_dev(self, username: str) -> list[str]:
        """List files that differ between user branch and dev."""
        if not self.repo_path.exists():
            return []
        return git_ops.diff_branches(self.repo_path, DEV_BRANCH, _user_branch(username))

    # ------------------------------------------------------------------
    # Branch info
    # ------------------------------------------------------------------

    def list_branches(self) -> list[dict]:
        """List all branches with metadata."""
        if not self.repo_path.exists():
            return []
        branches = git_ops.list_branches(self.repo_path)
        result = []
        for b in branches:
            sha = git_ops.branch_commit_sha(self.repo_path, b)
            result.append({
                "name": b,
                "sha": sha,
                "is_user": b.startswith("user/"),
                "is_dev": b == DEV_BRANCH,
                "is_prod": b == PROD_BRANCH,
            })
        return result

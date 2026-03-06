"""Three-tier git branching versioning service.

Manages the flow:  user draft (user/{username}/{entity_dir}/{slug} branch)
                 → push to dev (dev branch)
                 → promote to prod (main branch)

Uses git worktrees so each branch has its own filesystem path and
concurrent operations don't conflict.

Branch naming: user/{username}/{entity_dir}/{slug}
  e.g. user/admin/users/bob   (role assignment for user bob)
       user/alice/automations/my-playbook
"""

from __future__ import annotations

import logging
import re
import uuid as _uuid
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
    _serializer_dir,
)
from soas_backend.services.change_request_appliers import APPLIER_REGISTRY

logger = logging.getLogger(__name__)

DEFAULT_REPO_PATH = "data/git-sync"
DEFAULT_WORKTREE_BASE = "data/git-sync-worktrees"
PROD_BRANCH = "main"
DEV_BRANCH = "dev"

# Maps entity_type → branch directory segment.
# Most types use the same directory as their git serializer.
# user_role uses "users" to match the human-readable naming
# (e.g. user/admin/users/bob).
ENTITY_BRANCH_DIRS: dict[str, str] = {
    "user_role": "users",
}
# Fill remaining from serializer registry
for _et, _sk in ENTITY_TYPE_TO_SERIALIZER_KEY.items():
    if _et not in ENTITY_BRANCH_DIRS:
        ENTITY_BRANCH_DIRS[_et] = _serializer_dir(_et)


def _slugify(text: str, max_len: int = 40) -> str:
    """Convert arbitrary text to a safe git branch segment."""
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    text = text.strip("-")
    return text[:max_len]


def _entity_slug(entity_type: str, snapshot: dict, entity_id: str | None) -> str:
    """Return a human-readable slug for an entity, used in branch naming."""
    # user_role: use target username
    if entity_type == "user_role":
        raw = snapshot.get("target_username") or snapshot.get("username") or ""
    else:
        raw = (
            snapshot.get("name")
            or snapshot.get("title")
            or snapshot.get("display_name")
            or snapshot.get("key")
            or ""
        )
    if not raw and entity_id:
        raw = str(entity_id)[:8]
    return _slugify(raw) if raw else "unknown"


def _entity_branch(
    username: str,
    entity_type: str,
    snapshot: dict,
    entity_id: str | None,
) -> str:
    """Build the per-entity branch name.

    Format: user/{username}/{entity_dir}/{slug}-{short_uuid}

    A short UUID suffix is appended to guarantee uniqueness even when
    the same entity is edited multiple times (after previous CRs are
    applied and cleaned up).
    """
    entity_dir = ENTITY_BRANCH_DIRS.get(entity_type, entity_type.replace("_", "-"))
    slug = _entity_slug(entity_type, snapshot, entity_id)
    short_id = _uuid.uuid4().hex[:8]
    return f"user/{username}/{entity_dir}/{slug}-{short_id}"


def _entity_worktree_name(branch: str) -> str:
    """Filesystem-safe directory name derived from a branch name."""
    return branch.replace("/", "--")


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

    def _entity_worktree(self, entity_branch: str) -> Path:
        return self.worktree_base / _entity_worktree_name(entity_branch)

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

    def ensure_entity_branch(self, entity_branch: str) -> Path:
        """Create per-entity branch + worktree from dev.  Returns worktree path."""
        self._ensure_repo()
        self.ensure_dev_branch()
        git_ops.create_branch(self.repo_path, entity_branch, DEV_BRANCH)
        wt = self._entity_worktree(entity_branch)
        git_ops.add_worktree(self.repo_path, wt, entity_branch)
        return wt

    async def cleanup_entity_branch(self, entity_branch: str) -> None:
        """Remove an entity branch: worktree, local branch, and remote branch."""
        wt = self._entity_worktree(entity_branch)
        if wt.exists():
            git_ops.remove_worktree(self.repo_path, wt)
        # Delete local branch
        git_ops.delete_branch(self.repo_path, entity_branch)
        # Delete remote branch (non-fatal)
        try:
            from soas_backend.services.git_sync_service import GitSyncService
            config = await GitSyncService(self.db).get_config()
            if config.remote_url:
                git_ops.delete_remote_branch(
                    self.repo_path, entity_branch,
                    auth_type=config.auth_type,
                    auth_token=config.auth_token,
                    ssh_key_path=config.ssh_key_path,
                )
        except Exception:
            logger.warning("Failed to delete remote branch %s", entity_branch, exc_info=True)

    # ------------------------------------------------------------------
    # Read entity at a specific tier
    # ------------------------------------------------------------------

    def get_entity_at_tier(
        self,
        entity_type: str,
        entity_id: str,
        tier: str,
        entity_branch: str | None = None,
    ) -> dict | None:
        """Read an entity snapshot from a specific tier.

        tier = "prod"  → main repo path (main branch)
        tier = "dev"   → dev worktree
        tier = "user"  → entity branch worktree (requires entity_branch)
        """
        if tier == "prod":
            base = self.repo_path
        elif tier == "dev":
            base = self._dev_worktree()
        elif tier == "user" and entity_branch:
            base = self._entity_worktree(entity_branch)
        else:
            return None

        if not base.exists():
            return None
        return read_one(entity_type, entity_id, base)

    def get_effective_entity(
        self,
        entity_type: str,
        entity_id: str,
        entity_branch: str | None = None,
    ) -> tuple[dict | None, str]:
        """Get the most current version of an entity: user draft > dev > prod.

        Pass *entity_branch* (e.g. ``cr.git_branch``) to check the user tier.
        Returns ``(snapshot, source_tier)``.
        """
        if entity_branch:
            user_ver = self.get_entity_at_tier(entity_type, entity_id, "user", entity_branch)
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
        entity_branch: str | None = None,
    ) -> list[dict]:
        """List all entities of a type at a tier."""
        if tier == "prod":
            base = self.repo_path
        elif tier == "dev":
            base = self._dev_worktree()
        elif tier == "user" and entity_branch:
            base = self._entity_worktree(entity_branch)
        else:
            return []
        if not base.exists():
            return []
        return read_all_of_type(entity_type, base)

    # ------------------------------------------------------------------
    # Remote push helper
    # ------------------------------------------------------------------

    async def _pull_remote(self, worktree_path: Path) -> None:
        """Pull latest from remote for the branch at *worktree_path*, if any."""
        try:
            from soas_backend.services.git_sync_service import GitSyncService
            config = await GitSyncService(self.db).get_config()
            if not config.remote_url:
                return
            git_ops.pull(
                worktree_path,
                auth_type=config.auth_type,
                auth_token=config.auth_token,
                ssh_key_path=config.ssh_key_path,
            )
        except Exception:
            logger.warning("Remote pull failed for %s", worktree_path, exc_info=True)

    async def _push_remote(self, worktree_path: Path) -> None:
        """Push the branch at *worktree_path* to the configured remote, if any."""
        try:
            from soas_backend.services.git_sync_service import GitSyncService
            config = await GitSyncService(self.db).get_config()
            if not config.remote_url:
                return
            git_ops.push(
                worktree_path,
                auth_type=config.auth_type,
                auth_token=config.auth_token,
                ssh_key_path=config.ssh_key_path,
            )
        except Exception:
            logger.warning("Remote push failed for %s", worktree_path, exc_info=True)

    # ------------------------------------------------------------------
    # Save user draft
    # ------------------------------------------------------------------

    async def save_user_draft(
        self,
        username: str,
        entity_type: str,
        entity_id: str | None,
        snapshot: dict,
        *,
        action: str = "create",
    ) -> tuple[str | None, str]:
        """Write entity to its per-entity branch and commit.

        Branch name: user/{username}/{entity_dir}/{slug}
        Returns ``(git_sha, git_branch)``.
        """
        branch = _entity_branch(username, entity_type, snapshot, entity_id)
        wt = self.ensure_entity_branch(branch)
        export_one(entity_type, snapshot, wt, action=action)
        slug = _entity_slug(entity_type, snapshot, entity_id)
        sha = git_ops.commit_in_path(wt, f"Draft: {entity_type} {slug}")
        # Push entity branch to remote
        await self._push_remote(wt)
        return sha, branch

    # ------------------------------------------------------------------
    # Push to dev
    # ------------------------------------------------------------------

    async def push_to_dev(self, entity_branch: str, force: bool = False) -> MergeResult:
        """Merge the given entity branch into dev.

        *entity_branch* is the full branch name, e.g.
        ``user/admin/users/bob`` (stored in ``cr.git_branch``).

        If *force* is True, uses ``-X theirs`` strategy to overwrite dev
        with the entity branch's version on conflict.

        For ``users/*.json`` conflicts (user_role entities), the merge is
        resolved automatically by combining both sides' role lists.
        """
        # Ensure entity branch worktree exists (idempotent)
        entity_wt = self.ensure_entity_branch(entity_branch)
        dev_wt = self.ensure_dev_branch()

        # Pull latest remote dev before merging to avoid push rejection
        await self._pull_remote(dev_wt)

        strategy = "theirs" if force else None
        result = git_ops.merge_branch(
            dev_wt,
            entity_branch,
            message=f"Apply {entity_branch} to dev",
            strategy_option=strategy,
        )

        if result.status == "conflict":
            resolved = self._try_resolve_user_role_conflicts(
                result.conflicts, dev_wt, entity_wt,
            )
            if resolved:
                result = resolved

        if result.status in ("merged", "up-to-date"):
            await self._push_remote(dev_wt)
        return result

    def _try_resolve_user_role_conflicts(
        self,
        conflicts: list[str],
        dev_wt: Path,
        entity_wt: Path,
    ) -> MergeResult | None:
        """Resolve user_role merge conflicts by combining role lists.

        Only handles conflicts where *all* conflicted files are in the
        ``users/`` directory.  Returns a ``MergeResult`` on success,
        or ``None`` if the conflicts cannot be auto-resolved.

        The previous ``merge_branch`` call already aborted the merge, so
        we read the clean files from both sides, combine the role lists,
        write the result directly to dev, and commit.
        """
        import json as _json

        # Only auto-resolve if every conflict is in users/
        if not conflicts or not all(c.startswith("users/") for c in conflicts):
            return None

        for conflict_path in conflicts:
            # Read dev side (clean, merge was aborted)
            dev_file = dev_wt / conflict_path
            dev_data = None
            if dev_file.exists():
                try:
                    dev_data = _json.loads(dev_file.read_text(encoding="utf-8"))
                except (OSError, _json.JSONDecodeError):
                    pass

            # Read entity side
            entity_file = entity_wt / conflict_path
            entity_data = None
            if entity_file.exists():
                try:
                    entity_data = _json.loads(entity_file.read_text(encoding="utf-8"))
                except (OSError, _json.JSONDecodeError):
                    pass

            if dev_data is None and entity_data is None:
                return None

            # Combine: start from dev, add any roles from entity not in dev
            merged = dict(dev_data) if dev_data else {
                "user_id": (entity_data or {}).get("user_id"),
                "target_username": (entity_data or {}).get("target_username"),
                "roles": [],
            }
            dev_roles: list[dict] = list(merged.get("roles", []))
            entity_roles: list[dict] = (entity_data or {}).get("roles", [])

            existing_ids = {r.get("role_id") for r in dev_roles}
            for role in entity_roles:
                if role.get("role_id") not in existing_ids:
                    dev_roles.append(role)

            dev_roles.sort(key=lambda r: r.get("role_name", ""))
            merged["roles"] = dev_roles

            dev_file.parent.mkdir(parents=True, exist_ok=True)
            dev_file.write_text(
                _json.dumps(merged, indent=2, default=str), encoding="utf-8"
            )

        # Commit the combined result directly to dev
        sha = git_ops.commit_in_path(
            dev_wt, f"Resolve user_role conflicts: {', '.join(conflicts)}"
        )
        return MergeResult(status="merged", conflicts=[], sha=sha)

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
            await self._push_remote(self.repo_path)
        elif result.status == "up-to-date":
            await self._push_remote(self.repo_path)

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

    async def rebase_entity_from_dev(self, entity_branch: str) -> MergeResult:
        """Merge dev into entity branch so it picks up latest dev changes."""
        wt = self.ensure_entity_branch(entity_branch)
        result = git_ops.merge_branch(
            wt, DEV_BRANCH, message=f"Rebase {entity_branch} from dev"
        )
        if result.status in ("merged", "up-to-date"):
            await self._push_remote(wt)
        return result

    # ------------------------------------------------------------------
    # Diff helpers
    # ------------------------------------------------------------------

    def diff_dev_prod(self) -> list[str]:
        """List files that differ between dev and prod."""
        if not self.repo_path.exists():
            return []
        return git_ops.diff_branches(self.repo_path, PROD_BRANCH, DEV_BRANCH)

    def diff_entity_dev(self, entity_branch: str) -> list[str]:
        """List files that differ between an entity branch and dev."""
        if not self.repo_path.exists():
            return []
        return git_ops.diff_branches(self.repo_path, DEV_BRANCH, entity_branch)

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

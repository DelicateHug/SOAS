"""Git sync service - orchestrates bidirectional sync between DB and Git repo."""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import redis.asyncio as aioredis
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from soas_backend.models.app_setting import AppSetting
from soas_backend.models.git_sync_log import GitSyncLog
from soas_backend.services import git_ops
from soas_backend.services.git_serializers import SERIALIZER_REGISTRY

logger = logging.getLogger(__name__)

DEFAULT_REPO_PATH = "data/git-sync"


@dataclass
class GitSyncConfig:
    enabled: bool
    remote_url: str
    branch: str
    interval_seconds: int
    auth_type: str
    auth_token: str
    ssh_key_path: str
    entity_types: list[str]
    repo_path: str = DEFAULT_REPO_PATH


class GitSyncService:
    def __init__(self, db: AsyncSession, redis: aioredis.Redis | None = None):
        self.db = db
        self.redis = redis

    # ── Configuration ─────────────────────────────────────────────────

    async def get_config(self) -> GitSyncConfig:
        """Read git sync configuration from app_settings."""
        result = await self.db.execute(
            select(AppSetting).where(AppSetting.key.startswith("git_sync_"))
        )
        settings = {s.key: s.value for s in result.scalars().all()}

        entity_str = settings.get("git_sync_entity_types", "")
        entity_types = [e.strip() for e in entity_str.split(",") if e.strip()]

        return GitSyncConfig(
            enabled=settings.get("git_sync_enabled", "false").lower() == "true",
            remote_url=settings.get("git_sync_remote_url", ""),
            branch=settings.get("git_sync_branch", "main"),
            interval_seconds=max(300, int(settings.get("git_sync_interval_seconds", "300"))),
            auth_type=settings.get("git_sync_auth_type", "token"),
            auth_token=settings.get("git_sync_auth_token", ""),
            ssh_key_path=settings.get("git_sync_ssh_key_path", ""),
            entity_types=entity_types,
        )

    async def is_enabled(self) -> bool:
        result = await self.db.execute(
            select(AppSetting).where(AppSetting.key == "git_sync_enabled")
        )
        setting = result.scalar_one_or_none()
        return setting is not None and setting.value.lower() == "true"

    async def get_status(self) -> dict[str, Any]:
        """Get current sync status from Redis cache."""
        config = await self.get_config()
        status: dict[str, Any] = {
            "enabled": config.enabled,
            "remote_url": config.remote_url,
            "branch": config.branch,
            "entity_types": config.entity_types,
            "interval_seconds": config.interval_seconds,
            "last_sync_at": None,
            "last_status": None,
            "last_commit": None,
            "repo_initialized": False,
        }

        repo_path = Path(config.repo_path)
        if repo_path.exists() and git_ops.is_repo(repo_path):
            status["repo_initialized"] = True
            commit = git_ops.get_last_commit(repo_path)
            if commit:
                status["last_commit"] = {
                    "sha": commit.sha,
                    "message": commit.message,
                    "author": commit.author,
                    "date": commit.date,
                }

        if self.redis:
            last_sync = await self.redis.get("git_sync:last_sync_at")
            last_status = await self.redis.get("git_sync:last_status")
            if last_sync:
                status["last_sync_at"] = last_sync.decode() if isinstance(last_sync, bytes) else last_sync
            if last_status:
                status["last_status"] = last_status.decode() if isinstance(last_status, bytes) else last_status

        return status

    # ── Repository management ────────────────────────────────────────

    async def initialize_repo(self) -> dict[str, Any]:
        """Initialize the git repo (clone remote or create local)."""
        config = await self.get_config()
        repo_path = Path(config.repo_path)

        if repo_path.exists() and git_ops.is_repo(repo_path):
            return {"ok": True, "message": "Repository already initialized"}

        git_ops.init_repo(
            local_path=repo_path,
            remote_url=config.remote_url,
            branch=config.branch,
            auth_type=config.auth_type,
            auth_token=config.auth_token,
            ssh_key_path=config.ssh_key_path,
        )

        # Create directory structure with .gitkeep files
        for entity_type in config.entity_types:
            serializer = SERIALIZER_REGISTRY.get(entity_type)
            if serializer and hasattr(serializer, "directory"):
                dir_path = repo_path / serializer.directory
                dir_path.mkdir(parents=True, exist_ok=True)
                (dir_path / ".gitkeep").touch()

        # Initial commit with directory structure
        sha = git_ops.commit(repo_path, "Initialize SOAS git sync repository structure")

        # Push to remote if configured
        if config.remote_url and sha:
            try:
                git_ops.push(
                    repo_path,
                    auth_type=config.auth_type,
                    auth_token=config.auth_token,
                    ssh_key_path=config.ssh_key_path,
                )
            except git_ops.GitOpsError as exc:
                logger.warning("Initial push failed: %s", exc)
                return {"ok": True, "message": f"Repository initialized locally, but push failed: {exc}"}

        return {"ok": True, "message": "Repository initialized successfully"}

    async def test_connection(self, remote_url: str, auth_type: str, auth_token: str, ssh_key_path: str) -> dict:
        """Test connectivity to a remote git URL."""
        return git_ops.test_remote(
            remote_url=remote_url,
            auth_type=auth_type,
            auth_token=auth_token,
            ssh_key_path=ssh_key_path,
        )

    # ── Sync operations ──────────────────────────────────────────────

    async def full_sync(self, triggered_by: str = "scheduled") -> GitSyncLog:
        """Run a full bidirectional sync: pull → import → export → commit → push."""
        config = await self.get_config()
        repo_path = Path(config.repo_path)

        log = GitSyncLog(
            sync_type="full",
            status="success",
            entities_pushed=0,
            entities_pulled=0,
            conflicts=[],
            started_at=datetime.now(timezone.utc),
            triggered_by=triggered_by,
        )
        start_time = time.monotonic()

        try:
            if not repo_path.exists() or not git_ops.is_repo(repo_path):
                raise git_ops.GitOpsError("Repository not initialized. Call initialize first.")

            # Phase 1: Pull from remote
            pulled = 0
            if config.remote_url:
                pull_result = git_ops.pull(
                    repo_path,
                    auth_type=config.auth_type,
                    auth_token=config.auth_token,
                    ssh_key_path=config.ssh_key_path,
                )
                logger.info("Git pull result: %s", pull_result)

                if pull_result == "conflict":
                    log.conflicts = log.conflicts or []
                    log.conflicts.append({
                        "entity_type": "repo",
                        "entity_name": "pull",
                        "resolution": "rebase aborted, using local state",
                    })

                # Phase 2: Import from files → DB
                # Always import, but serializers use last_sync_at to skip
                # entities that were modified locally since last sync (last-write-wins).
                last_sync_at: datetime | None = None
                if self.redis:
                    raw = await self.redis.get("git_sync:last_sync_at")
                    if raw:
                        ts = raw.decode() if isinstance(raw, bytes) else raw
                        try:
                            last_sync_at = datetime.fromisoformat(ts)
                        except (ValueError, TypeError):
                            pass
                pulled = await self._import_from_repo(config, repo_path, last_sync_at)

            # Phase 3: Export from DB → files
            pushed = await self._export_to_repo(config, repo_path)

            # Phase 4: Commit changes
            now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
            sha = git_ops.commit(repo_path, f"SOAS sync: {now_str}")

            # Phase 5: Push to remote
            if config.remote_url and sha:
                try:
                    git_ops.push(
                        repo_path,
                        auth_type=config.auth_type,
                        auth_token=config.auth_token,
                        ssh_key_path=config.ssh_key_path,
                    )
                except git_ops.GitOpsError as exc:
                    logger.warning("Git push failed: %s", exc)
                    log.conflicts = log.conflicts or []
                    log.conflicts.append({
                        "entity_type": "repo",
                        "entity_name": "push",
                        "resolution": f"push failed: {exc}",
                    })
                    log.status = "partial"

            log.entities_pushed = pushed
            log.entities_pulled = pulled

        except Exception as exc:
            logger.exception("Git sync failed")
            log.status = "failed"
            log.error_message = str(exc)

        log.completed_at = datetime.now(timezone.utc)
        log.duration_ms = int((time.monotonic() - start_time) * 1000)

        self.db.add(log)
        await self.db.flush()

        # Update Redis cache
        if self.redis:
            await self.redis.set("git_sync:last_sync_at", log.completed_at.isoformat())
            await self.redis.set("git_sync:last_status", log.status)

        return log

    async def destructive_import(self, triggered_by: str) -> GitSyncLog:
        """Destructive import: delete all DB entities, then import everything from git.

        Replaces ALL application data for configured entity types with the
        contents of the remote git repository.  Admin-only, cannot be undone
        (other than restoring from a previous git state).
        """
        config = await self.get_config()
        repo_path = Path(config.repo_path)

        log = GitSyncLog(
            sync_type="destructive_import",
            status="success",
            entities_pushed=0,
            entities_pulled=0,
            conflicts=[],
            started_at=datetime.now(timezone.utc),
            triggered_by=triggered_by,
        )
        start_time = time.monotonic()

        try:
            # Step 1: Ensure repo exists
            if not repo_path.exists() or not git_ops.is_repo(repo_path):
                await self.initialize_repo()

            # Step 2: Pull latest from remote
            if config.remote_url:
                pull_result = git_ops.pull(
                    repo_path,
                    auth_type=config.auth_type,
                    auth_token=config.auth_token,
                    ssh_key_path=config.ssh_key_path,
                )
                logger.info("Git import pull result: %s", pull_result)
                if pull_result == "conflict":
                    raise git_ops.GitOpsError(
                        "Pull conflict during destructive import. Resolve manually."
                    )

            # Step 3: Delete all existing entities
            delete_counts = await self._delete_all_entities(config, triggered_by)
            logger.info("Git import deleted entities: %s", delete_counts)

            # Step 4: Import everything from repo (last_sync_at=None = import all)
            pulled = await self._import_from_repo(config, repo_path, last_sync_at=None)

            log.entities_pulled = pulled

        except Exception as exc:
            logger.exception("Destructive git import failed")
            log.status = "failed"
            log.error_message = str(exc)

        log.completed_at = datetime.now(timezone.utc)
        log.duration_ms = int((time.monotonic() - start_time) * 1000)

        self.db.add(log)
        await self.db.flush()

        # Update Redis cache
        if self.redis:
            await self.redis.set("git_sync:last_sync_at", log.completed_at.isoformat())
            await self.redis.set("git_sync:last_status", log.status)

        return log

    async def _delete_all_entities(
        self, config: GitSyncConfig, admin_user_id: str
    ) -> dict[str, int]:
        """Delete all entities for configured entity types.

        Deletion order respects FK constraints.  The triggering admin's role
        assignments are preserved so they don't get locked out.
        Settings are never deleted (upsert-only during import).
        """
        counts: dict[str, int] = {}

        if "automations" in config.entity_types:
            # Non-cascade FK references — must delete first
            r = await self.db.execute(text("DELETE FROM automation_trigger_log"))
            counts["automation_trigger_log"] = r.rowcount
            r = await self.db.execute(text("DELETE FROM execution_logs"))
            counts["execution_logs"] = r.rowcount
            r = await self.db.execute(text("DELETE FROM scheduled_jobs"))
            counts["scheduled_jobs"] = r.rowcount
            # source_automations references both automations and webhook_sources
            r = await self.db.execute(text("DELETE FROM source_automations"))
            counts["source_automations"] = r.rowcount
            # Main table (permissions, dependencies, versions cascade)
            r = await self.db.execute(text("DELETE FROM automations"))
            counts["automations"] = r.rowcount

        if "wiki" in config.entity_types:
            # Nullify self-referential parent FK before bulk delete
            await self.db.execute(text("UPDATE wiki_pages SET parent_id = NULL"))
            r = await self.db.execute(text("DELETE FROM wiki_pages"))
            counts["wiki_pages"] = r.rowcount

        if "code_library" in config.entity_types:
            r = await self.db.execute(text("DELETE FROM code_library_blocks"))
            counts["code_library_blocks"] = r.rowcount

        if "form_definitions" in config.entity_types:
            # form_submissions / case_form_submissions have RESTRICT FK
            r = await self.db.execute(text("DELETE FROM form_submissions"))
            counts["form_submissions"] = r.rowcount
            r = await self.db.execute(text("DELETE FROM case_form_submissions"))
            counts["case_form_submissions"] = r.rowcount
            r = await self.db.execute(text("DELETE FROM form_definitions"))
            counts["form_definitions"] = r.rowcount

        if "variables" in config.entity_types:
            r = await self.db.execute(text("DELETE FROM soas_variables"))
            counts["soas_variables"] = r.rowcount

        if "normalization" in config.entity_types:
            # Rules FK has no cascade — delete first
            r = await self.db.execute(text("DELETE FROM normalization_rules"))
            counts["normalization_rules"] = r.rowcount
            r = await self.db.execute(text("DELETE FROM normalization_groups"))
            counts["normalization_groups"] = r.rowcount

        if "webhook_sources" in config.entity_types:
            # source_automations may already be gone if automations was processed
            if "automations" not in config.entity_types:
                r = await self.db.execute(text("DELETE FROM source_automations"))
                counts["source_automations"] = r.rowcount
            r = await self.db.execute(text("DELETE FROM webhook_sources"))
            counts["webhook_sources"] = r.rowcount

        if "incident_variables" in config.entity_types:
            r = await self.db.execute(text("DELETE FROM incident_variables"))
            counts["incident_variables"] = r.rowcount

        if "roles" in config.entity_types:
            # Preserve the triggering admin's role assignments
            await self.db.execute(text("DELETE FROM role_permissions"))
            await self.db.execute(
                text("DELETE FROM user_roles WHERE user_id != :uid"),
                {"uid": admin_user_id},
            )
            r = await self.db.execute(
                text(
                    "DELETE FROM roles WHERE id NOT IN "
                    "(SELECT role_id FROM user_roles WHERE user_id = :uid)"
                ),
                {"uid": admin_user_id},
            )
            counts["roles"] = r.rowcount

        # settings: NO deletion — AppSettingsSerializer uses upsert

        await self.db.flush()
        return counts

    async def _export_to_repo(self, config: GitSyncConfig, repo_path: Path) -> int:
        """Export all enabled entity types from DB to git repo files."""
        total = 0
        for entity_type in config.entity_types:
            serializer = SERIALIZER_REGISTRY.get(entity_type)
            if not serializer:
                logger.warning("No serializer for entity type: %s", entity_type)
                continue
            try:
                count = await serializer.export_all(self.db, repo_path)
                total += count
                logger.debug("Exported %d %s entities", count, entity_type)
            except Exception:
                logger.exception("Failed to export %s", entity_type)
        return total

    async def _import_from_repo(
        self, config: GitSyncConfig, repo_path: Path, last_sync_at: datetime | None = None
    ) -> int:
        """Import all enabled entity types from git repo files to DB."""
        total = 0
        for entity_type in config.entity_types:
            serializer = SERIALIZER_REGISTRY.get(entity_type)
            if not serializer:
                continue
            try:
                count = await serializer.import_all(self.db, repo_path, last_sync_at)
                total += count
                logger.debug("Imported %d %s entities", count, entity_type)
            except Exception:
                logger.exception("Failed to import %s", entity_type)
        return total

    # ── Logs ──────────────────────────────────────────────────────────

    async def list_logs(
        self, limit: int = 20, offset: int = 0
    ) -> tuple[list[GitSyncLog], int]:
        """List sync logs with pagination."""
        from sqlalchemy import func

        count_result = await self.db.execute(
            select(func.count()).select_from(GitSyncLog)
        )
        total = count_result.scalar() or 0

        result = await self.db.execute(
            select(GitSyncLog)
            .order_by(GitSyncLog.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        logs = list(result.scalars().all())
        return logs, total

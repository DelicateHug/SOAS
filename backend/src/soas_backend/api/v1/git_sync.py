"""Git sync API endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

import redis.asyncio as aioredis

from soas_backend.api.deps import get_current_user, get_db, get_redis, require_permission
from soas_backend.models.user import User
from soas_backend.services.app_setting_service import AppSettingService
from soas_backend.services.git_sync_service import GitSyncService

router = APIRouter(prefix="/git-sync", tags=["git-sync"])


# ── Schemas ──────────────────────────────────────────────────────────

class GitSyncStatusResponse(BaseModel):
    enabled: bool
    remote_url: str
    branch: str
    entity_types: list[str]
    interval_seconds: int
    last_sync_at: str | None = None
    last_status: str | None = None
    last_commit: dict | None = None
    repo_initialized: bool = False


class GitSyncLogResponse(BaseModel):
    id: str
    sync_type: str
    status: str
    entities_pushed: int
    entities_pulled: int
    conflicts: list | None = None
    error_message: str | None = None
    started_at: str
    completed_at: str | None = None
    duration_ms: int | None = None
    triggered_by: str

    model_config = {"from_attributes": True}


class GitSyncLogsResponse(BaseModel):
    data: list[GitSyncLogResponse]
    total: int


class GitSyncConfigUpdate(BaseModel):
    git_sync_enabled: str | None = None
    git_sync_remote_url: str | None = None
    git_sync_branch: str | None = None
    git_sync_interval_seconds: str | None = None
    git_sync_auth_type: str | None = None
    git_sync_auth_token: str | None = None
    git_sync_ssh_key_path: str | None = None
    git_sync_entity_types: str | None = None


class TestConnectionRequest(BaseModel):
    remote_url: str
    auth_type: str = "token"
    auth_token: str = ""
    ssh_key_path: str = ""


# ── Endpoints ────────────────────────────────────────────────────────

@router.get("/status", response_model=GitSyncStatusResponse)
async def get_sync_status(
    _: dict = Depends(require_permission("git_sync", "read")),
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
):
    """Get current git sync status."""
    svc = GitSyncService(db, redis)
    return await svc.get_status()


@router.get("/logs", response_model=GitSyncLogsResponse)
async def list_sync_logs(
    limit: int = 20,
    offset: int = 0,
    _: dict = Depends(require_permission("git_sync", "read")),
    db: AsyncSession = Depends(get_db),
):
    """List git sync log history."""
    svc = GitSyncService(db)
    logs, total = await svc.list_logs(limit=min(limit, 100), offset=offset)
    return GitSyncLogsResponse(
        data=[
            GitSyncLogResponse(
                id=str(log.id),
                sync_type=log.sync_type,
                status=log.status,
                entities_pushed=log.entities_pushed,
                entities_pulled=log.entities_pulled,
                conflicts=log.conflicts,
                error_message=log.error_message,
                started_at=log.started_at.isoformat() if log.started_at else "",
                completed_at=log.completed_at.isoformat() if log.completed_at else None,
                duration_ms=log.duration_ms,
                triggered_by=log.triggered_by,
            )
            for log in logs
        ],
        total=total,
    )


@router.get("/config")
async def get_config(
    _: dict = Depends(require_permission("git_sync", "admin")),
    db: AsyncSession = Depends(get_db),
):
    """Get git sync configuration."""
    svc = GitSyncService(db)
    config = await svc.get_config()
    return {
        "git_sync_enabled": str(config.enabled).lower(),
        "git_sync_remote_url": config.remote_url,
        "git_sync_branch": config.branch,
        "git_sync_interval_seconds": str(config.interval_seconds),
        "git_sync_auth_type": config.auth_type,
        "git_sync_auth_token": "***" if config.auth_token else "",
        "git_sync_ssh_key_path": config.ssh_key_path,
        "git_sync_entity_types": ",".join(config.entity_types),
    }


@router.put("/config")
async def update_config(
    body: GitSyncConfigUpdate,
    current_user: User = Depends(get_current_user),
    _: dict = Depends(require_permission("git_sync", "admin")),
    db: AsyncSession = Depends(get_db),
):
    """Update git sync configuration."""
    svc = AppSettingService(db)
    updated = {}
    for key in [
        "git_sync_enabled",
        "git_sync_remote_url",
        "git_sync_branch",
        "git_sync_interval_seconds",
        "git_sync_auth_type",
        "git_sync_auth_token",
        "git_sync_ssh_key_path",
        "git_sync_entity_types",
    ]:
        value = getattr(body, key, None)
        if value is not None:
            # Validate interval minimum
            if key == "git_sync_interval_seconds":
                try:
                    val = max(300, int(value))
                    value = str(val)
                except ValueError:
                    raise HTTPException(status_code=400, detail="interval must be a number >= 300")
            await svc.set(key, value, updated_by=current_user.id)
            updated[key] = value if key != "git_sync_auth_token" else "***"

    return {"updated": updated}


@router.post("/initialize")
async def initialize_repo(
    _: dict = Depends(require_permission("git_sync", "admin")),
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
):
    """Initialize the git sync repository."""
    svc = GitSyncService(db, redis)
    try:
        result = await svc.initialize_repo()
        return result
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/test")
async def test_connection(
    body: TestConnectionRequest,
    _: dict = Depends(require_permission("git_sync", "admin")),
):
    """Test connectivity to a remote git URL."""
    from soas_backend.services.git_sync_service import GitSyncService
    result = GitSyncService.__new__(GitSyncService)
    return await result.test_connection(
        remote_url=body.remote_url,
        auth_type=body.auth_type,
        auth_token=body.auth_token,
        ssh_key_path=body.ssh_key_path,
    )


@router.post("/sync")
async def trigger_sync(
    current_user: User = Depends(get_current_user),
    _: dict = Depends(require_permission("git_sync", "admin")),
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
):
    """Manually trigger a git sync."""
    svc = GitSyncService(db, redis)
    if not await svc.is_enabled():
        raise HTTPException(status_code=400, detail="Git sync is not enabled")

    log = await svc.full_sync(triggered_by=str(current_user.id))
    return {
        "id": str(log.id),
        "status": log.status,
        "entities_pushed": log.entities_pushed,
        "entities_pulled": log.entities_pulled,
        "duration_ms": log.duration_ms,
        "error_message": log.error_message,
    }


@router.post("/import")
async def destructive_import(
    current_user: User = Depends(get_current_user),
    _: dict = Depends(require_permission("git_sync", "admin")),
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
):
    """Destructive import: replace ALL application data with git repo contents.

    Deletes all existing entities for configured types and re-imports
    everything from the configured git repository. Admin-only. Cannot be undone.
    """
    svc = GitSyncService(db, redis)

    config = await svc.get_config()
    if not config.entity_types:
        raise HTTPException(status_code=400, detail="No entity types configured for sync")

    log = await svc.destructive_import(triggered_by=str(current_user.id))

    if log.status == "failed":
        raise HTTPException(status_code=500, detail=log.error_message or "Import failed")

    return {
        "id": str(log.id),
        "status": log.status,
        "entities_pulled": log.entities_pulled,
        "duration_ms": log.duration_ms,
    }

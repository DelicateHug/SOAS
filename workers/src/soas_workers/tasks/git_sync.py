"""Periodic Git sync task."""

import json
import logging
from datetime import datetime, timezone

import redis

from soas_workers.celery_app import app
from soas_workers.config import config

logger = logging.getLogger(__name__)


@app.task(name="soas.git_sync")
def git_sync():
    """Periodic git sync task. Checks if enabled, then runs full sync.

    Runs every 5 minutes (configurable) via Celery Beat.
    Uses synchronous DB + Redis since Celery tasks are sync.
    """
    r = redis.from_url(config.REDIS_URL)

    # Check if git sync is enabled (fast check via direct DB query)
    import psycopg2
    try:
        conn = psycopg2.connect(config.DATABASE_URL, connect_timeout=5)
        cur = conn.cursor()
        cur.execute("SELECT value FROM app_settings WHERE key = 'git_sync_enabled'")
        row = cur.fetchone()
        conn.close()
        if not row or row[0].lower() != "true":
            return {"skipped": True, "reason": "git sync not enabled"}
    except Exception:
        logger.exception("Failed to check git sync enabled status")
        return {"skipped": True, "reason": "db check failed"}

    # Load full config
    try:
        conn = psycopg2.connect(config.DATABASE_URL, connect_timeout=5)
        cur = conn.cursor()
        cur.execute("SELECT key, value FROM app_settings WHERE key LIKE 'git_sync_%%'")
        settings = dict(cur.fetchall())
        conn.close()
    except Exception:
        logger.exception("Failed to load git sync config")
        return {"error": "failed to load config"}

    # Check interval - only run if enough time has passed
    last_sync = r.get("git_sync:last_sync_at")
    if last_sync:
        last_sync_str = last_sync.decode() if isinstance(last_sync, bytes) else last_sync
        try:
            last_dt = datetime.fromisoformat(last_sync_str)
            interval = max(300, int(settings.get("git_sync_interval_seconds", "300")))
            elapsed = (datetime.now(timezone.utc) - last_dt).total_seconds()
            if elapsed < interval - 30:  # 30s tolerance
                return {"skipped": True, "reason": f"too soon ({int(elapsed)}s < {interval}s)"}
        except (ValueError, TypeError):
            pass

    # Run the sync using the async service via asyncio
    import asyncio
    result = asyncio.run(_run_sync(settings))

    # Update Redis
    now = datetime.now(timezone.utc).isoformat()
    r.set("git_sync:last_sync_at", now)
    r.set("git_sync:last_status", result.get("status", "unknown"))

    # Publish event for real-time dashboard
    r.publish(
        "monitoring:health:channel",
        json.dumps({
            "type": "git_sync_update",
            "timestamp": now,
            "status": result.get("status"),
            "entities_pushed": result.get("entities_pushed", 0),
            "entities_pulled": result.get("entities_pulled", 0),
        }),
    )

    return result


async def _run_sync(settings: dict) -> dict:
    """Run the actual sync using async SQLAlchemy session."""
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
    from soas_backend.services.git_sync_service import GitSyncService
    import redis.asyncio as aioredis

    # Build async DB URL from worker's sync DATABASE_URL
    db_url = config.DATABASE_URL
    if db_url.startswith("postgresql://"):
        db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)

    engine = create_async_engine(db_url, pool_size=2, max_overflow=0)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    redis_client = aioredis.from_url(config.REDIS_URL)
    try:
        async with session_factory() as db:
            try:
                svc = GitSyncService(db, redis_client)
                log = await svc.full_sync(triggered_by="scheduled")
                await db.commit()
                return {
                    "status": log.status,
                    "entities_pushed": log.entities_pushed,
                    "entities_pulled": log.entities_pulled,
                    "duration_ms": log.duration_ms,
                    "error_message": log.error_message,
                }
            except Exception:
                await db.rollback()
                raise
    except Exception as exc:
        logger.exception("Git sync task failed")
        return {"status": "failed", "error_message": str(exc)}
    finally:
        await redis_client.aclose()
        await engine.dispose()

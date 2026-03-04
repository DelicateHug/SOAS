"""Periodic task to delete expired incident files."""

import logging
from datetime import datetime, timezone
from pathlib import Path

from soas_workers.celery_app import app
from soas_workers.config import config
from soas_workers.db import get_connection

logger = logging.getLogger(__name__)


@app.task(name="soas.cleanup_expired_files")
def cleanup_expired_files():
    """Delete incident files whose expires_at has passed.

    Files marked as evidence (is_evidence = true) are never auto-deleted.
    Processes up to 500 files per run to bound execution time.
    """
    now = datetime.now(timezone.utc)
    deleted_count = 0
    errors = 0

    storage_base = Path(config.FILE_STORAGE_PATH)

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, storage_path, filename, incident_id
                FROM incident_files
                WHERE expires_at <= %s
                  AND is_evidence = false
                LIMIT 500
                """,
                (now,),
            )
            expired_files = cur.fetchall()

        if not expired_files:
            logger.info("No expired files to clean up")
            return {"deleted": 0, "errors": 0}

        for row in expired_files:
            file_id = str(row["id"])
            storage_path = row["storage_path"]
            try:
                # Delete from disk
                disk_path = storage_base / storage_path
                if disk_path.exists():
                    disk_path.unlink()
                    logger.info("Deleted expired file from disk: %s", disk_path)

                # Delete from DB (re-check is_evidence in case it was toggled)
                with conn.cursor() as cur:
                    cur.execute(
                        "DELETE FROM incident_files WHERE id = %s::uuid AND is_evidence = false",
                        (file_id,),
                    )
                conn.commit()
                deleted_count += 1

            except Exception:
                logger.exception("Failed to delete expired file %s", file_id)
                conn.rollback()
                errors += 1

    logger.info(
        "Expired file cleanup complete: %d deleted, %d errors",
        deleted_count,
        errors,
    )
    return {"deleted": deleted_count, "errors": errors}

"""Cleanup old monitoring snapshots to prevent unbounded table growth."""

from datetime import datetime, timedelta, timezone

import sqlalchemy as sa
from sqlalchemy import create_engine

from soas_workers.celery_app import app
from soas_workers.config import config


@app.task(name="soas.monitoring_cleanup_snapshots")
def monitoring_cleanup_snapshots():
    """Delete health_metric_snapshots older than MONITORING_RETENTION_DAYS.

    Runs daily at 3 AM UTC via Celery Beat.
    """
    engine = create_engine(config.DATABASE_URL)
    cutoff = datetime.now(timezone.utc) - timedelta(days=config.MONITORING_RETENTION_DAYS)

    with engine.connect() as conn:
        result = conn.execute(
            sa.text("DELETE FROM health_metric_snapshots WHERE recorded_at < :cutoff"),
            {"cutoff": cutoff.isoformat()},
        )
        conn.commit()
        deleted = result.rowcount

    engine.dispose()
    return {"deleted": deleted, "cutoff": cutoff.isoformat()}

"""Persist Redis health snapshots to PostgreSQL for historical tracking."""

import json
import uuid
from datetime import datetime, timezone

import redis
import sqlalchemy as sa
from sqlalchemy import create_engine

from soas_workers.celery_app import app
from soas_workers.config import config


@app.task(name="soas.monitoring_persist_snapshots")
def monitoring_persist_snapshots():
    """Read current health data from Redis and persist to health_metric_snapshots table.

    Runs every 5 minutes via Celery Beat.
    """
    r = redis.from_url(config.REDIS_URL)
    engine = create_engine(config.DATABASE_URL)

    keys = r.keys("monitoring:health:*")
    snapshots = []
    for key in keys:
        raw = r.get(key)
        if raw:
            data = json.loads(raw)
            snapshots.append({
                "id": str(uuid.uuid4()),
                "component_type": data.get("component_type", "unknown"),
                "component_id": data.get("component_id", "unknown"),
                "status": data.get("status", "unknown"),
                "metrics": json.dumps(data.get("metrics", {})),
                "recorded_at": data.get("recorded_at", datetime.now(timezone.utc).isoformat()),
            })

    if snapshots:
        with engine.connect() as conn:
            conn.execute(
                sa.text(
                    "INSERT INTO health_metric_snapshots "
                    "(id, component_type, component_id, status, metrics, recorded_at) "
                    "VALUES (CAST(:id AS uuid), :component_type, :component_id, :status, "
                    "CAST(:metrics AS jsonb), CAST(:recorded_at AS timestamptz))"
                ),
                snapshots,
            )
            conn.commit()

    engine.dispose()
    return {"persisted": len(snapshots)}

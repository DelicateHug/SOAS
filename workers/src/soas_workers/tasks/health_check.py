"""Periodic worker health reporting."""

import json
import logging
import os
import socket
import time
from datetime import datetime, timezone

import redis

from soas_workers.celery_app import app
from soas_workers.config import config
from soas_workers.db import get_connection

logger = logging.getLogger(__name__)

# Per-process boot time so uptime_seconds is computed without psutil.
_BOOT_TS = time.time()


def _sample_resource_metrics() -> dict[str, float | int | None]:
    """Best-effort: collect CPU% / mem% via psutil if available, else None."""
    try:
        import psutil  # type: ignore

        cpu_pct = psutil.cpu_percent(interval=None)
        vm = psutil.virtual_memory()
        proc = psutil.Process(os.getpid())
        return {
            "cpu_pct": float(cpu_pct),
            "mem_pct": float(vm.percent),
            "mem_rss_bytes": int(proc.memory_info().rss),
        }
    except Exception:
        return {"cpu_pct": None, "mem_pct": None, "mem_rss_bytes": None}


@app.task(name="soas.worker_heartbeat")
def worker_heartbeat():
    """Report worker health to Redis and write a cluster sample row."""
    r = redis.from_url(config.REDIS_URL)
    info = {
        "hostname": socket.gethostname(),
        "pid": os.getpid(),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    key = f"worker:health:{info['hostname']}:{info['pid']}"
    r.setex(key, 30, json.dumps(info))

    # Phase 10: also write an instance_metric_samples row so the Cluster
    # panel shows live workers. Best-effort — never fail the heartbeat.
    try:
        metrics = _sample_resource_metrics()
        instance_id = f"{info['hostname']}:{info['pid']}"
        uptime_seconds = int(time.time() - _BOOT_TS)
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO instance_metric_samples
                      (instance_id, role, cpu_pct, mem_pct, mem_rss_bytes,
                       uptime_seconds, version)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        instance_id,
                        "worker",
                        metrics["cpu_pct"],
                        metrics["mem_pct"],
                        metrics["mem_rss_bytes"],
                        uptime_seconds,
                        os.environ.get("SOAS_VERSION", "0.1.0"),
                    ),
                )
            conn.commit()
    except Exception:
        logger.exception("worker_heartbeat: failed to write instance_metric_samples")

    return info

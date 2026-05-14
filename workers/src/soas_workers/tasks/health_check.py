"""Periodic worker health reporting."""

import json
import logging
import os
import re
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


def _resolve_agenttype_id(role: str) -> str:
    """Return a stable agenttype_id of the form `<role>_<n>`.

    Resolution order:
      1. $SOAS_AGENT_ID env var if set and well-formed.
      2. Otherwise allocate a deterministic id from hostname (treats
         restarts of the same container as the same agent).
    """
    candidate = os.environ.get("SOAS_AGENT_ID", "").strip()
    if candidate and re.fullmatch(r"[a-z][a-z0-9_]*_[0-9]{1,6}", candidate):
        return candidate
    # Hostname is stable within a container's lifetime; in docker-compose,
    # restart preserves the same name. Containers usually look like
    # "soas-worker" or just a random hex id when scaled.
    host = socket.gethostname().split(".", 1)[0]
    short = re.sub(r"^soas[-_]", "", host)
    m = re.match(r"^(\w+?)[-_]?(\d+)?$", short)
    if m and m.group(1):
        base = m.group(1).lower()
        num = m.group(2) or "001"
        return f"{base}_{num.zfill(3)}"
    return f"{role}_001"


@app.task(name="soas.worker_heartbeat")
def worker_heartbeat():
    """Report worker health to Redis and write a cluster sample row."""
    r = redis.from_url(config.REDIS_URL)
    role = os.environ.get("SOAS_AGENT_ROLE", "worker")
    agenttype_id = _resolve_agenttype_id(role)
    version = os.environ.get("SOAS_VERSION", "0.1.0")

    info = {
        "hostname": socket.gethostname(),
        "pid": os.getpid(),
        "agenttype_id": agenttype_id,
        "role": role,
        "version": version,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    key = f"worker:health:{agenttype_id}"
    r.setex(key, 30, json.dumps(info))

    # Phase 10/11: write an instance_metric_samples row keyed by the stable
    # agenttype_id (so restarts extend the same lifetime). Auto-register the
    # agent in registered_agents on first sight. Best-effort — never fail
    # the heartbeat.
    try:
        metrics = _sample_resource_metrics()
        instance_id = f"{info['hostname']}:{info['pid']}"
        uptime_seconds = int(time.time() - _BOOT_TS)
        with get_connection() as conn:
            with conn.cursor() as cur:
                # Auto-register the agent slot if it doesn't exist.
                cur.execute(
                    """
                    INSERT INTO registered_agents (agenttype_id, role, label)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (agenttype_id) DO NOTHING
                    """,
                    (agenttype_id, role, f"{role.title()} {agenttype_id.rsplit('_', 1)[-1]}"),
                )
                cur.execute(
                    """
                    INSERT INTO instance_metric_samples
                      (instance_id, agenttype_id, role, cpu_pct, mem_pct, mem_rss_bytes,
                       uptime_seconds, version)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        instance_id,
                        agenttype_id,
                        role,
                        metrics["cpu_pct"],
                        metrics["mem_pct"],
                        metrics["mem_rss_bytes"],
                        uptime_seconds,
                        version,
                    ),
                )
            conn.commit()
    except Exception:
        logger.exception("worker_heartbeat: failed to write instance_metric_samples")

    return info

"""Periodic worker health reporting."""

import json
import os
import socket
from datetime import datetime, timezone

import redis

from soas_workers.celery_app import app
from soas_workers.config import config


@app.task(name="soas.worker_heartbeat")
def worker_heartbeat():
    """Report worker health to Redis."""
    r = redis.from_url(config.REDIS_URL)
    info = {
        "hostname": socket.gethostname(),
        "pid": os.getpid(),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    key = f"worker:health:{info['hostname']}:{info['pid']}"
    r.setex(key, 30, json.dumps(info))
    return info

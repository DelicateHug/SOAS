"""Periodic system health monitoring task."""

import json
import time
from datetime import datetime, timezone

import redis

from soas_workers.celery_app import app
from soas_workers.config import config


@app.task(name="soas.monitoring_health_check")
def monitoring_health_check():
    """Run all health checks, store results in Redis, evaluate status.

    Runs every 30 seconds via Celery Beat. Each check stores results in Redis
    under monitoring:health:{type}:{id} with 60s TTL.
    """
    r = redis.from_url(config.REDIS_URL)
    now = datetime.now(timezone.utc).isoformat()
    results = []

    # 1. Check API health
    api_result = _check_api(r, now)
    results.append(api_result)

    # 2. Check PostgreSQL
    pg_result = _check_postgres(r, now)
    results.append(pg_result)

    # 3. Check Redis
    redis_result = _check_redis(r, now)
    results.append(redis_result)

    # 4. Check Celery Workers
    worker_results = _check_workers(r, now)
    results.extend(worker_results)

    # 5. Check Celery Beat (self-report)
    beat_result = _check_beat(r, now)
    results.append(beat_result)

    # 6. Check WebSocket connections
    ws_result = _check_websockets(r, now)
    results.append(ws_result)

    # Report this agent's own health (meta-monitoring)
    r.setex(
        "monitoring:agent:health_checker",
        90,
        json.dumps({
            "name": "health_checker",
            "last_check_at": now,
            "status": "healthy",
            "checks_run": len(results),
        }),
    )

    # Publish health update to channel for real-time dashboard
    r.publish(
        "monitoring:health:channel",
        json.dumps({
            "type": "health_update",
            "timestamp": now,
            "components": results,
        }),
    )

    return {"checked": len(results), "timestamp": now}


def _check_api(r, now):
    """Check API responsiveness via internal health endpoint."""
    import requests

    api_base = config.SOAS_API_URL.rsplit("/api/v1", 1)[0]
    url = f"{api_base}/api/health"
    start = time.monotonic()
    try:
        resp = requests.get(url, timeout=5)
        elapsed_ms = (time.monotonic() - start) * 1000
        if resp.status_code != 200:
            status = "unhealthy"
        elif elapsed_ms > 1000:
            status = "degraded"
        else:
            status = "healthy"
    except Exception:
        elapsed_ms = (time.monotonic() - start) * 1000
        status = "unhealthy"

    # Read request/error counters from middleware
    total_requests = int(r.get("monitoring:api:requests") or 0)
    total_errors = int(r.get("monitoring:api:errors") or 0)
    error_rate = (total_errors / total_requests * 100) if total_requests > 0 else 0

    result = {
        "component_type": "api",
        "component_id": "backend",
        "status": status,
        "metrics": {
            "response_time_ms": round(elapsed_ms, 2),
            "total_requests": total_requests,
            "total_errors": total_errors,
            "error_rate_pct": round(error_rate, 2),
        },
        "recorded_at": now,
    }
    r.setex("monitoring:health:api:backend", 60, json.dumps(result))
    return result


def _check_postgres(r, now):
    """Check PostgreSQL connectivity and stats."""
    import psycopg2

    start = time.monotonic()
    try:
        conn = psycopg2.connect(config.DATABASE_URL, connect_timeout=5)
        cur = conn.cursor()
        cur.execute("SELECT 1")
        latency_ms = (time.monotonic() - start) * 1000

        cur.execute("SELECT count(*) FROM pg_stat_activity WHERE state = 'active'")
        active_connections = cur.fetchone()[0]

        cur.execute("SELECT count(*) FROM pg_stat_activity")
        total_connections = cur.fetchone()[0]

        conn.close()
        status = "healthy" if latency_ms < 100 else "degraded"
    except Exception:
        latency_ms = (time.monotonic() - start) * 1000
        active_connections = 0
        total_connections = 0
        status = "unhealthy"

    result = {
        "component_type": "postgres",
        "component_id": "primary",
        "status": status,
        "metrics": {
            "query_latency_ms": round(latency_ms, 2),
            "active_connections": active_connections,
            "total_connections": total_connections,
        },
        "recorded_at": now,
    }
    r.setex("monitoring:health:postgres:primary", 60, json.dumps(result))
    return result


def _check_redis(r, now):
    """Check Redis health via INFO command."""
    start = time.monotonic()
    try:
        info = r.info()
        latency_ms = (time.monotonic() - start) * 1000
        memory_mb = info.get("used_memory", 0) / (1024 * 1024)
        connected_clients = info.get("connected_clients", 0)
        total_keys = sum(
            info.get(f"db{i}", {}).get("keys", 0)
            for i in range(16)
            if isinstance(info.get(f"db{i}"), dict)
        )
        status = "healthy"
        if latency_ms > 50 or memory_mb > 500:
            status = "degraded"
    except Exception:
        latency_ms = (time.monotonic() - start) * 1000
        memory_mb = 0
        connected_clients = 0
        total_keys = 0
        status = "unhealthy"

    result = {
        "component_type": "redis",
        "component_id": "primary",
        "status": status,
        "metrics": {
            "latency_ms": round(latency_ms, 2),
            "memory_mb": round(memory_mb, 2),
            "connected_clients": connected_clients,
            "total_keys": total_keys,
        },
        "recorded_at": now,
    }
    r.setex("monitoring:health:redis:primary", 60, json.dumps(result))
    return result


def _check_workers(r, now):
    """Check Celery worker health by scanning heartbeat keys."""
    worker_keys = r.keys("worker:health:*")
    results = []
    alive_count = 0

    for key in worker_keys:
        raw = r.get(key)
        if raw:
            alive_count += 1
            info = json.loads(raw)
            worker_id = f"{info.get('hostname', 'unknown')}:{info.get('pid', '?')}"
            result = {
                "component_type": "celery_worker",
                "component_id": worker_id,
                "status": "healthy",
                "metrics": {
                    "pid": info.get("pid"),
                    "hostname": info.get("hostname"),
                },
                "recorded_at": now,
            }
            r.setex(f"monitoring:health:celery_worker:{worker_id}", 60, json.dumps(result))
            results.append(result)

    # Aggregate worker metric with queue lengths
    queue_lengths = {}
    for queue_name in ["celery", "compile", "execute"]:
        queue_lengths[queue_name] = r.llen(queue_name) or 0

    aggregate = {
        "component_type": "celery_worker",
        "component_id": "aggregate",
        "status": "healthy" if alive_count > 0 else "unhealthy",
        "metrics": {
            "alive_workers": alive_count,
            "queue_celery": queue_lengths.get("celery", 0),
            "queue_compile": queue_lengths.get("compile", 0),
            "queue_execute": queue_lengths.get("execute", 0),
            "total_queue_depth": sum(queue_lengths.values()),
        },
        "recorded_at": now,
    }
    r.setex("monitoring:health:celery_worker:aggregate", 60, json.dumps(aggregate))
    results.append(aggregate)

    return results


def _check_beat(r, now):
    """Report Celery Beat as alive (this task runs via Beat)."""
    result = {
        "component_type": "celery_beat",
        "component_id": "scheduler",
        "status": "healthy",
        "metrics": {
            "last_run": now,
        },
        "recorded_at": now,
    }
    r.setex("monitoring:health:celery_beat:scheduler", 60, json.dumps(result))
    return result


def _check_websockets(r, now):
    """Check active WebSocket connection count."""
    active_count = int(r.get("monitoring:ws:active_count") or 0)
    result = {
        "component_type": "websocket",
        "component_id": "connections",
        "status": "healthy",
        "metrics": {
            "active_connections": active_count,
        },
        "recorded_at": now,
    }
    r.setex("monitoring:health:websocket:connections", 60, json.dumps(result))
    return result

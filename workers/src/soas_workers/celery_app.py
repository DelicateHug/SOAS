"""Celery application factory."""

from celery import Celery
from celery.schedules import crontab

from soas_workers.config import config

app = Celery("soas_workers")

app.conf.update(
    broker_url=config.CELERY_BROKER_URL,
    result_backend=config.CELERY_RESULT_BACKEND,
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_routes={
        "soas.compile_graph": {"queue": "compile"},
        "soas.run_automation": {"queue": "execute"},
        "soas.test_run_graph": {"queue": "execute"},
        "soas.worker_heartbeat": {"queue": "celery"},
        "soas.check_scheduled_jobs": {"queue": "celery"},
        "soas.monitoring_health_check": {"queue": "celery"},
        "soas.monitoring_persist_snapshots": {"queue": "celery"},
        "soas.monitoring_evaluate_alerts": {"queue": "celery"},
        "soas.cleanup_expired_files": {"queue": "celery"},
        "soas.git_sync": {"queue": "celery"},
        "soas.monitoring_cleanup_snapshots": {"queue": "celery"},
        "soas.reindex_wiki_page": {"queue": "celery"},
        "soas.reindex_wiki_all": {"queue": "celery"},
        "soas.delete_wiki_embeddings": {"queue": "celery"},
        "soas.compute_sla_snapshots": {"queue": "celery"},
    },
    beat_schedule={
        "worker-heartbeat": {
            "task": "soas.worker_heartbeat",
            "schedule": config.HEARTBEAT_INTERVAL,
        },
        "check-scheduled-jobs": {
            "task": "soas.check_scheduled_jobs",
            "schedule": 60,
        },
        "monitoring-health-check": {
            "task": "soas.monitoring_health_check",
            "schedule": config.MONITORING_CHECK_INTERVAL,
        },
        "monitoring-persist-snapshots": {
            "task": "soas.monitoring_persist_snapshots",
            "schedule": config.MONITORING_PERSIST_INTERVAL,
        },
        "monitoring-evaluate-alerts": {
            "task": "soas.monitoring_evaluate_alerts",
            "schedule": config.MONITORING_CHECK_INTERVAL,
        },
        "cleanup-expired-files": {
            "task": "soas.cleanup_expired_files",
            "schedule": 3600,  # every hour
        },
        "git-sync": {
            "task": "soas.git_sync",
            "schedule": config.GIT_SYNC_INTERVAL,
        },
        "monitoring-cleanup-snapshots": {
            "task": "soas.monitoring_cleanup_snapshots",
            "schedule": crontab(hour=3, minute=0),  # daily at 3 AM UTC
        },
        "compute-sla-snapshots": {
            "task": "soas.compute_sla_snapshots",
            "schedule": crontab(hour=2, minute=15),  # daily at 02:15 UTC
        },
    },
)

app.conf.include = [
    "soas_workers.tasks.health_check",
    "soas_workers.tasks.compile_graph",
    "soas_workers.tasks.run_automation",
    "soas_workers.tasks.test_run_graph",
    "soas_workers.tasks.check_scheduled_jobs",
    "soas_workers.tasks.monitoring_check",
    "soas_workers.tasks.monitoring_persist",
    "soas_workers.tasks.monitoring_alerts",
    "soas_workers.tasks.cleanup_expired_files",
    "soas_workers.tasks.git_sync",
    "soas_workers.tasks.monitoring_cleanup",
    "soas_workers.tasks.wiki_rag",
    "soas_workers.tasks.compute_sla_snapshots",
]


# Phase 11.2: beat-side heartbeat.
# `worker_heartbeat` runs on workers — beat itself never imports it, so the
# beat process is invisible to the Agents registry. We hook beat_init to
# spawn a small background thread that POSTs to /agents/heartbeat directly.
def _start_beat_heartbeat():
    import os
    import re
    import socket
    import threading
    import time

    from soas_workers.http_clients import internal_sync_client

    role = os.environ.get("SOAS_AGENT_ROLE", "beat")
    candidate = os.environ.get("SOAS_AGENT_ID", "").strip()
    if not (candidate and re.fullmatch(r"[a-z][a-z0-9_]*_[0-9]{1,6}", candidate)):
        host = socket.gethostname().split(".", 1)[0]
        short = re.sub(r"^soas[-_]", "", host)
        m = re.match(r"^(\w+?)[-_]?(\d+)?$", short)
        if m and m.group(1):
            candidate = f"{m.group(1).lower()}_{(m.group(2) or '001').zfill(3)}"
        else:
            candidate = f"{role}_001"

    api_url = os.environ.get("SOAS_API_URL", "https://backend:8000/api/v1")
    version = os.environ.get("SOAS_VERSION", "0.1.0")
    boot_ts = time.time()

    def loop() -> None:
        while True:
            try:
                body: dict = {
                    "agenttype_id": candidate,
                    "role": role,
                    "version": version,
                    "uptime_seconds": int(time.time() - boot_ts),
                    "instance_id": socket.gethostname(),
                }
                try:
                    import psutil  # type: ignore

                    proc = psutil.Process(os.getpid())
                    body["cpu_pct"] = float(psutil.cpu_percent(interval=None))
                    body["mem_pct"] = float(psutil.virtual_memory().percent)
                    body["mem_rss_bytes"] = int(proc.memory_info().rss)
                except Exception:
                    pass
                with internal_sync_client(timeout=5) as c:
                    c.post(f"{api_url}/agents/heartbeat", json=body)
            except Exception:
                pass
            time.sleep(30)

    t = threading.Thread(target=loop, name="beat-heartbeat", daemon=True)
    t.start()


from celery.signals import beat_init  # noqa: E402


@beat_init.connect
def _on_beat_init(sender=None, **kwargs):
    _start_beat_heartbeat()

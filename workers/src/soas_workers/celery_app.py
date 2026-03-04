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
]

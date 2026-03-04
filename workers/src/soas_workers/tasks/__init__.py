"""Celery tasks."""

from soas_workers.tasks.health_check import worker_heartbeat  # noqa: F401
from soas_workers.tasks.compile_graph import compile_graph  # noqa: F401
from soas_workers.tasks.run_automation import run_automation  # noqa: F401
from soas_workers.tasks.test_run_graph import test_run_graph  # noqa: F401

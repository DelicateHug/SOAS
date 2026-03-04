"""Shared Celery application instance for dispatching tasks."""

from celery import Celery

from soas_backend.config import settings

_celery: Celery | None = None


def get_celery() -> Celery:
    """Return the shared Celery application (lazily initialised)."""
    global _celery
    if _celery is None:
        _celery = Celery(broker=settings.celery_broker_url)
    return _celery

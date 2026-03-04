"""Worker configuration via environment variables."""

import os


class WorkerConfig:
    CELERY_BROKER_URL: str = os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379/0")
    CELERY_RESULT_BACKEND: str = os.environ.get("CELERY_RESULT_BACKEND", "redis://localhost:6379/1")
    DATABASE_URL: str = os.environ.get("DATABASE_URL", "postgresql://soas:changeme@localhost:5432/soas")
    REDIS_URL: str = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    AUTOMATIONS_DIR: str = os.environ.get("AUTOMATIONS_DIR", "/app/automations")
    SANDBOX_WORKDIR: str = os.environ.get("SANDBOX_WORKDIR", "/tmp/sandbox")
    HEARTBEAT_INTERVAL: int = int(os.environ.get("HEARTBEAT_INTERVAL", "15"))
    SOAS_API_URL: str = os.environ.get("SOAS_API_URL", "http://localhost:8000/api/v1")
    SOAS_API_TOKEN: str = os.environ.get("SOAS_API_TOKEN", "")
    MONITORING_CHECK_INTERVAL: int = int(os.environ.get("MONITORING_CHECK_INTERVAL", "30"))
    MONITORING_PERSIST_INTERVAL: int = int(os.environ.get("MONITORING_PERSIST_INTERVAL", "30"))
    MONITORING_RETENTION_DAYS: int = int(os.environ.get("MONITORING_RETENTION_DAYS", "30"))
    FILE_STORAGE_PATH: str = os.environ.get("FILE_STORAGE_PATH", "data/files")
    GIT_SYNC_REPO_PATH: str = os.environ.get("GIT_SYNC_REPO_PATH", "data/git-sync")
    GIT_SYNC_INTERVAL: int = int(os.environ.get("GIT_SYNC_INTERVAL", "300"))
    USER_SECRET_ENCRYPTION_KEY: str = os.environ.get("USER_SECRET_ENCRYPTION_KEY", "")


config = WorkerConfig()

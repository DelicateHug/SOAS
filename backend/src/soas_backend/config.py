"""Application configuration via environment variables."""

from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # App
    app_name: str = "SOC on a Stick"
    app_version: str = "0.1.0"
    debug: bool = False

    # Database
    database_url: str = "postgresql+asyncpg://soas:changeme@localhost:5432/soas"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # JWT
    jwt_private_key_path: str = "secrets/jwt_private.pem"
    jwt_public_key_path: str = "secrets/jwt_public.pem"
    jwt_algorithm: str = "RS256"
    jwt_access_token_expire_minutes: int = 60
    jwt_refresh_token_expire_hours: int = 2

    # WebAuthn
    webauthn_rp_id: str = "localhost"
    webauthn_rp_name: str = "SOC on a Stick"
    webauthn_origin: str = "http://localhost:3000"

    # CORS
    cors_origins: list[str] = ["http://localhost:3000", "http://localhost:5173"]

    # File storage
    file_storage_path: str = "data/files"

    # Celery
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/1"

    # User Secrets encryption
    user_secret_encryption_key: str = ""

    # Login security
    max_failed_login_attempts: int = 0  # 0 = no lockout (infinite)
    failed_login_lockout_minutes: int = 30

    # Monitoring
    monitoring_check_interval: int = 30
    monitoring_snapshot_persist_interval: int = 300
    monitoring_quorum_heartbeat_interval: int = 10

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    @property
    def jwt_private_key(self) -> str:
        return Path(self.jwt_private_key_path).read_text()

    @property
    def jwt_public_key(self) -> str:
        return Path(self.jwt_public_key_path).read_text()


settings = Settings()

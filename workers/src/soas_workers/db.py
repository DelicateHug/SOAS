"""Direct PostgreSQL connection for workers to write execution results."""

import json as _json
from datetime import datetime, timezone

import psycopg
from psycopg.rows import dict_row

from soas_workers.config import config


def get_connection():
    return psycopg.connect(config.DATABASE_URL, row_factory=dict_row)


def update_execution_status(
    execution_id: str,
    status: str,
    worker_id: str | None = None,
    started_at: datetime | None = None,
):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE execution_logs
                SET status = %s, worker_id = %s, started_at = %s
                WHERE id = %s::uuid
                """,
                (status, worker_id, started_at or datetime.now(timezone.utc), execution_id),
            )
        conn.commit()


def update_execution_complete(
    execution_id: str,
    status: str,
    stdout: str | None = None,
    stderr: str | None = None,
    exit_code: int | None = None,
    error_message: str | None = None,
    result_data: dict | None = None,
    duration_ms: int | None = None,
):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE execution_logs
                SET status = %s, stdout = %s, stderr = %s, exit_code = %s,
                    error_message = %s, result_data = %s::jsonb, duration_ms = %s,
                    completed_at = %s
                WHERE id = %s::uuid
                """,
                (
                    status,
                    stdout,
                    stderr,
                    exit_code,
                    error_message,
                    _json.dumps(result_data) if result_data else None,
                    duration_ms,
                    datetime.now(timezone.utc),
                    execution_id,
                ),
            )
        conn.commit()


def get_script_path(automation_id: str) -> str | None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT script_path FROM automations WHERE id = %s::uuid",
                (automation_id,),
            )
            row = cur.fetchone()
            return row["script_path"] if row else None


def get_automation_timeout(automation_id: str) -> int:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT timeout_seconds FROM automations WHERE id = %s::uuid",
                (automation_id,),
            )
            row = cur.fetchone()
            return row["timeout_seconds"] if row else 300


def get_execution_incident_id(execution_id: str) -> str | None:
    """Return the incident_id associated with an execution, or None."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT incident_id FROM execution_logs WHERE id = %s::uuid",
                (execution_id,),
            )
            row = cur.fetchone()
            return str(row["incident_id"]) if row and row["incident_id"] else None


def get_all_soas_vars() -> dict:
    """Get all SOAS variables (no permission filtering).

    Used for test runs where the user is already authenticated.
    Returns {name: value} dict.
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT name, value FROM soas_variables")
            return {row["name"]: row["value"] for row in cur.fetchall()}


def get_soas_vars_for_roles(role_ids: list[str]) -> dict:
    """Get all SOAS variables readable by the given role IDs.

    Returns {name: value} dict.
    """
    if not role_ids:
        return {}
    with get_connection() as conn:
        with conn.cursor() as cur:
            placeholders = ",".join(["%s::uuid"] * len(role_ids))
            cur.execute(
                f"""
                SELECT DISTINCT v.name, v.value
                FROM soas_variables v
                JOIN soas_variable_permissions p ON v.id = p.variable_id
                WHERE p.role_id IN ({placeholders})
                  AND p.can_read = true
                """,
                role_ids,
            )
            return {row["name"]: row["value"] for row in cur.fetchall()}


def get_writable_soas_vars_for_roles(role_ids: list[str]) -> list[str]:
    """Get names of SOAS variables writable by the given role IDs."""
    if not role_ids:
        return []
    with get_connection() as conn:
        with conn.cursor() as cur:
            placeholders = ",".join(["%s::uuid"] * len(role_ids))
            cur.execute(
                f"""
                SELECT DISTINCT v.name
                FROM soas_variables v
                JOIN soas_variable_permissions p ON v.id = p.variable_id
                WHERE p.role_id IN ({placeholders})
                  AND p.can_write = true
                """,
                role_ids,
            )
            return [row["name"] for row in cur.fetchall()]


def get_user_role_ids(user_id: str) -> list[str]:
    """Get role IDs for a user."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT role_id FROM user_roles WHERE user_id = %s::uuid",
                (user_id,),
            )
            return [str(row["role_id"]) for row in cur.fetchall()]


def get_user_secrets_for_user(user_id: str, encryption_key: str) -> dict[str, str]:
    """Get all decrypted user secrets for a specific user.

    Called at automation dispatch time to inject secrets into the bridge code.
    Returns {name: decrypted_value}.
    """
    if not encryption_key:
        return {}

    from cryptography.fernet import Fernet

    f = Fernet(encryption_key.encode())

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT name, encrypted_value FROM user_secrets WHERE user_id = %s::uuid",
                (user_id,),
            )
            secrets = {}
            for row in cur.fetchall():
                try:
                    secrets[row["name"]] = f.decrypt(row["encrypted_value"].encode()).decode()
                except Exception:
                    pass
            return secrets

"""Direct PostgreSQL connection for workers to write execution results."""

import base64
import json as _json
import os
from datetime import datetime, timezone

import psycopg
import redis as sync_redis
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


def get_automation_graph_data(automation_id: str) -> dict | None:
    """Return the graph_data JSONB for an automation, or None."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT graph_data FROM automations WHERE id = %s::uuid",
                (automation_id,),
            )
            row = cur.fetchone()
            return row["graph_data"] if row and row["graph_data"] else None


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


def get_execution_case_id(execution_id: str) -> str | None:
    """Return the case_id associated with an execution, or None."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT case_id FROM execution_logs WHERE id = %s::uuid",
                (execution_id,),
            )
            row = cur.fetchone()
            return str(row["case_id"]) if row and row["case_id"] else None


def get_case_incident_ids(case_id: str) -> list[str]:
    """Return incident IDs linked to a case, ordered by linked_at ASC."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT incident_id FROM case_incidents
                   WHERE case_id = %s::uuid
                   ORDER BY linked_at ASC""",
                (case_id,),
            )
            return [str(row["incident_id"]) for row in cur.fetchall()]


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


def _get_server_fernet():
    """Get a Fernet instance using the server encryption key."""
    from cryptography.fernet import Fernet

    key = config.USER_SECRET_ENCRYPTION_KEY
    if not key:
        key_path = os.environ.get("USER_SECRET_KEY_PATH", "secrets/user_secret.key")
        if os.path.exists(key_path):
            with open(key_path) as f:
                key = f.read().strip()
    if not key:
        return None
    return Fernet(key.encode())


def _get_user_dek_sync(user_id: str) -> bytes | None:
    """Get a user's DEK: try Redis cache first, then unwrap from server key."""
    # Try Redis cache
    try:
        r = sync_redis.from_url(config.REDIS_URL)
        val = r.get(f"user_dek:{user_id}")
        if val:
            return base64.urlsafe_b64decode(val)
    except Exception:
        pass

    # Fallback: unwrap from server key
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT server_wrapped_dek FROM users WHERE id = %s::uuid",
                (user_id,),
            )
            row = cur.fetchone()
            if not row or not row["server_wrapped_dek"]:
                return None

    server_f = _get_server_fernet()
    if not server_f:
        return None

    try:
        return server_f.decrypt(row["server_wrapped_dek"].encode())
    except Exception:
        return None


def get_user_secrets_for_user(user_id: str) -> dict[str, str]:
    """Get all decrypted user secrets for a specific user.

    Uses the per-user DEK (from Redis cache or server-wrapped fallback).
    Falls back to legacy server-key decryption for pre-migration secrets.
    Returns {name: decrypted_value}.
    """
    from cryptography.fernet import Fernet

    dek = _get_user_dek_sync(user_id)
    server_f = _get_server_fernet()

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT name, encrypted_value FROM user_secrets WHERE user_id = %s::uuid",
                (user_id,),
            )
            secrets = {}
            for row in cur.fetchall():
                try:
                    if dek:
                        secrets[row["name"]] = Fernet(dek).decrypt(
                            row["encrypted_value"].encode()
                        ).decode()
                    elif server_f:
                        # Legacy fallback: decrypt with server key
                        secrets[row["name"]] = server_f.decrypt(
                            row["encrypted_value"].encode()
                        ).decode()
                except Exception:
                    pass
            return secrets


def get_sensitive_user_secret_names(user_id: str) -> set[str]:
    """Get names of user secrets marked as sensitive for a given user."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT name FROM user_secrets WHERE user_id = %s::uuid AND sensitive = true",
                (user_id,),
            )
            return {row["name"] for row in cur.fetchall()}


def get_shared_secrets_for_roles(role_ids: list[str]) -> dict[str, str]:
    """Get shared secrets accessible by the given roles.

    Decrypts server_encrypted_value using the server key.
    Returns {name: decrypted_value}.
    """
    if not role_ids:
        return {}

    server_f = _get_server_fernet()
    if not server_f:
        return {}

    with get_connection() as conn:
        with conn.cursor() as cur:
            placeholders = ",".join(["%s::uuid"] * len(role_ids))
            cur.execute(
                f"""
                SELECT DISTINCT us.name, us.server_encrypted_value
                FROM user_secrets us
                JOIN shared_secret_permissions ssp ON us.id = ssp.secret_id
                WHERE ssp.role_id IN ({placeholders})
                  AND ssp.can_read = true
                  AND us.is_shared = true
                  AND us.server_encrypted_value IS NOT NULL
                """,
                role_ids,
            )
            secrets = {}
            for row in cur.fetchall():
                try:
                    secrets[row["name"]] = server_f.decrypt(
                        row["server_encrypted_value"].encode()
                    ).decode()
                except Exception:
                    pass
            return secrets


def get_sensitive_shared_secret_names(role_ids: list[str]) -> set[str]:
    """Get names of shared secrets marked as sensitive, accessible by the given roles."""
    if not role_ids:
        return set()
    with get_connection() as conn:
        with conn.cursor() as cur:
            placeholders = ",".join(["%s::uuid"] * len(role_ids))
            cur.execute(
                f"""
                SELECT DISTINCT us.name
                FROM user_secrets us
                JOIN shared_secret_permissions ssp ON us.id = ssp.secret_id
                WHERE ssp.role_id IN ({placeholders})
                  AND ssp.can_read = true
                  AND us.is_shared = true
                  AND us.sensitive = true
                """,
                role_ids,
            )
            return {row["name"] for row in cur.fetchall()}


def get_automation_team_id(automation_id: str) -> str | None:
    """Get the team_id for an automation, or None if globally scoped."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT team_id FROM automations WHERE id = %s::uuid",
                (automation_id,),
            )
            row = cur.fetchone()
            return str(row["team_id"]) if row and row["team_id"] else None


def get_team_vars_for_roles(team_id: str, role_ids: list[str]) -> dict:
    """Get all team variables readable by the given role IDs for a specific team.

    Returns {name: value} dict.
    """
    if not role_ids or not team_id:
        return {}
    with get_connection() as conn:
        with conn.cursor() as cur:
            placeholders = ",".join(["%s::uuid"] * len(role_ids))
            cur.execute(
                f"""
                SELECT DISTINCT v.name, v.value
                FROM team_variables v
                JOIN team_variable_permissions p ON v.id = p.variable_id
                WHERE v.team_id = %s::uuid
                  AND p.role_id IN ({placeholders})
                  AND p.can_read = true
                """,
                [team_id] + role_ids,
            )
            return {row["name"]: row["value"] for row in cur.fetchall()}


def get_writable_team_vars_for_roles(team_id: str, role_ids: list[str]) -> list[str]:
    """Get names of team variables writable by the given role IDs for a specific team."""
    if not role_ids or not team_id:
        return []
    with get_connection() as conn:
        with conn.cursor() as cur:
            placeholders = ",".join(["%s::uuid"] * len(role_ids))
            cur.execute(
                f"""
                SELECT DISTINCT v.name
                FROM team_variables v
                JOIN team_variable_permissions p ON v.id = p.variable_id
                WHERE v.team_id = %s::uuid
                  AND p.role_id IN ({placeholders})
                  AND p.can_write = true
                """,
                [team_id] + role_ids,
            )
            return [row["name"] for row in cur.fetchall()]


def get_all_team_vars(team_id: str) -> dict:
    """Get all team variables for a team (no permission filtering).

    Used for test runs where the user is already authenticated.
    Returns {name: value} dict.
    """
    if not team_id:
        return {}
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT name, value FROM team_variables WHERE team_id = %s::uuid",
                (team_id,),
            )
            return {row["name"]: row["value"] for row in cur.fetchall()}


def get_sensitive_team_variable_names(team_id: str) -> set[str]:
    """Get names of team variables marked as secret for a specific team."""
    if not team_id:
        return set()
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT name FROM team_variables WHERE team_id = %s::uuid AND is_secret = true",
                (team_id,),
            )
            return {row["name"] for row in cur.fetchall()}


def get_sensitive_incident_variable_names() -> set[str]:
    """Get names of incident variables marked as sensitive.

    Used at compile time to redact sensitive values in debug traces.
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT name FROM incident_variables WHERE sensitive = true"
            )
            return {row["name"] for row in cur.fetchall()}

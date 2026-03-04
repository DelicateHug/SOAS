"""Incident variable resolver - Redis first, Postgres fallback.

Used by workers at runtime when executing generated scripts that need
access to incident data.
"""

from __future__ import annotations

import json
from typing import Any, Dict, Optional

import redis
import psycopg


class IncidentVariableResolver:
    """Resolves incident variables from Redis (hot) or Postgres (cold).

    Redis key pattern: incident:{incident_id}:data (hash)
    Each field in the hash is a JSON-encoded variable value.
    """

    def __init__(self, redis_url: str, database_url: str) -> None:
        self._redis = redis.from_url(redis_url)
        self._db_url = database_url

    def get_incident_data(self, incident_id: str) -> Dict[str, Any]:
        """Get full incident data. Redis first, then Postgres."""
        redis_key = f"incident:{incident_id}:data"
        cached = self._redis.hgetall(redis_key)
        if cached:
            return {k.decode(): json.loads(v) for k, v in cached.items()}
        return self._fetch_from_postgres(incident_id)

    def get_variable(self, incident_id: str, var_name: str, default: Any = None) -> Any:
        """Get a single incident variable."""
        redis_key = f"incident:{incident_id}:data"
        val = self._redis.hget(redis_key, var_name)
        if val is not None:
            return json.loads(val)
        # Fallback to Postgres metadata field
        data = self._fetch_from_postgres(incident_id)
        return data.get(var_name, default)

    def set_variable(self, incident_id: str, var_name: str, value: Any) -> None:
        """Set an incident variable in Redis (pushed to Postgres on next read)."""
        redis_key = f"incident:{incident_id}:data"
        self._redis.hset(redis_key, var_name, json.dumps(value, default=str))
        # Mark as dirty so sync-on-read knows to merge
        self._redis.sadd(f"incident:{incident_id}:dirty_vars", var_name)

    def _fetch_from_postgres(self, incident_id: str) -> Dict[str, Any]:
        """Fetch incident data from Postgres and cache it in Redis."""
        try:
            with psycopg.connect(self._db_url) as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT i.id, i.title, i.summary, i.severity, i.status,
                               i.source, i.source_ref, i.tags, i.metadata,
                               i.created_at, i.closed_at,
                               (SELECT ci.case_id FROM case_incidents ci
                                WHERE ci.incident_id = i.id LIMIT 1)
                        FROM incidents i WHERE i.id = %s
                        """,
                        (incident_id,),
                    )
                    row = cur.fetchone()
                    if not row:
                        return {}

                    data = {
                        "id": str(row[0]),
                        "title": row[1],
                        "summary": row[2],
                        "severity": row[3],
                        "status": row[4],
                        "source": row[5],
                        "source_ref": row[6],
                        "tags": row[7] or [],
                        "metadata": row[8] or {},
                        "created_at": str(row[9]) if row[9] else None,
                        "closed_at": str(row[10]) if row[10] else None,
                        "case_id": str(row[11]) if row[11] else None,
                    }

                    # Also include metadata keys as top-level variables
                    if isinstance(data["metadata"], dict):
                        for k, v in data["metadata"].items():
                            if k not in data:
                                data[k] = v

                    # Cache to Redis with 24h TTL
                    redis_key = f"incident:{incident_id}:data"
                    pipe = self._redis.pipeline()
                    for field, value in data.items():
                        pipe.hset(redis_key, field, json.dumps(value, default=str))
                    pipe.expire(redis_key, 86400)
                    pipe.execute()

                    return data
        except Exception:
            return {}

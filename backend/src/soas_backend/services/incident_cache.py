"""Redis caching layer for open incident data."""

import json
import logging
from typing import Any
from uuid import UUID

import redis.asyncio as aioredis
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from soas_backend.models.incident import Incident

logger = logging.getLogger(__name__)

# Open statuses that qualify an incident for the active cache
_OPEN_STATUSES = frozenset({
    "detected",
    "triaging",
    "investigating",
    "containing",
    "remediating",
})


class IncidentCacheService:
    """Redis caching layer for open incident data.

    Key patterns:
      incident:{id}:data        -> HASH  (all incident fields as JSON values)
      incident:{id}:tags        -> SET   (tag strings)
      incident:{id}:dirty_vars  -> SET   (variable names modified by scripts)
      incidents:open            -> SET   (incident IDs with open statuses)
    """

    TTL_SECONDS = 60 * 60  # 1 hour default TTL

    def __init__(self, redis: aioredis.Redis):
        self._redis = redis

    # ------------------------------------------------------------------
    # Key helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _data_key(incident_id: UUID) -> str:
        return f"incident:{incident_id}:data"

    @staticmethod
    def _tags_key(incident_id: UUID) -> str:
        return f"incident:{incident_id}:tags"

    @staticmethod
    def _dirty_vars_key(incident_id: UUID) -> str:
        return f"incident:{incident_id}:dirty_vars"

    @staticmethod
    def _open_set_key() -> str:
        return "incidents:open"

    # ------------------------------------------------------------------
    # Core operations
    # ------------------------------------------------------------------

    async def cache_incident(self, incident_id: UUID, data: dict) -> None:
        """Cache incident data to Redis.

        Stores incident fields as a HASH, tags as a SET, and tracks the
        incident in the ``incidents:open`` set when appropriate.
        """
        data_key = self._data_key(incident_id)
        tags_key = self._tags_key(incident_id)
        open_key = self._open_set_key()

        # Serialise every value to JSON so the HASH stores strings
        hash_fields: dict[str, str] = {}
        tags: list[str] = []
        for field_name, value in data.items():
            if field_name == "tags":
                tags = value if isinstance(value, list) else []
            hash_fields[field_name] = json.dumps(value, default=str)

        pipe = self._redis.pipeline(transaction=True)

        # Store the hash
        if hash_fields:
            pipe.delete(data_key)
            pipe.hset(data_key, mapping=hash_fields)
            pipe.expire(data_key, self.TTL_SECONDS)

        # Store the tag set
        pipe.delete(tags_key)
        if tags:
            pipe.sadd(tags_key, *tags)
            pipe.expire(tags_key, self.TTL_SECONDS)

        # Track in open set when status qualifies
        status = data.get("status", "")
        iid = str(incident_id)
        if status in _OPEN_STATUSES:
            pipe.sadd(open_key, iid)
        else:
            pipe.srem(open_key, iid)

        await pipe.execute()

    async def get_incident_data(self, incident_id: UUID) -> dict | None:
        """Get cached incident data from Redis.

        Returns the full dict with JSON-decoded values, or ``None`` when
        the key does not exist.
        """
        data_key = self._data_key(incident_id)
        raw: dict[bytes, bytes] = await self._redis.hgetall(data_key)

        if not raw:
            return None

        result: dict[str, Any] = {}
        for k, v in raw.items():
            key_str = k.decode() if isinstance(k, bytes) else k
            val_str = v.decode() if isinstance(v, bytes) else v
            try:
                result[key_str] = json.loads(val_str)
            except (json.JSONDecodeError, TypeError):
                result[key_str] = val_str

        return result

    async def update_incident_tags(
        self,
        incident_id: UUID,
        old_tags: list[str],
        new_tags: list[str],
    ) -> list[str]:
        """Update tags, return the list of newly added tags.

        Replaces the cached tag set and also updates the ``tags`` field
        inside the data hash.
        """
        tags_key = self._tags_key(incident_id)
        data_key = self._data_key(incident_id)

        old_set = set(old_tags)
        new_set = set(new_tags)
        added = list(new_set - old_set)

        pipe = self._redis.pipeline(transaction=True)

        # Replace the tag set
        pipe.delete(tags_key)
        if new_tags:
            pipe.sadd(tags_key, *new_tags)
            pipe.expire(tags_key, self.TTL_SECONDS)

        # Keep the data hash in sync
        pipe.hset(data_key, "tags", json.dumps(new_tags))

        await pipe.execute()
        return added

    async def mark_dirty_var(self, incident_id: UUID, var_name: str) -> None:
        """Record a variable name as dirty (modified by a running script)."""
        key = self._dirty_vars_key(incident_id)
        await self._redis.sadd(key, var_name)
        await self._redis.expire(key, self.TTL_SECONDS)

    async def sync_dirty_vars_to_postgres(
        self,
        incident_id: UUID,
        db_session: AsyncSession,
    ) -> bool:
        """Sync-on-read: merge Redis dirty vars into Postgres metadata.

        Reads the ``dirty_vars`` set, fetches those fields from the data
        hash, and merges them into the Postgres ``metadata`` JSONB column.
        Returns ``True`` when at least one variable was synced.
        """
        dirty_key = self._dirty_vars_key(incident_id)
        data_key = self._data_key(incident_id)

        # Pop all dirty variable names atomically
        dirty_names: set[bytes] = await self._redis.smembers(dirty_key)
        if not dirty_names:
            return False

        decoded_names = [
            n.decode() if isinstance(n, bytes) else n for n in dirty_names
        ]

        # Read the current values from the data hash
        raw_values = await self._redis.hmget(data_key, *decoded_names)
        updates: dict[str, Any] = {}
        for name, raw_val in zip(decoded_names, raw_values):
            if raw_val is None:
                continue
            val_str = raw_val.decode() if isinstance(raw_val, bytes) else raw_val
            try:
                updates[name] = json.loads(val_str)
            except (json.JSONDecodeError, TypeError):
                updates[name] = val_str

        if not updates:
            return False

        # Fetch current metadata from Postgres
        result = await db_session.execute(
            select(Incident.metadata_).where(Incident.id == incident_id)
        )
        current_meta: dict = result.scalar_one_or_none() or {}
        merged = {**current_meta, **updates}

        # Write merged metadata back
        await db_session.execute(
            update(Incident)
            .where(Incident.id == incident_id)
            .values(metadata_=merged)
        )
        await db_session.flush()

        # Clear the dirty set now that we have persisted
        await self._redis.delete(dirty_key)
        logger.info(
            "Synced %d dirty vars for incident %s: %s",
            len(updates),
            incident_id,
            list(updates.keys()),
        )
        return True

    async def invalidate(self, incident_id: UUID) -> None:
        """Remove incident from cache entirely."""
        pipe = self._redis.pipeline(transaction=True)
        pipe.delete(self._data_key(incident_id))
        pipe.delete(self._tags_key(incident_id))
        pipe.delete(self._dirty_vars_key(incident_id))
        pipe.srem(self._open_set_key(), str(incident_id))
        await pipe.execute()

    async def get_open_incident_ids(self) -> list[str]:
        """Return the set of currently-open incident IDs."""
        members = await self._redis.smembers(self._open_set_key())
        return [m.decode() if isinstance(m, bytes) else m for m in members]

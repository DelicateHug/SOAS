"""Quorum service for tracking backend instance consensus."""

import json
import logging
from datetime import datetime, timezone

import redis.asyncio as aioredis

logger = logging.getLogger(__name__)


class QuorumService:
    """Tracks backend instances via Redis for quorum consensus."""

    HEARTBEAT_TTL = 20  # seconds
    INSTANCE_KEY_PREFIX = "monitoring:instance:"
    INSTANCES_SET_KEY = "monitoring:instances"

    def __init__(self, redis: aioredis.Redis):
        self._redis = redis

    async def register_instance(self, instance_id: str, hostname: str) -> None:
        """Register a backend instance on startup."""
        key = f"{self.INSTANCE_KEY_PREFIX}{instance_id}"
        now = datetime.now(timezone.utc).isoformat()
        await self._redis.hset(key, mapping={
            "instance_id": instance_id,
            "hostname": hostname,
            "started_at": now,
            "last_heartbeat": now,
        })
        await self._redis.expire(key, self.HEARTBEAT_TTL)
        await self._redis.sadd(self.INSTANCES_SET_KEY, instance_id)

        # Store uptime start for the first instance
        existing = await self._redis.get("monitoring:api:uptime_start")
        if not existing:
            await self._redis.set("monitoring:api:uptime_start", now)

        logger.info("Registered quorum instance %s (%s)", instance_id, hostname)

    async def heartbeat(self, instance_id: str) -> None:
        """Refresh instance heartbeat (called periodically)."""
        key = f"{self.INSTANCE_KEY_PREFIX}{instance_id}"
        now = datetime.now(timezone.utc).isoformat()
        await self._redis.hset(key, "last_heartbeat", now)
        await self._redis.expire(key, self.HEARTBEAT_TTL)

    async def deregister_instance(self, instance_id: str) -> None:
        """Remove instance on shutdown."""
        key = f"{self.INSTANCE_KEY_PREFIX}{instance_id}"
        await self._redis.delete(key)
        await self._redis.srem(self.INSTANCES_SET_KEY, instance_id)
        logger.info("Deregistered quorum instance %s", instance_id)

    async def get_quorum_status(self) -> dict:
        """Calculate quorum status from registered instances."""
        raw_ids = await self._redis.smembers(self.INSTANCES_SET_KEY)
        members = []
        alive_count = 0
        dead_ids = []

        for raw_id in raw_ids:
            iid = raw_id.decode("utf-8") if isinstance(raw_id, bytes) else raw_id
            key = f"{self.INSTANCE_KEY_PREFIX}{iid}"
            data = await self._redis.hgetall(key)

            if data:
                # Instance key exists (TTL hasn't expired) = alive
                alive_count += 1

                def _decode(val):
                    return val.decode("utf-8") if isinstance(val, bytes) else val

                members.append({
                    "instance_id": _decode(data.get(b"instance_id", b"")),
                    "hostname": _decode(data.get(b"hostname", b"")),
                    "started_at": _decode(data.get(b"started_at", b"")),
                    "last_heartbeat": _decode(data.get(b"last_heartbeat", b"")),
                    "is_alive": True,
                })
            else:
                # Key expired = dead; clean up from set
                dead_ids.append(iid)

        # Clean up dead instances from the set
        for dead_id in dead_ids:
            await self._redis.srem(self.INSTANCES_SET_KEY, dead_id)

        total = len(members)
        threshold = (total // 2) + 1 if total > 0 else 1
        has_quorum = alive_count >= threshold

        return {
            "has_quorum": has_quorum,
            "active_members": alive_count,
            "total_members": total,
            "quorum_threshold": threshold,
            "members": members,
        }

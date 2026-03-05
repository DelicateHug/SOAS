"""Redis cache for per-user Data Encryption Keys (DEKs).

The DEK is cached after login so that secret encrypt/decrypt operations
don't need to unwrap the server-wrapped DEK on every request.
"""

import base64
from uuid import UUID

import redis.asyncio as aioredis

DEK_CACHE_PREFIX = "user_dek:"
DEK_CACHE_TTL = 3600  # 1 hour


class DekCache:
    def __init__(self, redis: aioredis.Redis):
        self.redis = redis

    async def get(self, user_id: UUID) -> bytes | None:
        val = await self.redis.get(f"{DEK_CACHE_PREFIX}{user_id}")
        if val:
            return base64.urlsafe_b64decode(val)
        return None

    async def set(self, user_id: UUID, dek: bytes, ttl: int = DEK_CACHE_TTL) -> None:
        await self.redis.setex(
            f"{DEK_CACHE_PREFIX}{user_id}",
            ttl,
            base64.urlsafe_b64encode(dek),
        )

    async def delete(self, user_id: UUID) -> None:
        await self.redis.delete(f"{DEK_CACHE_PREFIX}{user_id}")

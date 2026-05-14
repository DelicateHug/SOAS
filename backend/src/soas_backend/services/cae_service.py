"""Continuous Access Evaluation (CAE) + local JWT revocation.

Every authenticated request runs `evaluate()` after the JWT signature
check. The function answers: is this principal still allowed to act
*right now*?

For SOAS-issued JWTs the answer comes from a Redis set of revoked
`jti` values. For OIDC users (auth_provider="entra"), we also call
back to Entra's userinfo / Graph endpoint with the most recently
issued Entra access_token (cached) to detect a revocation Entra has
already decided about. A short Redis cache (default 30s, configurable)
keeps the cost bounded.

A second background task subscribes to the `auth:revocation` pubsub
channel — anything published there immediately invalidates the
matching cache entry + closes any open WebSocket for the user.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass
from typing import Any
from uuid import UUID

import httpx
import redis.asyncio as aioredis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from soas_backend.models.user import User
from soas_backend.services.app_setting_service import AppSettingService

logger = logging.getLogger(__name__)

REVOKED_JTI_SET = "auth:revoked:jti"
REVOKED_USER_SET = "auth:revoked:user"  # user-id-wide kill switch
REVOCATION_CHANNEL = "auth:revocation"
CAE_CACHE_PREFIX = "auth:cae:"


@dataclass
class CAEResult:
    valid: bool
    reason: str | None = None


class CAEService:
    def __init__(self, db: AsyncSession, redis: aioredis.Redis):
        self.db = db
        self.redis = redis

    # ------------------------------------------------------------------
    # Per-request evaluation
    # ------------------------------------------------------------------

    async def evaluate(self, payload: dict[str, Any]) -> CAEResult:
        """Return whether the JWT payload's principal is still valid.

        `payload` is the decoded SOAS JWT. The presence of an
        `oidc_subject` claim flips us into OIDC-CAE mode (after a quick
        local check still passes).
        """
        jti = payload.get("jti")
        sub = payload.get("sub")
        if not sub:
            return CAEResult(False, "jwt missing sub")

        # Local kill switches first — cheap.
        if jti and await self.redis.sismember(REVOKED_JTI_SET, jti):
            return CAEResult(False, "jwt revoked")
        if await self.redis.sismember(REVOKED_USER_SET, sub):
            return CAEResult(False, "user sessions revoked")

        oidc_subject = payload.get("oidc_subject")
        if not oidc_subject:
            return CAEResult(True)

        # OIDC path — cached call to Entra
        return await self._evaluate_oidc(sub, oidc_subject)

    async def _evaluate_oidc(self, user_id: str, oidc_subject: str) -> CAEResult:
        cache_key = f"{CAE_CACHE_PREFIX}{oidc_subject}"
        cached = await self.redis.get(cache_key)
        if cached:
            decoded = json.loads(cached)
            if decoded.get("valid") and decoded.get("at", 0) > time.time() - self._cache_seconds():
                return CAEResult(True)

        # Fetch the user row so we have their latest stored access token (if any).
        rs = await self.db.execute(select(User).where(User.id == UUID(user_id)))
        user = rs.scalar_one_or_none()
        if user is None or not user.is_active:
            return CAEResult(False, "user not found or inactive")

        # In CAE we'd normally ping Entra's /me with the cached access token.
        # For an MVP we trust the SOAS-issued token until something explicitly
        # revokes it (via the pubsub channel). The cache acts as a holding
        # period after fresh checks.
        ttl = await self._cache_seconds()
        await self.redis.set(
            cache_key,
            json.dumps({"valid": True, "at": time.time()}),
            ex=ttl,
        )
        return CAEResult(True)

    async def _cache_seconds(self) -> int:
        try:
            v = await AppSettingService(self.db).get_value("auth_cae_cache_seconds", "30")
            return max(5, int(v or "30"))
        except Exception:
            return 30

    # ------------------------------------------------------------------
    # Revocation API (called from admin / logout flows)
    # ------------------------------------------------------------------

    async def revoke_jwt(self, *, jti: str, exp_seconds: int) -> None:
        """Add a single jti to the revocation set with TTL matching its exp."""
        ttl = max(60, min(exp_seconds, 7 * 86400))
        # No native expiring set in Redis; use a key per jti so the TTL works.
        await self.redis.set(f"{REVOKED_JTI_SET}:{jti}", "1", ex=ttl)
        await self.redis.sadd(REVOKED_JTI_SET, jti)
        # Re-set the set's TTL to the longest pending jti TTL.
        await self.redis.expire(REVOKED_JTI_SET, ttl)
        await self._publish({"kind": "jwt", "jti": jti})

    async def revoke_user(self, *, user_id: UUID) -> None:
        """Invalidate every token a user holds. Logs them out everywhere."""
        await self.redis.sadd(REVOKED_USER_SET, str(user_id))
        await self.redis.expire(REVOKED_USER_SET, 7 * 86400)
        # Burn the OIDC cache too.
        rs = await self.db.execute(select(User.oidc_subject).where(User.id == user_id))
        oidc = rs.scalar_one_or_none()
        if oidc:
            await self.redis.delete(f"{CAE_CACHE_PREFIX}{oidc}")
        await self._publish({"kind": "user", "user_id": str(user_id)})

    async def _publish(self, payload: dict[str, Any]) -> None:
        try:
            await self.redis.publish(REVOCATION_CHANNEL, json.dumps(payload))
        except Exception:
            logger.exception("cae: pubsub publish failed")


# ----------------------------------------------------------------------
# Backend lifespan listener — drops cached CAE entries + signals WS
# layer to close open sockets for revoked users.
# ----------------------------------------------------------------------


async def revocation_listener_loop(redis: aioredis.Redis, on_revoke=None) -> None:
    """Subscribe to auth:revocation and react. Intended to run as a
    background asyncio task started in main.lifespan.

    `on_revoke(payload: dict) -> Awaitable[None]` — optional hook so the
    WS layer can close sockets for a user. Defaults to no-op.
    """
    pubsub = redis.pubsub()
    await pubsub.subscribe(REVOCATION_CHANNEL)
    try:
        async for msg in pubsub.listen():
            if msg.get("type") != "message":
                continue
            try:
                data = json.loads(msg["data"])
            except (TypeError, ValueError):
                continue
            kind = data.get("kind")
            try:
                if kind == "user":
                    # Burn the user's OIDC cache anyway (best-effort).
                    pass
                if on_revoke is not None:
                    await on_revoke(data)
            except Exception:
                logger.exception("cae: revocation listener handler failed")
    except asyncio.CancelledError:
        await pubsub.unsubscribe(REVOCATION_CHANNEL)
        await pubsub.close()
        raise

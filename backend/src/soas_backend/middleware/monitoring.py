"""Request monitoring middleware for tracking API metrics.

Uses pure ASGI middleware (not BaseHTTPMiddleware) to avoid
interference with WebSocket connections.
"""

import time

import redis.asyncio as aioredis

from soas_backend.api.deps import get_redis_pool


class MonitoringMiddleware:
    """Tracks request count, error count, and response time in Redis.

    All Redis operations are fire-and-forget to never impact request handling.
    Pure ASGI implementation to avoid BaseHTTPMiddleware WebSocket issues.
    """

    def __init__(self, app):
        self.app = app

    async def _get_redis(self) -> aioredis.Redis:
        return await get_redis_pool()

    async def __call__(self, scope, receive, send):
        # Only track HTTP requests; pass WebSocket/lifespan straight through
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        start = time.monotonic()
        status_code = 500  # default in case of error

        async def send_wrapper(message):
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
            await send(message)

        await self.app(scope, receive, send_wrapper)

        elapsed_ms = (time.monotonic() - start) * 1000
        try:
            r = await self._get_redis()
            pipe = r.pipeline(transaction=False)
            pipe.incr("monitoring:api:requests")
            pipe.expire("monitoring:api:requests", 120)
            if status_code >= 500:
                pipe.incr("monitoring:api:errors")
                pipe.expire("monitoring:api:errors", 120)
            pipe.set("monitoring:api:last_response_ms", str(round(elapsed_ms, 2)))
            pipe.expire("monitoring:api:last_response_ms", 120)
            await pipe.execute()
        except Exception:
            pass  # Never let monitoring break the request

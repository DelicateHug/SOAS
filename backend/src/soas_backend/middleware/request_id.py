"""Middleware that attaches a unique request ID to every request/response
and records it into the in-memory request log.

Uses pure ASGI (not BaseHTTPMiddleware) to avoid WebSocket issues
and to reliably capture response status codes.
"""

import logging
import time
import uuid

from soas_backend.middleware.request_log import RequestRecord, record_request

logger = logging.getLogger(__name__)


class RequestIDMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # Extract or generate request ID
        headers = dict(scope.get("headers", []))
        request_id = None
        for key, value in scope.get("headers", []):
            if key == b"x-request-id":
                request_id = value.decode("utf-8", errors="replace")
                break
        if not request_id:
            request_id = str(uuid.uuid4())

        # Stash on scope for downstream access
        scope.setdefault("state", {})
        scope["state"]["request_id"] = request_id

        path = scope.get("path", "?")
        method = scope.get("method", "?")

        logger.info("[%s] %s %s", request_id[:8], method, path)

        start = time.monotonic()
        status_code = 500  # default if we never see a response start

        async def send_wrapper(message):
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
                # Inject X-Request-ID header into response
                raw_headers = list(message.get("headers", []))
                raw_headers.append((b"x-request-id", request_id.encode()))
                message = {**message, "headers": raw_headers}
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        except Exception:
            logger.exception("[%s] Unhandled exception", request_id[:8])
            raise
        finally:
            elapsed_ms = round((time.monotonic() - start) * 1000, 2)

            # Record into in-memory log
            record_request(RequestRecord(
                request_id=request_id,
                method=method,
                path=path,
                status_code=status_code,
                duration_ms=elapsed_ms,
            ))

            if status_code >= 400:
                logger.warning(
                    "[%s] %s %s -> %s (%.1fms)",
                    request_id[:8], method, path, status_code, elapsed_ms,
                )

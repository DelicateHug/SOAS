"""Per-user development mode guard middleware.

By default, all write operations on entity API paths are blocked (production mode).
Users with the 'deployment:dev_mode' permission can opt-in to development mode
by sending the X-Dev-Mode: true header, which enables editing.

Uses pure ASGI middleware to avoid BaseHTTPMiddleware WebSocket issues.
"""

import json
import logging

from soas_backend.auth.jwt import decode_access_token

logger = logging.getLogger(__name__)

# API path prefixes that are protected (writes blocked unless in dev mode).
PROTECTED_PREFIXES = (
    "/api/v1/automations",
    "/api/v1/wiki",
    "/api/v1/incidents",
    "/api/v1/cases",
    "/api/v1/issues",
    "/api/v1/soas-variables",
    "/api/v1/incident-variables",
    "/api/v1/code-library",
    "/api/v1/form-definitions",
    "/api/v1/normalization",
    "/api/v1/webhook-sources",
    "/api/v1/webhooks",
    "/api/v1/roles",
    "/api/v1/users",
    "/api/v1/user-secrets",
)

# Paths that are ALWAYS allowed regardless of mode.
ALWAYS_ALLOWED_PREFIXES = (
    "/api/v1/auth",
    "/api/v1/git-sync",
    "/api/v1/settings",
    "/api/v1/executions",
    "/api/v1/change-requests",
    "/api/v1/branch-versions",
    "/api/health",
    "/api/docs",
    "/api/openapi.json",
)

WRITE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


class ProductionGuardMiddleware:
    """Blocks write operations unless the user has dev_mode permission and sends X-Dev-Mode header."""

    def __init__(self, app):
        self.app = app

    def _extract_token(self, scope) -> str | None:
        """Extract Bearer token from Authorization header."""
        for header_name, header_value in scope.get("headers", []):
            if header_name == b"authorization":
                value = header_value.decode("utf-8", errors="ignore")
                if value.lower().startswith("bearer "):
                    return value[7:]
        return None

    def _has_dev_mode_header(self, scope) -> bool:
        """Check if X-Dev-Mode: true header is present."""
        for header_name, header_value in scope.get("headers", []):
            if header_name == b"x-dev-mode":
                return header_value.decode("utf-8", errors="ignore").lower() == "true"
        return False

    def _user_has_dev_permission(self, token: str) -> bool:
        """Check if the JWT contains the deployment:dev_mode permission."""
        payload = decode_access_token(token)
        if payload is None:
            return False

        # Admin bypasses all
        roles = payload.get("roles", [])
        if "admin" in roles:
            return True

        permissions = payload.get("permissions", [])
        return "deployment:dev_mode" in permissions

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        method = scope.get("method", "GET")
        path = scope.get("path", "")

        # Only check write methods
        if method not in WRITE_METHODS:
            await self.app(scope, receive, send)
            return

        # Check if path is always allowed
        for prefix in ALWAYS_ALLOWED_PREFIXES:
            if path.startswith(prefix):
                await self.app(scope, receive, send)
                return

        # Check if path is protected
        is_protected = False
        for prefix in PROTECTED_PREFIXES:
            if path.startswith(prefix):
                is_protected = True
                break

        if not is_protected:
            await self.app(scope, receive, send)
            return

        # Protected path + write method: check if user opted in to dev mode
        if self._has_dev_mode_header(scope):
            token = self._extract_token(scope)
            if token and self._user_has_dev_permission(token):
                # User has permission and opted in to dev mode — allow
                await self.app(scope, receive, send)
                return

        # Block the request
        body = json.dumps({
            "detail": "Editing is restricted in production mode. Switch to development mode to make changes."
        }).encode("utf-8")

        await send({
            "type": "http.response.start",
            "status": 403,
            "headers": [
                [b"content-type", b"application/json"],
                [b"content-length", str(len(body)).encode()],
            ],
        })
        await send({
            "type": "http.response.body",
            "body": body,
        })

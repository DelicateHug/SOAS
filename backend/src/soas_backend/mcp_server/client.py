"""Thin httpx client used by every tool module to call back into the SOAS REST API.

Authenticates with a service token (sst_…) loaded from a file or env var.
"""

from __future__ import annotations

import os
from typing import Any

import httpx

from soas_backend.http_clients import internal_async_client


class SoasClient:
    def __init__(self, base_url: str, token: str, timeout: float = 30.0):
        self.base_url = base_url.rstrip("/")
        # Internal mTLS-aware client: validates the backend server cert against the
        # SOAS CA and presents our client cert. The bearer token is still sent for
        # application-level RBAC.
        self._client = internal_async_client(
            timeout=timeout,
            base_url=self.base_url,
            headers={"Authorization": f"Bearer {token}"},
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    async def get(self, path: str, **params: Any) -> Any:
        r = await self._client.get(path, params=params)
        r.raise_for_status()
        return r.json()

    async def post(self, path: str, json: Any = None) -> Any:
        r = await self._client.post(path, json=json)
        r.raise_for_status()
        if r.headers.get("content-type", "").startswith("application/json"):
            return r.json()
        return r.text

    async def patch(self, path: str, json: Any = None) -> Any:
        r = await self._client.patch(path, json=json)
        r.raise_for_status()
        return r.json()

    async def delete(self, path: str) -> bool:
        r = await self._client.delete(path)
        r.raise_for_status()
        return True


def build_client_from_env() -> SoasClient:
    base = os.environ.get("SOAS_API_URL", "https://backend:8000/api/v1")
    token_file = os.environ.get("SOAS_TOKEN_FILE", "/run/secrets/mcp_token")
    token = os.environ.get("SOAS_API_TOKEN", "")
    if not token and os.path.exists(token_file):
        with open(token_file, "r", encoding="utf-8") as f:
            token = f.read().strip()
    if not token:
        raise RuntimeError("No SOAS service token available (set SOAS_API_TOKEN or SOAS_TOKEN_FILE)")
    return SoasClient(base, token)

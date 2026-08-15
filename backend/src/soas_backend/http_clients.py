"""Shared HTTP clients with internal mTLS preconfigured.

Use `internal_async_client(...)` whenever the backend dials another container on the
SOAS-internal network (embeddings, mcp, etc.). It presents the backend's client cert
and validates the upstream's server cert against the SOAS internal CA.

External calls (Microsoft Entra, GitHub, customer webhooks) must keep using a plain
`httpx.AsyncClient()` so they validate against the system trust store, not our internal
CA.
"""

import os
import ssl

import httpx

_MTLS_DIR = os.environ.get("MTLS_DIR", "/run/mtls")
_SERVICE = os.environ.get("MTLS_SERVICE_NAME", "backend")

_ssl_ctx: ssl.SSLContext | None = None


def _ctx() -> ssl.SSLContext:
    """Build (once) the SSLContext used for outbound internal mTLS calls."""
    global _ssl_ctx
    if _ssl_ctx is not None:
        return _ssl_ctx
    ctx = ssl.create_default_context(
        purpose=ssl.Purpose.SERVER_AUTH,
        cafile=f"{_MTLS_DIR}/ca/ca.crt",
    )
    ctx.load_cert_chain(
        certfile=f"{_MTLS_DIR}/{_SERVICE}/client.crt",
        keyfile=f"{_MTLS_DIR}/{_SERVICE}/client.key",
    )
    ctx.check_hostname = True
    ctx.verify_mode = ssl.CERT_REQUIRED
    _ssl_ctx = ctx
    return ctx


def internal_async_client(*, timeout: float = 30.0, **kwargs) -> httpx.AsyncClient:
    """Return an httpx.AsyncClient preconfigured for SOAS internal mTLS."""
    return httpx.AsyncClient(verify=_ctx(), timeout=timeout, **kwargs)


def internal_sync_client(*, timeout: float = 30.0, **kwargs) -> httpx.Client:
    """Sync variant — for places that haven't been switched to async."""
    return httpx.Client(verify=_ctx(), timeout=timeout, **kwargs)

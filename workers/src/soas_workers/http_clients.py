"""mTLS-aware HTTP helpers for worker tasks.

Workers are clients on the SOAS internal network. Every outbound call to another SOAS
service (backend, embeddings) must present this worker's client cert and validate the
upstream's server cert against the SOAS CA.

External calls (customer webhooks, third-party APIs) intentionally bypass this — they
should keep their default trust store.
"""

import os
import ssl

import httpx

_MTLS_DIR = os.environ.get("MTLS_DIR", "/run/mtls")
# Workers and worker-beat share the same role-type but get distinct certs from the
# generator so beat → backend calls are still attributable.
_SERVICE = os.environ.get("MTLS_SERVICE_NAME", "worker")

_ssl_ctx: ssl.SSLContext | None = None


def _ctx() -> ssl.SSLContext:
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


def internal_sync_client(*, timeout: float = 30.0, **kwargs) -> httpx.Client:
    return httpx.Client(verify=_ctx(), timeout=timeout, **kwargs)

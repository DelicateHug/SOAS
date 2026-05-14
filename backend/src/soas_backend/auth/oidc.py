"""Microsoft Entra (Azure AD) OIDC client.

Implements the authorization-code + PKCE flow against a per-tenant
endpoint. Config is read from app_settings so an admin can toggle and
configure entirely through the UI:

  auth_oidc_enabled        — gate. Off = endpoints return 503.
  auth_oidc_tenant         — tenant id (GUID or domain)
  auth_oidc_client_id      — Entra app (client) id
  auth_oidc_redirect_uri   — public callback URL registered with Entra
  auth_cae_cache_seconds   — read by cae_service, not by us directly

The Entra client secret lives in app_settings or a UserSecret if you
want it encrypted (see services/app_setting_service). Public-client
flows are also supported — when `auth_oidc_client_secret` is empty,
we run a public + PKCE flow.
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import logging
import secrets
import time
from dataclasses import dataclass
from typing import Any

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from soas_backend.services.app_setting_service import AppSettingService

logger = logging.getLogger(__name__)

# Microsoft's standard authority template. Per-tenant via `{tenant}`.
AUTHORITY_TEMPLATE = "https://login.microsoftonline.com/{tenant}/v2.0"

# Scopes we always request. `offline_access` enables refresh tokens;
# `openid profile email` is the canonical OIDC base; `User.Read` lets us
# call /me on Graph for CAE re-validation.
DEFAULT_SCOPES = ("openid", "profile", "email", "offline_access", "User.Read")

# OIDC discovery cache TTL — Entra's well-known doc changes rarely.
DISCOVERY_TTL_SECONDS = 3600

# JWKS cache TTL — same justification, and the validators handle key
# rollover by re-fetching on `kid` miss.
JWKS_TTL_SECONDS = 3600


@dataclass
class OIDCConfig:
    tenant: str
    client_id: str
    client_secret: str | None
    redirect_uri: str

    @property
    def issuer(self) -> str:
        return AUTHORITY_TEMPLATE.format(tenant=self.tenant)


@dataclass
class TokenResponse:
    access_token: str
    id_token: str
    refresh_token: str | None
    expires_in: int


class OIDCDisabledError(RuntimeError):
    """Raised when the OIDC toggle is off; the route layer turns this into 503."""


class OIDCConfigError(RuntimeError):
    """Raised when the toggle is on but config is missing or invalid."""


class OIDCService:
    # Process-wide caches keyed by tenant; cheap to share across requests.
    _discovery_cache: dict[str, tuple[float, dict[str, Any]]] = {}
    _jwks_cache: dict[str, tuple[float, dict[str, Any]]] = {}

    def __init__(self, db: AsyncSession):
        self.db = db

    # ------------------------------------------------------------------
    # Config
    # ------------------------------------------------------------------

    async def load_config(self) -> OIDCConfig:
        s = AppSettingService(self.db)
        enabled = (await s.get_value("auth_oidc_enabled", "false") or "false").lower() == "true"
        if not enabled:
            raise OIDCDisabledError("OIDC login is disabled in Danger Zone")

        tenant = (await s.get_value("auth_oidc_tenant", "") or "").strip()
        client_id = (await s.get_value("auth_oidc_client_id", "") or "").strip()
        client_secret = (await s.get_value("auth_oidc_client_secret", "") or "").strip() or None
        redirect_uri = (await s.get_value("auth_oidc_redirect_uri", "") or "").strip()
        if not tenant or not client_id or not redirect_uri:
            raise OIDCConfigError(
                "OIDC enabled but tenant / client_id / redirect_uri not set"
            )
        return OIDCConfig(
            tenant=tenant,
            client_id=client_id,
            client_secret=client_secret,
            redirect_uri=redirect_uri,
        )

    # ------------------------------------------------------------------
    # Discovery + JWKS (cached)
    # ------------------------------------------------------------------

    async def discovery(self, cfg: OIDCConfig) -> dict[str, Any]:
        cached = self._discovery_cache.get(cfg.tenant)
        if cached and cached[0] > time.monotonic():
            return cached[1]
        url = f"{cfg.issuer}/.well-known/openid-configuration"
        async with httpx.AsyncClient(timeout=10.0) as c:
            r = await c.get(url)
            r.raise_for_status()
            doc = r.json()
        self._discovery_cache[cfg.tenant] = (time.monotonic() + DISCOVERY_TTL_SECONDS, doc)
        return doc

    async def jwks(self, cfg: OIDCConfig, *, force: bool = False) -> dict[str, Any]:
        if not force:
            cached = self._jwks_cache.get(cfg.tenant)
            if cached and cached[0] > time.monotonic():
                return cached[1]
        doc = await self.discovery(cfg)
        jwks_uri = doc["jwks_uri"]
        async with httpx.AsyncClient(timeout=10.0) as c:
            r = await c.get(jwks_uri)
            r.raise_for_status()
            jwks = r.json()
        self._jwks_cache[cfg.tenant] = (time.monotonic() + JWKS_TTL_SECONDS, jwks)
        return jwks

    # ------------------------------------------------------------------
    # Authorization-code flow
    # ------------------------------------------------------------------

    def build_pkce_pair(self) -> tuple[str, str]:
        """Return (code_verifier, code_challenge) per RFC 7636 S256."""
        verifier = secrets.token_urlsafe(64)
        challenge = (
            base64.urlsafe_b64encode(hashlib.sha256(verifier.encode("ascii")).digest())
            .rstrip(b"=")
            .decode("ascii")
        )
        return verifier, challenge

    async def authorize_url(
        self,
        cfg: OIDCConfig,
        *,
        state: str,
        code_challenge: str,
        scopes: tuple[str, ...] = DEFAULT_SCOPES,
    ) -> str:
        doc = await self.discovery(cfg)
        from urllib.parse import urlencode

        # We append CAE capability via `xms_cc=["CP1"]` in claims so Entra
        # knows we honor continuous access evaluation signals.
        cae_claims = '{"access_token":{"xms_cc":{"values":["CP1"]}}}'
        params = {
            "client_id": cfg.client_id,
            "response_type": "code",
            "redirect_uri": cfg.redirect_uri,
            "response_mode": "query",
            "scope": " ".join(scopes),
            "state": state,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
            "claims": cae_claims,
        }
        return f"{doc['authorization_endpoint']}?{urlencode(params)}"

    async def exchange_code(
        self,
        cfg: OIDCConfig,
        *,
        code: str,
        code_verifier: str,
    ) -> TokenResponse:
        doc = await self.discovery(cfg)
        data: dict[str, str] = {
            "client_id": cfg.client_id,
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": cfg.redirect_uri,
            "code_verifier": code_verifier,
        }
        if cfg.client_secret:
            data["client_secret"] = cfg.client_secret
        async with httpx.AsyncClient(timeout=15.0) as c:
            r = await c.post(doc["token_endpoint"], data=data)
            if r.status_code != 200:
                raise OIDCConfigError(
                    f"token exchange failed: {r.status_code} {r.text[:200]}"
                )
            payload = r.json()
        return TokenResponse(
            access_token=payload["access_token"],
            id_token=payload["id_token"],
            refresh_token=payload.get("refresh_token"),
            expires_in=int(payload.get("expires_in", 3600)),
        )

    # ------------------------------------------------------------------
    # Token validation (signature + standard claims)
    # ------------------------------------------------------------------

    async def validate_id_token(
        self,
        cfg: OIDCConfig,
        id_token: str,
    ) -> dict[str, Any]:
        """Validate Entra id_token: signature against JWKS, exp, aud=client_id, iss."""
        from jose import JWTError, jwt

        # Inspect header for kid so we can fetch the right key.
        try:
            header = jwt.get_unverified_header(id_token)
        except JWTError as e:
            raise OIDCConfigError(f"id_token malformed: {e}") from e

        jwks = await self.jwks(cfg)
        key = _pick_key(jwks, header.get("kid"))
        if key is None:
            # Maybe key rolled — force re-fetch once.
            jwks = await self.jwks(cfg, force=True)
            key = _pick_key(jwks, header.get("kid"))
        if key is None:
            raise OIDCConfigError("id_token signed by unknown key (kid)")

        try:
            claims = jwt.decode(
                id_token,
                key,
                algorithms=[header.get("alg") or "RS256"],
                audience=cfg.client_id,
                issuer=f"https://login.microsoftonline.com/{cfg.tenant}/v2.0",
                options={"verify_at_hash": False},
            )
        except JWTError as e:
            raise OIDCConfigError(f"id_token rejected: {e}") from e
        return claims


def _pick_key(jwks: dict[str, Any], kid: str | None) -> dict[str, Any] | None:
    if kid is None:
        return None
    for key in jwks.get("keys") or []:
        if key.get("kid") == kid:
            return key
    return None

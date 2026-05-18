"""AppToken issuance, validation, revocation.

App tokens are short-lived (6h default) bearer credentials minted by SOAS *after* the
upstream identity provider (Microsoft Entra OIDC, or local password+MFA) has finished
validating the user. They are stored hashed (SHA-256) for lookup and Fernet-wrapped at
rest so admin tooling can re-issue cookies without round-tripping the user.

App tokens are always paired 1:1 with an AppSession (see app_session_service.py) — that
pairing is enforced by a UNIQUE constraint on app_sessions.app_token_id.
"""

import hashlib
import secrets as pysecrets
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from soas_backend.crypto import decrypt_value, encrypt_value
from soas_backend.models.app_token import AppToken
from soas_backend.models.user import User

# 48 random bytes → 64 chars urlsafe-b64. Prefix lets logs/audits identify the credential
# without leaking the secret half.
TOKEN_PREFIX = "sat_"
TOKEN_RANDOM_BYTES = 48
DEFAULT_TTL_HOURS = 6


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class AppTokenService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def issue(
        self,
        user_id: UUID,
        *,
        ttl_hours: int = DEFAULT_TTL_HOURS,
        issued_via: str = "local",
        oidc_subject: str | None = None,
    ) -> tuple[str, AppToken]:
        """Mint a fresh app token. Returns (raw_token, AppToken row).

        The raw token is shown to the caller exactly once — the server keeps only the SHA-256
        hash and a Fernet-wrapped ciphertext copy. The hash supports constant-time validation;
        the ciphertext supports operator workflows that need to re-issue the cookie without
        forcing the user through OIDC again.
        """
        raw = TOKEN_PREFIX + pysecrets.token_urlsafe(TOKEN_RANDOM_BYTES)
        now = datetime.now(timezone.utc)
        token = AppToken(
            user_id=user_id,
            token_hash=_hash(raw),
            token_ciphertext=encrypt_value(raw),
            issued_at=now,
            expires_at=now + timedelta(hours=ttl_hours),
            issued_via=issued_via,
            oidc_subject=oidc_subject,
        )
        self.db.add(token)
        await self.db.flush()
        return raw, token

    async def get_by_id(self, token_id: UUID) -> AppToken | None:
        result = await self.db.execute(select(AppToken).where(AppToken.id == token_id))
        return result.scalar_one_or_none()

    async def validate(self, raw_token: str) -> tuple[AppToken, User] | None:
        """Validate a raw token. Returns (token, user) if alive, else None.

        "Alive" = matching hash, not revoked, not past expires_at, user still active.
        """
        if not raw_token or not raw_token.startswith(TOKEN_PREFIX):
            return None
        h = _hash(raw_token)
        result = await self.db.execute(
            select(AppToken)
            .where(AppToken.token_hash == h)
            .options(selectinload(AppToken.user))
        )
        token = result.scalar_one_or_none()
        if token is None:
            return None
        if token.revoked_at is not None:
            return None
        if token.expires_at <= datetime.now(timezone.utc):
            return None
        user = token.user
        if user is None or not user.is_active:
            return None
        return token, user

    def reveal(self, token: AppToken) -> str:
        """Decrypt the Fernet-wrapped ciphertext back to the raw token string."""
        return decrypt_value(token.token_ciphertext)

    async def revoke(self, token_id: UUID) -> bool:
        token = await self.get_by_id(token_id)
        if token is None:
            return False
        if token.revoked_at is None:
            token.revoked_at = datetime.now(timezone.utc)
            await self.db.flush()
        return True

    async def revoke_for_user(self, user_id: UUID) -> int:
        """Revoke every live token for a user (e.g. on password change, admin lockout)."""
        now = datetime.now(timezone.utc)
        result = await self.db.execute(
            update(AppToken)
            .where(AppToken.user_id == user_id, AppToken.revoked_at.is_(None))
            .values(revoked_at=now)
        )
        await self.db.flush()
        return result.rowcount or 0

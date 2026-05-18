"""AppSession creation, lookup, IP-binding enforcement, revocation.

A session is the unit the browser carries (via httpOnly cookie). It is bound 1:1 to an
AppToken (UNIQUE constraint) and to the IP address it was created from. Every request
must HMAC-sign its canonical form with the session key, which is held by the client in
memory and stored Fernet-wrapped server-side.
"""

import base64
import secrets as pysecrets
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from soas_backend.crypto import decrypt_value, encrypt_value
from soas_backend.models.app_session import AppSession

SESSION_KEY_BYTES = 32  # 256-bit HMAC key


def generate_session_key() -> tuple[bytes, str]:
    """Return (raw_key_bytes, base64url_string). The string form is what the cookie carries."""
    raw = pysecrets.token_bytes(SESSION_KEY_BYTES)
    return raw, base64.urlsafe_b64encode(raw).decode().rstrip("=")


def session_key_from_b64(b64: str) -> bytes:
    """Inverse of the encoding in `generate_session_key()`."""
    pad = "=" * (-len(b64) % 4)
    return base64.urlsafe_b64decode(b64 + pad)


class AppSessionService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(
        self,
        *,
        app_token_id: UUID,
        user_id: UUID,
        ip: str,
        user_agent: str | None = None,
    ) -> tuple[str, AppSession]:
        """Create a session bound to an app token. Returns (b64 session key, session row).

        UNIQUE(app_token_id) means a second call with the same app_token_id will raise an
        IntegrityError — that's the 1:1 enforcement. Callers should treat that as "use the
        existing session" rather than retrying.
        """
        raw_key, b64_key = generate_session_key()
        session = AppSession(
            app_token_id=app_token_id,
            user_id=user_id,
            session_key_ciphertext=encrypt_value(b64_key),
            ip_address=ip,
            user_agent=user_agent,
        )
        self.db.add(session)
        await self.db.flush()
        return b64_key, session

    async def get_by_id(self, session_id: UUID) -> AppSession | None:
        result = await self.db.execute(
            select(AppSession).where(AppSession.id == session_id)
        )
        return result.scalar_one_or_none()

    def reveal_key(self, session: AppSession) -> str:
        """Decrypt the wrapped session key back to its base64 form."""
        return decrypt_value(session.session_key_ciphertext)

    async def touch(self, session_id: UUID) -> None:
        await self.db.execute(
            update(AppSession)
            .where(AppSession.id == session_id)
            .values(last_seen_at=func.now())
        )
        await self.db.flush()

    async def revoke(self, session_id: UUID, reason: str) -> bool:
        session = await self.get_by_id(session_id)
        if session is None:
            return False
        if session.revoked_at is None:
            session.revoked_at = datetime.now(timezone.utc)
            session.revoke_reason = reason
            await self.db.flush()
        return True

    async def revoke_for_user(self, user_id: UUID, reason: str) -> int:
        now = datetime.now(timezone.utc)
        result = await self.db.execute(
            update(AppSession)
            .where(AppSession.user_id == user_id, AppSession.revoked_at.is_(None))
            .values(revoked_at=now, revoke_reason=reason)
        )
        await self.db.flush()
        return result.rowcount or 0

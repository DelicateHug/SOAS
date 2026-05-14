"""Service token CRUD + validation."""

import hashlib
import secrets as pysecrets
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from soas_backend.models.role import UserRole
from soas_backend.models.service_token import ServiceToken
from soas_backend.models.user import User

# Tokens look like: "sst_<43 random url-safe base64 chars>" — sst = soas service token.
# The prefix lets operators identify the token at a glance and provides a useful failure
# signature in logs ("token did not start with sst_") without revealing the secret.
TOKEN_PREFIX = "sst_"
TOKEN_RANDOM_BYTES = 32  # → 43 chars urlsafe-b64
DISPLAY_PREFIX_CHARS = 12  # how many chars of the raw token to keep in token_prefix


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class ServiceTokenService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(
        self,
        name: str,
        user_id: UUID,
        description: str | None = None,
        scopes: list[str] | None = None,
        expires_at: datetime | None = None,
        created_by: UUID | None = None,
    ) -> tuple[ServiceToken, str]:
        """Create a service token. Returns (token_record, raw_token).

        The raw token is shown exactly once — the caller must surface it to the user/operator
        and never store it server-side beyond this call.
        """
        raw = TOKEN_PREFIX + pysecrets.token_urlsafe(TOKEN_RANDOM_BYTES)
        token = ServiceToken(
            name=name,
            description=description,
            token_hash=_hash(raw),
            token_prefix=raw[:DISPLAY_PREFIX_CHARS],
            user_id=user_id,
            scopes=scopes or [],
            expires_at=expires_at,
            created_by=created_by,
        )
        self.db.add(token)
        await self.db.flush()
        return token, raw

    async def get_by_id(self, token_id: UUID) -> ServiceToken | None:
        result = await self.db.execute(
            select(ServiceToken).where(ServiceToken.id == token_id)
        )
        return result.scalar_one_or_none()

    async def get_by_name(self, name: str) -> ServiceToken | None:
        result = await self.db.execute(
            select(ServiceToken).where(ServiceToken.name == name)
        )
        return result.scalar_one_or_none()

    async def list_tokens(self, include_revoked: bool = False) -> list[ServiceToken]:
        q = select(ServiceToken).order_by(ServiceToken.created_at.desc())
        if not include_revoked:
            q = q.where(ServiceToken.revoked_at.is_(None), ServiceToken.is_active.is_(True))
        result = await self.db.execute(q)
        return list(result.scalars().all())

    async def validate(self, raw_token: str) -> tuple[ServiceToken, User] | None:
        """Validate a presented bearer string and return (token, user) if valid.

        Returns None if the token is unknown, revoked, expired, or its user is inactive.
        Bumps last_used_at as a side-effect of successful validation.
        """
        if not raw_token or not raw_token.startswith(TOKEN_PREFIX):
            return None

        h = _hash(raw_token)
        result = await self.db.execute(
            select(ServiceToken)
            .where(ServiceToken.token_hash == h)
            .options(selectinload(ServiceToken.user).selectinload(User.user_roles))
        )
        token = result.scalar_one_or_none()
        if token is None:
            return None
        if not token.is_active or token.revoked_at is not None:
            return None
        if token.expires_at is not None and token.expires_at <= datetime.now(timezone.utc):
            return None
        user = token.user
        if user is None or not user.is_active:
            return None
        return token, user

    async def touch(self, token_id: UUID, ip: str | None = None) -> None:
        """Update last_used_at / last_used_ip out-of-band so it doesn't block validation."""
        await self.db.execute(
            update(ServiceToken)
            .where(ServiceToken.id == token_id)
            .values(last_used_at=func.now(), last_used_ip=ip)
        )
        await self.db.flush()

    async def revoke(self, token_id: UUID) -> bool:
        token = await self.get_by_id(token_id)
        if token is None:
            return False
        token.is_active = False
        token.revoked_at = datetime.now(timezone.utc)
        await self.db.flush()
        return True

    async def rotate(self, token_id: UUID) -> tuple[ServiceToken, str] | None:
        """Generate a new raw token, replacing the old hash. Old token immediately invalid."""
        token = await self.get_by_id(token_id)
        if token is None:
            return None
        raw = TOKEN_PREFIX + pysecrets.token_urlsafe(TOKEN_RANDOM_BYTES)
        token.token_hash = _hash(raw)
        token.token_prefix = raw[:DISPLAY_PREFIX_CHARS]
        token.is_active = True
        token.revoked_at = None
        await self.db.flush()
        return token, raw

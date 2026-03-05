"""User secret business logic - CRUD with per-user DEK encryption + sharing."""

import logging
from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from soas_backend.crypto import (
    decrypt_value,
    decrypt_with_dek,
    encrypt_value,
    encrypt_with_dek,
    unwrap_dek_server,
)
from soas_backend.models.user import User
from soas_backend.models.user_secret import SharedSecretPermission, UserSecret

logger = logging.getLogger(__name__)


class UserSecretService:
    def __init__(self, db: AsyncSession):
        self.db = db

    # ------------------------------------------------------------------
    # DEK resolution
    # ------------------------------------------------------------------

    async def _get_user_dek(self, user_id: UUID) -> bytes:
        """Get the user's DEK from Redis cache, or unwrap from server key."""
        from soas_backend.api.deps import get_redis_pool
        from soas_backend.services.dek_cache import DekCache

        redis = await get_redis_pool()
        cache = DekCache(redis)
        dek = await cache.get(user_id)
        if dek:
            return dek

        # Fallback: unwrap from server key stored on user
        result = await self.db.execute(
            select(User.server_wrapped_dek).where(User.id == user_id)
        )
        server_wrapped = result.scalar_one_or_none()
        if not server_wrapped:
            raise ValueError(f"No DEK available for user {user_id}")
        return unwrap_dek_server(server_wrapped)

    async def _encrypt_for_user(self, user_id: UUID, plaintext: str) -> str:
        """Encrypt with user DEK, falling back to server key."""
        try:
            dek = await self._get_user_dek(user_id)
            return encrypt_with_dek(plaintext, dek)
        except (ValueError, Exception):
            return encrypt_value(plaintext)

    async def _decrypt_for_user(self, user_id: UUID, token: str) -> str:
        """Decrypt with user DEK, falling back to server key."""
        try:
            dek = await self._get_user_dek(user_id)
            return decrypt_with_dek(token, dek)
        except (ValueError, Exception):
            return decrypt_value(token)

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    async def create(
        self,
        user_id: UUID,
        name: str,
        value: str,
        description: str | None = None,
        sensitive: bool = False,
    ) -> UserSecret:
        encrypted = await self._encrypt_for_user(user_id, value)
        secret = UserSecret(
            user_id=user_id,
            name=name,
            description=description,
            encrypted_value=encrypted,
            sensitive=sensitive,
        )
        self.db.add(secret)
        await self.db.flush()
        await self.db.refresh(secret)
        return secret

    async def get(self, secret_id: UUID) -> UserSecret | None:
        result = await self.db.execute(
            select(UserSecret).where(UserSecret.id == secret_id)
        )
        return result.scalar_one_or_none()

    async def get_by_name_for_user(self, user_id: UUID, name: str) -> UserSecret | None:
        result = await self.db.execute(
            select(UserSecret).where(
                UserSecret.user_id == user_id,
                UserSecret.name == name,
            )
        )
        return result.scalar_one_or_none()

    async def list_for_user(
        self, user_id: UUID, page: int = 1, per_page: int = 25
    ) -> tuple[list[UserSecret], int]:
        count_result = await self.db.execute(
            select(func.count()).select_from(UserSecret)
            .where(UserSecret.user_id == user_id)
        )
        total = count_result.scalar() or 0

        result = await self.db.execute(
            select(UserSecret)
            .where(UserSecret.user_id == user_id)
            .order_by(UserSecret.name)
            .offset((page - 1) * per_page)
            .limit(per_page)
        )
        return list(result.scalars().all()), total

    async def list_all_admin(
        self, page: int = 1, per_page: int = 25
    ) -> tuple[list[UserSecret], int]:
        """Admin listing - returns all user secrets (values never decrypted)."""
        count_result = await self.db.execute(
            select(func.count()).select_from(UserSecret)
        )
        total = count_result.scalar() or 0

        result = await self.db.execute(
            select(UserSecret)
            .options(selectinload(UserSecret.owner))
            .order_by(UserSecret.user_id, UserSecret.name)
            .offset((page - 1) * per_page)
            .limit(per_page)
        )
        return list(result.scalars().all()), total

    async def update(
        self,
        secret_id: UUID,
        value: str | None = None,
        description: str | None = ...,
    ) -> UserSecret | None:
        secret = await self.get(secret_id)
        if not secret:
            return None

        if value is not None:
            secret.encrypted_value = await self._encrypt_for_user(secret.user_id, value)
            # If shared, also update the server-encrypted copy
            if secret.is_shared:
                secret.server_encrypted_value = encrypt_value(value)

        if description is not ...:
            secret.description = description

        await self.db.flush()
        await self.db.refresh(secret)
        return secret

    async def delete_secret(self, secret_id: UUID) -> bool:
        secret = await self.get(secret_id)
        if not secret:
            return False
        await self.db.delete(secret)
        await self.db.flush()
        return True

    async def resolve_for_user(self, user_id: UUID) -> dict[str, str]:
        """Get all decrypted secrets for a user. Used at automation runtime."""
        result = await self.db.execute(
            select(UserSecret.name, UserSecret.encrypted_value)
            .where(UserSecret.user_id == user_id)
        )
        try:
            dek = await self._get_user_dek(user_id)
        except (ValueError, Exception):
            dek = None

        secrets = {}
        for row in result.all():
            try:
                if dek:
                    secrets[row.name] = decrypt_with_dek(row.encrypted_value, dek)
                else:
                    secrets[row.name] = decrypt_value(row.encrypted_value)
            except Exception:
                pass
        return secrets

    async def decrypt_single(self, secret: UserSecret) -> str:
        """Decrypt a single secret's value."""
        return await self._decrypt_for_user(secret.user_id, secret.encrypted_value)

    # ------------------------------------------------------------------
    # Sharing
    # ------------------------------------------------------------------

    async def share_secret(self, secret_id: UUID, role_ids: list[UUID]) -> UserSecret:
        """Share a secret with specific roles."""
        secret = await self.get(secret_id)
        if not secret:
            raise ValueError("Secret not found")

        # Decrypt the value to create a server-encrypted copy
        plaintext = await self._decrypt_for_user(secret.user_id, secret.encrypted_value)

        secret.is_shared = True
        secret.server_encrypted_value = encrypt_value(plaintext)

        # Replace permission rows
        await self.db.execute(
            delete(SharedSecretPermission).where(
                SharedSecretPermission.secret_id == secret_id
            )
        )
        for role_id in role_ids:
            self.db.add(SharedSecretPermission(
                secret_id=secret_id,
                role_id=role_id,
            ))

        await self.db.flush()
        await self.db.refresh(secret)
        return secret

    async def unshare_secret(self, secret_id: UUID) -> UserSecret:
        """Remove sharing from a secret."""
        secret = await self.get(secret_id)
        if not secret:
            raise ValueError("Secret not found")

        secret.is_shared = False
        secret.server_encrypted_value = None

        await self.db.execute(
            delete(SharedSecretPermission).where(
                SharedSecretPermission.secret_id == secret_id
            )
        )

        await self.db.flush()
        await self.db.refresh(secret)
        return secret

    async def update_share_permissions(
        self, secret_id: UUID, role_ids: list[UUID]
    ) -> None:
        """Update which roles a shared secret is accessible to."""
        await self.db.execute(
            delete(SharedSecretPermission).where(
                SharedSecretPermission.secret_id == secret_id
            )
        )
        for role_id in role_ids:
            self.db.add(SharedSecretPermission(
                secret_id=secret_id,
                role_id=role_id,
            ))
        await self.db.flush()

    async def get_share_permissions(
        self, secret_id: UUID
    ) -> list[SharedSecretPermission]:
        """Get sharing permissions for a secret."""
        result = await self.db.execute(
            select(SharedSecretPermission)
            .options(selectinload(SharedSecretPermission.role))
            .where(SharedSecretPermission.secret_id == secret_id)
        )
        return list(result.scalars().all())

    async def get_shared_for_roles(
        self, role_ids: list[UUID]
    ) -> list[dict]:
        """Get shared secrets visible to the given roles.

        Returns list of dicts with name, value (masked if sensitive),
        description, sensitive, owner_username, id.
        """
        if not role_ids:
            return []

        result = await self.db.execute(
            select(UserSecret)
            .join(SharedSecretPermission, SharedSecretPermission.secret_id == UserSecret.id)
            .options(selectinload(UserSecret.owner))
            .where(
                UserSecret.is_shared.is_(True),
                SharedSecretPermission.role_id.in_(role_ids),
                SharedSecretPermission.can_read.is_(True),
            )
            .distinct()
        )
        secrets = result.scalars().all()

        items = []
        for s in secrets:
            value = None
            if not s.sensitive and s.server_encrypted_value:
                try:
                    value = decrypt_value(s.server_encrypted_value)
                except Exception:
                    value = None

            items.append({
                "id": s.id,
                "name": s.name,
                "description": s.description,
                "sensitive": s.sensitive,
                "owner_username": s.owner.username if s.owner else "unknown",
                "value": "***" if s.sensitive else value,
                "is_shared": True,
            })
        return items

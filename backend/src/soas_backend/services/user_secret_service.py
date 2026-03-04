"""User secret business logic - CRUD with encryption."""

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from soas_backend.crypto import decrypt_value, encrypt_value
from soas_backend.models.user_secret import UserSecret


class UserSecretService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(
        self,
        user_id: UUID,
        name: str,
        value: str,
        description: str | None = None,
    ) -> UserSecret:
        secret = UserSecret(
            user_id=user_id,
            name=name,
            description=description,
            encrypted_value=encrypt_value(value),
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
            secret.encrypted_value = encrypt_value(value)
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
        secrets = {}
        for row in result.all():
            try:
                secrets[row.name] = decrypt_value(row.encrypted_value)
            except Exception:
                pass
        return secrets

    def decrypt_single(self, secret: UserSecret) -> str:
        """Decrypt a single secret's value."""
        return decrypt_value(secret.encrypted_value)

"""Authentication service - handles login, registration, token management."""

from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from soas_backend.auth.jwt import (
    create_access_token,
    create_refresh_token,
    hash_refresh_token,
)
from soas_backend.auth.password import hash_password, verify_password
from soas_backend.config import settings
from soas_backend.models.role import Permission, Role, RolePermission, UserRole
from soas_backend.models.user import RefreshToken, User


class AuthService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def register(
        self, username: str, email: str, display_name: str, password: str
    ) -> User:
        # Check if this is the first user
        user_count = await self.db.scalar(select(func.count()).select_from(User))

        user = User(
            username=username,
            email=email,
            display_name=display_name,
            password_hash=hash_password(password),
        )
        self.db.add(user)
        await self.db.flush()

        # First user gets admin role automatically
        if user_count == 0:
            admin_role = await self.db.scalar(
                select(Role).where(Role.name == "admin")
            )
            if admin_role:
                self.db.add(UserRole(user_id=user.id, role_id=admin_role.id))
                await self.db.flush()

        return user

    async def authenticate(self, username: str, password: str) -> User | None:
        result = await self.db.execute(
            select(User)
            .options(selectinload(User.user_roles))
            .where(or_(User.username == username, User.email == username))
        )
        user = result.scalar_one_or_none()

        if user is None or not user.is_active:
            return None
        if not verify_password(password, user.password_hash):
            return None

        user.last_login_at = datetime.now(timezone.utc)
        return user

    async def get_user_permissions(self, user_id: UUID) -> tuple[list[str], list[str]]:
        """Get the user's role names and flattened permissions list."""
        result = await self.db.execute(
            select(UserRole)
            .options(
                selectinload(UserRole.role)
                .selectinload(Role.role_permissions)
                .selectinload(RolePermission.permission)
            )
            .where(UserRole.user_id == user_id)
        )
        user_roles = result.scalars().all()

        role_names = []
        permissions = set()
        for ur in user_roles:
            role_names.append(ur.role.name)
            for rp in ur.role.role_permissions:
                permissions.add(f"{rp.permission.resource}:{rp.permission.action}")

        return role_names, sorted(permissions)

    async def create_tokens(self, user: User) -> tuple[str, str]:
        """Create access + refresh token pair for a user."""
        role_names, permissions = await self.get_user_permissions(user.id)

        access_token = create_access_token(
            user_id=user.id,
            username=user.username,
            roles=role_names,
            permissions=permissions,
        )

        raw_refresh, refresh_hash = create_refresh_token()
        refresh_record = RefreshToken(
            user_id=user.id,
            token_hash=refresh_hash,
            expires_at=datetime.now(timezone.utc)
            + timedelta(days=settings.jwt_refresh_token_expire_days),
        )
        self.db.add(refresh_record)
        await self.db.flush()

        return access_token, raw_refresh

    async def refresh_access_token(self, raw_refresh_token: str) -> tuple[str, str] | None:
        """Validate a refresh token and issue new token pair."""
        token_hash = hash_refresh_token(raw_refresh_token)
        now = datetime.now(timezone.utc)

        result = await self.db.execute(
            select(RefreshToken)
            .options(selectinload(RefreshToken.user))
            .where(
                RefreshToken.token_hash == token_hash,
                RefreshToken.revoked_at.is_(None),
                RefreshToken.expires_at > now,
            )
        )
        refresh_record = result.scalar_one_or_none()
        if refresh_record is None:
            return None

        # Revoke old token
        refresh_record.revoked_at = now

        user = refresh_record.user
        if not user.is_active:
            return None

        return await self.create_tokens(user)

    async def revoke_refresh_token(self, raw_refresh_token: str) -> bool:
        token_hash = hash_refresh_token(raw_refresh_token)
        result = await self.db.execute(
            select(RefreshToken).where(
                RefreshToken.token_hash == token_hash,
                RefreshToken.revoked_at.is_(None),
            )
        )
        record = result.scalar_one_or_none()
        if record:
            record.revoked_at = datetime.now(timezone.utc)
            return True
        return False

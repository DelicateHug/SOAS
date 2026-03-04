"""SOAS variable business logic - CRUD, permission resolution, Redis caching."""

import json
from typing import Any
from uuid import UUID

import redis.asyncio as aioredis
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from soas_backend.config import settings
from soas_backend.models.soas_variable import SOASVariable, SOASVariablePermission


class SOASVariableService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(
        self,
        name: str,
        created_by: UUID,
        value: Any = None,
        description: str | None = None,
        is_secret: bool = False,
    ) -> SOASVariable:
        variable = SOASVariable(
            name=name,
            description=description,
            value=value,
            is_secret=is_secret,
            created_by=created_by,
        )
        self.db.add(variable)
        await self.db.flush()
        await self.db.refresh(variable)
        await self._cache_variable(variable)
        return variable

    async def get(self, variable_id: UUID) -> SOASVariable | None:
        result = await self.db.execute(
            select(SOASVariable)
            .where(SOASVariable.id == variable_id)
            .options(selectinload(SOASVariable.permissions))
        )
        return result.scalar_one_or_none()

    async def get_by_name(self, name: str) -> SOASVariable | None:
        result = await self.db.execute(
            select(SOASVariable).where(SOASVariable.name == name)
        )
        return result.scalar_one_or_none()

    async def list_variables(
        self, page: int = 1, per_page: int = 25
    ) -> tuple[list[SOASVariable], int]:
        count_result = await self.db.execute(
            select(func.count()).select_from(SOASVariable)
        )
        total = count_result.scalar() or 0

        result = await self.db.execute(
            select(SOASVariable)
            .options(selectinload(SOASVariable.permissions))
            .order_by(SOASVariable.name)
            .offset((page - 1) * per_page)
            .limit(per_page)
        )
        return list(result.scalars().all()), total

    async def update(
        self,
        variable_id: UUID,
        updated_by: UUID,
        value: Any = ...,
        description: str | None = ...,
        is_secret: bool | None = None,
    ) -> SOASVariable | None:
        variable = await self.get(variable_id)
        if not variable:
            return None

        if value is not ...:
            variable.value = value
        if description is not ...:
            variable.description = description
        if is_secret is not None:
            variable.is_secret = is_secret
        variable.updated_by = updated_by

        await self.db.flush()
        await self.db.refresh(variable)
        await self._cache_variable(variable)
        return variable

    async def delete_variable(self, variable_id: UUID) -> bool:
        variable = await self.get(variable_id)
        if not variable:
            return False

        name = variable.name
        await self.db.delete(variable)
        await self.db.flush()

        # Remove from Redis cache
        try:
            from soas_backend.api.deps import get_redis_pool
            r = await get_redis_pool()
            await r.hdel("soas_vars:all", name)
            await r.delete(f"soas_var:{name}")
        except Exception:
            pass

        return True

    async def get_permissions(self, variable_id: UUID) -> list[SOASVariablePermission]:
        result = await self.db.execute(
            select(SOASVariablePermission)
            .where(SOASVariablePermission.variable_id == variable_id)
        )
        return list(result.scalars().all())

    async def set_permissions(
        self,
        variable_id: UUID,
        permissions: list[dict],
        granted_by: UUID | None = None,
    ) -> None:
        # Delete existing permissions
        await self.db.execute(
            delete(SOASVariablePermission)
            .where(SOASVariablePermission.variable_id == variable_id)
        )

        # Insert new permissions
        for perm in permissions:
            self.db.add(
                SOASVariablePermission(
                    variable_id=variable_id,
                    role_id=perm["role_id"],
                    can_read=perm.get("can_read", True),
                    can_write=perm.get("can_write", False),
                    granted_by=granted_by,
                )
            )
        await self.db.flush()

    async def resolve_for_user(self, user_role_ids: list[UUID]) -> dict[str, Any]:
        """Get all SOAS vars the user's roles can read. Returns {name: value}."""
        if not user_role_ids:
            return {}

        result = await self.db.execute(
            select(SOASVariable.name, SOASVariable.value)
            .join(SOASVariablePermission, SOASVariable.id == SOASVariablePermission.variable_id)
            .where(
                SOASVariablePermission.role_id.in_(user_role_ids),
                SOASVariablePermission.can_read == True,  # noqa: E712
            )
            .distinct()
        )
        return {row.name: row.value for row in result.all()}

    async def get_writable_for_user(self, user_role_ids: list[UUID]) -> set[str]:
        """Get names of SOAS vars the user's roles can write."""
        if not user_role_ids:
            return set()

        result = await self.db.execute(
            select(SOASVariable.name)
            .join(SOASVariablePermission, SOASVariable.id == SOASVariablePermission.variable_id)
            .where(
                SOASVariablePermission.role_id.in_(user_role_ids),
                SOASVariablePermission.can_write == True,  # noqa: E712
            )
            .distinct()
        )
        return {row.name for row in result.all()}

    async def _cache_variable(self, variable: SOASVariable) -> None:
        """Cache variable value in Redis for fast runtime access."""
        try:
            from soas_backend.api.deps import get_redis_pool
            r = await get_redis_pool()
            encoded = json.dumps(variable.value, default=str)
            await r.hset("soas_vars:all", variable.name, encoded)
            await r.set(f"soas_var:{variable.name}", encoded)
        except Exception:
            pass

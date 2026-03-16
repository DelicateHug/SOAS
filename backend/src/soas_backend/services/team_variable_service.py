"""Team variable business logic - CRUD, permission resolution, Redis caching."""

import json
from typing import Any
from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from soas_backend.models.team_variable import TeamVariable, TeamVariablePermission


class TeamVariableService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(
        self,
        team_id: UUID,
        name: str,
        created_by: UUID,
        value: Any = None,
        description: str | None = None,
        is_secret: bool = False,
    ) -> TeamVariable:
        variable = TeamVariable(
            team_id=team_id,
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

    async def get(self, variable_id: UUID) -> TeamVariable | None:
        result = await self.db.execute(
            select(TeamVariable)
            .where(TeamVariable.id == variable_id)
            .options(selectinload(TeamVariable.permissions))
        )
        return result.scalar_one_or_none()

    async def get_by_name(self, team_id: UUID, name: str) -> TeamVariable | None:
        result = await self.db.execute(
            select(TeamVariable).where(
                TeamVariable.team_id == team_id,
                TeamVariable.name == name,
            )
        )
        return result.scalar_one_or_none()

    async def list_variables(
        self, team_id: UUID, page: int = 1, per_page: int = 25
    ) -> tuple[list[TeamVariable], int]:
        count_result = await self.db.execute(
            select(func.count()).select_from(TeamVariable)
            .where(TeamVariable.team_id == team_id)
        )
        total = count_result.scalar() or 0

        result = await self.db.execute(
            select(TeamVariable)
            .where(TeamVariable.team_id == team_id)
            .options(selectinload(TeamVariable.permissions))
            .order_by(TeamVariable.name)
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
    ) -> TeamVariable | None:
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

        team_id = variable.team_id
        name = variable.name
        await self.db.delete(variable)
        await self.db.flush()

        # Remove from Redis cache
        try:
            from soas_backend.api.deps import get_redis_pool
            r = await get_redis_pool()
            await r.hdel(f"team_vars:{team_id}", name)
        except Exception:
            pass

        return True

    async def get_permissions(self, variable_id: UUID) -> list[TeamVariablePermission]:
        result = await self.db.execute(
            select(TeamVariablePermission)
            .where(TeamVariablePermission.variable_id == variable_id)
            .options(selectinload(TeamVariablePermission.role))
        )
        return list(result.scalars().all())

    async def set_permissions(
        self,
        variable_id: UUID,
        permissions: list[dict],
        granted_by: UUID | None = None,
    ) -> None:
        await self.db.execute(
            delete(TeamVariablePermission)
            .where(TeamVariablePermission.variable_id == variable_id)
        )

        for perm in permissions:
            self.db.add(
                TeamVariablePermission(
                    variable_id=variable_id,
                    role_id=perm["role_id"],
                    can_read=perm.get("can_read", True),
                    can_write=perm.get("can_write", False),
                    granted_by=granted_by,
                )
            )
        await self.db.flush()

    async def resolve_for_team_roles(
        self, team_id: UUID, role_ids: list[UUID]
    ) -> dict[str, Any]:
        """Get all team vars readable by the given roles. Returns {name: value}."""
        if not role_ids:
            return {}

        result = await self.db.execute(
            select(TeamVariable.name, TeamVariable.value)
            .join(TeamVariablePermission, TeamVariable.id == TeamVariablePermission.variable_id)
            .where(
                TeamVariable.team_id == team_id,
                TeamVariablePermission.role_id.in_(role_ids),
                TeamVariablePermission.can_read == True,  # noqa: E712
            )
            .distinct()
        )
        return {row.name: row.value for row in result.all()}

    async def get_writable_for_team_roles(
        self, team_id: UUID, role_ids: list[UUID]
    ) -> set[str]:
        """Get names of team vars writable by the given roles."""
        if not role_ids:
            return set()

        result = await self.db.execute(
            select(TeamVariable.name)
            .join(TeamVariablePermission, TeamVariable.id == TeamVariablePermission.variable_id)
            .where(
                TeamVariable.team_id == team_id,
                TeamVariablePermission.role_id.in_(role_ids),
                TeamVariablePermission.can_write == True,  # noqa: E712
            )
            .distinct()
        )
        return {row.name for row in result.all()}

    async def _cache_variable(self, variable: TeamVariable) -> None:
        """Cache variable value in Redis for fast runtime access."""
        try:
            from soas_backend.api.deps import get_redis_pool
            r = await get_redis_pool()
            encoded = json.dumps(variable.value, default=str)
            await r.hset(f"team_vars:{variable.team_id}", variable.name, encoded)
        except Exception:
            pass

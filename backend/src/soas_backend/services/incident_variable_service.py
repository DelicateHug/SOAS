"""Incident variable definition service - simple CRUD for variable name registry."""

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from soas_backend.models.incident_variable import IncidentVariable


class IncidentVariableService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(
        self,
        name: str,
        created_by: UUID,
        description: str | None = None,
        default_enabled: bool = True,
    ) -> IncidentVariable:
        variable = IncidentVariable(
            name=name,
            description=description,
            default_enabled=default_enabled,
            created_by=created_by,
        )
        self.db.add(variable)
        await self.db.flush()
        await self.db.refresh(variable)
        return variable

    async def get(self, variable_id: UUID) -> IncidentVariable | None:
        result = await self.db.execute(
            select(IncidentVariable).where(IncidentVariable.id == variable_id)
        )
        return result.scalar_one_or_none()

    async def get_by_name(self, name: str) -> IncidentVariable | None:
        result = await self.db.execute(
            select(IncidentVariable).where(IncidentVariable.name == name)
        )
        return result.scalar_one_or_none()

    async def list_variables(
        self, page: int = 1, per_page: int = 25
    ) -> tuple[list[IncidentVariable], int]:
        count_result = await self.db.execute(
            select(func.count()).select_from(IncidentVariable)
        )
        total = count_result.scalar() or 0

        result = await self.db.execute(
            select(IncidentVariable)
            .order_by(IncidentVariable.name)
            .offset((page - 1) * per_page)
            .limit(per_page)
        )
        return list(result.scalars().all()), total

    async def update(
        self,
        variable_id: UUID,
        description: str | None = ...,
        default_enabled: bool | None = None,
    ) -> IncidentVariable | None:
        variable = await self.get(variable_id)
        if not variable:
            return None

        if description is not ...:
            variable.description = description
        if default_enabled is not None:
            variable.default_enabled = default_enabled

        await self.db.flush()
        await self.db.refresh(variable)
        return variable

    async def delete_variable(self, variable_id: UUID) -> bool:
        variable = await self.get(variable_id)
        if not variable:
            return False
        await self.db.delete(variable)
        await self.db.flush()
        return True

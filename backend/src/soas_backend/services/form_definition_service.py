"""Form definition CRUD service."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from soas_backend.models.form_definition import FormDefinition


class FormDefinitionService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list(
        self,
        active_only: bool = False,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[list[FormDefinition], int]:
        query = select(FormDefinition).options(
            selectinload(FormDefinition.creator),
            selectinload(FormDefinition.updater),
        )
        count_query = select(func.count()).select_from(FormDefinition)

        if active_only:
            query = query.where(FormDefinition.is_active == True)  # noqa: E712
            count_query = count_query.where(FormDefinition.is_active == True)  # noqa: E712

        total = (await self.db.execute(count_query)).scalar()
        result = await self.db.execute(
            query.order_by(FormDefinition.name).offset(offset).limit(limit)
        )
        return list(result.scalars().all()), total

    async def get(self, definition_id: UUID) -> FormDefinition | None:
        result = await self.db.execute(
            select(FormDefinition)
            .where(FormDefinition.id == definition_id)
            .options(
                selectinload(FormDefinition.creator),
                selectinload(FormDefinition.updater),
            )
        )
        return result.scalar_one_or_none()

    async def create(
        self,
        name: str,
        fields: list[dict],
        created_by: UUID,
        description: str | None = None,
    ) -> FormDefinition:
        definition = FormDefinition(
            name=name,
            description=description,
            fields=fields,
            created_by=created_by,
        )
        self.db.add(definition)
        await self.db.flush()
        return await self.get(definition.id)

    async def update(
        self,
        definition_id: UUID,
        updated_by: UUID,
        name: str | None = None,
        description: str | None = None,
        fields: list[dict] | None = None,
        is_active: bool | None = None,
    ) -> FormDefinition | None:
        definition = await self.get(definition_id)
        if not definition:
            return None
        if name is not None:
            definition.name = name
        if description is not None:
            definition.description = description
        if fields is not None:
            definition.fields = fields
        if is_active is not None:
            definition.is_active = is_active
        definition.updated_by = updated_by
        await self.db.flush()
        return await self.get(definition_id)

    async def delete(self, definition_id: UUID) -> bool:
        definition = await self.get(definition_id)
        if not definition:
            return False
        await self.db.delete(definition)
        await self.db.flush()
        return True

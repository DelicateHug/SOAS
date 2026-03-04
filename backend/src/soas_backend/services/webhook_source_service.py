"""Webhook source CRUD and source-automation linking service."""

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from soas_backend.models.webhook_source import SourceAutomation, WebhookSource


class WebhookSourceService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_sources(self) -> list[WebhookSource]:
        result = await self.db.execute(
            select(WebhookSource)
            .options(selectinload(WebhookSource.automations))
            .order_by(WebhookSource.name)
        )
        return list(result.scalars().all())

    async def get(self, source_id: UUID) -> WebhookSource | None:
        result = await self.db.execute(
            select(WebhookSource)
            .where(WebhookSource.id == source_id)
            .options(
                selectinload(WebhookSource.automations).selectinload(
                    SourceAutomation.automation
                )
            )
        )
        return result.scalar_one_or_none()

    async def create(
        self,
        name: str,
        created_by: UUID,
        description: str | None = None,
        icon: str | None = None,
    ) -> WebhookSource:
        source = WebhookSource(
            name=name,
            description=description,
            icon=icon,
            created_by=created_by,
        )
        self.db.add(source)
        await self.db.flush()
        return await self.get(source.id)

    async def update(
        self,
        source_id: UUID,
        **kwargs,
    ) -> WebhookSource | None:
        source = await self.get(source_id)
        if not source:
            return None
        for key, value in kwargs.items():
            if hasattr(source, key) and value is not None:
                setattr(source, key, value)
        await self.db.flush()
        return await self.get(source_id)

    async def delete(self, source_id: UUID) -> bool:
        source = await self.get(source_id)
        if not source:
            return False
        await self.db.delete(source)
        await self.db.flush()
        return True

    async def link_automation(
        self,
        source_id: UUID,
        automation_id: UUID,
        is_enabled: bool = True,
        run_order: int = 0,
    ) -> SourceAutomation:
        link = SourceAutomation(
            source_id=source_id,
            automation_id=automation_id,
            is_enabled=is_enabled,
            run_order=run_order,
        )
        self.db.add(link)
        await self.db.flush()
        return link

    async def update_link(
        self, source_id: UUID, automation_id: UUID, **kwargs
    ) -> SourceAutomation | None:
        result = await self.db.execute(
            select(SourceAutomation).where(
                SourceAutomation.source_id == source_id,
                SourceAutomation.automation_id == automation_id,
            )
        )
        link = result.scalar_one_or_none()
        if not link:
            return None
        for key, value in kwargs.items():
            if hasattr(link, key) and value is not None:
                setattr(link, key, value)
        await self.db.flush()
        return link

    async def unlink_automation(self, source_id: UUID, automation_id: UUID) -> bool:
        result = await self.db.execute(
            select(SourceAutomation).where(
                SourceAutomation.source_id == source_id,
                SourceAutomation.automation_id == automation_id,
            )
        )
        link = result.scalar_one_or_none()
        if not link:
            return False
        await self.db.delete(link)
        await self.db.flush()
        return True

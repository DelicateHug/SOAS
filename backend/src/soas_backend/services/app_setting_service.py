"""Application settings service."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from soas_backend.models.app_setting import AppSetting


class AppSettingService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get(self, key: str) -> AppSetting | None:
        result = await self.db.execute(
            select(AppSetting).where(AppSetting.key == key)
        )
        return result.scalar_one_or_none()

    async def get_value(self, key: str, default: str | None = None) -> str | None:
        setting = await self.get(key)
        return setting.value if setting else default

    async def get_all(self) -> list[AppSetting]:
        result = await self.db.execute(
            select(AppSetting).order_by(AppSetting.key)
        )
        return list(result.scalars().all())

    async def set(self, key: str, value: str, updated_by: UUID | None = None) -> AppSetting:
        setting = await self.get(key)
        if setting:
            setting.value = value
            setting.updated_by = updated_by
        else:
            setting = AppSetting(key=key, value=value, updated_by=updated_by)
            self.db.add(setting)
        await self.db.flush()
        return setting

    async def get_file_ttl_days(self) -> int:
        """Return the configured file TTL in days. 0 means no expiration."""
        val = await self.get_value("file_ttl_days", "90")
        try:
            return max(0, int(val))
        except (ValueError, TypeError):
            return 90

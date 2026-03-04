"""Generic version control service for automations, code blocks, and jobs."""

from uuid import UUID

from sqlalchemy import delete as sa_delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from soas_backend.models.automation import Automation, AutomationVersion
from soas_backend.models.code_library import CodeLibraryBlock, CodeLibraryBlockVersion
from soas_backend.models.scheduled_job import ScheduledJob, ScheduledJobVersion

MAX_VERSIONS = 20


class VersionService:
    def __init__(self, db: AsyncSession):
        self.db = db

    # ── Automation versions ──────────────────────────────────────────

    async def list_automation_versions(self, automation_id: UUID) -> list[AutomationVersion]:
        result = await self.db.execute(
            select(AutomationVersion)
            .options(selectinload(AutomationVersion.creator))
            .where(AutomationVersion.automation_id == automation_id)
            .order_by(AutomationVersion.version_number.desc())
        )
        return list(result.scalars().all())

    async def get_automation_version(
        self, automation_id: UUID, version_number: int
    ) -> AutomationVersion | None:
        result = await self.db.execute(
            select(AutomationVersion)
            .options(selectinload(AutomationVersion.creator))
            .where(
                AutomationVersion.automation_id == automation_id,
                AutomationVersion.version_number == version_number,
            )
        )
        return result.scalar_one_or_none()

    async def save_automation_version(
        self,
        automation: Automation,
        created_by: UUID,
        name: str | None = None,
        description: str | None = None,
    ) -> AutomationVersion:
        """Save/upsert a version snapshot for the current automation state."""
        existing = await self.get_automation_version(automation.id, automation.version)
        if existing:
            existing.graph_data = automation.graph_data
            existing.parameters = automation.parameters
            existing.timeout_seconds = automation.timeout_seconds
            existing.tags = automation.tags
            existing.trigger_tags = automation.trigger_tags
            existing.is_trigger_enabled = automation.is_trigger_enabled
            existing.documentation = automation.documentation
            if name is not None:
                existing.name = name
            if description is not None:
                existing.description = description
            await self.db.flush()
            return existing

        version = AutomationVersion(
            automation_id=automation.id,
            version_number=automation.version,
            name=name,
            description=description,
            graph_data=automation.graph_data,
            parameters=automation.parameters,
            timeout_seconds=automation.timeout_seconds,
            tags=automation.tags,
            trigger_tags=automation.trigger_tags,
            is_trigger_enabled=automation.is_trigger_enabled,
            documentation=automation.documentation,
            created_by=created_by,
        )
        self.db.add(version)
        await self.db.flush()
        await self._prune_automation_versions(automation.id)
        return version

    async def create_automation_version(
        self,
        automation: Automation,
        created_by: UUID,
        name: str | None = None,
        description: str | None = None,
    ) -> AutomationVersion:
        """Create a new version by copying current state to version+1."""
        new_version_number = automation.version + 1
        automation.version = new_version_number
        await self.db.flush()

        version = AutomationVersion(
            automation_id=automation.id,
            version_number=new_version_number,
            name=name,
            description=description,
            graph_data=automation.graph_data,
            parameters=automation.parameters,
            timeout_seconds=automation.timeout_seconds,
            tags=automation.tags,
            trigger_tags=automation.trigger_tags,
            is_trigger_enabled=automation.is_trigger_enabled,
            documentation=automation.documentation,
            created_by=created_by,
        )
        self.db.add(version)
        await self.db.flush()
        await self._prune_automation_versions(automation.id)
        return version

    async def restore_automation_version(
        self, automation: Automation, version_number: int
    ) -> Automation | None:
        """Restore automation state from a version snapshot."""
        version = await self.get_automation_version(automation.id, version_number)
        if not version:
            return None

        automation.version = version.version_number
        automation.graph_data = version.graph_data
        automation.parameters = version.parameters or []
        automation.timeout_seconds = version.timeout_seconds or 300
        automation.tags = version.tags or []
        automation.trigger_tags = version.trigger_tags or []
        automation.is_trigger_enabled = version.is_trigger_enabled or False
        automation.documentation = version.documentation
        await self.db.flush()
        return automation

    async def update_automation_version_meta(
        self, automation_id: UUID, version_number: int, name: str | None, description: str | None
    ) -> AutomationVersion | None:
        version = await self.get_automation_version(automation_id, version_number)
        if not version:
            return None
        if name is not None:
            version.name = name
        if description is not None:
            version.description = description
        await self.db.flush()
        return version

    async def _prune_automation_versions(self, automation_id: UUID) -> None:
        count_result = await self.db.execute(
            select(func.count()).where(AutomationVersion.automation_id == automation_id)
        )
        count = count_result.scalar() or 0
        if count > MAX_VERSIONS:
            oldest = await self.db.execute(
                select(AutomationVersion.id)
                .where(AutomationVersion.automation_id == automation_id)
                .order_by(AutomationVersion.version_number.asc())
                .limit(count - MAX_VERSIONS)
            )
            ids_to_delete = [row.id for row in oldest.all()]
            if ids_to_delete:
                await self.db.execute(
                    sa_delete(AutomationVersion).where(AutomationVersion.id.in_(ids_to_delete))
                )

    # ── Code library block versions ──────────────────────────────────

    async def list_code_block_versions(self, block_id: UUID) -> list[CodeLibraryBlockVersion]:
        result = await self.db.execute(
            select(CodeLibraryBlockVersion)
            .options(selectinload(CodeLibraryBlockVersion.creator))
            .where(CodeLibraryBlockVersion.block_id == block_id)
            .order_by(CodeLibraryBlockVersion.version_number.desc())
        )
        return list(result.scalars().all())

    async def get_code_block_version(
        self, block_id: UUID, version_number: int
    ) -> CodeLibraryBlockVersion | None:
        result = await self.db.execute(
            select(CodeLibraryBlockVersion)
            .options(selectinload(CodeLibraryBlockVersion.creator))
            .where(
                CodeLibraryBlockVersion.block_id == block_id,
                CodeLibraryBlockVersion.version_number == version_number,
            )
        )
        return result.scalar_one_or_none()

    async def save_code_block_version(
        self,
        block: CodeLibraryBlock,
        created_by: UUID,
        name: str | None = None,
        description: str | None = None,
    ) -> CodeLibraryBlockVersion:
        existing = await self.get_code_block_version(block.id, block.version)
        if existing:
            existing.code = block.code
            existing.language = block.language
            existing.input_ports = block.input_ports
            existing.output_ports = block.output_ports
            existing.tags = block.tags
            if name is not None:
                existing.name = name
            if description is not None:
                existing.description = description
            await self.db.flush()
            return existing

        version = CodeLibraryBlockVersion(
            block_id=block.id,
            version_number=block.version,
            name=name,
            description=description,
            code=block.code,
            language=block.language,
            input_ports=block.input_ports,
            output_ports=block.output_ports,
            tags=block.tags,
            created_by=created_by,
        )
        self.db.add(version)
        await self.db.flush()
        await self._prune_code_block_versions(block.id)
        return version

    async def create_code_block_version(
        self,
        block: CodeLibraryBlock,
        created_by: UUID,
        name: str | None = None,
        description: str | None = None,
    ) -> CodeLibraryBlockVersion:
        new_version_number = block.version + 1
        block.version = new_version_number
        await self.db.flush()

        version = CodeLibraryBlockVersion(
            block_id=block.id,
            version_number=new_version_number,
            name=name,
            description=description,
            code=block.code,
            language=block.language,
            input_ports=block.input_ports,
            output_ports=block.output_ports,
            tags=block.tags,
            created_by=created_by,
        )
        self.db.add(version)
        await self.db.flush()
        await self._prune_code_block_versions(block.id)
        return version

    async def restore_code_block_version(
        self, block: CodeLibraryBlock, version_number: int
    ) -> CodeLibraryBlock | None:
        version = await self.get_code_block_version(block.id, version_number)
        if not version:
            return None

        block.version = version.version_number
        block.code = version.code
        block.language = version.language or "python"
        block.input_ports = version.input_ports
        block.output_ports = version.output_ports
        block.tags = version.tags or []
        await self.db.flush()
        return block

    async def update_code_block_version_meta(
        self, block_id: UUID, version_number: int, name: str | None, description: str | None
    ) -> CodeLibraryBlockVersion | None:
        version = await self.get_code_block_version(block_id, version_number)
        if not version:
            return None
        if name is not None:
            version.name = name
        if description is not None:
            version.description = description
        await self.db.flush()
        return version

    async def _prune_code_block_versions(self, block_id: UUID) -> None:
        count_result = await self.db.execute(
            select(func.count()).where(CodeLibraryBlockVersion.block_id == block_id)
        )
        count = count_result.scalar() or 0
        if count > MAX_VERSIONS:
            oldest = await self.db.execute(
                select(CodeLibraryBlockVersion.id)
                .where(CodeLibraryBlockVersion.block_id == block_id)
                .order_by(CodeLibraryBlockVersion.version_number.asc())
                .limit(count - MAX_VERSIONS)
            )
            ids_to_delete = [row.id for row in oldest.all()]
            if ids_to_delete:
                await self.db.execute(
                    sa_delete(CodeLibraryBlockVersion).where(
                        CodeLibraryBlockVersion.id.in_(ids_to_delete)
                    )
                )

    # ── Scheduled job versions ───────────────────────────────────────

    async def list_job_versions(self, job_id: UUID) -> list[ScheduledJobVersion]:
        result = await self.db.execute(
            select(ScheduledJobVersion)
            .options(selectinload(ScheduledJobVersion.creator))
            .where(ScheduledJobVersion.job_id == job_id)
            .order_by(ScheduledJobVersion.version_number.desc())
        )
        return list(result.scalars().all())

    async def get_job_version(
        self, job_id: UUID, version_number: int
    ) -> ScheduledJobVersion | None:
        result = await self.db.execute(
            select(ScheduledJobVersion)
            .options(selectinload(ScheduledJobVersion.creator))
            .where(
                ScheduledJobVersion.job_id == job_id,
                ScheduledJobVersion.version_number == version_number,
            )
        )
        return result.scalar_one_or_none()

    async def save_job_version(
        self,
        job: ScheduledJob,
        created_by: UUID,
        name: str | None = None,
        description: str | None = None,
    ) -> ScheduledJobVersion:
        # Jobs don't have a version field; we'll track by count
        count_result = await self.db.execute(
            select(func.count()).where(ScheduledJobVersion.job_id == job.id)
        )
        version_number = (count_result.scalar() or 0) + 1

        # Check if this version already exists
        existing = await self.get_job_version(job.id, version_number)
        if existing:
            existing.schedule_type = job.schedule_type
            existing.cron_expression = job.cron_expression
            existing.interval_seconds = job.interval_seconds
            existing.calendar_config = job.calendar_config
            existing.timezone = job.timezone
            existing.parameters = job.parameters
            if name is not None:
                existing.name = name
            if description is not None:
                existing.description = description
            await self.db.flush()
            return existing

        version = ScheduledJobVersion(
            job_id=job.id,
            version_number=version_number,
            name=name,
            description=description,
            schedule_type=job.schedule_type,
            cron_expression=job.cron_expression,
            interval_seconds=job.interval_seconds,
            calendar_config=job.calendar_config,
            timezone=job.timezone,
            parameters=job.parameters,
            created_by=created_by,
        )
        self.db.add(version)
        await self.db.flush()
        await self._prune_job_versions(job.id)
        return version

    async def create_job_version(
        self,
        job: ScheduledJob,
        created_by: UUID,
        name: str | None = None,
        description: str | None = None,
    ) -> ScheduledJobVersion:
        max_result = await self.db.execute(
            select(func.max(ScheduledJobVersion.version_number))
            .where(ScheduledJobVersion.job_id == job.id)
        )
        max_version = max_result.scalar() or 0
        new_version_number = max_version + 1

        version = ScheduledJobVersion(
            job_id=job.id,
            version_number=new_version_number,
            name=name,
            description=description,
            schedule_type=job.schedule_type,
            cron_expression=job.cron_expression,
            interval_seconds=job.interval_seconds,
            calendar_config=job.calendar_config,
            timezone=job.timezone,
            parameters=job.parameters,
            created_by=created_by,
        )
        self.db.add(version)
        await self.db.flush()
        await self._prune_job_versions(job.id)
        return version

    async def restore_job_version(
        self, job: ScheduledJob, version_number: int
    ) -> ScheduledJob | None:
        version = await self.get_job_version(job.id, version_number)
        if not version:
            return None

        job.schedule_type = version.schedule_type or job.schedule_type
        job.cron_expression = version.cron_expression
        job.interval_seconds = version.interval_seconds
        job.calendar_config = version.calendar_config
        job.timezone = version.timezone or "UTC"
        job.parameters = version.parameters or {}
        await self.db.flush()
        return job

    async def update_job_version_meta(
        self, job_id: UUID, version_number: int, name: str | None, description: str | None
    ) -> ScheduledJobVersion | None:
        version = await self.get_job_version(job_id, version_number)
        if not version:
            return None
        if name is not None:
            version.name = name
        if description is not None:
            version.description = description
        await self.db.flush()
        return version

    async def _prune_job_versions(self, job_id: UUID) -> None:
        count_result = await self.db.execute(
            select(func.count()).where(ScheduledJobVersion.job_id == job_id)
        )
        count = count_result.scalar() or 0
        if count > MAX_VERSIONS:
            oldest = await self.db.execute(
                select(ScheduledJobVersion.id)
                .where(ScheduledJobVersion.job_id == job_id)
                .order_by(ScheduledJobVersion.version_number.asc())
                .limit(count - MAX_VERSIONS)
            )
            ids_to_delete = [row.id for row in oldest.all()]
            if ids_to_delete:
                await self.db.execute(
                    sa_delete(ScheduledJobVersion).where(
                        ScheduledJobVersion.id.in_(ids_to_delete)
                    )
                )

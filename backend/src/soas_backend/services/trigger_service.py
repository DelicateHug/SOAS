"""Tag-based automation triggering.

When incident tags change, this service finds automations whose
``trigger_tags`` overlap with the new tags and dispatches execution.
"""

import logging
from typing import Any
from uuid import UUID

from soas_backend.celery_proxy import get_celery
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from soas_backend.config import settings
from soas_backend.models.automation import Automation
from soas_backend.models.execution import ExecutionLog
from soas_backend.models.webhook_source import SourceAutomation

logger = logging.getLogger(__name__)


class TriggerService:
    """Evaluate tag-change events and dispatch matching automations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def check_and_trigger(
        self,
        incident_id: UUID,
        new_tags: list[str],
        triggered_by: UUID,
    ) -> list[dict[str, Any]]:
        """Find automations with overlapping trigger_tags and dispatch them.

        Only automations that are ``active`` and have graph_data with
        ``trigger_tags`` matching at least one of *new_tags* will be
        dispatched.

        Args:
            incident_id: The incident whose tags changed.
            new_tags: The tags that were just added to the incident.
            triggered_by: User ID who caused the tag change.

        Returns:
            A list of dicts describing each triggered execution
            (``automation_id``, ``execution_id``, ``celery_task_id``).
        """
        if not new_tags:
            return []

        # Find active automations whose graph_data -> metadata -> trigger_tags
        # overlaps with the new tags.  Postgres ARRAY overlap operator: &&
        # The trigger_tags live in graph_data->'metadata'->'trigger_tags' as
        # a JSONB array.  We also check for a top-level ``tags`` column overlap
        # as a fallback for automations that store trigger tags there.
        query = (
            select(Automation)
            .where(
                Automation.status == "active",
                # ARRAY overlap: automation.tags has at least one of new_tags
                Automation.tags.overlap(new_tags),
            )
        )

        result = await self.db.execute(query)
        automations = list(result.scalars().all())

        if not automations:
            logger.debug(
                "No matching automations for tags %s on incident %s",
                new_tags,
                incident_id,
            )
            return []

        triggered: list[dict[str, Any]] = []
        celery = get_celery()

        for automation in automations:
            if not automation.script_path:
                logger.warning(
                    "Automation %s matched tags but has no compiled script, skipping",
                    automation.id,
                )
                continue

            # Create an execution log entry
            execution = ExecutionLog(
                automation_id=automation.id,
                triggered_by=triggered_by,
                incident_id=incident_id,
                parameters={"trigger_tags": new_tags},
                status="pending",
            )
            self.db.add(execution)
            await self.db.flush()

            # Dispatch Celery task
            task = celery.send_task(
                "soas.run_automation",
                args=[
                    str(execution.id),
                    str(automation.id),
                    {"trigger_tags": new_tags, "incident_id": str(incident_id)},
                ],
            )
            execution.celery_task_id = task.id
            execution.status = "queued"
            await self.db.flush()

            triggered.append({
                "automation_id": str(automation.id),
                "automation_name": automation.name,
                "execution_id": str(execution.id),
                "celery_task_id": task.id,
            })

            logger.info(
                "Triggered automation %s (%s) for incident %s via tags %s",
                automation.id,
                automation.name,
                incident_id,
                new_tags,
            )

        return triggered

    async def trigger_by_source(
        self,
        source_id: UUID,
        incident_id: UUID,
        triggered_by: UUID,
        exclude_automation_ids: set[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Dispatch automations linked to a webhook source.

        Args:
            source_id: The webhook source whose automations to run.
            incident_id: The incident that was just created.
            triggered_by: User ID who caused the trigger.
            exclude_automation_ids: Set of automation ID strings already
                triggered (e.g. by tag-based matching) to avoid duplicates.

        Returns:
            A list of dicts describing each triggered execution.
        """
        exclude = exclude_automation_ids or set()

        query = (
            select(SourceAutomation)
            .join(Automation, SourceAutomation.automation_id == Automation.id)
            .where(
                SourceAutomation.source_id == source_id,
                SourceAutomation.is_enabled == True,
                Automation.status == "active",
            )
            .order_by(SourceAutomation.run_order)
        )

        result = await self.db.execute(query)
        links = list(result.scalars().all())

        if not links:
            logger.debug("No source automations for source %s", source_id)
            return []

        # We need the full Automation objects for script_path
        automation_ids = [link.automation_id for link in links]
        auto_result = await self.db.execute(
            select(Automation).where(Automation.id.in_(automation_ids))
        )
        auto_map = {a.id: a for a in auto_result.scalars().all()}

        triggered: list[dict[str, Any]] = []
        celery = get_celery()

        for link in links:
            if str(link.automation_id) in exclude:
                logger.debug(
                    "Skipping source automation %s (already triggered by tags)",
                    link.automation_id,
                )
                continue

            automation = auto_map.get(link.automation_id)
            if not automation or not automation.script_path:
                continue

            execution = ExecutionLog(
                automation_id=automation.id,
                triggered_by=triggered_by,
                incident_id=incident_id,
                parameters={"trigger_source": str(source_id)},
                status="pending",
            )
            self.db.add(execution)
            await self.db.flush()

            task = celery.send_task(
                "soas.run_automation",
                args=[
                    str(execution.id),
                    str(automation.id),
                    {"trigger_source": str(source_id), "incident_id": str(incident_id)},
                ],
            )
            execution.celery_task_id = task.id
            execution.status = "queued"
            await self.db.flush()

            triggered.append({
                "automation_id": str(automation.id),
                "automation_name": automation.name,
                "execution_id": str(execution.id),
                "celery_task_id": task.id,
            })

            logger.info(
                "Triggered automation %s (%s) for incident %s via source %s",
                automation.id,
                automation.name,
                incident_id,
                source_id,
            )

        return triggered

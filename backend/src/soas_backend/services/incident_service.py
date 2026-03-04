"""Incident business logic."""

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from soas_backend.models.case import CaseIncident
from soas_backend.models.incident import Incident, IncidentAssignment
from soas_backend.models.timeline import TimelineEntry
from soas_shared.constants import ALLOWED_INCIDENT_TRANSITIONS, IncidentStatus


class IncidentService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(
        self,
        title: str,
        created_by: UUID,
        severity: str = "medium",
        summary: str | None = None,
        source: str | None = None,
        source_ref: str | None = None,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        raw_event: dict[str, Any] | None = None,
    ) -> Incident:
        incident = Incident(
            title=title,
            summary=summary,
            severity=severity,
            status="detected",
            source=source,
            source_ref=source_ref,
            created_by=created_by,
            tags=tags or [],
            metadata_=metadata or {},
            raw_event=raw_event,
        )
        self.db.add(incident)
        await self.db.flush()

        # Auto-create timeline entry
        self.db.add(
            TimelineEntry(
                incident_id=incident.id,
                entry_type="created",
                content=f"Incident created: {title}",
                details={"severity": severity},
                created_by=created_by,
            )
        )
        await self.db.flush()
        return incident

    async def get(self, incident_id: UUID) -> Incident | None:
        result = await self.db.execute(
            select(Incident)
            .options(
                selectinload(Incident.lead),
                selectinload(Incident.creator),
                selectinload(Incident.assignments).selectinload(IncidentAssignment.user),
                selectinload(Incident.case_incidents),
            )
            .where(Incident.id == incident_id)
        )
        return result.scalar_one_or_none()

    async def list_incidents(
        self,
        severity: str | None = None,
        status: str | None = None,
        page: int = 1,
        per_page: int = 25,
    ) -> tuple[list[Incident], int]:
        # Build filter conditions once, reuse for count and data queries
        conditions = []
        if severity:
            conditions.append(Incident.severity == severity)
        if status:
            conditions.append(Incident.status == status)

        count_query = select(func.count(Incident.id))
        for cond in conditions:
            count_query = count_query.where(cond)
        total = (await self.db.execute(count_query)).scalar() or 0

        query = (
            select(Incident)
            .options(
                selectinload(Incident.lead),
                selectinload(Incident.creator),
                selectinload(Incident.case_incidents),
            )
            .order_by(Incident.created_at.desc())
            .offset((page - 1) * per_page)
            .limit(per_page)
        )
        for cond in conditions:
            query = query.where(cond)

        result = await self.db.execute(query)
        return list(result.scalars().all()), total

    async def transition(
        self,
        incident_id: UUID,
        new_status: str,
        user_id: UUID,
        comment: str | None = None,
    ) -> Incident:
        incident = await self.get(incident_id)
        if not incident:
            raise ValueError("Incident not found")

        current = IncidentStatus(incident.status)
        target = IncidentStatus(new_status)
        allowed = ALLOWED_INCIDENT_TRANSITIONS.get(current, [])

        if target not in allowed:
            raise ValueError(
                f"Cannot transition from {current} to {target}. "
                f"Allowed: {[s.value for s in allowed]}"
            )

        old_status = incident.status
        incident.status = new_status

        if new_status == "resolved":
            incident.resolved_at = datetime.now(timezone.utc)
        elif new_status == "closed":
            incident.closed_at = datetime.now(timezone.utc)

        # Timeline entry
        content = f"Status changed from {old_status} to {new_status}"
        if comment:
            content += f": {comment}"

        self.db.add(
            TimelineEntry(
                incident_id=incident_id,
                entry_type="status_change",
                content=content,
                details={"old_status": old_status, "new_status": new_status},
                created_by=user_id,
            )
        )
        await self.db.flush()
        return incident

    async def assign(
        self,
        incident_id: UUID,
        user_id: UUID,
        role_in_incident: str = "responder",
        assigned_by: UUID | None = None,
    ) -> IncidentAssignment:
        assignment = IncidentAssignment(
            incident_id=incident_id,
            user_id=user_id,
            role_in_incident=role_in_incident,
            assigned_by=assigned_by,
        )
        self.db.add(assignment)

        if role_in_incident == "lead":
            result = await self.db.execute(
                select(Incident).where(Incident.id == incident_id)
            )
            incident = result.scalar_one()
            incident.lead_id = user_id

        self.db.add(
            TimelineEntry(
                incident_id=incident_id,
                entry_type="assignment",
                content=f"User assigned as {role_in_incident}",
                details={"user_id": str(user_id), "role": role_in_incident},
                created_by=assigned_by,
            )
        )
        await self.db.flush()
        return assignment

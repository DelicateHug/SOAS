"""Case business logic."""

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from soas_backend.models.case import Case, CaseIncident
from soas_backend.models.incident import Incident
from soas_backend.models.timeline import TimelineEntry
from soas_shared.constants import CaseStatus


class CaseService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(
        self,
        title: str,
        created_by: UUID,
        description: str | None = None,
        priority: int = 3,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        team_id: UUID | None = None,
    ) -> Case:
        case = Case(
            title=title,
            description=description,
            priority=priority,
            created_by=created_by,
            tags=tags or [],
            metadata_=metadata or {},
            team_id=team_id,
        )
        self.db.add(case)
        await self.db.flush()

        self.db.add(
            TimelineEntry(
                case_id=case.id,
                entry_type="created",
                content=f"Case created: {title}",
                details={"priority": priority},
                created_by=created_by,
            )
        )
        await self.db.flush()
        return case

    async def get(self, case_id: UUID) -> Case | None:
        result = await self.db.execute(
            select(Case)
            .options(
                selectinload(Case.lead),
                selectinload(Case.creator),
                selectinload(Case.case_incidents),
            )
            .where(Case.id == case_id)
        )
        return result.scalar_one_or_none()

    async def get_with_incidents(self, case_id: UUID) -> Case | None:
        """Get case with full incident details eager-loaded."""
        result = await self.db.execute(
            select(Case)
            .options(
                selectinload(Case.lead),
                selectinload(Case.creator),
                selectinload(Case.case_incidents)
                .selectinload(CaseIncident.incident)
                .selectinload(Incident.lead),
                selectinload(Case.case_incidents)
                .selectinload(CaseIncident.incident)
                .selectinload(Incident.creator),
            )
            .where(Case.id == case_id)
        )
        return result.scalar_one_or_none()

    async def update(
        self,
        case_id: UUID,
        user_id: UUID,
        *,
        title: str | None = None,
        description: str | None = None,
        status: str | None = None,
        priority: int | None = None,
        lead_id: UUID | None = ...,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        cascade_status: bool = False,
    ) -> Case:
        case = await self.get(case_id)
        if not case:
            raise ValueError("Case not found")

        changes: dict[str, Any] = {}

        if title is not None and title != case.title:
            changes["title"] = {"old": case.title, "new": title}
            case.title = title

        if description is not None and description != case.description:
            case.description = description

        if priority is not None and priority != case.priority:
            changes["priority"] = {"old": case.priority, "new": priority}
            case.priority = priority

        if tags is not None:
            case.tags = tags

        if metadata is not None:
            case.metadata_ = metadata

        # lead_id uses sentinel to distinguish "not provided" from "set to None"
        if lead_id is not ...:
            old_lead = case.lead_id
            if lead_id != old_lead:
                changes["lead_id"] = {"old": str(old_lead) if old_lead else None, "new": str(lead_id) if lead_id else None}
                case.lead_id = lead_id

        if status is not None and status != case.status:
            old_status = case.status
            case.status = status
            changes["status"] = {"old": old_status, "new": status}

            if status == "closed":
                case.closed_at = datetime.now(timezone.utc)

            self.db.add(
                TimelineEntry(
                    case_id=case_id,
                    entry_type="status_change",
                    content=f"Status changed from {old_status} to {status}",
                    details={"old_status": old_status, "new_status": status},
                    created_by=user_id,
                )
            )

            if cascade_status:
                await self._cascade_status_to_incidents(case, status, user_id)

        if changes and "status" not in changes:
            # Log non-status changes as a single timeline entry
            parts = []
            if "priority" in changes:
                parts.append(f"Priority changed from P{changes['priority']['old']} to P{changes['priority']['new']}")
            if "lead_id" in changes:
                parts.append("Lead updated")
            if "title" in changes:
                parts.append("Title updated")
            if parts:
                self.db.add(
                    TimelineEntry(
                        case_id=case_id,
                        entry_type="status_change",
                        content="; ".join(parts),
                        details=changes,
                        created_by=user_id,
                    )
                )

        await self.db.flush()
        return case

    async def _cascade_status_to_incidents(
        self, case: Case, new_case_status: str, user_id: UUID
    ) -> None:
        """Map case status to incident status and transition linked incidents."""
        case_to_incident_map = {
            "investigating": "investigating",
            "closed": "closed",
        }
        incident_status = case_to_incident_map.get(new_case_status)
        if not incident_status:
            return

        for ci in case.case_incidents:
            result = await self.db.execute(
                select(Incident).where(Incident.id == ci.incident_id)
            )
            incident = result.scalar_one_or_none()
            if incident and incident.status != incident_status:
                old = incident.status
                incident.status = incident_status
                if incident_status == "closed":
                    incident.closed_at = datetime.now(timezone.utc)
                self.db.add(
                    TimelineEntry(
                        incident_id=incident.id,
                        entry_type="status_change",
                        content=f"Status changed from {old} to {incident_status} (cascaded from case)",
                        details={"old_status": old, "new_status": incident_status, "cascaded_from_case": str(case.id)},
                        created_by=user_id,
                    )
                )

    async def list_cases(
        self,
        status: str | None = None,
        page: int = 1,
        per_page: int = 25,
        priority: int | None = None,
        user_teams: list[dict] | None = None,
        team_id: UUID | None = None,
    ) -> tuple[list[Case], int]:
        conditions = []
        if status:
            conditions.append(Case.status == status)
        if priority is not None:
            conditions.append(Case.priority == priority)

        # Team scoping
        if team_id:
            conditions.append(Case.team_id == team_id)
        elif user_teams is not None:
            team_ids = [UUID(t["id"]) for t in user_teams]
            conditions.append(
                or_(Case.team_id.in_(team_ids), Case.team_id.is_(None))
            )

        query = select(Case).options(
            selectinload(Case.lead),
            selectinload(Case.creator),
            selectinload(Case.case_incidents),
        ).where(*conditions)

        count_query = select(func.count()).select_from(query.subquery())
        total = (await self.db.execute(count_query)).scalar() or 0

        query = query.order_by(Case.created_at.desc())
        query = query.offset((page - 1) * per_page).limit(per_page)

        result = await self.db.execute(query)
        return list(result.scalars().all()), total

    async def link_incident(
        self, case_id: UUID, incident_id: UUID, linked_by: UUID
    ) -> None:
        self.db.add(
            CaseIncident(case_id=case_id, incident_id=incident_id, linked_by=linked_by)
        )
        self.db.add(
            TimelineEntry(
                case_id=case_id,
                entry_type="linked",
                content="Incident linked to case",
                details={"incident_id": str(incident_id)},
                created_by=linked_by,
            )
        )
        await self.db.flush()

    async def list_cases_with_incidents(
        self,
        status: str | None = None,
        page: int = 1,
        per_page: int = 50,
        user_teams: list[dict] | None = None,
        team_id: UUID | None = None,
    ) -> tuple[list[Case], int]:
        """Return cases with their linked incidents eager-loaded."""
        conditions = []
        if status:
            conditions.append(Case.status == status)

        # Team scoping
        if team_id:
            conditions.append(Case.team_id == team_id)
        elif user_teams is not None:
            team_ids = [UUID(t["id"]) for t in user_teams]
            conditions.append(
                or_(Case.team_id.in_(team_ids), Case.team_id.is_(None))
            )

        query = select(Case).options(
            selectinload(Case.lead),
            selectinload(Case.creator),
            selectinload(Case.case_incidents).selectinload(CaseIncident.incident).selectinload(Incident.lead),
            selectinload(Case.case_incidents).selectinload(CaseIncident.incident).selectinload(Incident.creator),
        ).where(*conditions)

        count_query = select(func.count()).select_from(query.subquery())
        total = (await self.db.execute(count_query)).scalar() or 0

        query = query.order_by(Case.created_at.desc())
        query = query.offset((page - 1) * per_page).limit(per_page)

        result = await self.db.execute(query)
        return list(result.scalars().all()), total

    async def unlink_incident(self, case_id: UUID, incident_id: UUID) -> bool:
        result = await self.db.execute(
            select(CaseIncident).where(
                CaseIncident.case_id == case_id,
                CaseIncident.incident_id == incident_id,
            )
        )
        link = result.scalar_one_or_none()
        if link:
            await self.db.delete(link)
            return True
        return False

    async def delete_case(self, case_id: UUID, actor_id: UUID) -> bool:
        """Delete a case and all its dependent rows.

        Tier-3 / danger-zone operation. CaseIncident, CaseNote, CaseFile, TimelineEntry
        rows are all FK-cascaded via ON DELETE CASCADE at the schema level — we don't
        need to walk them manually here.
        """
        result = await self.db.execute(select(Case).where(Case.id == case_id))
        case = result.scalar_one_or_none()
        if case is None:
            return False
        await self.db.delete(case)
        await self.db.flush()
        return True

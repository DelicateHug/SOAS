"""Issue CRUD service."""

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from soas_backend.models.automation import Automation
from soas_backend.models.case import Case
from soas_backend.models.code_library import CodeLibraryBlock
from soas_backend.models.execution import ExecutionLog
from soas_backend.models.incident import Incident
from soas_backend.models.issue import Issue, IssueChecklistItem, IssueLink, IssueNote
from soas_backend.models.normalization import NormalizationRule
from soas_backend.models.role import Role
from soas_backend.models.scheduled_job import ScheduledJob

# Statuses that close an issue
_CLOSED_STATUSES = {"resolved", "closed", "wont_fix"}

# Map target_type -> (Model, name column)
_TARGET_MODEL_MAP: dict[str, tuple] = {
    "incident": (Incident, Incident.title),
    "automation": (Automation, Automation.name),
    "scheduled_job": (ScheduledJob, ScheduledJob.name),
    "role": (Role, Role.display_name),
    "code_library_block": (CodeLibraryBlock, CodeLibraryBlock.name),
    "normalization_rule": (NormalizationRule, NormalizationRule.target_field),
    "case": (Case, Case.title),
    "execution_log": (ExecutionLog, ExecutionLog.id),
}


class IssueService:
    def __init__(self, db: AsyncSession):
        self.db = db

    # ─── helpers ───

    def _base_query(self):
        return select(Issue).options(
            selectinload(Issue.owner),
            selectinload(Issue.creator),
            selectinload(Issue.links),
            selectinload(Issue.notes),
            selectinload(Issue.checklist_items),
        )

    async def _resolve_target_name(self, target_type: str, target_id: UUID) -> str | None:
        entry = _TARGET_MODEL_MAP.get(target_type)
        if not entry:
            return None
        model, name_col = entry
        result = await self.db.execute(
            select(name_col).where(model.id == target_id)
        )
        val = result.scalar_one_or_none()
        return str(val) if val is not None else None

    # ─── Core Issue CRUD ───

    async def get(self, issue_id: UUID) -> Issue | None:
        result = await self.db.execute(
            self._base_query().where(Issue.id == issue_id)
        )
        return result.scalar_one_or_none()

    async def list_issues(
        self,
        status: str | None = None,
        assigned_to: UUID | None = None,
        target_type: str | None = None,
        target_id: UUID | None = None,
        search: str | None = None,
        page: int = 1,
        per_page: int = 25,
    ) -> tuple[list[Issue], int]:
        query = self._base_query()

        if status:
            query = query.where(Issue.status == status)
        if assigned_to:
            query = query.where(Issue.assigned_to == assigned_to)
        if search:
            query = query.where(Issue.title.ilike(f"%{search}%"))

        # Filter by linked target
        if target_type and target_id:
            query = query.where(
                Issue.id.in_(
                    select(IssueLink.issue_id).where(
                        IssueLink.target_type == target_type,
                        IssueLink.target_id == target_id,
                    )
                )
            )

        count_query = select(func.count()).select_from(query.subquery())
        total = (await self.db.execute(count_query)).scalar() or 0

        query = query.order_by(Issue.created_at.desc())
        query = query.offset((page - 1) * per_page).limit(per_page)

        result = await self.db.execute(query)
        return list(result.scalars().unique().all()), total

    async def create(
        self,
        title: str,
        created_by: UUID,
        description: str | None = None,
        assigned_to: UUID | None = None,
        graph_annotation: dict | None = None,
        links: list[dict] | None = None,
    ) -> Issue:
        issue = Issue(
            title=title,
            description=description,
            assigned_to=assigned_to,
            created_by=created_by,
            graph_annotation=graph_annotation,
        )
        self.db.add(issue)
        await self.db.flush()

        # Create initial links
        if links:
            for link_data in links:
                self.db.add(
                    IssueLink(
                        issue_id=issue.id,
                        target_type=link_data["target_type"],
                        target_id=link_data["target_id"],
                    )
                )
            await self.db.flush()

        return await self.get(issue.id)

    async def update(self, issue_id: UUID, **fields) -> Issue | None:
        issue = await self.get(issue_id)
        if not issue:
            return None

        for key, value in fields.items():
            if hasattr(issue, key):
                setattr(issue, key, value)

        # Auto-manage closed_at based on status
        new_status = fields.get("status")
        if new_status:
            if new_status in _CLOSED_STATUSES:
                issue.closed_at = datetime.now(timezone.utc)
            else:
                issue.closed_at = None

        await self.db.flush()
        return await self.get(issue_id)

    async def delete(self, issue_id: UUID) -> bool:
        issue = await self.get(issue_id)
        if not issue:
            return False
        await self.db.delete(issue)
        await self.db.flush()
        return True

    # ─── Links ───

    async def add_link(
        self, issue_id: UUID, target_type: str, target_id: UUID
    ) -> IssueLink:
        link = IssueLink(
            issue_id=issue_id,
            target_type=target_type,
            target_id=target_id,
        )
        self.db.add(link)
        await self.db.flush()
        return link

    async def remove_link(self, link_id: UUID) -> bool:
        result = await self.db.execute(
            select(IssueLink).where(IssueLink.id == link_id)
        )
        link = result.scalar_one_or_none()
        if not link:
            return False
        await self.db.delete(link)
        await self.db.flush()
        return True

    async def get_link(self, link_id: UUID) -> IssueLink | None:
        result = await self.db.execute(
            select(IssueLink).where(IssueLink.id == link_id)
        )
        return result.scalar_one_or_none()

    async def get_issues_for_target(
        self, target_type: str, target_id: UUID
    ) -> list[Issue]:
        query = (
            self._base_query()
            .where(
                Issue.id.in_(
                    select(IssueLink.issue_id).where(
                        IssueLink.target_type == target_type,
                        IssueLink.target_id == target_id,
                    )
                )
            )
            .order_by(Issue.created_at.desc())
        )
        result = await self.db.execute(query)
        return list(result.scalars().unique().all())

    async def get_issues_for_automation_graph(
        self, automation_id: UUID
    ) -> list[Issue]:
        query = (
            self._base_query()
            .where(
                Issue.id.in_(
                    select(IssueLink.issue_id).where(
                        IssueLink.target_type == "automation",
                        IssueLink.target_id == automation_id,
                    )
                ),
                Issue.graph_annotation.isnot(None),
            )
            .order_by(Issue.created_at.desc())
        )
        result = await self.db.execute(query)
        return list(result.scalars().unique().all())

    async def resolve_link_names(self, links: list[IssueLink]) -> list[dict]:
        """Resolve target_name for a list of issue links."""
        results = []
        for link in links:
            name = await self._resolve_target_name(link.target_type, link.target_id)
            results.append(
                {
                    "id": link.id,
                    "target_type": link.target_type,
                    "target_id": link.target_id,
                    "target_name": name,
                }
            )
        return results

    # ─── Notes ───

    async def list_notes(self, issue_id: UUID) -> list[IssueNote]:
        result = await self.db.execute(
            select(IssueNote)
            .where(IssueNote.issue_id == issue_id)
            .options(
                selectinload(IssueNote.creator),
                selectinload(IssueNote.updater),
            )
            .order_by(IssueNote.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_note(self, note_id: UUID) -> IssueNote | None:
        result = await self.db.execute(
            select(IssueNote)
            .where(IssueNote.id == note_id)
            .options(
                selectinload(IssueNote.creator),
                selectinload(IssueNote.updater),
            )
        )
        return result.scalar_one_or_none()

    async def create_note(
        self, issue_id: UUID, content: str, created_by: UUID
    ) -> IssueNote:
        note = IssueNote(
            issue_id=issue_id,
            content=content,
            created_by=created_by,
        )
        self.db.add(note)
        await self.db.flush()
        return await self.get_note(note.id)

    async def update_note(
        self, note_id: UUID, updated_by: UUID, content: str | None = None
    ) -> IssueNote | None:
        note = await self.get_note(note_id)
        if not note:
            return None
        if content is not None:
            note.content = content
        note.updated_by = updated_by
        await self.db.flush()
        return await self.get_note(note_id)

    async def delete_note(self, note_id: UUID) -> bool:
        note = await self.get_note(note_id)
        if not note:
            return False
        await self.db.delete(note)
        await self.db.flush()
        return True

    async def toggle_evidence(self, note_id: UUID) -> IssueNote | None:
        note = await self.get_note(note_id)
        if not note:
            return None
        note.is_evidence = not note.is_evidence
        await self.db.flush()
        return await self.get_note(note_id)

    # ─── Checklist ───

    async def list_checklist(self, issue_id: UUID) -> list[IssueChecklistItem]:
        result = await self.db.execute(
            select(IssueChecklistItem)
            .where(IssueChecklistItem.issue_id == issue_id)
            .options(selectinload(IssueChecklistItem.creator))
            .order_by(IssueChecklistItem.sort_order)
        )
        return list(result.scalars().all())

    async def get_checklist_item(self, item_id: UUID) -> IssueChecklistItem | None:
        result = await self.db.execute(
            select(IssueChecklistItem)
            .where(IssueChecklistItem.id == item_id)
            .options(selectinload(IssueChecklistItem.creator))
        )
        return result.scalar_one_or_none()

    async def create_checklist_item(
        self,
        issue_id: UUID,
        content: str,
        created_by: UUID,
        sort_order: int = 0,
    ) -> IssueChecklistItem:
        item = IssueChecklistItem(
            issue_id=issue_id,
            content=content,
            created_by=created_by,
            sort_order=sort_order,
        )
        self.db.add(item)
        await self.db.flush()
        return await self.get_checklist_item(item.id)

    async def update_checklist_item(
        self, item_id: UUID, **fields
    ) -> IssueChecklistItem | None:
        item = await self.get_checklist_item(item_id)
        if not item:
            return None
        for key, value in fields.items():
            if value is not None and hasattr(item, key):
                setattr(item, key, value)
        await self.db.flush()
        return await self.get_checklist_item(item_id)

    async def delete_checklist_item(self, item_id: UUID) -> bool:
        item = await self.get_checklist_item(item_id)
        if not item:
            return False
        await self.db.delete(item)
        await self.db.flush()
        return True

    async def reorder_checklist(self, issue_id: UUID, item_ids: list[UUID]) -> None:
        for idx, item_id in enumerate(item_ids):
            result = await self.db.execute(
                select(IssueChecklistItem).where(
                    IssueChecklistItem.id == item_id,
                    IssueChecklistItem.issue_id == issue_id,
                )
            )
            item = result.scalar_one_or_none()
            if item:
                item.sort_order = idx
        await self.db.flush()

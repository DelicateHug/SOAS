"""Case note CRUD service."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from soas_backend.models.case_note import CaseNote
from soas_backend.models.timeline import TimelineEntry


class CaseNoteService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def _get_linked_timeline_entry(self, note_id: UUID) -> TimelineEntry | None:
        result = await self.db.execute(
            select(TimelineEntry).where(
                TimelineEntry.details["note_id"].as_string() == str(note_id)
            )
        )
        return result.scalar_one_or_none()

    async def list_notes(self, case_id: UUID) -> list[CaseNote]:
        result = await self.db.execute(
            select(CaseNote)
            .where(CaseNote.case_id == case_id)
            .options(
                selectinload(CaseNote.creator),
                selectinload(CaseNote.updater),
            )
            .order_by(CaseNote.created_at.desc())
        )
        return list(result.scalars().all())

    async def get(self, note_id: UUID) -> CaseNote | None:
        result = await self.db.execute(
            select(CaseNote)
            .where(CaseNote.id == note_id)
            .options(
                selectinload(CaseNote.creator),
                selectinload(CaseNote.updater),
            )
        )
        return result.scalar_one_or_none()

    async def create(
        self,
        case_id: UUID,
        content: str,
        created_by: UUID,
    ) -> CaseNote:
        note = CaseNote(
            case_id=case_id,
            content=content,
            created_by=created_by,
        )
        self.db.add(note)
        await self.db.flush()

        self.db.add(TimelineEntry(
            case_id=case_id,
            entry_type="note",
            content=content,
            details={"note_id": str(note.id)},
            created_by=created_by,
        ))
        await self.db.flush()

        return await self.get(note.id)

    async def update(
        self,
        note_id: UUID,
        updated_by: UUID,
        content: str | None = None,
    ) -> CaseNote | None:
        note = await self.get(note_id)
        if not note:
            return None
        if content is not None:
            note.content = content
        note.updated_by = updated_by
        await self.db.flush()

        if content is not None:
            timeline_entry = await self._get_linked_timeline_entry(note_id)
            if timeline_entry:
                timeline_entry.content = content
                await self.db.flush()

        return await self.get(note_id)

    async def delete(self, note_id: UUID) -> bool:
        note = await self.get(note_id)
        if not note:
            return False
        timeline_entry = await self._get_linked_timeline_entry(note_id)
        if timeline_entry:
            await self.db.delete(timeline_entry)
        await self.db.delete(note)
        await self.db.flush()
        return True

    async def toggle_evidence(self, note_id: UUID) -> CaseNote | None:
        note = await self.get(note_id)
        if not note:
            return None
        note.is_evidence = not note.is_evidence
        await self.db.flush()

        timeline_entry = await self._get_linked_timeline_entry(note_id)
        if timeline_entry:
            timeline_entry.is_evidence = note.is_evidence
            await self.db.flush()

        return await self.get(note_id)

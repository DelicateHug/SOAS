"""Work-session state machine + timeline integration.

Invariants:
  - One active session per user at any time.
  - Starting work auto-pauses any prior active session.
  - Pausing freezes accumulated_seconds; resume re-arms active_since.
  - Closing computes final accumulated_seconds and clears active_since.

Every state transition emits an entry into the target's timeline so
the case/incident detail page tells the story.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import and_, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from soas_backend.models.timeline import TimelineEntry
from soas_backend.models.work_session import WorkSession

logger = logging.getLogger(__name__)


class WorkSessionService:
    def __init__(self, db: AsyncSession):
        self.db = db

    # ------------------------------------------------------------------
    # Reads
    # ------------------------------------------------------------------

    async def current_for(self, user_id: UUID) -> WorkSession | None:
        rs = await self.db.execute(
            select(WorkSession)
            .where(WorkSession.user_id == user_id, WorkSession.status == "active")
            .order_by(WorkSession.started_at.desc())
            .limit(1)
        )
        return rs.scalar_one_or_none()

    async def get(self, session_id: UUID) -> WorkSession | None:
        rs = await self.db.execute(select(WorkSession).where(WorkSession.id == session_id))
        return rs.scalar_one_or_none()

    async def list_for_target(
        self,
        *,
        incident_id: UUID | None = None,
        case_id: UUID | None = None,
        limit: int = 50,
    ) -> list[WorkSession]:
        q = select(WorkSession).order_by(WorkSession.started_at.desc()).limit(limit)
        if incident_id is not None:
            q = q.where(WorkSession.incident_id == incident_id)
        elif case_id is not None:
            q = q.where(WorkSession.case_id == case_id)
        else:
            return []
        rs = await self.db.execute(q)
        return list(rs.scalars().all())

    # ------------------------------------------------------------------
    # Transitions
    # ------------------------------------------------------------------

    async def start(
        self,
        *,
        user_id: UUID,
        incident_id: UUID | None,
        case_id: UUID | None,
        note: str | None = None,
    ) -> WorkSession:
        if (incident_id is None) == (case_id is None):
            raise ValueError("Provide exactly one of incident_id or case_id")

        # If the user is already in an active session on the SAME target, just
        # return it (start is idempotent).
        cur = await self.current_for(user_id)
        if cur is not None:
            if (incident_id is not None and cur.incident_id == incident_id) or \
               (case_id is not None and cur.case_id == case_id):
                return cur
            # Different target — auto-pause the existing session.
            await self._pause_inner(cur, reason="auto-paused: started new session")

        now = datetime.now(timezone.utc)
        ws = WorkSession(
            user_id=user_id,
            incident_id=incident_id,
            case_id=case_id,
            status="active",
            started_at=now,
            active_since=now,
            note=note,
        )
        self.db.add(ws)
        await self.db.flush()
        await self._emit_timeline(ws, "work_started", "Work started")
        return ws

    async def pause(self, *, session_id: UUID, user_id: UUID) -> WorkSession:
        ws = await self._owned(session_id, user_id)
        if ws.status != "active":
            return ws
        await self._pause_inner(ws, reason=None)
        await self._emit_timeline(ws, "work_paused", "Work paused")
        return ws

    async def resume(self, *, session_id: UUID, user_id: UUID) -> WorkSession:
        ws = await self._owned(session_id, user_id)
        if ws.status != "paused":
            return ws
        # Pause any other active session first.
        other = await self.current_for(user_id)
        if other is not None and other.id != ws.id:
            await self._pause_inner(other, reason="auto-paused: resumed another session")
        ws.status = "active"
        ws.active_since = datetime.now(timezone.utc)
        ws.paused_at = None
        await self.db.flush()
        await self._emit_timeline(ws, "work_resumed", "Work resumed")
        return ws

    async def stop(self, *, session_id: UUID, user_id: UUID) -> WorkSession:
        ws = await self._owned(session_id, user_id)
        if ws.status == "closed":
            return ws
        now = datetime.now(timezone.utc)
        if ws.status == "active" and ws.active_since is not None:
            ws.accumulated_seconds += int((now - ws.active_since).total_seconds())
        ws.status = "closed"
        ws.active_since = None
        ws.paused_at = None
        ws.ended_at = now
        await self.db.flush()
        await self._emit_timeline(
            ws,
            "work_stopped",
            f"Work stopped ({ws.accumulated_seconds // 60}m total)",
        )
        return ws

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    async def _owned(self, session_id: UUID, user_id: UUID) -> WorkSession:
        ws = await self.get(session_id)
        if ws is None:
            raise LookupError("Work session not found")
        if ws.user_id != user_id:
            raise PermissionError("Not the session owner")
        return ws

    async def _pause_inner(self, ws: WorkSession, reason: str | None) -> None:
        now = datetime.now(timezone.utc)
        if ws.active_since is not None:
            ws.accumulated_seconds += int((now - ws.active_since).total_seconds())
        ws.active_since = None
        ws.paused_at = now
        ws.status = "paused"
        await self.db.flush()
        if reason:
            await self._emit_timeline(ws, "work_paused", reason)

    async def _emit_timeline(self, ws: WorkSession, entry_type: str, content: str) -> None:
        """Emit a timeline row when the target is an incident.

        TimelineEntry only has FK to incidents today; case-level timelines
        come via case_incidents. Skip when target is a bare case so we don't
        crash; case detail can read work_sessions directly.
        """
        try:
            if ws.incident_id is None:
                return
            self.db.add(
                TimelineEntry(
                    incident_id=ws.incident_id,
                    entry_type=entry_type,
                    content=content,
                    details={
                        "work_session_id": str(ws.id),
                        "accumulated_seconds": ws.accumulated_seconds,
                    },
                    created_by=ws.user_id,
                )
            )
            await self.db.flush()
        except Exception:
            logger.exception("work_session: timeline emit failed")

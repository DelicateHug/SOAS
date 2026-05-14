"""Work-session REST API.

Endpoints:
  GET    /work-sessions/current        — the current user's active session, or null
  POST   /work-sessions/start          — start work on an incident or case
  POST   /work-sessions/{id}/pause     — pause
  POST   /work-sessions/{id}/resume    — resume (auto-pauses any other active)
  POST   /work-sessions/{id}/stop      — close
  GET    /work-sessions/by-incident/{id}
  GET    /work-sessions/by-case/{id}
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from soas_backend.api.deps import get_current_user
from soas_backend.database import get_db
from soas_backend.models.user import User
from soas_backend.models.work_session import WorkSession
from soas_backend.services.work_session_service import WorkSessionService

router = APIRouter(prefix="/work-sessions", tags=["work-sessions"])


class SessionRead(BaseModel):
    id: UUID
    user_id: UUID
    incident_id: UUID | None
    case_id: UUID | None
    status: str
    started_at: str | None
    active_since: str | None
    paused_at: str | None
    ended_at: str | None
    accumulated_seconds: int
    note: str | None
    # Computed: total seconds including the currently-running segment if active.
    live_seconds: int

    model_config = {"from_attributes": True}


def _serialise(ws: WorkSession) -> SessionRead:
    from datetime import datetime, timezone

    live = ws.accumulated_seconds
    if ws.status == "active" and ws.active_since is not None:
        live += int((datetime.now(timezone.utc) - ws.active_since).total_seconds())
    return SessionRead(
        id=ws.id,
        user_id=ws.user_id,
        incident_id=ws.incident_id,
        case_id=ws.case_id,
        status=ws.status,
        started_at=ws.started_at.isoformat() if ws.started_at else None,
        active_since=ws.active_since.isoformat() if ws.active_since else None,
        paused_at=ws.paused_at.isoformat() if ws.paused_at else None,
        ended_at=ws.ended_at.isoformat() if ws.ended_at else None,
        accumulated_seconds=ws.accumulated_seconds,
        note=ws.note,
        live_seconds=live,
    )


class StartBody(BaseModel):
    incident_id: UUID | None = None
    case_id: UUID | None = None
    note: str | None = Field(default=None, max_length=500)


@router.get("/current", response_model=SessionRead | None)
async def current_session(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    ws = await WorkSessionService(db).current_for(current_user.id)
    return _serialise(ws) if ws else None


@router.post("/start", response_model=SessionRead, status_code=201)
async def start_session(
    body: StartBody,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = WorkSessionService(db)
    try:
        ws = await svc.start(
            user_id=current_user.id,
            incident_id=body.incident_id,
            case_id=body.case_id,
            note=body.note,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return _serialise(ws)


@router.post("/{session_id}/pause", response_model=SessionRead)
async def pause_session(
    session_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = WorkSessionService(db)
    try:
        ws = await svc.pause(session_id=session_id, user_id=current_user.id)
    except LookupError:
        raise HTTPException(status_code=404, detail="Session not found")
    except PermissionError:
        raise HTTPException(status_code=403, detail="Not the session owner")
    return _serialise(ws)


@router.post("/{session_id}/resume", response_model=SessionRead)
async def resume_session(
    session_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = WorkSessionService(db)
    try:
        ws = await svc.resume(session_id=session_id, user_id=current_user.id)
    except LookupError:
        raise HTTPException(status_code=404, detail="Session not found")
    except PermissionError:
        raise HTTPException(status_code=403, detail="Not the session owner")
    return _serialise(ws)


@router.post("/{session_id}/stop", response_model=SessionRead)
async def stop_session(
    session_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = WorkSessionService(db)
    try:
        ws = await svc.stop(session_id=session_id, user_id=current_user.id)
    except LookupError:
        raise HTTPException(status_code=404, detail="Session not found")
    except PermissionError:
        raise HTTPException(status_code=403, detail="Not the session owner")
    return _serialise(ws)


@router.get("/by-incident/{incident_id}", response_model=list[SessionRead])
async def by_incident(
    incident_id: UUID,
    limit: int = Query(50, ge=1, le=500),
    _: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    rs = await WorkSessionService(db).list_for_target(incident_id=incident_id, limit=limit)
    return [_serialise(s) for s in rs]


@router.get("/by-case/{case_id}", response_model=list[SessionRead])
async def by_case(
    case_id: UUID,
    limit: int = Query(50, ge=1, le=500),
    _: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    rs = await WorkSessionService(db).list_for_target(case_id=case_id, limit=limit)
    return [_serialise(s) for s in rs]

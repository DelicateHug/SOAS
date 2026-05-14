"""Registered-agent registry + live status + history (Phase 11)."""

from __future__ import annotations

import re
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from soas_backend.api.deps import require_role
from soas_backend.database import get_db
from soas_backend.services.agent_registry_service import AgentRegistryService

router = APIRouter(prefix="/agents", tags=["agents"])

AGENTTYPE_ID_RE = re.compile(r"^[a-z][a-z0-9_]*_[0-9]{1,6}$")


class AgentRead(BaseModel):
    id: str | None
    agenttype_id: str
    role: str
    label: str | None
    description: str | None
    fresh_seconds: int
    is_enabled: bool
    status: str
    latest: dict[str, Any] | None


class AgentCreate(BaseModel):
    agenttype_id: str = Field(min_length=3, max_length=64)
    role: str = Field(min_length=1, max_length=32)
    label: str | None = None
    description: str | None = None
    fresh_seconds: int = Field(default=60, ge=15, le=3600)


@router.get("", response_model=list[AgentRead])
async def list_agents(
    _: dict = Depends(require_role("admin", "soc_manager", "analyst")),
    db: AsyncSession = Depends(get_db),
):
    """All registered agents with live status (alive / stale / missing)."""
    return await AgentRegistryService(db).list_agents()


@router.post("", response_model=AgentRead, status_code=201)
async def create_agent(
    body: AgentCreate,
    _: dict = Depends(require_role("admin", "soc_manager")),
    db: AsyncSession = Depends(get_db),
):
    if not AGENTTYPE_ID_RE.fullmatch(body.agenttype_id):
        raise HTTPException(
            status_code=400,
            detail="agenttype_id must be lowercase `<role>_<digits>` (e.g. worker_002)",
        )
    svc = AgentRegistryService(db)
    agent = await svc.create(
        agenttype_id=body.agenttype_id,
        role=body.role,
        label=body.label,
        description=body.description,
        fresh_seconds=body.fresh_seconds,
    )
    # Return shape matches list_agents
    agents = await svc.list_agents()
    found = next((a for a in agents if a["agenttype_id"] == agent.agenttype_id), None)
    if not found:
        raise HTTPException(status_code=500, detail="Created agent could not be re-read")
    return found


@router.delete("/{agent_id}", status_code=204)
async def delete_agent(
    agent_id: UUID,
    _: dict = Depends(require_role("admin", "soc_manager")),
    db: AsyncSession = Depends(get_db),
):
    if not await AgentRegistryService(db).delete(agent_id):
        raise HTTPException(status_code=404, detail="Agent not found")


@router.get("/{agenttype_id}/history")
async def agent_history(
    agenttype_id: str,
    hours: int = Query(24, ge=1, le=168),
    _: dict = Depends(require_role("admin", "soc_manager", "analyst")),
    db: AsyncSession = Depends(get_db),
):
    """Historical samples for one agenttype_id."""
    return await AgentRegistryService(db).history(agenttype_id, hours=hours)


# ------------------------------------------------------------------
# Heartbeat ingest — any service (Python / Node / browser) can post
# ------------------------------------------------------------------


class HeartbeatBody(BaseModel):
    agenttype_id: str = Field(min_length=3, max_length=64)
    role: str = Field(min_length=1, max_length=32)
    version: str | None = None
    cpu_pct: float | None = None
    mem_pct: float | None = None
    mem_rss_bytes: int | None = None
    uptime_seconds: int | None = None
    instance_id: str | None = None


@router.post("/heartbeat", status_code=204)
async def post_heartbeat(
    body: HeartbeatBody,
    db: AsyncSession = Depends(get_db),
):
    """Any service can post a heartbeat. Auto-registers the agent on first sight.

    No auth required so browser tabs and the Node MCP can post without
    threading a token through their startup. The model is append-only +
    keyed by agenttype_id; the worst case if abused is noisy samples.
    """
    if not AGENTTYPE_ID_RE.fullmatch(body.agenttype_id):
        raise HTTPException(status_code=400, detail="Invalid agenttype_id format")
    from sqlalchemy import text

    await db.execute(
        text(
            "INSERT INTO registered_agents (agenttype_id, role, label) "
            "VALUES (:aid, :role, :label) ON CONFLICT (agenttype_id) DO NOTHING"
        ),
        {
            "aid": body.agenttype_id,
            "role": body.role,
            "label": f"{body.role.title()} {body.agenttype_id.rsplit('_', 1)[-1]}",
        },
    )
    await db.execute(
        text(
            """
            INSERT INTO instance_metric_samples
              (instance_id, agenttype_id, role, cpu_pct, mem_pct, mem_rss_bytes,
               uptime_seconds, version)
            VALUES (:iid, :aid, :role, :cpu, :mem, :rss, :up, :ver)
            """
        ),
        {
            "iid": body.instance_id or body.agenttype_id,
            "aid": body.agenttype_id,
            "role": body.role,
            "cpu": body.cpu_pct,
            "mem": body.mem_pct,
            "rss": body.mem_rss_bytes,
            "up": body.uptime_seconds,
            "ver": body.version,
        },
    )


# ------------------------------------------------------------------
# Logs — ingest + read
# ------------------------------------------------------------------


class LogEntry(BaseModel):
    level: str = Field(default="info", max_length=16)
    message: str = Field(min_length=1, max_length=16000)
    context: dict[str, Any] = Field(default_factory=dict)
    version: str | None = None
    occurred_at: str | None = None  # ISO-8601, optional


class LogBatch(BaseModel):
    entries: list[LogEntry] = Field(min_length=1, max_length=500)


@router.post("/{agenttype_id}/logs", status_code=204)
async def ingest_logs(
    agenttype_id: str,
    body: LogBatch,
    db: AsyncSession = Depends(get_db),
):
    """Bulk log ingest. Unauth like heartbeat for the same reason."""
    if not AGENTTYPE_ID_RE.fullmatch(agenttype_id):
        raise HTTPException(status_code=400, detail="Invalid agenttype_id")
    from datetime import datetime
    from soas_backend.models.agent_log import AgentLog

    for e in body.entries:
        occurred = None
        if e.occurred_at:
            try:
                occurred = datetime.fromisoformat(e.occurred_at.replace("Z", "+00:00"))
            except ValueError:
                occurred = None
        db.add(
            AgentLog(
                agenttype_id=agenttype_id,
                level=e.level[:16],
                message=e.message,
                context=e.context or {},
                version=e.version,
                occurred_at=occurred,
            )
        )
    await db.flush()


@router.get("/{agenttype_id}/logs")
async def list_logs(
    agenttype_id: str,
    limit: int = Query(200, ge=1, le=2000),
    level: str | None = Query(None),
    search: str | None = Query(None, max_length=200),
    _: dict = Depends(require_role("admin", "soc_manager", "analyst")),
    db: AsyncSession = Depends(get_db),
):
    """Recent log rows for one agent. Newest first."""
    from sqlalchemy import select
    from soas_backend.models.agent_log import AgentLog

    q = select(AgentLog).where(AgentLog.agenttype_id == agenttype_id)
    if level:
        q = q.where(AgentLog.level == level)
    if search:
        q = q.where(AgentLog.message.ilike(f"%{search}%"))
    q = q.order_by(AgentLog.created_at.desc()).limit(limit)
    rs = await db.execute(q)
    return [
        {
            "id": str(r.id),
            "level": r.level,
            "message": r.message,
            "context": r.context,
            "version": r.version,
            "occurred_at": r.occurred_at.isoformat() if r.occurred_at else None,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rs.scalars().all()
    ]

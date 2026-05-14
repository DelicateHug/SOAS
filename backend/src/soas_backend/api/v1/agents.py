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

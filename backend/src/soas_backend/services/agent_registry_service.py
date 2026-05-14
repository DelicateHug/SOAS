"""Agent registry helpers (Phase 11).

A small mix of:
  - resolve_agenttype_id: same logic as the worker heartbeat — pull from
    env, or derive from hostname.
  - record_agent_sample: async wrapper that the backend's lifespan
    heartbeat uses; mirrors the SQL the worker emits.
  - AgentRegistryService: read/write over RegisteredAgent rows + the
    "currently alive" join against instance_metric_samples.
"""

from __future__ import annotations

import logging
import os
import re
import socket
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

import psutil
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from soas_backend.database import async_session
from soas_backend.models.observability import InstanceMetricSample
from soas_backend.models.registered_agent import RegisteredAgent

logger = logging.getLogger(__name__)


def resolve_agenttype_id(role: str) -> str:
    """Stable agenttype_id from $SOAS_AGENT_ID or hostname."""
    candidate = os.environ.get("SOAS_AGENT_ID", "").strip()
    if candidate and re.fullmatch(r"[a-z][a-z0-9_]*_[0-9]{1,6}", candidate):
        return candidate
    host = socket.gethostname().split(".", 1)[0]
    short = re.sub(r"^soas[-_]", "", host)
    m = re.match(r"^(\w+?)[-_]?(\d+)?$", short)
    if m and m.group(1):
        base = m.group(1).lower()
        num = m.group(2) or "001"
        return f"{base}_{num.zfill(3)}"
    return f"{role}_001"


def _sample_resource_metrics() -> dict[str, float | int | None]:
    try:
        proc = psutil.Process(os.getpid())
        return {
            "cpu_pct": float(psutil.cpu_percent(interval=None)),
            "mem_pct": float(psutil.virtual_memory().percent),
            "mem_rss_bytes": int(proc.memory_info().rss),
        }
    except Exception:
        return {"cpu_pct": None, "mem_pct": None, "mem_rss_bytes": None}


async def record_agent_sample(
    *,
    agenttype_id: str,
    role: str,
    version: str,
    instance_id: str,
    uptime_seconds: int,
) -> None:
    """Auto-register the agent and write one metric sample. Best-effort."""
    metrics = _sample_resource_metrics()
    async with async_session() as db:
        await db.execute(
            text(
                "INSERT INTO registered_agents (agenttype_id, role, label) "
                "VALUES (:aid, :role, :label) ON CONFLICT (agenttype_id) DO NOTHING"
            ),
            {
                "aid": agenttype_id,
                "role": role,
                "label": f"{role.title()} {agenttype_id.rsplit('_', 1)[-1]}",
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
                "iid": instance_id,
                "aid": agenttype_id,
                "role": role,
                "cpu": metrics["cpu_pct"],
                "mem": metrics["mem_pct"],
                "rss": metrics["mem_rss_bytes"],
                "up": uptime_seconds,
                "ver": version,
            },
        )
        await db.commit()


# ---------------------------------------------------------------------------
# Registry CRUD
# ---------------------------------------------------------------------------


class AgentRegistryService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_agents(self) -> list[dict[str, Any]]:
        """All registered agent slots + latest sample / liveness."""
        rs = await self.db.execute(
            select(RegisteredAgent).order_by(RegisteredAgent.role, RegisteredAgent.agenttype_id)
        )
        agents = list(rs.scalars().all())

        # Pull the latest sample per agenttype_id in one query.
        sample_sql = text(
            """
            SELECT DISTINCT ON (agenttype_id)
              agenttype_id, captured_at, cpu_pct, mem_pct, mem_rss_bytes,
              uptime_seconds, version, instance_id
            FROM instance_metric_samples
            WHERE agenttype_id IS NOT NULL
            ORDER BY agenttype_id, captured_at DESC
            """
        )
        sample_rows = await self.db.execute(sample_sql)
        latest: dict[str, Any] = {}
        for r in sample_rows.all():
            latest[r.agenttype_id] = {
                "captured_at": r.captured_at.isoformat() if r.captured_at else None,
                "cpu_pct": float(r.cpu_pct) if r.cpu_pct is not None else None,
                "mem_pct": float(r.mem_pct) if r.mem_pct is not None else None,
                "mem_rss_bytes": int(r.mem_rss_bytes) if r.mem_rss_bytes is not None else None,
                "uptime_seconds": int(r.uptime_seconds) if r.uptime_seconds is not None else None,
                "version": r.version,
                "instance_id": r.instance_id,
            }

        # Also surface agenttype_ids that reported but have no registry row
        # (auto-registration may be lagging; fall back to ad-hoc entries).
        known_ids = {a.agenttype_id for a in agents}
        for unknown_id in [k for k in latest if k not in known_ids]:
            agents.append(
                RegisteredAgent(
                    agenttype_id=unknown_id,
                    role=(latest[unknown_id].get("instance_id") or "unknown").split("_", 1)[0],
                    label=None,
                    fresh_seconds=60,
                    is_enabled=True,
                )
            )

        now = datetime.now(timezone.utc)
        out: list[dict[str, Any]] = []
        for a in agents:
            sample = latest.get(a.agenttype_id)
            status = "missing"
            if sample and sample["captured_at"]:
                last_seen = datetime.fromisoformat(sample["captured_at"])
                age = (now - last_seen).total_seconds()
                if age <= a.fresh_seconds:
                    status = "alive"
                elif age <= a.fresh_seconds * 3:
                    status = "stale"
            out.append({
                "id": str(a.id) if a.id else None,
                "agenttype_id": a.agenttype_id,
                "role": a.role,
                "label": a.label,
                "description": a.description,
                "fresh_seconds": a.fresh_seconds,
                "is_enabled": a.is_enabled,
                "status": status,
                "latest": sample,
            })
        return out

    async def create(
        self,
        *,
        agenttype_id: str,
        role: str,
        label: str | None = None,
        description: str | None = None,
        fresh_seconds: int = 60,
    ) -> RegisteredAgent:
        agent = RegisteredAgent(
            agenttype_id=agenttype_id,
            role=role,
            label=label,
            description=description,
            fresh_seconds=fresh_seconds,
        )
        self.db.add(agent)
        await self.db.flush()
        return agent

    async def delete(self, agent_id: UUID) -> bool:
        rs = await self.db.execute(select(RegisteredAgent).where(RegisteredAgent.id == agent_id))
        a = rs.scalar_one_or_none()
        if not a:
            return False
        await self.db.delete(a)
        return True

    async def history(self, agenttype_id: str, hours: int = 24) -> list[dict[str, Any]]:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        rs = await self.db.execute(
            select(InstanceMetricSample)
            .where(
                InstanceMetricSample.agenttype_id == agenttype_id,
                InstanceMetricSample.captured_at >= cutoff,
            )
            .order_by(InstanceMetricSample.captured_at.asc())
            .limit(5000)
        )
        out: list[dict[str, Any]] = []
        for s in rs.scalars().all():
            out.append({
                "captured_at": s.captured_at.isoformat() if s.captured_at else None,
                "cpu_pct": float(s.cpu_pct) if s.cpu_pct is not None else None,
                "mem_pct": float(s.mem_pct) if s.mem_pct is not None else None,
                "mem_rss_bytes": int(s.mem_rss_bytes) if s.mem_rss_bytes is not None else None,
                "uptime_seconds": int(s.uptime_seconds) if s.uptime_seconds is not None else None,
                "version": s.version,
                "instance_id": s.instance_id,
            })
        return out

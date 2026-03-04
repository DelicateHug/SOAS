"""Monitoring service for system health checks and metrics."""

import json
import logging
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from uuid import UUID

import redis.asyncio as aioredis
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from soas_backend.models.monitoring import HealthMetricSnapshot, MonitoringAgent

logger = logging.getLogger(__name__)


class MonitoringService:
    """Aggregates health data from Redis and provides historical metrics from PostgreSQL."""

    def __init__(self, db: AsyncSession, redis: aioredis.Redis):
        self.db = db
        self._redis = redis

    # ------------------------------------------------------------------
    # Real-time health checks (reads from Redis, populated by Celery task)
    # ------------------------------------------------------------------

    async def _get_health_from_redis(self, component_type: str, component_id: str) -> dict | None:
        key = f"monitoring:health:{component_type}:{component_id}"
        raw = await self._redis.get(key)
        if raw is None:
            return None
        data = raw.decode("utf-8") if isinstance(raw, bytes) else raw
        return json.loads(data)

    async def _get_all_health_keys(self) -> list[dict]:
        """Scan Redis for all monitoring:health:* keys and return parsed data."""
        results = []
        cursor = 0
        while True:
            cursor, keys = await self._redis.scan(
                cursor=cursor, match="monitoring:health:*", count=100
            )
            for key in keys:
                raw = await self._redis.get(key)
                if raw:
                    data = raw.decode("utf-8") if isinstance(raw, bytes) else raw
                    try:
                        results.append(json.loads(data))
                    except json.JSONDecodeError:
                        pass
            if cursor == 0:
                break
        return results

    async def get_system_health(self) -> dict:
        """Get overall system health with all component statuses."""
        all_health = await self._get_all_health_keys()

        # Determine overall status
        statuses = [h.get("status", "unknown") for h in all_health]
        if not statuses:
            overall = "unknown"
        elif "unhealthy" in statuses:
            overall = "unhealthy"
        elif "degraded" in statuses:
            overall = "degraded"
        else:
            overall = "healthy"

        # Calculate uptime from Redis key
        uptime_raw = await self._redis.get("monitoring:api:uptime_start")
        uptime_seconds = 0.0
        if uptime_raw:
            start_str = uptime_raw.decode("utf-8") if isinstance(uptime_raw, bytes) else uptime_raw
            try:
                start = datetime.fromisoformat(start_str)
                uptime_seconds = (datetime.now(timezone.utc) - start).total_seconds()
            except (ValueError, TypeError):
                pass

        components = []
        for h in all_health:
            components.append({
                "component_type": h.get("component_type", "unknown"),
                "component_id": h.get("component_id", "unknown"),
                "status": h.get("status", "unknown"),
                "metrics": h.get("metrics", {}),
                "last_check_at": h.get("recorded_at"),
            })

        return {
            "overall_status": overall,
            "components": components,
            "uptime_seconds": uptime_seconds,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    async def get_component_health(self, component_type: str) -> list[dict]:
        """Get health for a specific component type."""
        all_health = await self._get_all_health_keys()
        return [
            {
                "component_type": h.get("component_type", "unknown"),
                "component_id": h.get("component_id", "unknown"),
                "status": h.get("status", "unknown"),
                "metrics": h.get("metrics", {}),
                "last_check_at": h.get("recorded_at"),
            }
            for h in all_health
            if h.get("component_type") == component_type
        ]

    # ------------------------------------------------------------------
    # Aggregated health over a time window (PostgreSQL)
    # ------------------------------------------------------------------

    async def get_aggregated_health(self, minutes: int = 10) -> dict:
        """Get system health aggregated over the last N minutes from stored snapshots.

        Instead of using the single most recent check, this averages metrics
        across all snapshots in the window and derives status from the
        distribution of healthy/degraded/unhealthy checks.
        """
        now = datetime.now(timezone.utc)
        start = now - timedelta(minutes=minutes)

        result = await self.db.execute(
            select(HealthMetricSnapshot)
            .where(HealthMetricSnapshot.recorded_at >= start)
            .order_by(HealthMetricSnapshot.recorded_at.asc())
        )
        rows = result.scalars().all()

        # If no snapshots available, fall back to real-time Redis data
        if not rows:
            return await self.get_system_health()

        # Group snapshots by (component_type, component_id)
        groups: dict[tuple[str, str], list[HealthMetricSnapshot]] = defaultdict(list)
        for row in rows:
            groups[(row.component_type, row.component_id)].append(row)

        components = []
        for (comp_type, comp_id), snapshots in groups.items():
            # Aggregate status by majority vote
            status_counts: dict[str, int] = defaultdict(int)
            for s in snapshots:
                status_counts[s.status] += 1
            total = len(snapshots)
            unhealthy_pct = status_counts.get("unhealthy", 0) / total
            degraded_pct = status_counts.get("degraded", 0) / total

            if unhealthy_pct >= 0.5:
                agg_status = "unhealthy"
            elif (unhealthy_pct + degraded_pct) >= 0.2:
                agg_status = "degraded"
            else:
                agg_status = "healthy"

            # Average numeric metrics
            all_metric_keys: set[str] = set()
            for s in snapshots:
                if s.metrics:
                    all_metric_keys.update(s.metrics.keys())

            avg_metrics: dict[str, float | str] = {}
            for key in all_metric_keys:
                values = []
                last_non_numeric = None
                for s in snapshots:
                    val = (s.metrics or {}).get(key)
                    if val is None:
                        continue
                    try:
                        values.append(float(val))
                    except (ValueError, TypeError):
                        last_non_numeric = val
                if values:
                    avg_metrics[key] = round(sum(values) / len(values), 2)
                elif last_non_numeric is not None:
                    avg_metrics[key] = last_non_numeric

            components.append({
                "component_type": comp_type,
                "component_id": comp_id,
                "status": agg_status,
                "metrics": avg_metrics,
                "last_check_at": snapshots[-1].recorded_at.isoformat(),
                "snapshot_count": total,
            })

        # Determine overall status
        statuses = [c["status"] for c in components]
        if "unhealthy" in statuses:
            overall = "unhealthy"
        elif "degraded" in statuses:
            overall = "degraded"
        else:
            overall = "healthy"

        # Uptime from Redis
        uptime_raw = await self._redis.get("monitoring:api:uptime_start")
        uptime_seconds = 0.0
        if uptime_raw:
            start_str = uptime_raw.decode("utf-8") if isinstance(uptime_raw, bytes) else uptime_raw
            try:
                uptime_start = datetime.fromisoformat(start_str)
                uptime_seconds = (now - uptime_start).total_seconds()
            except (ValueError, TypeError):
                pass

        return {
            "overall_status": overall,
            "components": components,
            "uptime_seconds": uptime_seconds,
            "timestamp": now.isoformat(),
            "window_minutes": minutes,
        }

    # ------------------------------------------------------------------
    # Historical metrics (PostgreSQL)
    # ------------------------------------------------------------------

    async def get_historical_metrics(
        self,
        component_type: str,
        component_id: str | None,
        start: datetime,
        end: datetime,
        limit: int = 200,
    ) -> list[dict]:
        """Query health_metric_snapshots table for time-series data."""
        query = (
            select(HealthMetricSnapshot)
            .where(HealthMetricSnapshot.component_type == component_type)
            .where(HealthMetricSnapshot.recorded_at >= start)
            .where(HealthMetricSnapshot.recorded_at <= end)
            .order_by(HealthMetricSnapshot.recorded_at.asc())
            .limit(limit)
        )
        if component_id:
            query = query.where(HealthMetricSnapshot.component_id == component_id)

        result = await self.db.execute(query)
        rows = result.scalars().all()
        return [
            {
                "id": str(row.id),
                "component_type": row.component_type,
                "component_id": row.component_id,
                "status": row.status,
                "metrics": row.metrics,
                "recorded_at": row.recorded_at.isoformat(),
            }
            for row in rows
        ]

    # ------------------------------------------------------------------
    # Monitoring Agents (meta-monitoring)
    # ------------------------------------------------------------------

    async def get_all_agents(self) -> list[dict]:
        """List all monitoring agents with alive status derived from Redis health data."""
        result = await self.db.execute(
            select(MonitoringAgent).order_by(MonitoringAgent.name)
        )
        agents = result.scalars().all()
        now = datetime.now(timezone.utc)

        # Build map of component_type -> latest health entry from Redis
        all_health = await self._get_all_health_keys()
        health_by_type: dict[str, dict] = {}
        for h in all_health:
            ct = h.get("component_type", "unknown")
            recorded = h.get("recorded_at", "")
            if ct not in health_by_type or recorded > health_by_type[ct].get("recorded_at", ""):
                health_by_type[ct] = h

        out = []
        for a in agents:
            health = health_by_type.get(a.component_type)
            if health:
                last_check_str = health.get("recorded_at")
                last_status = health.get("status", a.last_status)
                try:
                    last_check = datetime.fromisoformat(last_check_str) if last_check_str else None
                except (ValueError, TypeError):
                    last_check = None
                is_alive = (
                    last_check is not None
                    and (now - last_check).total_seconds() < a.check_interval_seconds * 3
                )
            else:
                last_check_str = a.last_check_at.isoformat() if a.last_check_at else None
                last_status = a.last_status
                is_alive = (
                    a.last_check_at is not None
                    and (now - a.last_check_at).total_seconds() < a.check_interval_seconds * 3
                )

            out.append({
                "id": str(a.id),
                "name": a.name,
                "description": a.description,
                "component_type": a.component_type,
                "check_interval_seconds": a.check_interval_seconds,
                "is_enabled": a.is_enabled,
                "last_check_at": last_check_str,
                "last_status": last_status,
                "consecutive_failures": a.consecutive_failures,
                "is_alive": is_alive,
                "created_at": a.created_at.isoformat(),
                "updated_at": a.updated_at.isoformat(),
            })
        return out

    async def update_agent(self, agent_id: UUID, is_enabled: bool) -> None:
        """Enable or disable a monitoring agent."""
        await self.db.execute(
            update(MonitoringAgent)
            .where(MonitoringAgent.id == agent_id)
            .values(is_enabled=is_enabled)
        )
        await self.db.flush()

    async def report_agent_check(
        self, agent_name: str, status: str
    ) -> None:
        """Record that a monitoring agent performed a check."""
        now = datetime.now(timezone.utc)
        result = await self.db.execute(
            select(MonitoringAgent).where(MonitoringAgent.name == agent_name)
        )
        agent = result.scalar_one_or_none()
        if agent:
            agent.last_check_at = now
            agent.last_status = status
            if status == "healthy":
                agent.consecutive_failures = 0
            else:
                agent.consecutive_failures += 1
            await self.db.flush()

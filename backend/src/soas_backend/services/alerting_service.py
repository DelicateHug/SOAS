"""Alerting service for managing alert rules and firing alerts."""

import json
import logging
from datetime import datetime, timezone
from uuid import UUID

import redis.asyncio as aioredis
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from soas_backend.models.monitoring import Alert, AlertRule

logger = logging.getLogger(__name__)

CONDITION_OPS = {
    "gt": lambda v, t: v > t,
    "lt": lambda v, t: v < t,
    "gte": lambda v, t: v >= t,
    "lte": lambda v, t: v <= t,
    "eq": lambda v, t: v == t,
    "ne": lambda v, t: v != t,
}


class AlertingService:
    """Manages alert rules, evaluates them, and handles alert lifecycle."""

    def __init__(self, db: AsyncSession, redis: aioredis.Redis):
        self.db = db
        self._redis = redis

    # ------------------------------------------------------------------
    # Alert Rule CRUD
    # ------------------------------------------------------------------

    async def get_rules(self, component_type: str | None = None) -> list[AlertRule]:
        query = select(AlertRule).order_by(AlertRule.created_at.desc())
        if component_type:
            query = query.where(AlertRule.component_type == component_type)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def create_rule(self, data: dict, created_by: UUID) -> AlertRule:
        rule = AlertRule(
            name=data["name"],
            description=data.get("description"),
            component_type=data["component_type"],
            metric_key=data["metric_key"],
            condition=data["condition"],
            threshold=data["threshold"],
            severity=data.get("severity", "warning"),
            is_enabled=data.get("is_enabled", True),
            cooldown_seconds=data.get("cooldown_seconds", 300),
            created_by=created_by,
        )
        self.db.add(rule)
        await self.db.flush()
        await self.db.refresh(rule)
        return rule

    async def update_rule(self, rule_id: UUID, data: dict) -> AlertRule | None:
        result = await self.db.execute(
            select(AlertRule).where(AlertRule.id == rule_id)
        )
        rule = result.scalar_one_or_none()
        if not rule:
            return None

        for field in ["name", "description", "metric_key", "condition", "threshold",
                       "severity", "is_enabled", "cooldown_seconds"]:
            if field in data and data[field] is not None:
                setattr(rule, field, data[field])

        await self.db.flush()
        await self.db.refresh(rule)
        return rule

    async def delete_rule(self, rule_id: UUID) -> bool:
        result = await self.db.execute(
            select(AlertRule).where(AlertRule.id == rule_id)
        )
        rule = result.scalar_one_or_none()
        if not rule:
            return False
        await self.db.delete(rule)
        await self.db.flush()
        return True

    # ------------------------------------------------------------------
    # Alert Management
    # ------------------------------------------------------------------

    async def get_alerts(
        self,
        status: str | None = None,
        severity: str | None = None,
        page: int = 1,
        per_page: int = 25,
    ) -> tuple[list[Alert], int]:
        query = select(Alert).order_by(Alert.created_at.desc())
        count_query = select(func.count()).select_from(Alert)

        if status:
            query = query.where(Alert.status == status)
            count_query = count_query.where(Alert.status == status)
        if severity:
            query = query.where(Alert.severity == severity)
            count_query = count_query.where(Alert.severity == severity)

        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0

        query = query.offset((page - 1) * per_page).limit(per_page)
        result = await self.db.execute(query)
        alerts = list(result.scalars().all())

        return alerts, total

    async def acknowledge_alert(self, alert_id: UUID, user_id: UUID) -> Alert | None:
        result = await self.db.execute(
            select(Alert).where(Alert.id == alert_id)
        )
        alert = result.scalar_one_or_none()
        if not alert:
            return None

        alert.status = "acknowledged"
        alert.acknowledged_by = user_id
        alert.acknowledged_at = datetime.now(timezone.utc)
        await self.db.flush()
        await self.db.refresh(alert)

        # Publish update
        await self._publish_alert_update(alert, "alert_acknowledged")
        return alert

    async def resolve_alert(self, alert_id: UUID) -> Alert | None:
        result = await self.db.execute(
            select(Alert).where(Alert.id == alert_id)
        )
        alert = result.scalar_one_or_none()
        if not alert:
            return None

        alert.status = "resolved"
        alert.resolved_at = datetime.now(timezone.utc)
        await self.db.flush()
        await self.db.refresh(alert)

        await self._publish_alert_update(alert, "alert_resolved")
        return alert

    async def get_active_alert_count(self) -> dict[str, int]:
        """Count active alerts grouped by severity."""
        result = await self.db.execute(
            select(Alert.severity, func.count())
            .where(Alert.status == "active")
            .group_by(Alert.severity)
        )
        counts = {row[0]: row[1] for row in result.all()}
        return counts

    # ------------------------------------------------------------------
    # Real-time notifications
    # ------------------------------------------------------------------

    async def _publish_alert_update(self, alert: Alert, event_type: str) -> None:
        try:
            await self._redis.publish(
                "monitoring:alerts:channel",
                json.dumps({
                    "type": event_type,
                    "alert_id": str(alert.id),
                    "severity": alert.severity,
                    "title": alert.title,
                    "status": alert.status,
                    "component_type": alert.component_type,
                    "component_id": alert.component_id,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }),
            )
        except Exception:
            logger.warning("Failed to publish alert update to Redis", exc_info=True)

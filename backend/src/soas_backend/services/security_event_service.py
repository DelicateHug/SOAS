"""Helper for recording SecurityEvent rows from anywhere in the app.

Usage:
    await SecurityEventService(db).record(
        event_type="auth.login_success",
        actor_id=user.id,
        actor_label=user.username,
        ip_address=request.client.host,
    )
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from soas_backend.models.security_event import SecurityEvent

logger = logging.getLogger(__name__)


class SecurityEventService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def record(
        self,
        *,
        event_type: str,
        severity: str = "info",
        actor_id: UUID | None = None,
        actor_label: str | None = None,
        target_kind: str | None = None,
        target_id: UUID | None = None,
        target_label: str | None = None,
        message: str | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
        extra: dict[str, Any] | None = None,
    ) -> SecurityEvent | None:
        """Append a security event. Best-effort; never raises."""
        try:
            row = SecurityEvent(
                event_type=event_type[:64],
                severity=severity[:16],
                actor_id=actor_id,
                actor_label=(actor_label[:200] if actor_label else None),
                target_kind=(target_kind[:64] if target_kind else None),
                target_id=target_id,
                target_label=(target_label[:500] if target_label else None),
                message=message,
                ip_address=(ip_address[:64] if ip_address else None),
                user_agent=(user_agent[:500] if user_agent else None),
                extra=extra or {},
            )
            self.db.add(row)
            await self.db.flush()
            return row
        except Exception:
            logger.exception("security_event.record failed type=%s", event_type)
            return None

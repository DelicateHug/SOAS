"""Webhook management and ingestion service."""

import json
import logging
import secrets
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from soas_backend.models.webhook import Webhook, WebhookLog

logger = logging.getLogger(__name__)

# Maximum size (in characters) for stored request bodies to prevent massive storage usage.
MAX_REQUEST_BODY_SIZE = 64 * 1024  # 64 KB


class WebhookService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(
        self,
        name: str,
        created_by: UUID,
        description: str | None = None,
        source_type: str = "custom",
        source_id: UUID | None = None,
        default_severity: str = "medium",
        default_tags: list[str] | None = None,
        rate_limit_per_minute: int = 60,
    ) -> Webhook:
        """Create a new webhook endpoint."""
        secret_token = secrets.token_urlsafe(32)
        webhook = Webhook(
            name=name,
            description=description,
            secret_token=secret_token,
            source_type=source_type,
            source_id=source_id,
            default_severity=default_severity,
            default_tags=default_tags or [],
            rate_limit_per_minute=rate_limit_per_minute,
            created_by=created_by,
        )
        self.db.add(webhook)
        await self.db.flush()
        return webhook

    async def get(self, webhook_id: UUID) -> Webhook | None:
        """Get a webhook by ID, eagerly loading the creator."""
        result = await self.db.execute(
            select(Webhook)
            .options(selectinload(Webhook.creator))
            .where(Webhook.id == webhook_id)
        )
        return result.scalar_one_or_none()

    async def get_by_token(self, secret_token: str) -> Webhook | None:
        """Look up a webhook by its secret token, eagerly loading the creator."""
        result = await self.db.execute(
            select(Webhook)
            .options(selectinload(Webhook.creator))
            .where(Webhook.secret_token == secret_token)
        )
        return result.scalar_one_or_none()

    async def list_webhooks(
        self,
        page: int = 1,
        per_page: int = 25,
    ) -> tuple[list[Webhook], int]:
        """List webhooks with pagination, ordered by created_at descending."""
        query = select(Webhook)

        # Count total matching rows
        count_query = select(func.count()).select_from(query.subquery())
        total = (await self.db.execute(count_query)).scalar() or 0

        # Paginate
        query = query.order_by(Webhook.created_at.desc())
        query = query.offset((page - 1) * per_page).limit(per_page)

        result = await self.db.execute(query)
        return list(result.scalars().all()), total

    async def update(self, webhook_id: UUID, **kwargs: Any) -> Webhook:
        """Update a webhook's mutable fields.

        Accepted keyword arguments: name, description, source_type,
        is_enabled, default_severity, default_tags, rate_limit_per_minute.
        """
        webhook = await self.get(webhook_id)
        if not webhook:
            raise ValueError("Webhook not found")

        allowed_fields = {
            "name",
            "description",
            "source_type",
            "source_id",
            "is_enabled",
            "default_severity",
            "default_tags",
            "rate_limit_per_minute",
        }

        # source_id is the only nullable updatable field — None clears the link.
        for field, value in kwargs.items():
            if field not in allowed_fields:
                continue
            if value is None and field != "source_id":
                continue
            setattr(webhook, field, value)

        await self.db.flush()
        return webhook

    async def delete(self, webhook_id: UUID) -> None:
        """Delete a webhook and its associated logs (via cascade)."""
        webhook = await self.get(webhook_id)
        if not webhook:
            raise ValueError("Webhook not found")

        await self.db.delete(webhook)
        await self.db.flush()

    async def regenerate_token(self, webhook_id: UUID) -> str:
        """Regenerate the secret token for a webhook. Returns the new token."""
        webhook = await self.get(webhook_id)
        if not webhook:
            raise ValueError("Webhook not found")

        new_token = secrets.token_urlsafe(32)
        webhook.secret_token = new_token
        await self.db.flush()
        return new_token

    async def increment_counter(self, webhook_id: UUID) -> None:
        """Bump the received counter and update last_received_at timestamp."""
        webhook = await self.get(webhook_id)
        if not webhook:
            raise ValueError("Webhook not found")

        webhook.total_received = (webhook.total_received or 0) + 1
        webhook.last_received_at = datetime.now(timezone.utc)
        await self.db.flush()

    async def log_request(
        self,
        webhook_id: UUID,
        status: str,
        request_body: dict[str, Any] | None = None,
        normalized_data: dict[str, Any] | None = None,
        incident_id: UUID | None = None,
        error_message: str | None = None,
        processing_time_ms: int | None = None,
        remote_ip: str | None = None,
    ) -> WebhookLog:
        """Record an incoming webhook request in the log table.

        The request_body is truncated to the first 64 KB of its JSON
        representation to avoid storing excessively large payloads.
        """
        # Truncate request_body to avoid massive storage
        truncated_body = request_body
        if request_body is not None:
            body_str = json.dumps(request_body)
            if len(body_str) > MAX_REQUEST_BODY_SIZE:
                body_str = body_str[:MAX_REQUEST_BODY_SIZE]
                # Re-parse as best-effort; fall back to a wrapper if the
                # truncated string is no longer valid JSON.
                try:
                    truncated_body = json.loads(body_str)
                except json.JSONDecodeError:
                    truncated_body = {"_truncated": body_str}

        log_entry = WebhookLog(
            webhook_id=webhook_id,
            status=status,
            request_body=truncated_body or {},
            normalized_data=normalized_data,
            incident_id=incident_id,
            error_message=error_message,
            processing_time_ms=processing_time_ms,
            remote_ip=remote_ip,
        )
        self.db.add(log_entry)
        await self.db.flush()
        return log_entry

    async def get_logs(
        self,
        webhook_id: UUID,
        page: int = 1,
        per_page: int = 25,
        status_filter: str | None = None,
    ) -> tuple[list[WebhookLog], int]:
        """Retrieve paginated webhook logs for a given webhook.

        Optionally filter by status. Ordered by created_at descending.
        """
        query = select(WebhookLog).where(WebhookLog.webhook_id == webhook_id)

        if status_filter:
            query = query.where(WebhookLog.status == status_filter)

        # Count total matching rows
        count_query = select(func.count()).select_from(query.subquery())
        total = (await self.db.execute(count_query)).scalar() or 0

        # Paginate
        query = query.order_by(WebhookLog.created_at.desc())
        query = query.offset((page - 1) * per_page).limit(per_page)

        result = await self.db.execute(query)
        return list(result.scalars().all()), total

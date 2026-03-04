"""Webhook ingestion (public) and admin CRUD endpoints."""

import logging
import time
from uuid import UUID

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from soas_backend.api.deps import get_current_user, get_redis, require_permission
from soas_backend.database import get_db
from soas_backend.models.user import User
from soas_backend.models.webhook import Webhook
from soas_backend.services.incident_cache import IncidentCacheService
from soas_backend.services.incident_service import IncidentService
from soas_backend.services.normalization_service import NormalizationService
from soas_backend.services.trigger_service import TriggerService
from soas_backend.services.webhook_service import WebhookService
from soas_shared.schemas.common import PaginatedResponse, PaginationMeta
from soas_shared.schemas.user import UserBrief
from soas_shared.schemas.webhook import (
    WebhookCreate,
    WebhookListItem,
    WebhookLogRead,
    WebhookRead,
    WebhookUpdate,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _webhook_to_read(webhook: Webhook) -> WebhookRead:
    return WebhookRead(
        id=webhook.id,
        name=webhook.name,
        description=webhook.description,
        secret_token=webhook.secret_token,
        source_type=webhook.source_type,
        source_id=webhook.source_id,
        source_name=webhook.source.name if webhook.source else None,
        is_enabled=webhook.is_enabled,
        default_severity=webhook.default_severity,
        default_tags=webhook.default_tags or [],
        rate_limit_per_minute=webhook.rate_limit_per_minute,
        ingest_url=f"/api/v1/webhooks/ingest/{webhook.secret_token}",
        last_received_at=webhook.last_received_at,
        total_received=webhook.total_received,
        created_by=UserBrief(
            id=webhook.creator.id,
            username=webhook.creator.username,
            display_name=webhook.creator.display_name,
        )
        if webhook.creator
        else UserBrief(
            id=webhook.created_by,
            username="system",
            display_name="System",
        ),
        created_at=webhook.created_at,
        updated_at=webhook.updated_at,
    )


def _incident_to_cache_dict(incident) -> dict:
    """Build a flat dict suitable for IncidentCacheService.cache_incident."""
    return {
        "id": str(incident.id),
        "title": incident.title,
        "summary": incident.summary,
        "severity": incident.severity,
        "status": incident.status,
        "source": incident.source,
        "source_ref": incident.source_ref,
        "tags": incident.tags or [],
        "metadata": incident.metadata_,
        "created_at": str(incident.created_at) if incident.created_at else None,
        "updated_at": str(incident.updated_at) if incident.updated_at else None,
    }


# ===========================================================================
# Public ingest router (NO JWT auth)
# ===========================================================================

ingest_router = APIRouter(prefix="/webhooks", tags=["webhook-ingest"])


@ingest_router.post("/ingest/{webhook_token}")
async def ingest_webhook(
    webhook_token: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
):
    """Receive an incoming webhook payload, normalise it, and create an incident."""
    remote_ip = request.client.host if request.client else None
    webhook_svc = WebhookService(db)

    # 1. Look up webhook by secret token
    webhook = await webhook_svc.get_by_token(webhook_token)
    if not webhook:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Webhook not found")

    # 2. Check if enabled
    if not webhook.is_enabled:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Webhook is disabled")

    # 3. Rate-limit check (sliding window via Redis sorted set)
    now = time.time()
    rate_key = f"webhook:{webhook.id}:ratelimit"

    pipe = redis.pipeline()
    pipe.zadd(rate_key, {str(now): now})
    pipe.zremrangebyscore(rate_key, 0, now - 60)
    pipe.zcard(rate_key)
    pipe.expire(rate_key, 120)
    results = await pipe.execute()
    request_count = results[2]

    if request_count > webhook.rate_limit_per_minute:
        await webhook_svc.log_request(
            webhook_id=webhook.id,
            status="rate_limited",
            remote_ip=remote_ip,
        )
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded",
        )

    # 4. Process the webhook payload
    start = time.time()
    try:
        body = await request.json()

        # 5. Normalise
        norm_svc = NormalizationService(db, redis)
        normalized, errors, warnings = await norm_svc.normalize(body)

        # 6. If normalization produced errors and no usable data, fail
        if errors and not normalized:
            await webhook_svc.log_request(
                webhook_id=webhook.id,
                status="normalization_failed",
                request_body=body,
                error_message="; ".join(errors),
                processing_time_ms=int((time.time() - start) * 1000),
                remote_ip=remote_ip,
            )
            await db.commit()
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"errors": errors, "warnings": warnings},
            )

        # 7. Create the incident
        incident_svc = IncidentService(db)
        tags = list(set((normalized.get("tags") or []) + (webhook.default_tags or [])))
        incident = await incident_svc.create(
            title=normalized.get("title") or f"Webhook alert from {webhook.name}",
            severity=normalized.get("severity") or webhook.default_severity,
            source=webhook.source_type,
            source_ref=webhook.name,
            tags=tags,
            metadata=normalized,
            created_by=webhook.created_by,
        )

        # 8. Re-fetch incident with relationships
        incident = await incident_svc.get(incident.id)

        # 9. Cache the incident
        cache = IncidentCacheService(redis)
        await cache.cache_incident(incident.id, _incident_to_cache_dict(incident))

        # 10. Check automation triggers if tags present
        triggered = []
        trigger_svc = TriggerService(db)
        if tags:
            triggered = await trigger_svc.check_and_trigger(
                incident_id=incident.id,
                new_tags=tags,
                triggered_by=webhook.created_by,
            )
            if triggered:
                logger.info(
                    "Webhook %s incident %s triggered %d automation(s) via tags",
                    webhook.id,
                    incident.id,
                    len(triggered),
                )

        # 10b. Source-based automation triggers
        if webhook.source_id:
            tag_triggered_ids = {t["automation_id"] for t in triggered} if triggered else set()
            source_triggered = await trigger_svc.trigger_by_source(
                source_id=webhook.source_id,
                incident_id=incident.id,
                triggered_by=webhook.created_by,
                exclude_automation_ids=tag_triggered_ids,
            )
            if source_triggered:
                logger.info(
                    "Webhook %s incident %s triggered %d automation(s) via source",
                    webhook.id,
                    incident.id,
                    len(source_triggered),
                )

        # 11. Increment webhook counter
        await webhook_svc.increment_counter(webhook.id)

        # 12. Calculate processing time and log success
        processing_time_ms = int((time.time() - start) * 1000)
        await webhook_svc.log_request(
            webhook_id=webhook.id,
            status="success",
            request_body=body,
            normalized_data=normalized,
            incident_id=incident.id,
            processing_time_ms=processing_time_ms,
            remote_ip=remote_ip,
        )
        await db.commit()

        return {
            "status": "success",
            "incident_id": str(incident.id),
            "warnings": warnings,
        }

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Webhook ingest error for token %s: %s", webhook_token, exc)
        processing_time_ms = int((time.time() - start) * 1000)
        try:
            await webhook_svc.log_request(
                webhook_id=webhook.id,
                status="error",
                error_message=str(exc),
                processing_time_ms=processing_time_ms,
                remote_ip=remote_ip,
            )
            await db.commit()
        except Exception:
            logger.exception("Failed to log webhook error for %s", webhook.id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error while processing webhook",
        )


# ===========================================================================
# Admin CRUD router (JWT + RBAC)
# ===========================================================================

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.get("", response_model=PaginatedResponse[WebhookListItem])
async def list_webhooks(
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    _: dict = Depends(require_permission("webhook", "read")),
    db: AsyncSession = Depends(get_db),
):
    svc = WebhookService(db)
    webhooks, total = await svc.list_webhooks(page, per_page)

    return PaginatedResponse(
        data=[
            WebhookListItem(
                id=w.id,
                name=w.name,
                source_type=w.source_type,
                is_enabled=w.is_enabled,
                last_received_at=w.last_received_at,
                total_received=w.total_received,
                created_at=w.created_at,
            )
            for w in webhooks
        ],
        meta=PaginationMeta(
            total=total,
            page=page,
            per_page=per_page,
            total_pages=(total + per_page - 1) // per_page if total else 0,
        ),
    )


@router.post("", response_model=WebhookRead, status_code=status.HTTP_201_CREATED)
async def create_webhook(
    body: WebhookCreate,
    current_user: User = Depends(get_current_user),
    _: dict = Depends(require_permission("webhook", "create")),
    db: AsyncSession = Depends(get_db),
):
    svc = WebhookService(db)
    webhook = await svc.create(
        name=body.name,
        created_by=current_user.id,
        description=body.description,
        source_type=body.source_type,
        source_id=body.source_id,
        default_severity=body.default_severity,
        default_tags=body.default_tags,
        rate_limit_per_minute=body.rate_limit_per_minute,
    )
    # Re-fetch with relationships
    webhook = await svc.get(webhook.id)
    return _webhook_to_read(webhook)


@router.get("/{webhook_id}", response_model=WebhookRead)
async def get_webhook(
    webhook_id: UUID,
    _: dict = Depends(require_permission("webhook", "read")),
    db: AsyncSession = Depends(get_db),
):
    svc = WebhookService(db)
    webhook = await svc.get(webhook_id)
    if not webhook:
        raise HTTPException(status_code=404, detail="Webhook not found")
    return _webhook_to_read(webhook)


@router.patch("/{webhook_id}", response_model=WebhookRead)
async def update_webhook(
    webhook_id: UUID,
    body: WebhookUpdate,
    _: dict = Depends(require_permission("webhook", "update")),
    db: AsyncSession = Depends(get_db),
):
    svc = WebhookService(db)
    webhook = await svc.get(webhook_id)
    if not webhook:
        raise HTTPException(status_code=404, detail="Webhook not found")

    # Apply only non-None fields via the service
    update_fields = body.model_dump(exclude_unset=True)
    if update_fields:
        webhook = await svc.update(webhook_id, **update_fields)
        # Re-fetch with relationships
        webhook = await svc.get(webhook_id)

    return _webhook_to_read(webhook)


@router.delete("/{webhook_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_webhook(
    webhook_id: UUID,
    _: dict = Depends(require_permission("webhook", "delete")),
    db: AsyncSession = Depends(get_db),
):
    svc = WebhookService(db)
    webhook = await svc.get(webhook_id)
    if not webhook:
        raise HTTPException(status_code=404, detail="Webhook not found")

    await svc.delete(webhook_id)
    return None


@router.post("/{webhook_id}/regenerate-token")
async def regenerate_token(
    webhook_id: UUID,
    _: dict = Depends(require_permission("webhook", "update")),
    db: AsyncSession = Depends(get_db),
):
    svc = WebhookService(db)
    webhook = await svc.get(webhook_id)
    if not webhook:
        raise HTTPException(status_code=404, detail="Webhook not found")

    new_token = await svc.regenerate_token(webhook_id)
    return {
        "secret_token": new_token,
        "ingest_url": f"/api/v1/webhooks/ingest/{new_token}",
    }


@router.get("/{webhook_id}/logs", response_model=PaginatedResponse[WebhookLogRead])
async def list_webhook_logs(
    webhook_id: UUID,
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=1, le=100),
    log_status: str | None = Query(None, alias="status"),
    _: dict = Depends(require_permission("webhook", "read")),
    db: AsyncSession = Depends(get_db),
):
    svc = WebhookService(db)
    webhook = await svc.get(webhook_id)
    if not webhook:
        raise HTTPException(status_code=404, detail="Webhook not found")

    logs, total = await svc.get_logs(
        webhook_id=webhook_id,
        page=page,
        per_page=per_page,
        status_filter=log_status,
    )

    return PaginatedResponse(
        data=[
            WebhookLogRead(
                id=log.id,
                webhook_id=log.webhook_id,
                status=log.status,
                request_body=log.request_body or {},
                normalized_data=log.normalized_data,
                incident_id=log.incident_id,
                error_message=log.error_message,
                processing_time_ms=log.processing_time_ms,
                remote_ip=log.remote_ip,
                created_at=log.created_at,
            )
            for log in logs
        ],
        meta=PaginationMeta(
            total=total,
            page=page,
            per_page=per_page,
            total_pages=(total + per_page - 1) // per_page if total else 0,
        ),
    )

"""Webhook source management endpoints."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from soas_backend.api.deps import get_current_user, require_permission
from soas_backend.database import get_db
from soas_backend.models.user import User
from soas_backend.services.webhook_source_service import WebhookSourceService
from soas_shared.schemas.webhook_source import (
    SourceAutomationCreate,
    SourceAutomationRead,
    SourceAutomationUpdate,
    WebhookSourceCreate,
    WebhookSourceListItem,
    WebhookSourceRead,
    WebhookSourceUpdate,
)

router = APIRouter(prefix="/webhook-sources", tags=["webhook-sources"])


def _source_to_read(source) -> WebhookSourceRead:
    return WebhookSourceRead(
        id=source.id,
        name=source.name,
        description=source.description,
        icon=source.icon,
        automations=[
            SourceAutomationRead(
                id=link.id,
                source_id=link.source_id,
                automation_id=link.automation_id,
                automation_name=link.automation.name if link.automation else "Unknown",
                is_enabled=link.is_enabled,
                run_order=link.run_order,
                created_at=link.created_at,
            )
            for link in (source.automations or [])
        ],
        created_at=source.created_at,
        updated_at=source.updated_at,
    )


@router.get("", response_model=list[WebhookSourceListItem])
async def list_sources(
    _: dict = Depends(require_permission("webhook_source", "read")),
    db: AsyncSession = Depends(get_db),
):
    svc = WebhookSourceService(db)
    sources = await svc.list_sources()
    return [
        WebhookSourceListItem(
            id=s.id,
            name=s.name,
            description=s.description,
            icon=s.icon,
            automation_count=len(s.automations) if s.automations else 0,
            created_at=s.created_at,
        )
        for s in sources
    ]


@router.post("", response_model=WebhookSourceRead, status_code=status.HTTP_201_CREATED)
async def create_source(
    body: WebhookSourceCreate,
    current_user: User = Depends(get_current_user),
    _: dict = Depends(require_permission("webhook_source", "create")),
    db: AsyncSession = Depends(get_db),
):
    svc = WebhookSourceService(db)
    source = await svc.create(
        name=body.name,
        created_by=current_user.id,
        description=body.description,
        icon=body.icon,
    )
    return _source_to_read(source)


@router.get("/{source_id}", response_model=WebhookSourceRead)
async def get_source(
    source_id: UUID,
    _: dict = Depends(require_permission("webhook_source", "read")),
    db: AsyncSession = Depends(get_db),
):
    svc = WebhookSourceService(db)
    source = await svc.get(source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    return _source_to_read(source)


@router.patch("/{source_id}", response_model=WebhookSourceRead)
async def update_source(
    source_id: UUID,
    body: WebhookSourceUpdate,
    _: dict = Depends(require_permission("webhook_source", "update")),
    db: AsyncSession = Depends(get_db),
):
    svc = WebhookSourceService(db)
    source = await svc.get(source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")

    update_fields = body.model_dump(exclude_unset=True)
    if update_fields:
        source = await svc.update(source_id, **update_fields)
    return _source_to_read(source)


@router.delete("/{source_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_source(
    source_id: UUID,
    _: dict = Depends(require_permission("webhook_source", "delete")),
    db: AsyncSession = Depends(get_db),
):
    svc = WebhookSourceService(db)
    source = await svc.get(source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    await svc.delete(source_id)
    return None


@router.post("/{source_id}/automations", response_model=SourceAutomationRead, status_code=status.HTTP_201_CREATED)
async def link_automation(
    source_id: UUID,
    body: SourceAutomationCreate,
    _: dict = Depends(require_permission("webhook_source", "update")),
    db: AsyncSession = Depends(get_db),
):
    svc = WebhookSourceService(db)
    source = await svc.get(source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")

    link = await svc.link_automation(
        source_id=source_id,
        automation_id=body.automation_id,
        is_enabled=body.is_enabled,
        run_order=body.run_order,
    )

    # Evict cached source so re-fetch loads the new link with eager-loaded automation
    db.expunge(source)
    source = await svc.get(source_id)
    for a in source.automations:
        if a.id == link.id:
            return SourceAutomationRead(
                id=a.id,
                source_id=a.source_id,
                automation_id=a.automation_id,
                automation_name=a.automation.name if a.automation else "Unknown",
                is_enabled=a.is_enabled,
                run_order=a.run_order,
                created_at=a.created_at,
            )

    raise HTTPException(status_code=500, detail="Failed to retrieve linked automation")


@router.patch("/{source_id}/automations/{automation_id}", response_model=SourceAutomationRead)
async def update_source_automation(
    source_id: UUID,
    automation_id: UUID,
    body: SourceAutomationUpdate,
    _: dict = Depends(require_permission("webhook_source", "update")),
    db: AsyncSession = Depends(get_db),
):
    svc = WebhookSourceService(db)
    update_fields = body.model_dump(exclude_unset=True)
    if not update_fields:
        raise HTTPException(status_code=400, detail="No fields to update")

    link = await svc.update_link(source_id, automation_id, **update_fields)
    if not link:
        raise HTTPException(status_code=404, detail="Link not found")

    # Re-fetch to get automation name via eager load
    source = await svc.get(source_id)
    for a in source.automations:
        if a.automation_id == automation_id:
            return SourceAutomationRead(
                id=a.id,
                source_id=a.source_id,
                automation_id=a.automation_id,
                automation_name=a.automation.name if a.automation else "Unknown",
                is_enabled=a.is_enabled,
                run_order=a.run_order,
                created_at=a.created_at,
            )

    raise HTTPException(status_code=500, detail="Failed to retrieve updated link")


@router.delete("/{source_id}/automations/{automation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def unlink_automation(
    source_id: UUID,
    automation_id: UUID,
    _: dict = Depends(require_permission("webhook_source", "update")),
    db: AsyncSession = Depends(get_db),
):
    svc = WebhookSourceService(db)
    removed = await svc.unlink_automation(source_id, automation_id)
    if not removed:
        raise HTTPException(status_code=404, detail="Link not found")
    return None

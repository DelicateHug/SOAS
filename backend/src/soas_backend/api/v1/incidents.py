"""Incident CRUD endpoints with Redis caching and tag-based triggering."""

import logging
from uuid import UUID

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from soas_backend.api.deps import get_current_user, get_redis, get_user_teams, require_permission
from soas_backend.database import get_db
from soas_backend.models.user import User
from soas_backend.services.audit import audit
from soas_backend.services.incident_cache import IncidentCacheService
from soas_backend.services.incident_service import IncidentService
from soas_backend.services.normalization_service import NormalizationService
from soas_backend.services.trigger_service import TriggerService
from soas_shared.schemas.common import PaginatedResponse, PaginationMeta
from soas_shared.schemas.incident import (
    IncidentAssign,
    IncidentCreate,
    IncidentListItem,
    IncidentRead,
    IncidentTransition,
    IncidentUpdate,
)
from soas_shared.schemas.user import UserBrief

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/incidents", tags=["incidents"])


def _user_brief(user) -> UserBrief | None:
    if user is None:
        return None
    return UserBrief(id=user.id, username=user.username, display_name=user.display_name)


def _incident_read(incident) -> IncidentRead:
    case_id = None
    group_ids: list = []
    if hasattr(incident, "case_incidents") and incident.case_incidents:
        case_id = incident.case_incidents[0].case_id
        group_ids = [ci.case_id for ci in incident.case_incidents]
    return IncidentRead(
        id=incident.id,
        title=incident.title,
        summary=incident.summary,
        severity=incident.severity,
        status=incident.status,
        source=incident.source,
        source_ref=incident.source_ref,
        lead=_user_brief(incident.lead),
        created_by=_user_brief(incident.creator),
        detected_at=incident.detected_at,
        resolved_at=incident.resolved_at,
        closed_at=incident.closed_at,
        tags=incident.tags or [],
        metadata=incident.metadata_,
        raw_event=incident.raw_event,
        created_at=incident.created_at,
        updated_at=incident.updated_at,
        assignment_count=len(incident.assignments),
        case_id=case_id,
        group_ids=group_ids,
        team_id=incident.team_id,
    )


def _incident_to_cache_dict(incident) -> dict:
    """Build a flat dict suitable for IncidentCacheService.cache_incident."""
    case_id = None
    if hasattr(incident, "case_incidents") and incident.case_incidents:
        case_id = str(incident.case_incidents[0].case_id)
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
        "raw_event": incident.raw_event,
        "created_at": str(incident.created_at) if incident.created_at else None,
        "updated_at": str(incident.updated_at) if incident.updated_at else None,
        "closed_at": str(incident.closed_at) if incident.closed_at else None,
        "case_id": case_id,
    }


@router.get("", response_model=PaginatedResponse[IncidentListItem])
async def list_incidents(
    severity: str | None = None,
    incident_status: str | None = Query(None, alias="status"),
    team_id: UUID | None = None,
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    _: dict = Depends(require_permission("incident", "read")),
    user_teams: list | None = Depends(get_user_teams),
    db: AsyncSession = Depends(get_db),
):
    svc = IncidentService(db)
    incidents, total = await svc.list_incidents(
        severity, incident_status, page, per_page,
        user_teams=user_teams, team_id=team_id,
    )

    return PaginatedResponse(
        data=[
            IncidentListItem(
                id=i.id,
                title=i.title,
                severity=i.severity,
                status=i.status,
                lead=_user_brief(i.lead),
                created_by=_user_brief(i.creator),
                detected_at=i.detected_at,
                tags=i.tags or [],
                created_at=i.created_at,
                updated_at=i.updated_at,
                group_ids=[ci.case_id for ci in i.case_incidents]
                if hasattr(i, "case_incidents") and i.case_incidents
                else [],
                team_id=i.team_id,
            )
            for i in incidents
        ],
        meta=PaginationMeta(
            total=total,
            page=page,
            per_page=per_page,
            total_pages=(total + per_page - 1) // per_page if total else 0,
        ),
    )


@router.post("", response_model=IncidentRead, status_code=status.HTTP_201_CREATED)
@audit(
    "incident.created",
    target_kind="incident",
    extract_target=lambda r: getattr(r, "id", None),
    extract_label=lambda r: getattr(r, "title", None),
)
async def create_incident(
    body: IncidentCreate,
    current_user: User = Depends(get_current_user),
    _: dict = Depends(require_permission("incident", "create")),
    user_teams: list | None = Depends(get_user_teams),
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
):
    # Run normalization on metadata to enrich incident fields
    effective_severity = body.severity
    effective_summary = body.summary
    norm_tags: list[str] = []

    if body.metadata:
        norm_svc = NormalizationService(db, redis)
        normalized, _errors, _warnings = await norm_svc.normalize(body.metadata)
        if normalized:
            # Use normalized values as fallbacks for fields not explicitly set
            if body.severity == "medium" and normalized.get("severity"):
                effective_severity = normalized["severity"]
            if not body.summary and normalized.get("summary"):
                effective_summary = normalized["summary"]
            norm_tags = normalized.get("tags") or []
            if isinstance(norm_tags, str):
                norm_tags = [norm_tags]

    effective_tags = list(set(body.tags + norm_tags))

    # Auto-stamp team_id from the caller's primary team if they didn't pick one.
    # Without this, rows land with team_id=NULL and get hidden from the team-filtered list view.
    effective_team_id = body.team_id
    if effective_team_id is None and user_teams:
        effective_team_id = UUID(user_teams[0]["id"])

    svc = IncidentService(db)
    incident = await svc.create(
        title=body.title,
        created_by=current_user.id,
        severity=effective_severity,
        summary=effective_summary,
        source=body.source,
        source_ref=body.source_ref,
        tags=effective_tags,
        metadata=body.metadata,
        raw_event=body.raw_event,
        team_id=effective_team_id,
    )
    # Re-fetch with relationships
    incident = await svc.get(incident.id)

    # Cache the newly created incident
    cache = IncidentCacheService(redis)
    await cache.cache_incident(incident.id, _incident_to_cache_dict(incident))

    # If the incident was created with tags, check for triggers
    if effective_tags:
        trigger_svc = TriggerService(db)
        triggered = await trigger_svc.check_and_trigger(
            incident_id=incident.id,
            new_tags=effective_tags,
            triggered_by=current_user.id,
        )
        if triggered:
            logger.info(
                "Incident %s creation triggered %d automation(s)",
                incident.id,
                len(triggered),
            )

    return _incident_read(incident)


@router.get("/{incident_id}", response_model=IncidentRead)
async def get_incident(
    incident_id: UUID,
    _: dict = Depends(require_permission("incident", "read")),
    user_teams: list | None = Depends(get_user_teams),
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
):
    # Sync-on-read: merge any dirty variables from Redis into Postgres
    cache = IncidentCacheService(redis)
    await cache.sync_dirty_vars_to_postgres(incident_id, db)

    svc = IncidentService(db)
    incident = await svc.get(incident_id)
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")

    # Team visibility check
    if user_teams is not None and incident.team_id is not None:
        team_ids = [t["id"] for t in user_teams]
        if str(incident.team_id) not in team_ids:
            raise HTTPException(status_code=404, detail="Incident not found")

    return _incident_read(incident)


@router.patch("/{incident_id}", response_model=IncidentRead)
@audit(
    "incident.updated",
    target_kind="incident",
    extract_target=lambda r: getattr(r, "id", None),
    extract_label=lambda r: getattr(r, "title", None),
)
async def update_incident(
    incident_id: UUID,
    body: IncidentUpdate,
    current_user: User = Depends(get_current_user),
    _: dict = Depends(require_permission("incident", "update")),
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
):
    """Update incident fields.  When tags change, triggers are evaluated."""
    svc = IncidentService(db)
    incident = await svc.get(incident_id)
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")

    old_tags = list(incident.tags or [])

    # Apply field updates
    if body.title is not None:
        incident.title = body.title
    if body.summary is not None:
        incident.summary = body.summary
    if body.severity is not None:
        incident.severity = body.severity
    if body.source is not None:
        incident.source = body.source
    if body.source_ref is not None:
        incident.source_ref = body.source_ref
    if body.tags is not None:
        incident.tags = body.tags
    if body.metadata is not None:
        incident.metadata_ = body.metadata
    if body.raw_event is not None:
        incident.raw_event = body.raw_event

    await db.flush()

    # Re-fetch with relationships
    incident = await svc.get(incident_id)

    # Update cache
    cache = IncidentCacheService(redis)
    await cache.cache_incident(incident.id, _incident_to_cache_dict(incident))

    # If tags changed, check for triggers
    new_tags = list(incident.tags or [])
    if body.tags is not None:
        added_tags = await cache.update_incident_tags(incident_id, old_tags, new_tags)
        if added_tags:
            trigger_svc = TriggerService(db)
            triggered = await trigger_svc.check_and_trigger(
                incident_id=incident_id,
                new_tags=added_tags,
                triggered_by=current_user.id,
            )
            if triggered:
                logger.info(
                    "Incident %s tag update triggered %d automation(s) via tags %s",
                    incident_id,
                    len(triggered),
                    added_tags,
                )

    return _incident_read(incident)


@router.post("/{incident_id}/transition", response_model=IncidentRead)
@audit(
    "incident.transitioned",
    target_kind="incident",
    extract_target=lambda r: getattr(r, "id", None),
    extract_label=lambda r: getattr(r, "title", None),
)
async def transition_incident(
    incident_id: UUID,
    body: IncidentTransition,
    current_user: User = Depends(get_current_user),
    _: dict = Depends(require_permission("incident", "update")),
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
):
    svc = IncidentService(db)
    try:
        incident = await svc.transition(
            incident_id, body.new_status, current_user.id, body.comment
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    incident = await svc.get(incident_id)

    # Update cache after status transition
    cache = IncidentCacheService(redis)
    await cache.cache_incident(incident.id, _incident_to_cache_dict(incident))

    return _incident_read(incident)


@router.post("/{incident_id}/assign", status_code=status.HTTP_201_CREATED)
async def assign_to_incident(
    incident_id: UUID,
    body: IncidentAssign,
    current_user: User = Depends(get_current_user),
    _: dict = Depends(require_permission("incident", "assign")),
    db: AsyncSession = Depends(get_db),
):
    svc = IncidentService(db)
    await svc.assign(
        incident_id,
        body.user_id,
        body.role_in_incident,
        assigned_by=current_user.id,
    )
    return {"message": "User assigned to incident"}

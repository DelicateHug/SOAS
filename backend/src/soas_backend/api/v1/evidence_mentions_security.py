"""REST API for evidence snapshots, chat mentions, and security events."""

from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import and_, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from soas_backend.api.deps import get_current_user, require_role
from soas_backend.database import get_db
from soas_backend.models.chat_mention import ChatMention, ChatReadReceipt
from soas_backend.models.evidence_snapshot import EvidenceSnapshot
from soas_backend.models.security_event import SecurityEvent
from soas_backend.models.user import User

router = APIRouter(tags=["evidence-mentions-security"])


# ============================================================
# Evidence snapshots
# ============================================================


class EvidenceCreate(BaseModel):
    incident_id: UUID | None = None
    case_id: UUID | None = None
    title: str = Field(min_length=1, max_length=500)
    source: str = "manual"
    source_ref: str | None = None
    query_text: str | None = None
    columns: list[str] = Field(default_factory=list)
    rows: list[list[Any]] = Field(default_factory=list, max_length=5000)


class EvidenceRead(BaseModel):
    id: UUID
    incident_id: UUID | None
    case_id: UUID | None
    title: str
    source: str
    source_ref: str | None
    query_text: str | None
    query_hash: str | None
    columns: list[str]
    rows: list[list[Any]]
    row_count: int
    created_by: UUID
    created_at: datetime

    model_config = {"from_attributes": True}


@router.post("/evidence", response_model=EvidenceRead, status_code=201)
async def create_evidence(
    body: EvidenceCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if (body.incident_id is None) == (body.case_id is None):
        raise HTTPException(status_code=400, detail="Provide exactly one of incident_id or case_id")
    query_hash = None
    if body.query_text:
        query_hash = hashlib.sha256(
            f"{body.source}|{body.query_text}".encode("utf-8")
        ).hexdigest()
    snap = EvidenceSnapshot(
        incident_id=body.incident_id,
        case_id=body.case_id,
        title=body.title,
        source=body.source,
        source_ref=body.source_ref,
        query_text=body.query_text,
        query_hash=query_hash,
        columns=body.columns,
        rows=body.rows,
        row_count=len(body.rows),
        created_by=current_user.id,
    )
    db.add(snap)
    await db.flush()
    return snap


@router.get("/evidence/by-incident/{incident_id}", response_model=list[EvidenceRead])
async def evidence_by_incident(
    incident_id: UUID,
    _: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    rs = await db.execute(
        select(EvidenceSnapshot)
        .where(EvidenceSnapshot.incident_id == incident_id)
        .order_by(EvidenceSnapshot.created_at.desc())
        .limit(200)
    )
    return list(rs.scalars().all())


@router.get("/evidence/by-case/{case_id}", response_model=list[EvidenceRead])
async def evidence_by_case(
    case_id: UUID,
    _: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    rs = await db.execute(
        select(EvidenceSnapshot)
        .where(EvidenceSnapshot.case_id == case_id)
        .order_by(EvidenceSnapshot.created_at.desc())
        .limit(200)
    )
    return list(rs.scalars().all())


@router.delete("/evidence/{evidence_id}", status_code=204)
async def delete_evidence(
    evidence_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    rs = await db.execute(select(EvidenceSnapshot).where(EvidenceSnapshot.id == evidence_id))
    snap = rs.scalar_one_or_none()
    if not snap:
        raise HTTPException(status_code=404, detail="Evidence not found")
    if snap.created_by != current_user.id:
        raise HTTPException(status_code=403, detail="Not the owner")
    await db.delete(snap)


# ============================================================
# Mentions
# ============================================================

MENTION_RE = re.compile(r"@([a-zA-Z0-9_.-]+)")


class MentionRead(BaseModel):
    id: UUID
    user_id: UUID
    author_id: UUID
    incident_id: UUID | None
    case_id: UUID | None
    source_kind: str
    source_ref: UUID | None
    excerpt: str | None
    is_read: bool
    read_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class MentionsCreateBody(BaseModel):
    text: str
    incident_id: UUID | None = None
    case_id: UUID | None = None
    source_kind: str
    source_ref: UUID | None = None


@router.post("/mentions/extract", response_model=list[MentionRead], status_code=201)
async def extract_and_record_mentions(
    body: MentionsCreateBody,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Parse @username references from `text` and create mention rows.

    Returns the mentions created. Unknown usernames are silently skipped.
    """
    usernames = list({m.group(1).lower() for m in MENTION_RE.finditer(body.text or "")})
    if not usernames:
        return []
    rs = await db.execute(
        select(User).where(User.username.in_(usernames))
    )
    users = list(rs.scalars().all())
    excerpt = body.text[:480]
    created: list[ChatMention] = []
    for u in users:
        if u.id == current_user.id:
            continue  # don't notify yourself
        m = ChatMention(
            user_id=u.id,
            author_id=current_user.id,
            incident_id=body.incident_id,
            case_id=body.case_id,
            source_kind=body.source_kind,
            source_ref=body.source_ref,
            excerpt=excerpt,
        )
        db.add(m)
        created.append(m)
    await db.flush()
    return created


@router.get("/mentions/me", response_model=list[MentionRead])
async def my_mentions(
    unread_only: bool = Query(True),
    limit: int = Query(50, ge=1, le=500),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    q = select(ChatMention).where(ChatMention.user_id == current_user.id)
    if unread_only:
        q = q.where(ChatMention.is_read.is_(False))
    q = q.order_by(ChatMention.created_at.desc()).limit(limit)
    rs = await db.execute(q)
    return list(rs.scalars().all())


@router.post("/mentions/{mention_id}/read", status_code=204)
async def mark_mention_read(
    mention_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await db.execute(
        update(ChatMention)
        .where(and_(ChatMention.id == mention_id, ChatMention.user_id == current_user.id))
        .values(is_read=True, read_at=datetime.now(timezone.utc))
    )


@router.post("/mentions/read-all", status_code=204)
async def mark_all_read(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await db.execute(
        update(ChatMention)
        .where(and_(ChatMention.user_id == current_user.id, ChatMention.is_read.is_(False)))
        .values(is_read=True, read_at=datetime.now(timezone.utc))
    )


# ============================================================
# Security events (admin read-only)
# ============================================================


class SecurityEventRead(BaseModel):
    id: UUID
    event_type: str
    severity: str
    actor_id: UUID | None
    actor_label: str | None
    target_kind: str | None
    target_id: UUID | None
    target_label: str | None
    message: str | None
    ip_address: str | None
    extra: dict[str, Any]
    created_at: datetime

    model_config = {"from_attributes": True}


@router.get("/security-events", response_model=list[SecurityEventRead])
async def list_security_events(
    event_type: str | None = Query(None),
    severity: str | None = Query(None),
    actor_id: UUID | None = Query(None),
    limit: int = Query(200, ge=1, le=2000),
    _: dict = Depends(require_role("admin", "soc_manager")),
    db: AsyncSession = Depends(get_db),
):
    q = select(SecurityEvent).order_by(SecurityEvent.created_at.desc()).limit(limit)
    if event_type:
        q = q.where(SecurityEvent.event_type == event_type)
    if severity:
        q = q.where(SecurityEvent.severity == severity)
    if actor_id:
        q = q.where(SecurityEvent.actor_id == actor_id)
    rs = await db.execute(q)
    return list(rs.scalars().all())

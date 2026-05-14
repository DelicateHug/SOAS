"""Saved queries CRUD + favorites + template substitution (Phase 4).

Heavy query execution is deferred to connector-specific runners (Phase
10 + future connector work). This phase ships the library: save, list,
favorite, share, template render, and a single in-line execute for
incidents_sql / raw_sql against the local DB.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import delete, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from soas_backend.api.deps import get_current_user, require_role, security
from soas_backend.auth.jwt import decode_access_token
from fastapi.security import HTTPAuthorizationCredentials
from soas_backend.database import get_db
from soas_backend.models.saved_query import SavedQuery, SavedQueryFavorite
from soas_backend.models.user import User

router = APIRouter(prefix="/saved-queries", tags=["saved-queries"])

ALLOWED_QUERY_TYPES = {"incidents_sql", "leql", "kql", "raw_sql"}
TEMPLATE_RE = re.compile(r"\$\{([a-zA-Z_][a-zA-Z0-9_]*)\}")


# ----- schemas -----


class QueryRead(BaseModel):
    id: UUID
    name: str
    description: str | None
    query_type: str
    query_text: str
    connector_id: UUID | None
    is_public: bool
    tags: list[str]
    owner_id: UUID
    favorite_count: int
    is_favorite: bool = False

    model_config = {"from_attributes": True}


class QueryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = None
    query_type: str
    query_text: str = Field(min_length=1)
    connector_id: UUID | None = None
    is_public: bool = False
    tags: list[str] = Field(default_factory=list)


class QueryUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    query_text: str | None = None
    connector_id: UUID | None = None
    is_public: bool | None = None
    tags: list[str] | None = None


class QueryExecute(BaseModel):
    parameters: dict[str, Any] = Field(default_factory=dict)


# ----- helpers -----


def _render_template(query_text: str, params: dict[str, Any]) -> str:
    """Substitute ${var} placeholders with stringified parameter values.

    Unmatched placeholders are left as ${var} so the runner can reject them.
    """
    def repl(m: re.Match[str]) -> str:
        key = m.group(1)
        return str(params[key]) if key in params else m.group(0)
    return TEMPLATE_RE.sub(repl, query_text)


# ----- routes -----


@router.get("", response_model=list[QueryRead])
async def list_queries(
    current_user: User = Depends(get_current_user),
    only_mine: bool = Query(False),
    favorited: bool = Query(False),
    db: AsyncSession = Depends(get_db),
):
    q = select(SavedQuery).order_by(SavedQuery.updated_at.desc())
    if only_mine:
        q = q.where(SavedQuery.owner_id == current_user.id)
    else:
        q = q.where(
            or_(SavedQuery.is_public.is_(True), SavedQuery.owner_id == current_user.id)
        )
    if favorited:
        fav_q = select(SavedQueryFavorite.saved_query_id).where(
            SavedQueryFavorite.user_id == current_user.id
        )
        q = q.where(SavedQuery.id.in_(fav_q))
    result = await db.execute(q)
    rows = list(result.scalars().all())

    # Mark favorites
    fav_result = await db.execute(
        select(SavedQueryFavorite.saved_query_id)
        .where(SavedQueryFavorite.user_id == current_user.id)
    )
    fav_ids = {r[0] for r in fav_result.all()}
    return [
        QueryRead(
            id=r.id, name=r.name, description=r.description, query_type=r.query_type,
            query_text=r.query_text, connector_id=r.connector_id, is_public=r.is_public,
            tags=r.tags or [], owner_id=r.owner_id, favorite_count=r.favorite_count,
            is_favorite=r.id in fav_ids,
        )
        for r in rows
    ]


@router.post("", response_model=QueryRead, status_code=201)
async def create_query(
    body: QueryCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if body.query_type not in ALLOWED_QUERY_TYPES:
        raise HTTPException(status_code=400, detail=f"Unknown query_type: {body.query_type}")
    # raw_sql creation is permissive; the execute path enforces admin.
    sq = SavedQuery(
        name=body.name,
        description=body.description,
        query_type=body.query_type,
        query_text=body.query_text,
        connector_id=body.connector_id,
        is_public=body.is_public,
        tags=body.tags,
        owner_id=current_user.id,
    )
    db.add(sq)
    await db.flush()
    return QueryRead(
        id=sq.id, name=sq.name, description=sq.description, query_type=sq.query_type,
        query_text=sq.query_text, connector_id=sq.connector_id, is_public=sq.is_public,
        tags=sq.tags or [], owner_id=sq.owner_id, favorite_count=0, is_favorite=False,
    )


@router.get("/{query_id}", response_model=QueryRead)
async def get_query(
    query_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(SavedQuery).where(SavedQuery.id == query_id))
    sq = result.scalar_one_or_none()
    if not sq:
        raise HTTPException(status_code=404, detail="Saved query not found")
    if not sq.is_public and sq.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")
    fav_check = await db.execute(
        select(SavedQueryFavorite).where(
            SavedQueryFavorite.user_id == current_user.id,
            SavedQueryFavorite.saved_query_id == sq.id,
        )
    )
    return QueryRead(
        id=sq.id, name=sq.name, description=sq.description, query_type=sq.query_type,
        query_text=sq.query_text, connector_id=sq.connector_id, is_public=sq.is_public,
        tags=sq.tags or [], owner_id=sq.owner_id, favorite_count=sq.favorite_count,
        is_favorite=fav_check.scalar_one_or_none() is not None,
    )


@router.patch("/{query_id}", response_model=QueryRead)
async def update_query(
    query_id: UUID,
    body: QueryUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(SavedQuery).where(SavedQuery.id == query_id))
    sq = result.scalar_one_or_none()
    if not sq:
        raise HTTPException(status_code=404, detail="Saved query not found")
    if sq.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not the owner")
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(sq, k, v)
    await db.flush()
    return await get_query(query_id, current_user, db)


@router.delete("/{query_id}", status_code=204)
async def delete_query(
    query_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(SavedQuery).where(SavedQuery.id == query_id))
    sq = result.scalar_one_or_none()
    if not sq:
        raise HTTPException(status_code=404, detail="Saved query not found")
    if sq.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not the owner")
    await db.delete(sq)


@router.post("/{query_id}/favorite", status_code=204)
async def add_favorite(
    query_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Idempotent.
    result = await db.execute(
        select(SavedQueryFavorite).where(
            SavedQueryFavorite.user_id == current_user.id,
            SavedQueryFavorite.saved_query_id == query_id,
        )
    )
    if result.scalar_one_or_none():
        return
    db.add(SavedQueryFavorite(user_id=current_user.id, saved_query_id=query_id))
    sq_result = await db.execute(select(SavedQuery).where(SavedQuery.id == query_id))
    sq = sq_result.scalar_one_or_none()
    if sq:
        sq.favorite_count = (sq.favorite_count or 0) + 1
    await db.flush()


@router.delete("/{query_id}/favorite", status_code=204)
async def remove_favorite(
    query_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        delete(SavedQueryFavorite).where(
            SavedQueryFavorite.user_id == current_user.id,
            SavedQueryFavorite.saved_query_id == query_id,
        ).returning(SavedQueryFavorite.id)
    )
    deleted_ids = list(result.all())
    if deleted_ids:
        sq_result = await db.execute(select(SavedQuery).where(SavedQuery.id == query_id))
        sq = sq_result.scalar_one_or_none()
        if sq and sq.favorite_count > 0:
            sq.favorite_count -= 1
        await db.flush()


# ----- execute -----


async def _is_admin(credentials: HTTPAuthorizationCredentials) -> bool:
    payload = decode_access_token(credentials.credentials)
    return bool(payload) and "admin" in (payload.get("roles") or [])


@router.post("/{query_id}/execute")
async def execute_query(
    query_id: UUID,
    body: QueryExecute,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Execute a saved query inline. Only safe types are run server-side
    here — incidents_sql / raw_sql against the local DB. leql/kql route
    to the connector framework (not implemented in this phase)."""
    result = await db.execute(select(SavedQuery).where(SavedQuery.id == query_id))
    sq = result.scalar_one_or_none()
    if not sq:
        raise HTTPException(status_code=404, detail="Saved query not found")
    if not sq.is_public and sq.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")

    rendered = _render_template(sq.query_text, body.parameters)
    if TEMPLATE_RE.search(rendered):
        raise HTTPException(status_code=400, detail="Unresolved template parameters")

    if sq.query_type == "raw_sql":
        # Admin-only, SELECT-only, hard timeout, capped rows.
        if not await _is_admin(credentials):
            raise HTTPException(status_code=403, detail="raw_sql is admin-only")
        if not re.match(r"^\s*select\b", rendered, re.IGNORECASE):
            raise HTTPException(status_code=400, detail="Only SELECT statements are allowed")
        try:
            await db.execute(text("SET LOCAL statement_timeout = 10000"))
        except Exception:
            pass
        try:
            res = await db.execute(text(rendered).execution_options(stream_results=False))
            rows = [dict(r._mapping) for r in res.fetchmany(500)]
            return {"data": rows, "meta": {"rendered_query": rendered, "row_count": len(rows)}}
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Query error: {e}")

    if sq.query_type == "incidents_sql":
        # Stricter wrapper: must include "from incidents" somewhere, must be SELECT,
        # parameters already substituted via the template render above.
        if not re.match(r"^\s*select\b", rendered, re.IGNORECASE):
            raise HTTPException(status_code=400, detail="incidents_sql requires SELECT")
        if "from incidents" not in rendered.lower():
            raise HTTPException(status_code=400, detail="incidents_sql must reference 'from incidents'")
        try:
            res = await db.execute(text(rendered))
            rows = [dict(r._mapping) for r in res.fetchmany(500)]
            return {"data": rows, "meta": {"rendered_query": rendered, "row_count": len(rows)}}
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Query error: {e}")

    # LEQL / KQL not implemented in this phase — return an empty stub so the
    # frontend can hand off to the connector flow once Phase 10 lands.
    return {
        "data": [],
        "meta": {
            "rendered_query": rendered,
            "note": f"{sq.query_type} execution is gated on connector framework (Phase 10).",
        },
    }

"""RAG (Retrieval-Augmented Generation) endpoints for the wiki.

These endpoints expose the local semantic search over wiki content. They are read-mostly
for any authenticated user with `wiki:read`, while reindex operations require admin.
"""

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from soas_backend.api.deps import get_user_teams, require_permission, require_role
from soas_backend.database import get_db
from soas_backend.services.wiki_rag_service import WikiRagService

router = APIRouter(prefix="/rag", tags=["rag"])


class RagSearchHitOut(BaseModel):
    page_id: UUID
    page_title: str
    page_slug: str
    chunk_index: int
    chunk_text: str
    score: float


class RagSearchResponse(BaseModel):
    query: str
    hits: list[RagSearchHitOut]
    count: int


class RagReindexResponse(BaseModel):
    scheduled: int


class RagPageStatusOut(BaseModel):
    page_id: UUID
    status: str
    indexed_version: int | None
    chunk_count: int
    model_name: str | None
    error_message: str | None


class RagOverallStatusOut(BaseModel):
    total_pages: int
    indexed_pages: int
    failed_pages: int
    total_chunks: int
    embedding_service: dict[str, Any]


@router.get("/search", response_model=RagSearchResponse)
async def rag_search(
    q: str = Query(..., min_length=1, description="Free-text query"),
    top_k: int = Query(5, ge=1, le=50),
    min_score: float = Query(0.0, ge=-1.0, le=1.0),
    _: dict = Depends(require_permission("wiki", "read")),
    user_teams: list | None = Depends(get_user_teams),
    db: AsyncSession = Depends(get_db),
):
    """Semantic search over the wiki. Returns the top-k chunks ranked by cosine similarity."""
    svc = WikiRagService(db)
    team_uuids = None
    if user_teams is not None:
        team_uuids = [UUID(t["id"]) for t in user_teams]

    try:
        hits = await svc.search(q, top_k=top_k, min_score=min_score, team_ids=team_uuids)
    except Exception as e:
        # Embedding service not reachable, model still loading, etc. Surface as 503 so
        # callers know to back off rather than treating as no-results.
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"RAG search unavailable: {e}",
        )

    return RagSearchResponse(
        query=q,
        hits=[RagSearchHitOut(**h.__dict__) for h in hits],
        count=len(hits),
    )


@router.post("/reindex", response_model=RagReindexResponse)
async def rag_reindex_all(
    _: dict = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    """Schedule a full re-index of every wiki page (admin only)."""
    # Importing inside the function avoids paying the celery import cost on cold start.
    from celery import Celery
    import os
    broker = os.environ.get("CELERY_BROKER_URL", "redis://redis:6379/0")
    backend = os.environ.get("CELERY_RESULT_BACKEND", "redis://redis:6379/1")
    c = Celery("soas_backend_proxy", broker=broker, backend=backend)
    result = c.send_task("soas.reindex_wiki_all", queue="celery")

    # Best effort: count pages so we can show "scheduled X tasks" in the UI.
    from sqlalchemy import func, select
    from soas_backend.models.wiki import WikiPage
    total_q = await db.execute(select(func.count()).select_from(WikiPage))
    total = int(total_q.scalar() or 0)

    # We don't block on the celery result — the task itself fans out per-page tasks.
    _ = result
    return RagReindexResponse(scheduled=total)


@router.post("/reindex/{page_id}")
async def rag_reindex_page(
    page_id: UUID,
    _: dict = Depends(require_role("admin")),
):
    """Force re-index of a single page."""
    from celery import Celery
    import os
    broker = os.environ.get("CELERY_BROKER_URL", "redis://redis:6379/0")
    backend = os.environ.get("CELERY_RESULT_BACKEND", "redis://redis:6379/1")
    c = Celery("soas_backend_proxy", broker=broker, backend=backend)
    c.send_task("soas.reindex_wiki_page", args=[str(page_id)], queue="celery")
    return {"page_id": str(page_id), "scheduled": True}


@router.get("/status", response_model=RagOverallStatusOut)
async def rag_overall_status(
    _: dict = Depends(require_permission("wiki", "read")),
    db: AsyncSession = Depends(get_db),
):
    """Overall index health + embedding service status."""
    svc = WikiRagService(db)
    return RagOverallStatusOut(**await svc.overall_status())


@router.get("/status/{page_id}", response_model=RagPageStatusOut)
async def rag_page_status(
    page_id: UUID,
    _: dict = Depends(require_permission("wiki", "read")),
    db: AsyncSession = Depends(get_db),
):
    svc = WikiRagService(db)
    s = await svc.get_status(page_id)
    if s is None:
        return RagPageStatusOut(
            page_id=page_id,
            status="not_indexed",
            indexed_version=None,
            chunk_count=0,
            model_name=None,
            error_message=None,
        )
    return RagPageStatusOut(
        page_id=s.page_id,
        status=s.status,
        indexed_version=s.indexed_version,
        chunk_count=s.chunk_count,
        model_name=s.model_name,
        error_message=s.error_message,
    )

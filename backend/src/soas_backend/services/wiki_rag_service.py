"""Wiki RAG service: chunking, embedding, indexing, and semantic retrieval.

The retrieval path computes cosine similarity in Python over JSONB-stored vectors.
This is acceptable for the typical SOAS deployment (dozens to a few thousand chunks).
The migration to pgvector is intentionally well-defined: replace the JSONB column with
`vector(dim)` and replace `_cosine_topk` with an SQL `<#>` operator query — the rest of
the service is shape-stable.
"""

import asyncio
import hashlib
import logging
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

import httpx
import numpy as np
from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from soas_backend.models.wiki import WikiPage
from soas_backend.models.wiki_embedding import WikiEmbedding, WikiEmbeddingStatus

logger = logging.getLogger(__name__)

EMBEDDING_SERVICE_URL = os.environ.get("EMBEDDING_SERVICE_URL", "http://embeddings:8200")
EMBEDDING_TIMEOUT_S = float(os.environ.get("EMBEDDING_TIMEOUT_S", "60"))
EMBEDDING_BATCH_SIZE = int(os.environ.get("EMBEDDING_BATCH_SIZE", "32"))

# Conservative chunk size for MiniLM (max_seq_length 256 tokens ≈ 1000 chars).
# Overlap helps queries that straddle chunk boundaries; a 128-char overlap is small
# enough that index size doesn't bloat materially but big enough to catch most cases.
CHUNK_TARGET_CHARS = int(os.environ.get("WIKI_CHUNK_TARGET_CHARS", "900"))
CHUNK_OVERLAP_CHARS = int(os.environ.get("WIKI_CHUNK_OVERLAP_CHARS", "150"))

# Strip common HTML tags before chunking. The wiki stores HTML so leaving tags inside
# embeddings dilutes the signal with markup noise.
_TAG_PATTERN = re.compile(r"<[^>]+>")
_WHITESPACE_PATTERN = re.compile(r"\s+")


def _strip_html(text: str) -> str:
    return _WHITESPACE_PATTERN.sub(" ", _TAG_PATTERN.sub(" ", text)).strip()


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _chunk_text(text: str) -> list[str]:
    """Greedy chunking on paragraph/sentence boundaries with a target size + overlap.

    The algorithm prefers splitting on paragraph boundaries; when a paragraph is bigger
    than the target it falls back to sentence boundaries; when a sentence is bigger,
    it hard-splits at the target. The overlap region is taken from the tail of the
    previous chunk to maintain context across boundaries.
    """
    text = text.strip()
    if not text:
        return []

    # First-pass: paragraphs
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    if not paragraphs:
        paragraphs = [text]

    chunks: list[str] = []
    current = ""

    def flush():
        nonlocal current
        if current.strip():
            chunks.append(current.strip())
        current = ""

    for para in paragraphs:
        # Hard-split paragraphs that overflow on their own.
        if len(para) > CHUNK_TARGET_CHARS:
            sentences = re.split(r"(?<=[.!?])\s+", para)
            for sent in sentences:
                if len(sent) > CHUNK_TARGET_CHARS:
                    # Last-resort hard split.
                    for i in range(0, len(sent), CHUNK_TARGET_CHARS):
                        piece = sent[i : i + CHUNK_TARGET_CHARS]
                        if len(current) + len(piece) + 1 > CHUNK_TARGET_CHARS and current:
                            flush()
                        current = (current + " " + piece).strip() if current else piece
                else:
                    if len(current) + len(sent) + 1 > CHUNK_TARGET_CHARS and current:
                        flush()
                    current = (current + " " + sent).strip() if current else sent
        else:
            if len(current) + len(para) + 2 > CHUNK_TARGET_CHARS and current:
                flush()
            current = (current + "\n\n" + para).strip() if current else para

    flush()

    # Inject overlap.
    if CHUNK_OVERLAP_CHARS > 0 and len(chunks) > 1:
        with_overlap: list[str] = [chunks[0]]
        for i in range(1, len(chunks)):
            tail = chunks[i - 1][-CHUNK_OVERLAP_CHARS:]
            with_overlap.append((tail + " " + chunks[i]).strip())
        chunks = with_overlap

    return chunks


@dataclass
class RagSearchHit:
    page_id: UUID
    page_title: str
    page_slug: str
    chunk_index: int
    chunk_text: str
    score: float


class EmbeddingClient:
    """Thin async client over the local embedding sidecar."""

    def __init__(self, base_url: str = EMBEDDING_SERVICE_URL, timeout_s: float = EMBEDDING_TIMEOUT_S):
        self.base_url = base_url.rstrip("/")
        self.timeout_s = timeout_s

    async def health(self) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=self.timeout_s) as client:
            r = await client.get(f"{self.base_url}/health")
            r.raise_for_status()
            return r.json()

    async def info(self) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=self.timeout_s) as client:
            r = await client.get(f"{self.base_url}/info")
            r.raise_for_status()
            return r.json()

    async def embed(self, texts: list[str]) -> tuple[list[list[float]], str, int]:
        """Embed a batch. Returns (embeddings, model_name, dim)."""
        if not texts:
            return [], "", 0
        async with httpx.AsyncClient(timeout=self.timeout_s) as client:
            r = await client.post(
                f"{self.base_url}/embed",
                json={"texts": texts, "normalize": True},
            )
            r.raise_for_status()
            data = r.json()
            return data["embeddings"], data["model"], data["dim"]


class WikiRagService:
    def __init__(self, db: AsyncSession, client: EmbeddingClient | None = None):
        self.db = db
        self.client = client or EmbeddingClient()

    # ─── Status ───

    async def get_status(self, page_id: UUID) -> WikiEmbeddingStatus | None:
        result = await self.db.execute(
            select(WikiEmbeddingStatus).where(WikiEmbeddingStatus.page_id == page_id)
        )
        return result.scalar_one_or_none()

    async def overall_status(self) -> dict[str, Any]:
        total = await self.db.execute(select(func.count()).select_from(WikiPage))
        indexed = await self.db.execute(
            select(func.count()).select_from(WikiEmbeddingStatus).where(
                WikiEmbeddingStatus.status == "indexed"
            )
        )
        chunks = await self.db.execute(select(func.count()).select_from(WikiEmbedding))
        failed = await self.db.execute(
            select(func.count()).select_from(WikiEmbeddingStatus).where(
                WikiEmbeddingStatus.status == "failed"
            )
        )
        try:
            health = await self.client.health()
        except Exception as e:
            health = {"status": "unreachable", "error": str(e)}
        return {
            "total_pages": int(total.scalar() or 0),
            "indexed_pages": int(indexed.scalar() or 0),
            "failed_pages": int(failed.scalar() or 0),
            "total_chunks": int(chunks.scalar() or 0),
            "embedding_service": health,
        }

    # ─── Indexing ───

    async def _set_status(
        self,
        page_id: UUID,
        status: str,
        *,
        error: str | None = None,
        version: int | None = None,
        model: str | None = None,
        chunk_count: int | None = None,
    ) -> None:
        existing = await self.get_status(page_id)
        if existing is None:
            self.db.add(
                WikiEmbeddingStatus(
                    page_id=page_id,
                    status=status,
                    error_message=error,
                    indexed_version=version,
                    indexed_at=datetime.now(timezone.utc) if status == "indexed" else None,
                    model_name=model,
                    chunk_count=chunk_count or 0,
                )
            )
        else:
            existing.status = status
            existing.error_message = error
            if version is not None:
                existing.indexed_version = version
            if status == "indexed":
                existing.indexed_at = datetime.now(timezone.utc)
            if model is not None:
                existing.model_name = model
            if chunk_count is not None:
                existing.chunk_count = chunk_count
        await self.db.flush()

    async def index_page(self, page_id: UUID) -> dict[str, Any]:
        """(Re-)index a single page. Idempotent and chunk-incremental.

        Returns a small summary dict for callers/audit. Raises on hard failures so
        Celery can retry; for "page deleted between enqueue and run", we simply prune
        any leftover embeddings and return a noop summary.
        """
        result = await self.db.execute(select(WikiPage).where(WikiPage.id == page_id))
        page = result.scalar_one_or_none()

        if page is None:
            await self.db.execute(delete(WikiEmbedding).where(WikiEmbedding.page_id == page_id))
            await self.db.execute(
                delete(WikiEmbeddingStatus).where(WikiEmbeddingStatus.page_id == page_id)
            )
            await self.db.flush()
            return {"page_id": str(page_id), "status": "deleted", "chunks": 0}

        # If the page is empty, prune embeddings and mark indexed-but-empty.
        cleaned = _strip_html((page.content or "").strip())
        if not cleaned:
            await self.db.execute(delete(WikiEmbedding).where(WikiEmbedding.page_id == page_id))
            await self._set_status(
                page_id,
                "indexed",
                version=page.version,
                chunk_count=0,
                model=None,
            )
            return {"page_id": str(page_id), "status": "empty", "chunks": 0}

        # Always include the title in chunk text — it's a strong relevance signal.
        title_prefix = f"{page.title}\n\n"
        full_text = title_prefix + cleaned

        try:
            await self._set_status(page_id, "indexing", version=page.version)
            chunks = _chunk_text(full_text)
            if not chunks:
                chunks = [full_text]

            # Determine which chunks have changed vs. what's already indexed. We only
            # re-embed chunks whose hash differs (or are new). This keeps re-index of
            # large pages fast when only a paragraph changed.
            existing_q = await self.db.execute(
                select(WikiEmbedding.chunk_index, WikiEmbedding.chunk_hash)
                .where(WikiEmbedding.page_id == page_id)
            )
            existing_hashes: dict[int, str] = {row[0]: row[1] for row in existing_q.all()}

            to_embed: list[tuple[int, str, str]] = []  # (chunk_index, text, hash)
            keep_indices: set[int] = set()
            for idx, chunk in enumerate(chunks):
                h = _hash(chunk)
                if existing_hashes.get(idx) == h:
                    keep_indices.add(idx)
                else:
                    to_embed.append((idx, chunk, h))

            # Drop any chunks beyond the new chunk count, plus any whose hash changed
            # (we'll re-insert them fresh below).
            old_indices = set(existing_hashes.keys())
            stale_indices = (old_indices - keep_indices) | (old_indices - set(range(len(chunks))))
            if stale_indices:
                await self.db.execute(
                    delete(WikiEmbedding).where(
                        WikiEmbedding.page_id == page_id,
                        WikiEmbedding.chunk_index.in_(list(stale_indices)),
                    )
                )

            # Embed in batches.
            if to_embed:
                model_name = ""
                model_dim = 0
                for batch_start in range(0, len(to_embed), EMBEDDING_BATCH_SIZE):
                    batch = to_embed[batch_start : batch_start + EMBEDDING_BATCH_SIZE]
                    texts = [t for _, t, _ in batch]
                    embeddings, model_name, model_dim = await self.client.embed(texts)
                    for (idx, text, h), vec in zip(batch, embeddings, strict=True):
                        self.db.add(
                            WikiEmbedding(
                                page_id=page_id,
                                chunk_index=idx,
                                chunk_text=text,
                                chunk_hash=h,
                                token_count=len(text.split()),
                                embedding=vec,
                                model_name=model_name,
                                model_dimension=model_dim,
                                page_version=page.version,
                            )
                        )
                    await self.db.flush()
                model_used = model_name
            else:
                # Nothing to embed; pull the model name from any existing chunk for status.
                row = await self.db.execute(
                    select(WikiEmbedding.model_name).where(WikiEmbedding.page_id == page_id).limit(1)
                )
                model_used = row.scalar() or None

            await self._set_status(
                page_id,
                "indexed",
                version=page.version,
                model=model_used,
                chunk_count=len(chunks),
            )
            return {
                "page_id": str(page_id),
                "status": "indexed",
                "chunks": len(chunks),
                "embedded_now": len(to_embed),
                "skipped_unchanged": len(keep_indices),
            }
        except Exception as e:
            logger.exception("Failed to index wiki page %s", page_id)
            await self._set_status(page_id, "failed", error=str(e)[:500], version=page.version)
            raise

    async def reindex_all(self) -> dict[str, Any]:
        """Mark every page as pending and re-index sequentially.

        Sequential because most deployments will have a single embedding sidecar instance
        and the model encoder is single-threaded by default; concurrent batches contend
        for the same encoder and don't speed things up. For very large wikis a parallel
        path could be added, but it's intentionally not the default.
        """
        ids_q = await self.db.execute(select(WikiPage.id))
        ids = [r[0] for r in ids_q.all()]
        results: list[dict[str, Any]] = []
        for pid in ids:
            try:
                results.append(await self.index_page(pid))
            except Exception as e:
                results.append({"page_id": str(pid), "status": "failed", "error": str(e)})
        ok = sum(1 for r in results if r.get("status") == "indexed")
        return {"total": len(ids), "succeeded": ok, "failed": len(ids) - ok, "details": results}

    async def delete_page_embeddings(self, page_id: UUID) -> None:
        await self.db.execute(delete(WikiEmbedding).where(WikiEmbedding.page_id == page_id))
        await self.db.execute(
            delete(WikiEmbeddingStatus).where(WikiEmbeddingStatus.page_id == page_id)
        )
        await self.db.flush()

    # ─── Retrieval ───

    async def search(
        self,
        query: str,
        top_k: int = 5,
        min_score: float = 0.0,
        team_ids: list[UUID] | None = None,
    ) -> list[RagSearchHit]:
        """Embed the query and return the top-k most similar wiki chunks.

        team_ids: when provided, restrict matches to pages within the given teams (plus
        team-less/global pages). Pass None to search everywhere (admin behaviour).
        """
        if not query.strip():
            return []

        embeddings, _model, _dim = await self.client.embed([query])
        if not embeddings:
            return []
        q_vec = np.asarray(embeddings[0], dtype=np.float32)
        # /embed normalizes by default so q_vec is unit-length, but be defensive.
        norm = float(np.linalg.norm(q_vec))
        if norm > 0:
            q_vec = q_vec / norm

        # Pull candidate chunks from DB. Team scoping happens here at the SQL layer
        # rather than after the cosine pass to keep the working set bounded.
        stmt = (
            select(WikiEmbedding, WikiPage)
            .join(WikiPage, WikiPage.id == WikiEmbedding.page_id)
        )
        if team_ids is not None:
            from sqlalchemy import or_
            stmt = stmt.where(or_(WikiPage.team_id.in_(team_ids), WikiPage.team_id.is_(None)))
        result = await self.db.execute(stmt.options(selectinload(WikiPage.creator)))
        rows = result.all()
        if not rows:
            return []

        # Build a single matrix and do one numpy dot product. For thousands of chunks
        # this is microseconds — far cheaper than per-row Python loops.
        vectors = np.array([r[0].embedding for r in rows], dtype=np.float32)
        # Re-normalize defensively in case some rows were inserted with a different
        # normalization setting.
        norms = np.linalg.norm(vectors, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        vectors = vectors / norms

        scores = vectors @ q_vec  # shape: (n_chunks,)

        # argpartition for top-k is O(n) instead of O(n log n) for full sort.
        if top_k >= len(scores):
            order = np.argsort(-scores)
        else:
            partial = np.argpartition(-scores, top_k)[:top_k]
            order = partial[np.argsort(-scores[partial])]

        hits: list[RagSearchHit] = []
        for i in order:
            score = float(scores[int(i)])
            if score < min_score:
                continue
            emb, page = rows[int(i)]
            hits.append(
                RagSearchHit(
                    page_id=page.id,
                    page_title=page.title,
                    page_slug=page.slug,
                    chunk_index=emb.chunk_index,
                    chunk_text=emb.chunk_text,
                    score=score,
                )
            )
        return hits


# ───────────────────────────────────────────────────────────────────────────
# Sync helpers for Celery workers — workers use psycopg2, not asyncpg, so the
# async service can't run there. We expose a tiny enqueue helper that's used
# by the wiki API to schedule re-indexing without blocking the request.
# ───────────────────────────────────────────────────────────────────────────


async def schedule_index(page_id: UUID) -> None:
    """Best-effort enqueue: schedule a Celery re-index task for a single page.

    Imported lazily because the API process doesn't have soas_workers installed,
    only Celery's broker connection. We use Celery's send_task by name.
    """
    try:
        from celery import Celery
        broker = os.environ.get("CELERY_BROKER_URL", "redis://redis:6379/0")
        backend = os.environ.get("CELERY_RESULT_BACKEND", "redis://redis:6379/1")
        # Lightweight Celery client used purely to enqueue tasks. Reuses the same
        # broker the worker pool listens on.
        c = Celery("soas_backend_proxy", broker=broker, backend=backend)
        c.send_task("soas.reindex_wiki_page", args=[str(page_id)], queue="celery")
    except Exception:
        # Running indexing inline is acceptable as a fallback in dev — surface failures
        # in logs but never block wiki writes on RAG infrastructure.
        logger.warning("Could not enqueue wiki reindex task", exc_info=True)


async def schedule_delete(page_id: UUID) -> None:
    try:
        from celery import Celery
        broker = os.environ.get("CELERY_BROKER_URL", "redis://redis:6379/0")
        backend = os.environ.get("CELERY_RESULT_BACKEND", "redis://redis:6379/1")
        c = Celery("soas_backend_proxy", broker=broker, backend=backend)
        c.send_task("soas.delete_wiki_embeddings", args=[str(page_id)], queue="celery")
    except Exception:
        logger.warning("Could not enqueue wiki embedding delete task", exc_info=True)


# Used by tests: synchronous awaitable to run an indexing pass without Celery.
async def index_inline(db: AsyncSession, page_id: UUID) -> dict[str, Any]:
    return await WikiRagService(db).index_page(page_id)


# Re-exported for convenience.
__all__ = [
    "WikiRagService",
    "EmbeddingClient",
    "RagSearchHit",
    "schedule_index",
    "schedule_delete",
    "index_inline",
]


# Keep imports tidy — silence unused-import warning for asyncio (kept for future use).
_ = asyncio

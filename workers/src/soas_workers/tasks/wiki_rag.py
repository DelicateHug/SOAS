"""Wiki RAG indexing tasks (sync, runs in Celery worker pool).

Mirrors the chunking + indexing logic in soas_backend.services.wiki_rag_service but uses
psycopg synchronously, since the worker pool isn't async-friendly. Embedding calls go to
the local embeddings sidecar over HTTP.

Why duplicate the chunking? Two reasons:
  1. The worker package shouldn't import from the backend package — they ship as separate
     containers and we don't want them coupled.
  2. The async vs sync DB difference makes naive code-sharing fragile.
The two algorithms must stay aligned; the chunking parameters live here as constants
identical to the backend's.
"""

import hashlib
import json
import logging
import os
import re
from datetime import datetime, timezone

import httpx
import psycopg
from psycopg.rows import dict_row

from soas_workers.celery_app import app
from soas_workers.config import config
from soas_workers.http_clients import internal_sync_client

logger = logging.getLogger(__name__)

EMBEDDING_SERVICE_URL = os.environ.get("EMBEDDING_SERVICE_URL", "https://embeddings:8200")
EMBEDDING_TIMEOUT_S = float(os.environ.get("EMBEDDING_TIMEOUT_S", "60"))
EMBEDDING_BATCH_SIZE = int(os.environ.get("EMBEDDING_BATCH_SIZE", "32"))
CHUNK_TARGET_CHARS = int(os.environ.get("WIKI_CHUNK_TARGET_CHARS", "900"))
CHUNK_OVERLAP_CHARS = int(os.environ.get("WIKI_CHUNK_OVERLAP_CHARS", "150"))

_TAG_PATTERN = re.compile(r"<[^>]+>")
_WHITESPACE_PATTERN = re.compile(r"\s+")


def _strip_html(text: str) -> str:
    return _WHITESPACE_PATTERN.sub(" ", _TAG_PATTERN.sub(" ", text)).strip()


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _chunk_text(text: str) -> list[str]:
    text = text.strip()
    if not text:
        return []
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
        if len(para) > CHUNK_TARGET_CHARS:
            sentences = re.split(r"(?<=[.!?])\s+", para)
            for sent in sentences:
                if len(sent) > CHUNK_TARGET_CHARS:
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

    if CHUNK_OVERLAP_CHARS > 0 and len(chunks) > 1:
        with_overlap = [chunks[0]]
        for i in range(1, len(chunks)):
            tail = chunks[i - 1][-CHUNK_OVERLAP_CHARS:]
            with_overlap.append((tail + " " + chunks[i]).strip())
        chunks = with_overlap
    return chunks


def _embed_batch(texts: list[str]) -> tuple[list[list[float]], str, int]:
    if not texts:
        return [], "", 0
    with internal_sync_client(timeout=EMBEDDING_TIMEOUT_S) as client:
        resp = client.post(
            f"{EMBEDDING_SERVICE_URL.rstrip('/')}/embed",
            json={"texts": texts, "normalize": True},
        )
        resp.raise_for_status()
        data = resp.json()
        return data["embeddings"], data["model"], data["dim"]


def _set_status(
    cur,
    page_id: str,
    *,
    status: str,
    error: str | None = None,
    version: int | None = None,
    model: str | None = None,
    chunk_count: int | None = None,
):
    indexed_at = datetime.now(timezone.utc) if status == "indexed" else None
    cur.execute(
        """
        INSERT INTO wiki_embedding_status
            (page_id, status, error_message, indexed_version, indexed_at, model_name, chunk_count)
        VALUES (%s::uuid, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (page_id) DO UPDATE SET
            status = EXCLUDED.status,
            error_message = EXCLUDED.error_message,
            indexed_version = COALESCE(EXCLUDED.indexed_version, wiki_embedding_status.indexed_version),
            indexed_at = COALESCE(EXCLUDED.indexed_at, wiki_embedding_status.indexed_at),
            model_name = COALESCE(EXCLUDED.model_name, wiki_embedding_status.model_name),
            chunk_count = COALESCE(EXCLUDED.chunk_count, wiki_embedding_status.chunk_count)
        """,
        (page_id, status, error, version, indexed_at, model, chunk_count or 0),
    )


@app.task(name="soas.reindex_wiki_page", bind=True, max_retries=3, default_retry_delay=15)
def reindex_wiki_page(self, page_id: str) -> dict:
    """Re-index a single wiki page. Idempotent and chunk-incremental.

    Retries on transient failures (embedding sidecar warming up, etc.) up to 3 times.
    """
    try:
        with psycopg.connect(config.DATABASE_URL, row_factory=dict_row) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id, title, content, version FROM wiki_pages WHERE id = %s::uuid",
                    (page_id,),
                )
                page = cur.fetchone()
                if page is None:
                    cur.execute("DELETE FROM wiki_embeddings WHERE page_id = %s::uuid", (page_id,))
                    cur.execute(
                        "DELETE FROM wiki_embedding_status WHERE page_id = %s::uuid",
                        (page_id,),
                    )
                    conn.commit()
                    return {"page_id": page_id, "status": "deleted"}

                cleaned = _strip_html(page["content"] or "")
                if not cleaned:
                    cur.execute("DELETE FROM wiki_embeddings WHERE page_id = %s::uuid", (page_id,))
                    _set_status(
                        cur, page_id, status="indexed", version=page["version"], chunk_count=0
                    )
                    conn.commit()
                    return {"page_id": page_id, "status": "empty"}

                full_text = f"{page['title']}\n\n{cleaned}"
                chunks = _chunk_text(full_text) or [full_text]

                # Build hash diff to skip unchanged chunks.
                cur.execute(
                    "SELECT chunk_index, chunk_hash FROM wiki_embeddings WHERE page_id = %s::uuid",
                    (page_id,),
                )
                existing_hashes = {row["chunk_index"]: row["chunk_hash"] for row in cur.fetchall()}

                to_embed: list[tuple[int, str, str]] = []
                keep_indices: set[int] = set()
                for idx, chunk in enumerate(chunks):
                    h = _hash(chunk)
                    if existing_hashes.get(idx) == h:
                        keep_indices.add(idx)
                    else:
                        to_embed.append((idx, chunk, h))

                old_indices = set(existing_hashes.keys())
                stale_indices = (old_indices - keep_indices) | (
                    old_indices - set(range(len(chunks)))
                )
                if stale_indices:
                    cur.execute(
                        "DELETE FROM wiki_embeddings WHERE page_id = %s::uuid AND chunk_index = ANY(%s)",
                        (page_id, list(stale_indices)),
                    )

                _set_status(cur, page_id, status="indexing", version=page["version"])
                conn.commit()

                model_used = None
                if to_embed:
                    for batch_start in range(0, len(to_embed), EMBEDDING_BATCH_SIZE):
                        batch = to_embed[batch_start : batch_start + EMBEDDING_BATCH_SIZE]
                        texts = [t for _, t, _ in batch]
                        embeddings, model_name, model_dim = _embed_batch(texts)
                        model_used = model_name
                        with conn.cursor() as bcur:
                            for (idx, text, h), vec in zip(batch, embeddings, strict=True):
                                bcur.execute(
                                    """
                                    INSERT INTO wiki_embeddings
                                        (page_id, chunk_index, chunk_text, chunk_hash,
                                         token_count, embedding, model_name, model_dimension,
                                         page_version)
                                    VALUES
                                        (%s::uuid, %s, %s, %s, %s, %s::jsonb, %s, %s, %s)
                                    ON CONFLICT (page_id, chunk_index) DO UPDATE SET
                                        chunk_text = EXCLUDED.chunk_text,
                                        chunk_hash = EXCLUDED.chunk_hash,
                                        token_count = EXCLUDED.token_count,
                                        embedding = EXCLUDED.embedding,
                                        model_name = EXCLUDED.model_name,
                                        model_dimension = EXCLUDED.model_dimension,
                                        page_version = EXCLUDED.page_version
                                    """,
                                    (
                                        page_id,
                                        idx,
                                        text,
                                        h,
                                        len(text.split()),
                                        json.dumps(vec),
                                        model_name,
                                        model_dim,
                                        page["version"],
                                    ),
                                )
                        conn.commit()
                else:
                    cur.execute(
                        "SELECT model_name FROM wiki_embeddings WHERE page_id = %s::uuid LIMIT 1",
                        (page_id,),
                    )
                    row = cur.fetchone()
                    model_used = row["model_name"] if row else None

                with conn.cursor() as scur:
                    _set_status(
                        scur,
                        page_id,
                        status="indexed",
                        version=page["version"],
                        model=model_used,
                        chunk_count=len(chunks),
                    )
                conn.commit()

                return {
                    "page_id": page_id,
                    "status": "indexed",
                    "chunks": len(chunks),
                    "embedded_now": len(to_embed),
                    "skipped_unchanged": len(keep_indices),
                }
    except httpx.HTTPError as e:
        # Embedding sidecar may still be loading the model on first start; retry.
        logger.warning("Embedding service error indexing page %s: %s", page_id, e)
        try:
            with psycopg.connect(config.DATABASE_URL) as conn:
                with conn.cursor() as cur:
                    _set_status(cur, page_id, status="failed", error=str(e)[:500])
                conn.commit()
        except Exception:
            pass
        raise self.retry(exc=e)
    except Exception as e:
        logger.exception("Failed to index wiki page %s", page_id)
        try:
            with psycopg.connect(config.DATABASE_URL) as conn:
                with conn.cursor() as cur:
                    _set_status(cur, page_id, status="failed", error=str(e)[:500])
                conn.commit()
        except Exception:
            pass
        raise


@app.task(name="soas.delete_wiki_embeddings")
def delete_wiki_embeddings(page_id: str) -> dict:
    """Drop all embeddings for a page (called when the page is deleted)."""
    with psycopg.connect(config.DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM wiki_embeddings WHERE page_id = %s::uuid", (page_id,))
            cur.execute(
                "DELETE FROM wiki_embedding_status WHERE page_id = %s::uuid", (page_id,)
            )
        conn.commit()
    return {"page_id": page_id, "status": "deleted"}


@app.task(name="soas.reindex_wiki_all")
def reindex_wiki_all() -> dict:
    """Mark every wiki page for re-indexing. Schedules per-page tasks."""
    with psycopg.connect(config.DATABASE_URL, row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM wiki_pages")
            ids = [str(row["id"]) for row in cur.fetchall()]

    for pid in ids:
        reindex_wiki_page.apply_async(args=[pid], queue="celery")

    return {"scheduled": len(ids)}

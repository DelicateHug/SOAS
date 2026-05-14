"""Local embedding service using sentence-transformers.

Exposes:
    POST /embed         { "texts": [str, ...], "normalize": bool }  →  { embeddings, model, dim }
    GET  /health        liveness + model info
    GET  /info          model metadata
    POST /similarity    { "a": [float], "b": [float] }              →  { cosine }

Designed for low-latency local use; runs on CPU by default. No external network calls
once the model image is built. Authentication is not required because the service binds
only to the internal Docker network — exposing it externally is a deployment-time choice.
"""

import logging
import os
from contextlib import asynccontextmanager
from time import perf_counter
from typing import Any

import numpy as np
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from sentence_transformers import SentenceTransformer

logger = logging.getLogger("embeddings")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

MODEL_NAME = os.environ.get("SENTENCE_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
MAX_BATCH = int(os.environ.get("EMBEDDING_MAX_BATCH", "128"))
MAX_TEXT_CHARS = int(os.environ.get("EMBEDDING_MAX_TEXT_CHARS", "8000"))

# Module-level state, populated in lifespan.
_state: dict[str, Any] = {"model": None, "dim": 0}


@asynccontextmanager
async def lifespan(_app: FastAPI):
    logger.info("Loading sentence-transformers model: %s", MODEL_NAME)
    t0 = perf_counter()
    model = SentenceTransformer(MODEL_NAME, cache_folder="/models")
    dim = int(model.get_sentence_embedding_dimension())
    _state["model"] = model
    _state["dim"] = dim
    logger.info("Model loaded in %.2fs (dim=%d)", perf_counter() - t0, dim)
    yield
    _state["model"] = None


app = FastAPI(title="SOAS Embeddings", lifespan=lifespan)


class EmbedRequest(BaseModel):
    texts: list[str] = Field(..., min_length=1, max_length=MAX_BATCH)
    normalize: bool = True


class EmbedResponse(BaseModel):
    embeddings: list[list[float]]
    model: str
    dim: int
    elapsed_ms: float


class SimilarityRequest(BaseModel):
    a: list[float]
    b: list[float]


@app.get("/health")
async def health() -> dict:
    ready = _state["model"] is not None
    return {
        "status": "ok" if ready else "loading",
        "model": MODEL_NAME,
        "dim": _state["dim"],
        "max_batch": MAX_BATCH,
    }


@app.get("/info")
async def info() -> dict:
    return {
        "model": MODEL_NAME,
        "dim": _state["dim"],
        "max_batch": MAX_BATCH,
        "max_text_chars": MAX_TEXT_CHARS,
    }


@app.post("/embed", response_model=EmbedResponse)
async def embed(req: EmbedRequest) -> EmbedResponse:
    model = _state["model"]
    if model is None:
        raise HTTPException(status_code=503, detail="Model not loaded yet")

    # Cap text length to avoid pathological inputs hogging the encoder. The model's own
    # tokenizer truncates to its max_seq_length anyway, but guarding at the edge keeps
    # OOMs and DoS surface small.
    cleaned = [t[:MAX_TEXT_CHARS] for t in req.texts]

    t0 = perf_counter()
    vectors = model.encode(
        cleaned,
        normalize_embeddings=req.normalize,
        convert_to_numpy=True,
        show_progress_bar=False,
    )
    elapsed_ms = (perf_counter() - t0) * 1000.0

    return EmbedResponse(
        embeddings=vectors.tolist(),
        model=MODEL_NAME,
        dim=int(vectors.shape[1]),
        elapsed_ms=round(elapsed_ms, 2),
    )


@app.post("/similarity")
async def similarity(req: SimilarityRequest) -> dict:
    if len(req.a) != len(req.b):
        raise HTTPException(status_code=400, detail="Vectors must have the same dimension")
    a = np.array(req.a, dtype=np.float32)
    b = np.array(req.b, dtype=np.float32)
    denom = float(np.linalg.norm(a) * np.linalg.norm(b))
    if denom == 0.0:
        return {"cosine": 0.0}
    return {"cosine": float(np.dot(a, b) / denom)}

"""FastAPI application factory."""

import asyncio
import logging
import socket
import uuid as _uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone

import redis.asyncio as aioredis
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from soas_backend.api.v1.collaboration import collab_ws_router
from soas_backend.api.v1.executions import ws_router
from soas_backend.api.v1.monitoring_ws import monitoring_ws_router
from soas_backend.api.v1.wiki_collaboration import wiki_collab_ws_router
from soas_backend.api.v1.router import v1_router
from soas_backend.config import settings
from soas_backend.middleware.monitoring import MonitoringMiddleware
from soas_backend.middleware.production_guard import ProductionGuardMiddleware
from soas_backend.middleware.request_id import RequestIDMiddleware
from soas_backend.middleware.request_log import cleanup_if_healthy
from soas_backend.services.quorum_service import QuorumService

logger = logging.getLogger(__name__)

REQUEST_LOG_CLEANUP_INTERVAL = 300  # 5 minutes

INSTANCE_ID = str(_uuid.uuid4())


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: register quorum instance
    from soas_backend.api.deps import get_redis_pool
    r = await get_redis_pool()
    quorum_svc = QuorumService(r)
    hostname = socket.gethostname()
    await quorum_svc.register_instance(INSTANCE_ID, hostname)

    # Background heartbeat task
    async def _heartbeat_loop():
        # Resolve a stable agenttype_id once at startup (matches the worker
        # heartbeat semantics — restarts re-use the same id).
        from soas_backend.services.agent_registry_service import (
            record_agent_sample,
            resolve_agenttype_id,
        )
        import os, time
        role = os.environ.get("SOAS_AGENT_ROLE", "backend")
        agenttype_id = resolve_agenttype_id(role)
        version = os.environ.get("SOAS_VERSION", "0.1.0")
        boot_ts = time.time()

        while True:
            await asyncio.sleep(settings.monitoring_quorum_heartbeat_interval)
            try:
                await quorum_svc.heartbeat(INSTANCE_ID)
            except Exception:
                logger.warning("Quorum heartbeat failed", exc_info=True)
            try:
                await record_agent_sample(
                    agenttype_id=agenttype_id,
                    role=role,
                    version=version,
                    instance_id=f"{hostname}:{INSTANCE_ID}",
                    uptime_seconds=int(time.time() - boot_ts),
                )
            except Exception:
                logger.warning("Agent metric sample failed", exc_info=True)

    task = asyncio.create_task(_heartbeat_loop())

    # Background request log cleanup (clears buffers when no errors)
    async def _request_log_cleanup_loop():
        while True:
            await asyncio.sleep(REQUEST_LOG_CLEANUP_INTERVAL)
            try:
                cleared = cleanup_if_healthy()
                if cleared:
                    logger.debug("Request log buffers cleared (no errors)")
            except Exception:
                logger.warning("Request log cleanup failed", exc_info=True)

    log_cleanup_task = asyncio.create_task(_request_log_cleanup_loop())

    # Seed default data (idempotent, non-fatal)
    try:
        from soas_backend.seed import seed_defaults
        await seed_defaults()
    except Exception:
        logger.warning("Seed data failed (non-fatal)", exc_info=True)

    yield

    # Shutdown: deregister and cleanup
    task.cancel()
    log_cleanup_task.cancel()
    for t in (task, log_cleanup_task):
        try:
            await t
        except asyncio.CancelledError:
            pass
    await quorum_svc.deregister_instance(INSTANCE_ID)
    await r.aclose()


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
        lifespan=lifespan,
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Production mode guard (blocks writes on entity APIs in production mode)
    app.add_middleware(ProductionGuardMiddleware)

    # Request ID middleware (attaches UUID to every request for tracing)
    app.add_middleware(RequestIDMiddleware)

    # Monitoring middleware (tracks request count, errors, response time)
    app.add_middleware(MonitoringMiddleware)

    # Routes
    app.include_router(v1_router)
    app.include_router(ws_router)  # WebSocket routes
    app.include_router(collab_ws_router)  # Collaboration WebSocket
    app.include_router(monitoring_ws_router)  # Monitoring WebSocket
    app.include_router(wiki_collab_ws_router)  # Wiki collaboration WebSocket

    @app.get("/api/health")
    async def health():
        return {
            "status": "healthy",
            "version": settings.app_version,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "instance_id": INSTANCE_ID,
        }

    return app


app = create_app()

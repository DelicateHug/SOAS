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
from soas_backend.api.v1.router import v1_router
from soas_backend.config import settings
from soas_backend.middleware.monitoring import MonitoringMiddleware
from soas_backend.services.quorum_service import QuorumService

logger = logging.getLogger(__name__)

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
        while True:
            await asyncio.sleep(settings.monitoring_quorum_heartbeat_interval)
            try:
                await quorum_svc.heartbeat(INSTANCE_ID)
            except Exception:
                logger.warning("Quorum heartbeat failed", exc_info=True)

    task = asyncio.create_task(_heartbeat_loop())

    yield

    # Shutdown: deregister and cleanup
    task.cancel()
    try:
        await task
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

    # Monitoring middleware (tracks request count, errors, response time)
    app.add_middleware(MonitoringMiddleware)

    # Routes
    app.include_router(v1_router)
    app.include_router(ws_router)  # WebSocket routes
    app.include_router(collab_ws_router)  # Collaboration WebSocket
    app.include_router(monitoring_ws_router)  # Monitoring WebSocket

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

"""Real-time monitoring WebSocket for dashboard updates."""

import asyncio
import json
import logging

import redis.asyncio as aioredis
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from soas_backend.auth.jwt import decode_access_token
from soas_backend.config import settings

logger = logging.getLogger(__name__)

monitoring_ws_router = APIRouter()


@monitoring_ws_router.websocket("/api/v1/ws/monitoring")
async def monitoring_ws(websocket: WebSocket):
    """Real-time monitoring updates via WebSocket.

    Subscribes to Redis pub/sub channels for alerts and health updates,
    forwarding them to connected monitoring dashboard clients.

    Authentication: JWT token via query parameter ?token=<jwt>
    Required permission: monitoring:read
    """
    await websocket.accept()

    # Authenticate via query param
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=4001, reason="Missing token")
        return

    payload = decode_access_token(token)
    if not payload:
        await websocket.close(code=4001, reason="Invalid token")
        return

    permissions = payload.get("permissions", [])
    if "monitoring:read" not in permissions:
        await websocket.close(code=4003, reason="Insufficient permissions")
        return

    r = None
    pubsub = None
    try:
        from soas_backend.api.deps import get_redis_pool
        r = await get_redis_pool()
        pubsub = r.pubsub()
        await pubsub.subscribe("monitoring:alerts:channel", "monitoring:health:channel")

        while True:
            try:
                message = await asyncio.wait_for(
                    pubsub.get_message(ignore_subscribe_messages=True),
                    timeout=1.0,
                )
            except asyncio.TimeoutError:
                # Send heartbeat ping to detect disconnects
                try:
                    await websocket.send_json({"type": "heartbeat"})
                except Exception:
                    break
                continue

            if message and message["type"] == "message":
                data = message["data"]
                if isinstance(data, bytes):
                    data = data.decode("utf-8")
                await websocket.send_text(data)

    except WebSocketDisconnect:
        pass
    except Exception:
        logger.warning("Monitoring WebSocket error", exc_info=True)
        try:
            await websocket.close(code=1011)
        except Exception:
            pass
    finally:
        if pubsub:
            try:
                await pubsub.unsubscribe()
                await pubsub.aclose()
            except Exception:
                pass
        if r:
            try:
                await r.aclose()
            except Exception:
                pass

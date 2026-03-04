"""Real-time collaboration WebSocket for graph co-editing."""

import asyncio
import hashlib
import json
from datetime import datetime, timezone

import redis.asyncio as aioredis
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from soas_backend.auth.jwt import decode_access_token
from soas_backend.config import settings
from soas_backend.database import async_session

collab_ws_router = APIRouter()

# Deterministic colour palette for collaborator cursors
_COLORS = [
    "#3b82f6",  # blue
    "#ef4444",  # red
    "#10b981",  # emerald
    "#f59e0b",  # amber
    "#8b5cf6",  # violet
    "#ec4899",  # pink
    "#06b6d4",  # cyan
    "#f97316",  # orange
]


def _assign_color(user_id: str) -> str:
    idx = int(hashlib.md5(user_id.encode()).hexdigest(), 16) % len(_COLORS)
    return _COLORS[idx]


# ---------------------------------------------------------------------------
# DB helpers for lock persistence
# ---------------------------------------------------------------------------

async def _set_lock_in_db(automation_id: str, user_id: str) -> None:
    from sqlalchemy import update
    from soas_backend.models.automation import Automation
    from uuid import UUID

    async with async_session() as session:
        await session.execute(
            update(Automation)
            .where(Automation.id == UUID(automation_id))
            .values(locked_by=UUID(user_id), locked_at=datetime.now(timezone.utc))
        )
        await session.commit()


async def _release_lock_in_db(automation_id: str) -> None:
    from sqlalchemy import update
    from soas_backend.models.automation import Automation
    from uuid import UUID

    async with async_session() as session:
        await session.execute(
            update(Automation)
            .where(Automation.id == UUID(automation_id))
            .values(locked_by=None, locked_at=None)
        )
        await session.commit()


# ---------------------------------------------------------------------------
# Lock request handlers
# ---------------------------------------------------------------------------

async def _handle_lock_request(
    ws: WebSocket,
    r: aioredis.Redis,
    automation_id: str,
    user_id: str,
    can_edit: bool,
    channel: str,
    display_name: str,
) -> None:
    lock_key = f"collab:{automation_id}:lock"

    if not can_edit:
        await ws.send_text(json.dumps({"type": "error", "message": "No edit permission"}))
        return

    lock_info = json.dumps({
        "user_id": user_id,
        "display_name": display_name,
        "locked_at": datetime.now(timezone.utc).isoformat(),
    })
    acquired = await r.set(lock_key, lock_info, nx=True, ex=600)

    if acquired:
        await _set_lock_in_db(automation_id, user_id)
        await r.publish(channel, json.dumps({
            "type": "lock_acquired",
            "user_id": user_id,
            "display_name": display_name,
        }))
    else:
        existing_raw = await r.get(lock_key)
        existing = json.loads(existing_raw) if existing_raw else {}
        await ws.send_text(json.dumps({
            "type": "lock_denied",
            "locked_by": existing.get("user_id"),
            "display_name": existing.get("display_name"),
        }))


async def _handle_unlock_request(
    ws: WebSocket,
    r: aioredis.Redis,
    automation_id: str,
    user_id: str,
    channel: str,
) -> None:
    lock_key = f"collab:{automation_id}:lock"
    existing_raw = await r.get(lock_key)
    if not existing_raw:
        return

    existing = json.loads(existing_raw)
    if existing.get("user_id") != user_id:
        await ws.send_text(json.dumps({"type": "error", "message": "You do not hold the lock"}))
        return

    await r.delete(lock_key)
    await _release_lock_in_db(automation_id)
    await r.publish(channel, json.dumps({
        "type": "lock_released",
        "user_id": user_id,
    }))


# ---------------------------------------------------------------------------
# Bidirectional message tasks
# ---------------------------------------------------------------------------

async def _read_from_client(
    ws: WebSocket,
    r: aioredis.Redis,
    channel: str,
    user_id: str,
    automation_id: str,
    can_edit: bool,
    display_name: str,
) -> None:
    """Read messages from the WebSocket client, validate, and publish to Redis."""
    presence_key = f"collab:{automation_id}:presence"
    lock_key = f"collab:{automation_id}:lock"

    while True:
        raw = await ws.receive_text()
        msg = json.loads(raw)
        msg_type = msg.get("type")

        if msg_type == "heartbeat":
            await r.expire(presence_key, 3600)
            # Refresh lock if held by this user
            lock_raw = await r.get(lock_key)
            if lock_raw:
                try:
                    lock_data = json.loads(lock_raw)
                    if lock_data.get("user_id") == user_id:
                        await r.expire(lock_key, 600)
                except (json.JSONDecodeError, KeyError):
                    pass
            continue

        if msg_type == "cursor_move":
            await r.publish(channel, json.dumps({
                "type": "cursor_move",
                "user_id": user_id,
                "x": msg.get("x", 0),
                "y": msg.get("y", 0),
            }))
            continue

        if msg_type == "lock_request":
            await _handle_lock_request(ws, r, automation_id, user_id, can_edit, channel, display_name)
            continue

        if msg_type == "unlock_request":
            await _handle_unlock_request(ws, r, automation_id, user_id, channel)
            continue

        if msg_type == "issues_changed":
            msg["user_id"] = user_id
            await r.publish(channel, json.dumps(msg))
            continue

        if msg_type == "graph_op":
            # Permission check: must have edit capability
            if not can_edit:
                await ws.send_text(json.dumps({"type": "error", "message": "Read-only"}))
                continue

            # Lock check: if locked by someone else, reject
            lock_raw = await r.get(lock_key)
            if lock_raw:
                lock_info = json.loads(lock_raw)
                if lock_info.get("user_id") != user_id:
                    await ws.send_text(json.dumps({
                        "type": "error",
                        "message": "Graph is locked by another user",
                    }))
                    continue

            # Stamp and broadcast
            msg["user_id"] = user_id
            msg["timestamp"] = datetime.now(timezone.utc).isoformat()
            await r.publish(channel, json.dumps(msg))
            continue


async def _read_from_redis(
    ws: WebSocket,
    pubsub: aioredis.client.PubSub,
    my_user_id: str,
) -> None:
    """Read messages from Redis pubsub and forward to this WebSocket client."""
    async for message in pubsub.listen():
        if message["type"] != "message":
            continue

        data = message["data"]
        if isinstance(data, bytes):
            data = data.decode("utf-8")

        # Don't echo a user's own graph_ops or cursor_moves back
        try:
            parsed = json.loads(data)
            if parsed.get("user_id") == my_user_id and parsed.get("type") in (
                "graph_op",
                "cursor_move",
                "issues_changed",
            ):
                continue
        except (json.JSONDecodeError, KeyError):
            pass

        await ws.send_text(data)


# ---------------------------------------------------------------------------
# Main WebSocket endpoint
# ---------------------------------------------------------------------------

@collab_ws_router.websocket("/api/v1/ws/collaboration/{automation_id}")
async def collaboration_ws(websocket: WebSocket, automation_id: str):
    """Bidirectional WebSocket for real-time graph collaboration.

    Clients connect with a JWT token as a query parameter. The server
    subscribes to a Redis pub/sub channel per automation and relays
    graph operations, cursor positions, and lock state between all
    connected collaborators.
    """
    await websocket.accept()

    # --- Authenticate ---
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=4001, reason="Missing token")
        return

    payload = decode_access_token(token)
    if not payload:
        await websocket.close(code=4001, reason="Invalid token")
        return

    user_id: str = payload["sub"]
    username: str = payload.get("username", "unknown")
    display_name: str = payload.get("display_name", username)
    permissions: list[str] = payload.get("permissions", [])
    can_edit = "automation:update" in permissions

    color = _assign_color(user_id)

    # --- Redis setup ---
    # Use the shared pool for commands (get/set/publish) and a dedicated
    # connection for pub/sub so we don't exhaust the pool's connections.
    r: aioredis.Redis | None = None
    pubsub_redis: aioredis.Redis | None = None
    pubsub: aioredis.client.PubSub | None = None

    try:
        from soas_backend.api.deps import get_redis_pool
        r = await get_redis_pool()
        # Dedicated connection for pub/sub (not from the shared pool)
        pubsub_redis = aioredis.from_url(settings.redis_url, decode_responses=False)
        pubsub = pubsub_redis.pubsub()
        channel = f"collab:{automation_id}"
        presence_key = f"collab:{automation_id}:presence"
        lock_key = f"collab:{automation_id}:lock"

        # Track WebSocket connection for monitoring
        await r.incr("monitoring:ws:active_count")

        # Register in presence hash
        await r.hset(presence_key, user_id, json.dumps({
            "user_id": user_id,
            "username": username,
            "display_name": display_name,
            "color": color,
            "can_edit": can_edit,
        }))
        await r.expire(presence_key, 3600)

        # Subscribe to channel
        await pubsub.subscribe(channel)

        # Send initial session state
        presence_raw = await r.hgetall(presence_key)
        collaborators = []
        for v in presence_raw.values():
            val = v.decode("utf-8") if isinstance(v, bytes) else v
            collaborators.append(json.loads(val))

        lock_raw = await r.get(lock_key)
        lock_data = json.loads(lock_raw.decode("utf-8") if isinstance(lock_raw, bytes) else lock_raw) if lock_raw else None

        await websocket.send_text(json.dumps({
            "type": "session_state",
            "collaborators": collaborators,
            "lock": lock_data,
        }))

        # Announce join
        await r.publish(channel, json.dumps({
            "type": "user_joined",
            "user_id": user_id,
            "username": username,
            "display_name": display_name,
            "color": color,
        }))

        # Bidirectional message loop
        await asyncio.gather(
            _read_from_client(websocket, r, channel, user_id, automation_id, can_edit, display_name),
            _read_from_redis(websocket, pubsub, user_id),
        )

    except WebSocketDisconnect:
        pass
    except Exception:
        try:
            await websocket.close(code=1011)
        except Exception:
            pass
    finally:
        # --- Cleanup ---
        # Decrement WebSocket connection counter for monitoring
        if r:
            try:
                await r.decr("monitoring:ws:active_count")
            except Exception:
                pass
        if r:
            presence_key = f"collab:{automation_id}:presence"
            lock_key = f"collab:{automation_id}:lock"
            channel = f"collab:{automation_id}"

            try:
                await r.hdel(presence_key, user_id)
            except Exception:
                pass

            # Auto-release lock if this user held it
            try:
                lock_raw = await r.get(lock_key)
                if lock_raw:
                    raw_str = lock_raw.decode("utf-8") if isinstance(lock_raw, bytes) else lock_raw
                    lock_info = json.loads(raw_str)
                    if lock_info.get("user_id") == user_id:
                        await r.delete(lock_key)
                        await _release_lock_in_db(automation_id)
                        await r.publish(channel, json.dumps({
                            "type": "lock_released",
                            "user_id": user_id,
                        }))
            except Exception:
                pass

            # Announce departure
            try:
                await r.publish(channel, json.dumps({
                    "type": "user_left",
                    "user_id": user_id,
                }))
            except Exception:
                pass

        if pubsub:
            try:
                await pubsub.unsubscribe()
                await pubsub.aclose()
            except Exception:
                pass
        # Close the dedicated pub/sub Redis connection
        if pubsub_redis:
            try:
                await pubsub_redis.aclose()
            except Exception:
                pass
        # NOTE: Do NOT close `r` here — it is the shared connection pool
        # returned by get_redis_pool(). Closing it would break all other
        # Redis consumers in the application.

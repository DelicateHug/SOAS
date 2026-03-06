"""Real-time wiki collaboration WebSocket using Y.js CRDT sync.

Supports two room types:
- **Wiki page rooms** (page_id is a wiki page UUID): full DB persistence of Y.js state, HTML content, and editor count.
- **Draft rooms** (room_id prefixed with ``draft:``): Y.js state is persisted to Redis only (no WikiPage row exists yet). Used for pending-create change requests.
"""

import asyncio
import base64
import hashlib
import json
import logging
from datetime import datetime, timezone
from uuid import UUID

import redis.asyncio as aioredis
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy import select, update

from soas_backend.auth.jwt import decode_access_token
from soas_backend.config import settings
from soas_backend.database import async_session

logger = logging.getLogger("wiki_collab")

wiki_collab_ws_router = APIRouter()

# Deterministic colour palette (same as graph editor)
_COLORS = [
    "#3b82f6", "#ef4444", "#10b981", "#f59e0b",
    "#8b5cf6", "#ec4899", "#06b6d4", "#f97316",
]


def _assign_color(user_id: str) -> str:
    idx = int(hashlib.md5(user_id.encode()).hexdigest(), 16) % len(_COLORS)
    return _COLORS[idx]


def _is_draft_room(room_id: str) -> bool:
    """Return True if room_id represents a draft CR room (not a real wiki page)."""
    return room_id.startswith("draft-")


# ---------------------------------------------------------------------------
# DB helpers for Y.js state persistence (wiki page rooms only)
# ---------------------------------------------------------------------------

async def _load_yjs_state(page_id: str) -> bytes | None:
    from soas_backend.models.wiki import WikiPage
    async with async_session() as session:
        result = await session.execute(
            select(WikiPage.yjs_state).where(WikiPage.id == UUID(page_id))
        )
        return result.scalar_one_or_none()


async def _save_yjs_state(page_id: str, state: bytes) -> None:
    from soas_backend.models.wiki import WikiPage
    async with async_session() as session:
        await session.execute(
            update(WikiPage)
            .where(WikiPage.id == UUID(page_id))
            .values(yjs_state=state)
        )
        await session.commit()


async def _save_html_content(page_id: str, html: str, user_id: str) -> None:
    """Save the rendered HTML content to the wiki page (for non-Y.js clients)."""
    from soas_backend.models.wiki import WikiPage
    async with async_session() as session:
        await session.execute(
            update(WikiPage)
            .where(WikiPage.id == UUID(page_id))
            .values(content=html, updated_by=UUID(user_id))
        )
        await session.commit()


async def _update_editor_count(page_id: str, delta: int) -> None:
    from soas_backend.models.wiki import WikiPage
    async with async_session() as session:
        await session.execute(
            update(WikiPage)
            .where(WikiPage.id == UUID(page_id))
            .values(active_editors=WikiPage.active_editors + delta)
        )
        await session.commit()


# ---------------------------------------------------------------------------
# Redis-only Y.js state persistence (draft rooms)
# ---------------------------------------------------------------------------

DRAFT_YJS_STATE_TTL = 86400 * 7  # 7 days


async def _load_draft_yjs_state(r: aioredis.Redis, room_id: str) -> bytes | None:
    data = await r.get(f"wiki-collab:{room_id}:yjs_state")
    return data if isinstance(data, bytes) else (data.encode("latin-1") if data else None)


async def _save_draft_yjs_state(r: aioredis.Redis, room_id: str, state: bytes) -> None:
    await r.set(f"wiki-collab:{room_id}:yjs_state", state, ex=DRAFT_YJS_STATE_TTL)


# ---------------------------------------------------------------------------
# Bidirectional message tasks
# ---------------------------------------------------------------------------

async def _read_from_client(
    ws: WebSocket,
    r: aioredis.Redis,
    channel: str,
    user_id: str,
    room_id: str,
    can_edit: bool,
    display_name: str,
) -> None:
    """Read messages from the WebSocket client, validate, and publish to Redis."""
    presence_key = f"wiki-collab:{room_id}:presence"
    last_save_time = 0.0  # Save on first update immediately
    is_draft = _is_draft_room(room_id)

    while True:
        raw = await ws.receive_text()
        msg = json.loads(raw)
        msg_type = msg.get("type")

        if msg_type == "heartbeat":
            await r.expire(presence_key, 3600)
            continue

        if msg_type == "yjs_update":
            # Y.js document update (binary, base64 encoded)
            if not can_edit:
                await ws.send_text(json.dumps({"type": "error", "message": "Read-only"}))
                continue

            # Broadcast to all other clients
            msg["user_id"] = user_id
            msg["timestamp"] = datetime.now(timezone.utc).isoformat()
            update_len = len(msg.get("update", ""))
            logger.info(f"[yjs_update] user={display_name} room={room_id} update_b64_len={update_len}")
            await r.publish(channel, json.dumps(msg))

            # Persist Y.js state periodically (every 5 seconds)
            now = asyncio.get_event_loop().time()
            if now - last_save_time > 5:
                last_save_time = now
                try:
                    state_b64 = msg.get("state")
                    if state_b64:
                        state_bytes = base64.b64decode(state_b64)
                        if is_draft:
                            await _save_draft_yjs_state(r, room_id, state_bytes)
                        else:
                            await _save_yjs_state(room_id, state_bytes)
                except Exception:
                    pass
            continue

        if msg_type == "yjs_sync":
            # Y.js sync protocol message (step 1 or step 2)
            msg["user_id"] = user_id
            await r.publish(channel, json.dumps(msg))
            continue

        if msg_type == "awareness_update":
            # Cursor position + user info for collaborative cursors
            msg["user_id"] = user_id
            await r.publish(channel, json.dumps(msg))
            continue

        if msg_type == "field_update":
            # Non-content field changes (title, tags, status, etc.)
            if not can_edit:
                await ws.send_text(json.dumps({"type": "error", "message": "Read-only"}))
                continue

            msg["user_id"] = user_id
            msg["timestamp"] = datetime.now(timezone.utc).isoformat()
            await r.publish(channel, json.dumps(msg))
            continue

        if msg_type == "save_html":
            # Client sends rendered HTML for DB persistence (wiki page rooms only)
            if not can_edit or is_draft:
                continue
            html = msg.get("html", "")
            try:
                await _save_html_content(room_id, html, user_id)
            except Exception:
                pass
            continue

        if msg_type == "save_yjs_state":
            # Client sends full Y.js state for persistence
            if not can_edit:
                continue
            try:
                state_bytes = base64.b64decode(msg.get("state", ""))
                if state_bytes:
                    if is_draft:
                        await _save_draft_yjs_state(r, room_id, state_bytes)
                    else:
                        await _save_yjs_state(room_id, state_bytes)
            except Exception:
                pass
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

        # Don't echo a user's own updates back
        try:
            parsed = json.loads(data)
            msg_type = parsed.get("type")
            msg_user = parsed.get("user_id")
            if msg_user == my_user_id and msg_type in (
                "yjs_update", "yjs_sync", "awareness_update", "field_update",
            ):
                continue
            if msg_type == "yjs_update":
                logger.info(f"[relay] Forwarding yjs_update from={msg_user} to={my_user_id}")
        except (json.JSONDecodeError, KeyError):
            pass

        await ws.send_text(data)


# ---------------------------------------------------------------------------
# Main WebSocket endpoint
# ---------------------------------------------------------------------------

@wiki_collab_ws_router.websocket("/api/v1/ws/wiki/{room_id}")
async def wiki_collaboration_ws(websocket: WebSocket, room_id: str):
    """Bidirectional WebSocket for real-time wiki page co-editing.

    Uses Y.js CRDT for conflict-free simultaneous editing. Clients connect
    with a JWT token as a query parameter. The server relays Y.js sync
    messages, document updates, and awareness (cursor) info between all
    connected editors via Redis pub/sub.

    **Room types:**
    - ``<uuid>`` — existing wiki page (full DB persistence)
    - ``draft:<cr_id>`` — pending-create change request (Redis-only persistence)
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
    can_edit = "wiki:update" in permissions or "wiki:create" in permissions

    color = _assign_color(user_id)
    is_draft = _is_draft_room(room_id)

    # --- Redis setup ---
    r: aioredis.Redis | None = None
    pubsub_redis: aioredis.Redis | None = None
    pubsub: aioredis.client.PubSub | None = None

    try:
        from soas_backend.api.deps import get_redis_pool
        r = await get_redis_pool()
        pubsub_redis = aioredis.from_url(settings.redis_url, decode_responses=False)
        pubsub = pubsub_redis.pubsub()
        channel = f"wiki-collab:{room_id}"
        presence_key = f"wiki-collab:{room_id}:presence"

        # Track WebSocket connection for monitoring
        await r.incr("monitoring:ws:active_count")

        # Increment active editor count (wiki page rooms only)
        if not is_draft:
            await _update_editor_count(room_id, 1)

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

        # Load existing Y.js state
        if is_draft:
            yjs_state = await _load_draft_yjs_state(r, room_id)
        else:
            yjs_state = await _load_yjs_state(room_id)
        yjs_state_b64 = base64.b64encode(yjs_state).decode("utf-8") if yjs_state else None

        # Send initial session state
        presence_raw = await r.hgetall(presence_key)
        collaborators = []
        for v in presence_raw.values():
            val = v.decode("utf-8") if isinstance(v, bytes) else v
            collaborators.append(json.loads(val))

        await websocket.send_text(json.dumps({
            "type": "session_state",
            "collaborators": collaborators,
            "yjs_state": yjs_state_b64,
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
            _read_from_client(websocket, r, channel, user_id, room_id, can_edit, display_name),
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
        if r:
            try:
                await r.decr("monitoring:ws:active_count")
            except Exception:
                pass

        # Decrement active editor count (wiki page rooms only)
        if not is_draft:
            try:
                await _update_editor_count(room_id, -1)
            except Exception:
                pass

        if r:
            presence_key = f"wiki-collab:{room_id}:presence"
            channel = f"wiki-collab:{room_id}"

            try:
                await r.hdel(presence_key, user_id)
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
        if pubsub_redis:
            try:
                await pubsub_redis.aclose()
            except Exception:
                pass
        # NOTE: Do NOT close `r` — it is the shared connection pool.

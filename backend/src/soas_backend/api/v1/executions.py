"""Execution log endpoints + WebSocket live output."""

import asyncio
import json
import logging
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

import redis.asyncio as aioredis

from soas_backend.api.deps import get_redis, require_permission
from soas_backend.database import get_db
from soas_backend.services.execution_service import ExecutionService
from soas_shared.schemas.common import PaginatedResponse, PaginationMeta
from soas_shared.schemas.execution import ExecutionListItem, ExecutionLogRead
from soas_shared.schemas.user import UserBrief

router = APIRouter(prefix="/executions", tags=["executions"])


def _user_brief(user) -> UserBrief | None:
    if user is None:
        return None
    return UserBrief(id=user.id, username=user.username, display_name=user.display_name)


def _to_list_item(e) -> ExecutionListItem:
    return ExecutionListItem(
        id=e.id,
        automation_id=e.automation_id,
        automation_name=e.automation.name if e.automation else None,
        triggered_by=_user_brief(e.user),
        status=e.status,
        celery_task_id=e.celery_task_id,
        worker_id=e.worker_id,
        started_at=e.started_at,
        completed_at=e.completed_at,
        duration_ms=e.duration_ms,
        created_at=e.created_at,
    )


@router.get("", response_model=PaginatedResponse[ExecutionListItem])
async def list_executions(
    automation_id: UUID | None = None,
    execution_status: str | None = Query(None, alias="status"),
    started_after: datetime | None = Query(None),
    started_before: datetime | None = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=1, le=100),
    _: dict = Depends(require_permission("execution", "read")),
    db: AsyncSession = Depends(get_db),
):
    svc = ExecutionService(db)
    executions, total = await svc.list_executions(
        automation_id, execution_status, started_after, started_before, page, per_page
    )

    return PaginatedResponse(
        data=[_to_list_item(e) for e in executions],
        meta=PaginationMeta(
            total=total,
            page=page,
            per_page=per_page,
            total_pages=(total + per_page - 1) // per_page if total else 0,
        ),
    )


@router.get("/pending-input")
async def get_executions_with_pending_input(
    _: dict = Depends(require_permission("execution", "read")),
    redis: aioredis.Redis = Depends(get_redis),
):
    """Return execution IDs that currently have a pending input request in Redis."""
    members = await redis.smembers("executions:pending_input")
    pending = [
        m.decode("utf-8") if isinstance(m, bytes) else m for m in members
    ]
    return {"execution_ids": pending}


@router.get("/{execution_id}", response_model=ExecutionLogRead)
async def get_execution(
    execution_id: UUID,
    response: Response,
    _: dict = Depends(require_permission("execution", "read")),
    db: AsyncSession = Depends(get_db),
):
    response.headers["Cache-Control"] = "no-store"
    svc = ExecutionService(db)
    execution = await svc.get(execution_id)
    if not execution:
        raise HTTPException(status_code=404, detail="Execution not found")

    return ExecutionLogRead(
        id=execution.id,
        automation_id=execution.automation_id,
        automation_name=execution.automation.name if execution.automation else None,
        triggered_by=_user_brief(execution.user),
        incident_id=execution.incident_id,
        case_id=execution.case_id,
        status=execution.status,
        worker_id=execution.worker_id,
        parameters=execution.parameters,
        stdout=execution.stdout,
        stderr=execution.stderr,
        result_data=execution.result_data,
        exit_code=execution.exit_code,
        started_at=execution.started_at,
        completed_at=execution.completed_at,
        duration_ms=execution.duration_ms,
        error_message=execution.error_message,
        created_at=execution.created_at,
    )


@router.post("/{execution_id}/cancel")
async def cancel_execution(
    execution_id: UUID,
    _: dict = Depends(require_permission("execution", "cancel")),
    db: AsyncSession = Depends(get_db),
):
    svc = ExecutionService(db)
    cancelled = await svc.cancel(execution_id)
    if not cancelled:
        raise HTTPException(status_code=400, detail="Cannot cancel this execution")
    return {"message": "Execution cancelled"}


# WebSocket for live execution output
ws_router = APIRouter()


@ws_router.websocket("/api/v1/ws/executions/{execution_id}")
async def execution_ws(websocket: WebSocket, execution_id: str):
    """Bidirectional WebSocket for live execution I/O.

    Output direction (worker → frontend):
        Workers publish output lines to Redis pub/sub channel
        ``execution:{execution_id}:output``.  This endpoint subscribes
        and forwards messages to the WebSocket client.

    Input direction (frontend → worker):
        When the frontend sends an ``input_response`` message, this
        endpoint pushes it to a Redis list that the subprocess is
        blocking on via ``BLPOP``.
    """
    await websocket.accept()

    r = None
    pubsub = None
    done = asyncio.Event()

    async def _relay_output():
        """Redis pubsub → WebSocket (output + input_request messages)."""
        nonlocal pubsub
        deadline = asyncio.get_event_loop().time() + 3600  # 1 hour to accommodate input waits

        pubsub = r.pubsub()
        channel = f"execution:{execution_id}:output"
        await pubsub.subscribe(channel)

        # Check for a pending input request that was published before we
        # subscribed (race condition fix).  The subprocess stores this in
        # a Redis key so we can recover it even if the pubsub msg was missed.
        pending_key = f"execution:{execution_id}:pending_input"
        pending = await r.get(pending_key)
        if pending:
            if isinstance(pending, bytes):
                pending = pending.decode("utf-8")
            await websocket.send_text(pending)

        while not done.is_set() and asyncio.get_event_loop().time() < deadline:
            message = await pubsub.get_message(
                ignore_subscribe_messages=True, timeout=1.0,
            )

            if message is None:
                continue

            if message["type"] == "message":
                data = message["data"]
                if isinstance(data, bytes):
                    data = data.decode("utf-8")
                await websocket.send_text(data)

                try:
                    parsed = json.loads(data)
                    if parsed.get("type") in ("complete", "compile_error"):
                        done.set()
                        break
                except (json.JSONDecodeError, KeyError):
                    pass

    async def _relay_input():
        """WebSocket → Celery resume task (input_response messages).

        When the user provides input, we inject the value into the
        checkpoint state in Redis and dispatch a Celery task to resume
        the automation from the next segment.
        """
        while not done.is_set():
            try:
                raw = await asyncio.wait_for(
                    websocket.receive_text(),
                    timeout=1.0,
                )
            except asyncio.TimeoutError:
                continue
            except WebSocketDisconnect:
                done.set()
                return

            try:
                msg = json.loads(raw)
            except (json.JSONDecodeError, ValueError):
                continue

            if msg.get("type") == "input_response" and msg.get("request_id"):
                input_value = msg.get("value", "")
                input_cancelled = msg.get("cancelled", False)

                try:
                    # Read checkpoint metadata to get segment_index
                    meta_key = f"execution:{execution_id}:checkpoint_meta"
                    meta_raw = await r.get(meta_key)
                    if not meta_raw:
                        logger.warning("No checkpoint meta for execution %s", execution_id)
                        continue

                    if isinstance(meta_raw, bytes):
                        meta_raw = meta_raw.decode("utf-8")
                    meta = json.loads(meta_raw)
                    segment_index = meta.get("segment_index", 0)

                    # Inject input value into the checkpoint state
                    import pickle
                    import hashlib
                    import hmac as _hmac

                    state_key = f"execution:{execution_id}:checkpoint_state"
                    pickled = await r.get(state_key)
                    if pickled:
                        hmac_key = execution_id.encode()
                        state = pickle.loads(pickled)
                        state["__input_value__"] = input_value
                        state["__input_cancelled__"] = input_cancelled
                        new_pickled = pickle.dumps(state, protocol=pickle.HIGHEST_PROTOCOL)
                        new_sig = _hmac.new(hmac_key, new_pickled, hashlib.sha256).hexdigest()
                        meta["signature"] = new_sig
                        await r.set(state_key, new_pickled, ex=3600)
                        await r.set(meta_key, json.dumps(meta), ex=3600)

                    # Clean up pending input key
                    pending_key = f"execution:{execution_id}:pending_input"
                    await r.delete(pending_key)
                    await r.srem("executions:pending_input", execution_id)

                    # Read resume context and dispatch Celery task
                    ctx_key = f"execution:{execution_id}:resume_context"
                    ctx_raw = await r.get(ctx_key)
                    if ctx_raw:
                        if isinstance(ctx_raw, bytes):
                            ctx_raw = ctx_raw.decode("utf-8")
                        ctx = json.loads(ctx_raw)

                        from soas_backend.celery_proxy import get_celery
                        celery_app = get_celery()

                        if "graph_json" in ctx:
                            # Test run — re-dispatch test_run_graph
                            celery_app.send_task(
                                "soas.test_run_graph",
                                kwargs={
                                    "execution_id": execution_id,
                                    "automation_id": ctx["automation_id"],
                                    "graph_json": ctx["graph_json"],
                                    "parameters": ctx["parameters"],
                                    "incident_id": ctx.get("incident_id"),
                                    "timeout_seconds": ctx.get("timeout_seconds", 300),
                                    "user_role_ids": ctx.get("user_role_ids"),
                                    "api_token": ctx.get("api_token"),
                                    "triggering_user_id": ctx.get("triggering_user_id"),
                                    "resume_segment": segment_index,
                                },
                            )
                        else:
                            # Production run — re-dispatch run_automation
                            celery_app.send_task(
                                "soas.run_automation",
                                kwargs={
                                    "execution_id": execution_id,
                                    "automation_id": ctx["automation_id"],
                                    "parameters": ctx["parameters"],
                                    "user_role_ids": ctx.get("user_role_ids"),
                                    "api_token": ctx.get("api_token"),
                                    "resume_segment": segment_index,
                                },
                            )
                except Exception:
                    logger.exception("Failed to dispatch resume for execution %s", execution_id)

    try:
        from soas_backend.api.deps import get_redis_pool

        r = await get_redis_pool()
        await r.incr("monitoring:ws:active_count")

        await asyncio.gather(
            _relay_output(),
            _relay_input(),
        )

    except WebSocketDisconnect:
        pass
    except Exception:
        logger.exception("WebSocket relay error for execution %s", execution_id)
        try:
            await websocket.close(code=1011)
        except Exception:
            pass
    finally:
        done.set()
        if r:
            try:
                await r.decr("monitoring:ws:active_count")
            except Exception:
                pass
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

"""@audit decorator: records a SecurityEvent on every call to the wrapped
FastAPI handler.

Usage:

    from soas_backend.services.audit import audit

    @audit(
        event_type="case.created",
        target_kind="case",
        severity="info",
        extract_target=lambda result: getattr(result, "id", None),
    )
    @router.post("/cases")
    async def create_case(
        body: CaseCreate,
        request: Request,
        db: AsyncSession = Depends(get_db),
    ):
        ...

The decorator:
  - Pulls the `Request` and the `AsyncSession` out of the handler's
    kwargs (FastAPI injects them positionally or by name, depending on
    style — we accept either).
  - Reads `request.state.user` if `get_authenticated_user` set it,
    falling back to a JWT decode of the Authorization header.
  - Records IP + user-agent on every call.
  - On exception, records `severity="error"` with the exception class
    and re-raises.

Read-only endpoints should NOT be decorated. The gateway access log
captures those; auditing them here is noisy and expensive.
"""

from __future__ import annotations

import functools
import logging
from typing import Any, Callable, Coroutine, TypeVar
from uuid import UUID

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

T = TypeVar("T")


def audit(
    event_type: str,
    *,
    target_kind: str | None = None,
    severity: str = "info",
    extract_target: Callable[[Any], UUID | str | None] | None = None,
    extract_label: Callable[[Any], str | None] | None = None,
    message: str | None = None,
) -> Callable[[Callable[..., Coroutine[Any, Any, T]]], Callable[..., Coroutine[Any, Any, T]]]:
    """Wrap an async FastAPI handler with audit-logging behaviour."""

    def decorator(fn: Callable[..., Coroutine[Any, Any, T]]) -> Callable[..., Coroutine[Any, Any, T]]:
        @functools.wraps(fn)
        async def wrapper(*args: Any, **kwargs: Any) -> T:
            request = _pick_request(args, kwargs)
            db = _pick_db(args, kwargs)
            try:
                result = await fn(*args, **kwargs)
            except Exception as exc:
                await _record(
                    db=db,
                    request=request,
                    handler_kwargs=kwargs,
                    event_type=event_type,
                    severity="error",
                    target_kind=target_kind,
                    target_id=None,
                    target_label=None,
                    message=f"{type(exc).__name__}: {exc}",
                )
                raise

            try:
                target_id = extract_target(result) if extract_target else None
                target_label = extract_label(result) if extract_label else None
            except Exception:
                target_id = None
                target_label = None

            await _record(
                db=db,
                request=request,
                handler_kwargs=kwargs,
                event_type=event_type,
                severity=severity,
                target_kind=target_kind,
                target_id=_as_uuid(target_id),
                target_label=str(target_label) if target_label else None,
                message=message,
            )
            return result

        return wrapper

    return decorator


def _pick_request(args: tuple, kwargs: dict) -> Request | None:
    for v in kwargs.values():
        if isinstance(v, Request):
            return v
    for v in args:
        if isinstance(v, Request):
            return v
    return None


def _pick_db(args: tuple, kwargs: dict) -> AsyncSession | None:
    for v in kwargs.values():
        if isinstance(v, AsyncSession):
            return v
    for v in args:
        if isinstance(v, AsyncSession):
            return v
    return None


def _as_uuid(v: Any) -> UUID | None:
    if v is None:
        return None
    if isinstance(v, UUID):
        return v
    try:
        return UUID(str(v))
    except (ValueError, AttributeError, TypeError):
        return None


async def _record(
    *,
    db: AsyncSession | None,
    request: Request | None,
    handler_kwargs: dict | None = None,
    event_type: str,
    severity: str,
    target_kind: str | None,
    target_id: UUID | None,
    target_label: str | None,
    message: str | None,
) -> None:
    if db is None:
        return  # nothing to write to
    try:
        actor_id, actor_label = _resolve_actor(request, handler_kwargs)
        ip = request.client.host if (request and request.client) else None
        ua = request.headers.get("user-agent") if request else None
        from soas_backend.services.security_event_service import SecurityEventService

        await SecurityEventService(db).record(
            event_type=event_type,
            severity=severity,
            actor_id=actor_id,
            actor_label=actor_label,
            target_kind=target_kind,
            target_id=target_id,
            target_label=target_label,
            message=message,
            ip_address=ip,
            user_agent=ua,
        )
    except Exception:
        logger.exception("audit: record failed for %s", event_type)


def _resolve_actor(
    request: Request | None,
    kwargs: dict | None = None,
) -> tuple[UUID | None, str | None]:
    # 1. request.state.user (set by get_authenticated_user)
    if request is not None:
        user = getattr(request.state, "user", None)
        if user is not None:
            return getattr(user, "id", None), getattr(user, "username", None)

    # 2. a `current_user` kwarg from the legacy get_current_user dep
    if kwargs:
        cu = kwargs.get("current_user")
        if cu is not None:
            return getattr(cu, "id", None), getattr(cu, "username", None)

    # 3. Bearer token in the request header (last resort)
    if request is not None:
        auth = request.headers.get("authorization") or ""
        if auth.lower().startswith("bearer "):
            try:
                from soas_backend.auth.jwt import decode_access_token

                payload = decode_access_token(auth[7:].strip())
                if payload:
                    return (_as_uuid(payload.get("sub")), payload.get("username"))
            except Exception:
                pass
    return None, None

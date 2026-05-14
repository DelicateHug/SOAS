"""User certificate API.

Admin endpoints under /admin/users/{user_id}/certificates manage other
users' certs. Self-service endpoints under /me/certificates let an
analyst issue + download their own.

PKCS#12 + passphrase are returned exactly once via a Redis-backed
one-time download token; the .p12 is never written to disk on the
server, and the private key is never persisted.
"""

from __future__ import annotations

import base64
import json
import secrets
from datetime import datetime
from typing import Any
from uuid import UUID

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from soas_backend.api.deps import get_current_user, get_redis, require_role
from soas_backend.database import get_db
from soas_backend.models.user import User
from soas_backend.services.cert_authority_service import (
    VALID_PURPOSES,
    CertAuthorityService,
)
from soas_backend.services.security_event_service import SecurityEventService

router = APIRouter(tags=["user-certificates"])

# How long a fresh-issue download token is valid before the .p12 + passphrase
# are wiped from Redis. Short on purpose — the admin/user is supposed to
# download immediately on the same screen.
DOWNLOAD_TTL_SECONDS = 300


class CertRead(BaseModel):
    id: UUID
    user_id: UUID
    purpose: str
    serial: str
    fingerprint_sha256: str
    common_name: str
    not_before: datetime
    not_after: datetime
    issued_by: UUID | None
    issued_at: datetime
    downloaded_at: datetime | None
    revoked_at: datetime | None
    revocation_reason: str | None

    model_config = {"from_attributes": True}


class IssueRequest(BaseModel):
    purpose: str = Field(default="web")
    common_name: str | None = None


class IssueResponse(BaseModel):
    cert: CertRead
    download_token: str
    download_expires_at: datetime


async def _stash_download(
    redis: aioredis.Redis,
    *,
    p12_bytes: bytes,
    passphrase: str,
    cert_id: UUID,
    user_id: UUID,
    common_name: str,
) -> str:
    token = secrets.token_urlsafe(24)
    payload = {
        "p12_b64": base64.b64encode(p12_bytes).decode("ascii"),
        "passphrase": passphrase,
        "cert_id": str(cert_id),
        "user_id": str(user_id),
        "common_name": common_name,
    }
    await redis.set(
        f"cert:dl:{token}",
        json.dumps(payload),
        ex=DOWNLOAD_TTL_SECONDS,
    )
    return token


def _can_act_on_user(payload: dict, target_user_id: UUID) -> bool:
    """Return True if the request principal can issue/revoke certs for
    the given user. Admins always can; non-admins can only act on
    themselves."""
    if "admin" in (payload.get("roles") or []):
        return True
    sub = payload.get("sub")
    return sub is not None and UUID(sub) == target_user_id


# ============================================================
# Admin / per-user routes
# ============================================================


@router.post(
    "/admin/users/{user_id}/certificates",
    response_model=IssueResponse,
    status_code=status.HTTP_201_CREATED,
)
async def issue_for_user(
    user_id: UUID,
    body: IssueRequest,
    payload: dict = Depends(require_role("admin", "soc_manager")),
    redis: aioredis.Redis = Depends(get_redis),
    db: AsyncSession = Depends(get_db),
):
    if body.purpose not in VALID_PURPOSES:
        raise HTTPException(status_code=400, detail=f"purpose must be one of {VALID_PURPOSES}")

    rs = await db.execute(select(User).where(User.id == user_id))
    user = rs.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    common_name = body.common_name or f"user:{user.id}"
    actor_id = UUID(payload["sub"]) if payload.get("sub") else None

    svc = CertAuthorityService(db)
    issued = await svc.issue_for_user(
        user_id=user.id,
        common_name=common_name,
        purpose=body.purpose,
        issued_by=actor_id,
    )
    token = await _stash_download(
        redis,
        p12_bytes=issued.p12_bytes,
        passphrase=issued.passphrase,
        cert_id=issued.record.id,
        user_id=user.id,
        common_name=common_name,
    )

    await SecurityEventService(db).record(
        event_type="cert.issued",
        actor_id=actor_id,
        actor_label=payload.get("username"),
        target_kind="user",
        target_id=user.id,
        target_label=user.username,
        message=f"Issued {body.purpose} cert (serial {issued.record.serial})",
        extra={"purpose": body.purpose, "cert_id": str(issued.record.id)},
    )

    return IssueResponse(
        cert=CertRead.model_validate(issued.record),
        download_token=token,
        download_expires_at=_expires_at(),
    )


@router.get("/admin/users/{user_id}/certificates", response_model=list[CertRead])
async def list_for_user(
    user_id: UUID,
    include_revoked: bool = False,
    payload: dict = Depends(require_role("admin", "soc_manager")),
    db: AsyncSession = Depends(get_db),
):
    rows = await CertAuthorityService(db).list_for_user(user_id, include_revoked=include_revoked)
    return [CertRead.model_validate(r) for r in rows]


@router.delete(
    "/admin/users/{user_id}/certificates/{cert_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def revoke_user_cert(
    user_id: UUID,
    cert_id: UUID,
    payload: dict = Depends(require_role("admin", "soc_manager")),
    redis: aioredis.Redis = Depends(get_redis),
    db: AsyncSession = Depends(get_db),
):
    svc = CertAuthorityService(db)
    cert = await svc.revoke(
        cert_id=cert_id,
        actor_id=UUID(payload["sub"]) if payload.get("sub") else None,
        reason="admin revocation",
    )
    if cert is None:
        raise HTTPException(status_code=404, detail="Cert not found")
    # Publish on the revocation pubsub so the cert validator drops cached
    # payloads immediately (CAE service subscribes).
    try:
        await redis.publish(
            "auth:revocation",
            json.dumps(
                {
                    "kind": "cert",
                    "fingerprint": cert.fingerprint_sha256,
                    "serial": cert.serial,
                    "user_id": str(cert.user_id),
                }
            ),
        )
    except Exception:
        pass
    await SecurityEventService(db).record(
        event_type="cert.revoked",
        severity="warn",
        actor_id=UUID(payload["sub"]) if payload.get("sub") else None,
        actor_label=payload.get("username"),
        target_kind="user_certificate",
        target_id=cert.id,
        target_label=cert.common_name,
        extra={"serial": cert.serial, "purpose": cert.purpose},
    )


# ============================================================
# Self-service routes
# ============================================================


@router.get("/me/certificates", response_model=list[CertRead])
async def list_my_certificates(
    include_revoked: bool = False,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    rows = await CertAuthorityService(db).list_for_user(current_user.id, include_revoked=include_revoked)
    return [CertRead.model_validate(r) for r in rows]


@router.post(
    "/me/certificates",
    response_model=IssueResponse,
    status_code=status.HTTP_201_CREATED,
)
async def issue_my_certificate(
    body: IssueRequest,
    current_user: User = Depends(get_current_user),
    redis: aioredis.Redis = Depends(get_redis),
    db: AsyncSession = Depends(get_db),
):
    if body.purpose not in VALID_PURPOSES:
        raise HTTPException(status_code=400, detail=f"purpose must be one of {VALID_PURPOSES}")
    common_name = body.common_name or f"user:{current_user.id}"
    svc = CertAuthorityService(db)
    issued = await svc.issue_for_user(
        user_id=current_user.id,
        common_name=common_name,
        purpose=body.purpose,
        issued_by=current_user.id,
    )
    token = await _stash_download(
        redis,
        p12_bytes=issued.p12_bytes,
        passphrase=issued.passphrase,
        cert_id=issued.record.id,
        user_id=current_user.id,
        common_name=common_name,
    )
    await SecurityEventService(db).record(
        event_type="cert.issued",
        actor_id=current_user.id,
        actor_label=current_user.username,
        target_kind="user",
        target_id=current_user.id,
        target_label=current_user.username,
        message=f"Self-issued {body.purpose} cert",
        extra={"purpose": body.purpose, "self": True},
    )
    return IssueResponse(
        cert=CertRead.model_validate(issued.record),
        download_token=token,
        download_expires_at=_expires_at(),
    )


@router.get("/me/certificates/download/{token}")
async def download_my_certificate(
    token: str,
    current_user: User = Depends(get_current_user),
    redis: aioredis.Redis = Depends(get_redis),
    db: AsyncSession = Depends(get_db),
):
    """One-time .p12 download. Verifies the token belongs to the current
    user before serving, then deletes the Redis stash."""
    raw = await redis.get(f"cert:dl:{token}")
    if not raw:
        raise HTTPException(status_code=404, detail="Download expired or unknown")
    payload = json.loads(raw)
    if UUID(payload["user_id"]) != current_user.id:
        raise HTTPException(status_code=403, detail="Not your certificate")
    p12_bytes = base64.b64decode(payload["p12_b64"])

    # Burn the token immediately
    await redis.delete(f"cert:dl:{token}")

    # Mark downloaded + record event
    await CertAuthorityService(db).mark_downloaded(UUID(payload["cert_id"]))
    await SecurityEventService(db).record(
        event_type="cert.downloaded",
        actor_id=current_user.id,
        actor_label=current_user.username,
        target_kind="user_certificate",
        target_id=UUID(payload["cert_id"]),
        target_label=payload["common_name"],
    )

    filename = f"{payload['common_name'].replace(':', '-')}.p12"
    return Response(
        content=p12_bytes,
        media_type="application/x-pkcs12",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "X-Cert-Passphrase": payload["passphrase"],
            # Tell the browser this is one-time; don't let any cache hold it.
            "Cache-Control": "no-store, no-cache, must-revalidate",
        },
    )


def _expires_at() -> datetime:
    from datetime import datetime, timedelta, timezone
    return datetime.now(timezone.utc) + timedelta(seconds=DOWNLOAD_TTL_SECONDS)

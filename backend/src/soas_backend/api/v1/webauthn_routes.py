"""WebAuthn (Windows Hello / FIDO2) registration and login endpoints."""

import base64
import secrets

import redis
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from soas_backend.api.deps import get_current_user, get_redis_pool
from soas_backend.auth.jwt import create_access_token
from soas_backend.crypto import unwrap_dek_server
from soas_backend.services.dek_cache import DekCache
from soas_backend.auth.webauthn import (
    generate_authentication,
    generate_registration,
    verify_authentication,
    verify_registration,
)
from soas_backend.config import settings
from soas_backend.database import get_db
from soas_backend.models.user import User, WebAuthnCredential
from soas_backend.services.auth_service import AuthService
from soas_shared.schemas.auth import (
    LoginResponse,
    WebAuthnLoginBeginRequest,
    WebAuthnLoginBeginResponse,
    WebAuthnLoginCompleteRequest,
    WebAuthnRegisterBeginResponse,
    WebAuthnRegisterCompleteRequest,
)

router = APIRouter(prefix="/auth/webauthn", tags=["webauthn"])

# Use Redis to store challenge state between begin/complete
_redis = redis.from_url(settings.redis_url)
CHALLENGE_TTL = 300  # 5 minutes


@router.post("/register/begin", response_model=WebAuthnRegisterBeginResponse)
async def webauthn_register_begin(
    current_user: User = Depends(get_current_user),
):
    user_id_bytes = current_user.id.bytes
    options = generate_registration(
        user_id=user_id_bytes,
        username=current_user.username,
        display_name=current_user.display_name,
    )

    # Serialize options for the frontend
    challenge = base64.urlsafe_b64encode(options.challenge).decode()
    _redis.setex(
        f"webauthn:register:{current_user.id}",
        CHALLENGE_TTL,
        challenge,
    )

    # Convert options to dict for JSON serialization
    options_dict = {
        "rp": {"id": options.rp.id, "name": options.rp.name},
        "user": {
            "id": base64.urlsafe_b64encode(options.user.id).decode(),
            "name": options.user.name,
            "displayName": options.user.display_name,
        },
        "challenge": challenge,
        "pubKeyCredParams": [
            {"type": "public-key", "alg": alg.value}
            for alg in options.pub_key_cred_params
        ],
        "timeout": options.timeout,
        "attestation": options.attestation,
        "authenticatorSelection": {
            "authenticatorAttachment": options.authenticator_selection.authenticator_attachment,
            "residentKey": options.authenticator_selection.resident_key,
            "userVerification": options.authenticator_selection.user_verification,
        },
    }

    return WebAuthnRegisterBeginResponse(options=options_dict)


@router.post("/register/complete")
async def webauthn_register_complete(
    body: WebAuthnRegisterCompleteRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    challenge_b64 = _redis.get(f"webauthn:register:{current_user.id}")
    if not challenge_b64:
        raise HTTPException(status_code=400, detail="Challenge expired, start over")

    challenge = base64.urlsafe_b64decode(challenge_b64)
    _redis.delete(f"webauthn:register:{current_user.id}")

    try:
        result = verify_registration(body.credential, expected_challenge=challenge)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Verification failed: {e}")

    cred = WebAuthnCredential(
        user_id=current_user.id,
        credential_id=result["credential_id"],
        public_key=result["credential_public_key"],
        sign_count=result["sign_count"],
        device_name=body.device_name or "Windows Hello",
    )
    db.add(cred)
    await db.flush()

    return {"message": "WebAuthn credential registered", "device_name": cred.device_name}


@router.post("/login/begin", response_model=WebAuthnLoginBeginResponse)
async def webauthn_login_begin(
    body: WebAuthnLoginBeginRequest,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(User)
        .options(selectinload(User.webauthn_credentials))
        .where(User.username == body.username)
    )
    user = result.scalar_one_or_none()
    if not user or not user.webauthn_credentials:
        raise HTTPException(status_code=400, detail="No WebAuthn credentials found")

    creds = [
        {"credential_id": c.credential_id} for c in user.webauthn_credentials
    ]
    options = generate_authentication(creds)

    challenge = base64.urlsafe_b64encode(options.challenge).decode()
    _redis.setex(f"webauthn:login:{user.id}", CHALLENGE_TTL, challenge)

    options_dict = {
        "challenge": challenge,
        "timeout": options.timeout,
        "rpId": options.rp_id,
        "allowCredentials": [
            {
                "type": "public-key",
                "id": base64.urlsafe_b64encode(c.credential_id).decode(),
            }
            for c in user.webauthn_credentials
        ],
        "userVerification": options.user_verification,
    }

    return WebAuthnLoginBeginResponse(options=options_dict)


@router.post("/login/complete", response_model=LoginResponse)
async def webauthn_login_complete(
    body: WebAuthnLoginCompleteRequest,
    db: AsyncSession = Depends(get_db),
):
    # Find the credential
    credential_id_b64 = body.credential.get("id", "")
    try:
        credential_id = base64.urlsafe_b64decode(credential_id_b64 + "==")
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid credential ID")

    result = await db.execute(
        select(WebAuthnCredential)
        .options(selectinload(WebAuthnCredential.user))
        .where(WebAuthnCredential.credential_id == credential_id)
    )
    stored_cred = result.scalar_one_or_none()
    if not stored_cred:
        raise HTTPException(status_code=400, detail="Credential not found")

    user = stored_cred.user
    challenge_b64 = _redis.get(f"webauthn:login:{user.id}")
    if not challenge_b64:
        raise HTTPException(status_code=400, detail="Challenge expired")

    challenge = base64.urlsafe_b64decode(challenge_b64)
    _redis.delete(f"webauthn:login:{user.id}")

    try:
        verification = verify_authentication(
            credential=body.credential,
            expected_challenge=challenge,
            credential_public_key=stored_cred.public_key,
            credential_current_sign_count=stored_cred.sign_count,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Verification failed: {e}")

    stored_cred.sign_count = verification["new_sign_count"]
    await db.flush()

    # Cache DEK from server-wrapped copy (no password available with passkeys)
    if user.server_wrapped_dek:
        try:
            dek = unwrap_dek_server(user.server_wrapped_dek)
            aioredis = await get_redis_pool()
            await DekCache(aioredis).set(user.id, dek)
        except Exception:
            pass  # Non-fatal; secret ops will fallback to server-wrapped

    auth_service = AuthService(db)
    access_token, refresh_token = await auth_service.create_tokens(user)

    return LoginResponse(access_token=access_token, refresh_token=refresh_token)

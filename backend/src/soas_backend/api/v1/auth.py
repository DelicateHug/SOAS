"""Authentication endpoints."""

import asyncio
import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from soas_backend.auth.totp import generate_backup_codes, generate_totp_secret, get_totp_uri, verify_totp
from soas_backend.database import get_db
from soas_backend.api.deps import get_current_user, get_redis_pool
from soas_backend.models.user import User
from soas_backend.config import settings
from soas_backend.crypto import (
    derive_kek,
    encrypt_value,
    decrypt_value,
    encrypt_with_dek,
    generate_dek,
    generate_salt,
    setup_user_dek,
    unwrap_dek,
    unwrap_dek_server,
    wrap_dek,
    wrap_dek_server,
)
from soas_backend.services.app_setting_service import AppSettingService
from soas_backend.services.auth_service import AccountLockedException, AuthService
from soas_backend.services.dek_cache import DekCache
from soas_backend.auth.password import hash_password, verify_password
from soas_shared.schemas.auth import (
    ChangePasswordRequest,
    LoginRequest,
    LoginResponse,
    MFARequiredResponse,
    MFASetupResponse,
    MFAVerifyRequest,
    MFAVerifySetupRequest,
    RefreshRequest,
    TokenResponse,
)
from soas_shared.schemas.user import UserCreate, UserRead

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


async def _run_deferred_seed() -> None:
    """Run seed_defaults() after first user registration (non-fatal)."""
    try:
        from soas_backend.seed import seed_defaults
        await seed_defaults()
    except Exception:
        logger.warning("Deferred seed failed (non-fatal)", exc_info=True)


@router.get("/registration-open")
async def registration_open(db: AsyncSession = Depends(get_db)):
    """Check whether public registration is available (only when no users exist)."""
    user_count = await db.scalar(select(func.count()).select_from(User))
    return {"open": user_count == 0}


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def register(body: UserCreate, db: AsyncSession = Depends(get_db)):
    # Only allow registration when no users exist (initial setup)
    user_count = await db.scalar(select(func.count()).select_from(User))
    if user_count > 0:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Registration is disabled. Contact an administrator to create your account.",
        )

    auth_service = AuthService(db)
    try:
        user = await auth_service.register(
            username=body.username,
            email=body.email,
            display_name=body.display_name,
            password=body.password,
        )
        # First user registered - trigger deferred seeding in the background
        asyncio.create_task(_run_deferred_seed())

        return UserRead(
            id=user.id,
            username=user.username,
            email=user.email,
            display_name=user.display_name,
            is_active=user.is_active,
            is_mfa_enabled=user.is_mfa_enabled,
            created_at=user.created_at,
            updated_at=user.updated_at,
        )
    except Exception as e:
        if "unique" in str(e).lower():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Username or email already exists",
            )
        raise


@router.post("/login", response_model=LoginResponse | MFARequiredResponse)
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)):
    app_svc = AppSettingService(db)
    max_attempts_str = await app_svc.get_value("max_failed_login_attempts")
    lockout_min_str = await app_svc.get_value("failed_login_lockout_minutes")
    try:
        max_attempts = int(max_attempts_str) if max_attempts_str is not None else settings.max_failed_login_attempts
    except (ValueError, TypeError):
        max_attempts = settings.max_failed_login_attempts
    try:
        lockout_minutes = int(lockout_min_str) if lockout_min_str is not None else settings.failed_login_lockout_minutes
    except (ValueError, TypeError):
        lockout_minutes = settings.failed_login_lockout_minutes

    auth_service = AuthService(db)
    try:
        user = await auth_service.authenticate(
            body.username,
            body.password,
            max_failed_attempts=max_attempts,
            lockout_minutes=lockout_minutes,
        )
    except AccountLockedException:
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail="Account temporarily locked due to too many failed attempts. Try again later.",
        )

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    # Cache the user's DEK (or initialize it for pre-migration users)
    await _cache_user_dek(user, body.password, db)

    if user.is_mfa_enabled:
        # Issue a short-lived MFA token (reuses JWT machinery with a flag)
        from soas_backend.auth.jwt import create_access_token

        mfa_token = create_access_token(
            user_id=user.id,
            username=user.username,
            roles=[],
            permissions=["mfa:pending"],
        )
        return MFARequiredResponse(mfa_token=mfa_token)

    access_token, refresh_token = await auth_service.create_tokens(user)
    return LoginResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        must_reset_password=user.must_reset_password,
    )


@router.post("/mfa/verify", response_model=LoginResponse)
async def mfa_verify(body: MFAVerifyRequest, db: AsyncSession = Depends(get_db)):
    from soas_backend.auth.jwt import decode_access_token
    from sqlalchemy import select

    payload = decode_access_token(body.mfa_token)
    if payload is None or "mfa:pending" not in payload.get("permissions", []):
        raise HTTPException(status_code=401, detail="Invalid MFA token")

    user_id = payload["sub"]
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if user is None or not user.mfa_secret:
        raise HTTPException(status_code=401, detail="MFA not configured")

    if not verify_totp(user.mfa_secret, body.totp_code):
        raise HTTPException(status_code=401, detail="Invalid TOTP code")

    # Extend DEK cache TTL (was set with short TTL during password step)
    redis = await get_redis_pool()
    cache = DekCache(redis)
    dek = await cache.get(user.id)
    if dek:
        await cache.set(user.id, dek)

    auth_service = AuthService(db)
    access_token, refresh_token = await auth_service.create_tokens(user)
    return LoginResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        must_reset_password=user.must_reset_password,
    )


@router.post("/refresh", response_model=LoginResponse)
async def refresh(body: RefreshRequest, db: AsyncSession = Depends(get_db)):
    auth_service = AuthService(db)
    tokens = await auth_service.refresh_access_token(body.refresh_token)

    if tokens is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )

    access_token, refresh_token = tokens
    return LoginResponse(access_token=access_token, refresh_token=refresh_token)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    body: RefreshRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    auth_service = AuthService(db)
    await auth_service.revoke_refresh_token(body.refresh_token)
    # Evict DEK cache on logout
    redis = await get_redis_pool()
    await DekCache(redis).delete(current_user.id)


@router.post("/mfa/setup", response_model=MFASetupResponse)
async def mfa_setup(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if current_user.is_mfa_enabled:
        raise HTTPException(status_code=400, detail="MFA is already enabled")

    secret = generate_totp_secret()
    qr_uri = get_totp_uri(secret, current_user.username)
    backup_codes = generate_backup_codes()

    # Store secret temporarily (not yet confirmed)
    current_user.mfa_secret = secret
    await db.flush()

    return MFASetupResponse(secret=secret, qr_code_uri=qr_uri, backup_codes=backup_codes)


@router.post("/mfa/verify-setup", status_code=status.HTTP_200_OK)
async def mfa_verify_setup(
    body: MFAVerifySetupRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not current_user.mfa_secret:
        raise HTTPException(status_code=400, detail="Run MFA setup first")

    if not verify_totp(current_user.mfa_secret, body.totp_code):
        raise HTTPException(status_code=400, detail="Invalid TOTP code")

    current_user.is_mfa_enabled = True
    await db.flush()
    return {"message": "MFA enabled successfully"}


@router.post("/change-password", status_code=status.HTTP_200_OK)
async def change_password(
    body: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not verify_password(body.current_password, current_user.password_hash):
        raise HTTPException(status_code=400, detail="Current password is incorrect")

    # Re-wrap existing DEK with new password (secrets preserved)
    dek: bytes | None = None
    if current_user.password_wrapped_dek and current_user.dek_salt:
        old_kek = derive_kek(body.current_password, current_user.dek_salt)
        dek = unwrap_dek(current_user.password_wrapped_dek, old_kek)
    elif current_user.server_wrapped_dek:
        dek = unwrap_dek_server(current_user.server_wrapped_dek)
    else:
        # Pre-migration user with no DEK — generate fresh
        dek = generate_dek()
        current_user.server_wrapped_dek = wrap_dek_server(dek)

    new_salt = generate_salt()
    new_kek = derive_kek(body.new_password, new_salt)
    current_user.dek_salt = new_salt
    current_user.password_wrapped_dek = wrap_dek(dek, new_kek)

    current_user.password_hash = hash_password(body.new_password)
    current_user.must_reset_password = False
    await db.flush()

    # Update DEK cache
    redis = await get_redis_pool()
    await DekCache(redis).set(current_user.id, dek)

    return {"message": "Password changed successfully"}


async def _cache_user_dek(user: User, password: str, db: AsyncSession) -> None:
    """Derive or initialize the user's DEK and cache it in Redis.

    Handles three cases:
    1. User has password_wrapped_dek → unwrap with password KEK
    2. User has server_wrapped_dek but no password wrap → initialize password wrap
    3. User has no DEK at all (pre-migration) → generate, re-encrypt secrets
    """
    redis = await get_redis_pool()
    cache = DekCache(redis)
    ttl = 300 if user.is_mfa_enabled else 3600

    if user.password_wrapped_dek and user.dek_salt:
        kek = derive_kek(password, user.dek_salt)
        dek = unwrap_dek(user.password_wrapped_dek, kek)
        await cache.set(user.id, dek, ttl=ttl)
        return

    if user.server_wrapped_dek:
        # Has server-wrapped DEK but no password wrap — first password login
        # after migration. Initialize the password wrapping.
        dek = unwrap_dek_server(user.server_wrapped_dek)
        salt = generate_salt()
        kek = derive_kek(password, salt)
        user.dek_salt = salt
        user.password_wrapped_dek = wrap_dek(dek, kek)
        await db.flush()
        await cache.set(user.id, dek, ttl=ttl)
        return

    # No DEK at all — pre-migration user. Generate DEK and re-encrypt secrets.
    from soas_backend.models.user_secret import UserSecret

    dek, salt, pw_wrapped, srv_wrapped = setup_user_dek(password)
    user.dek_salt = salt
    user.password_wrapped_dek = pw_wrapped
    user.server_wrapped_dek = srv_wrapped

    # Re-encrypt existing secrets from server key to user DEK
    result = await db.execute(
        select(UserSecret).where(UserSecret.user_id == user.id)
    )
    for secret in result.scalars().all():
        try:
            plaintext = decrypt_value(secret.encrypted_value)
            secret.encrypted_value = encrypt_with_dek(plaintext, dek)
            if secret.is_shared and secret.server_encrypted_value:
                # Keep server_encrypted_value as-is (already server-key encrypted)
                pass
        except Exception:
            pass  # Skip secrets that can't be decrypted

    await db.flush()
    await cache.set(user.id, dek, ttl=ttl)

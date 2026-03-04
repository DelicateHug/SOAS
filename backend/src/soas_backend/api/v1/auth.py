"""Authentication endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from soas_backend.auth.totp import generate_backup_codes, generate_totp_secret, get_totp_uri, verify_totp
from soas_backend.database import get_db
from soas_backend.api.deps import get_current_user
from soas_backend.models.user import User
from soas_backend.services.auth_service import AuthService
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

router = APIRouter(prefix="/auth", tags=["auth"])


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
    auth_service = AuthService(db)
    user = await auth_service.authenticate(body.username, body.password)

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

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
async def logout(body: RefreshRequest, db: AsyncSession = Depends(get_db)):
    auth_service = AuthService(db)
    await auth_service.revoke_refresh_token(body.refresh_token)


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

    current_user.password_hash = hash_password(body.new_password)
    current_user.must_reset_password = False
    await db.flush()
    return {"message": "Password changed successfully"}

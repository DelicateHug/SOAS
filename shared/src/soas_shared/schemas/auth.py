"""Authentication schemas."""

from typing import Any

from pydantic import Field

from soas_shared.schemas.common import BaseSchema



class LoginRequest(BaseSchema):
    username: str
    password: str


class LoginResponse(BaseSchema):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    must_reset_password: bool = False


class MFARequiredResponse(BaseSchema):
    mfa_required: bool = True
    mfa_token: str


class MFAVerifyRequest(BaseSchema):
    mfa_token: str
    totp_code: str = Field(min_length=6, max_length=6)


class MFASetupResponse(BaseSchema):
    secret: str
    qr_code_uri: str
    backup_codes: list[str]


class MFAVerifySetupRequest(BaseSchema):
    totp_code: str = Field(min_length=6, max_length=6)


class ChangePasswordRequest(BaseSchema):
    current_password: str
    new_password: str = Field(min_length=8, max_length=128)


class RefreshRequest(BaseSchema):
    refresh_token: str


class TokenResponse(BaseSchema):
    access_token: str
    token_type: str = "bearer"


class WebAuthnRegisterBeginResponse(BaseSchema):
    options: dict[str, Any]


class WebAuthnRegisterCompleteRequest(BaseSchema):
    credential: dict[str, Any]
    device_name: str | None = None


class WebAuthnLoginBeginRequest(BaseSchema):
    username: str


class WebAuthnLoginBeginResponse(BaseSchema):
    options: dict[str, Any]


class WebAuthnLoginCompleteRequest(BaseSchema):
    credential: dict[str, Any]

"""WebAuthn (Windows Hello / FIDO2) registration and authentication."""

from webauthn import (
    generate_authentication_options,
    generate_registration_options,
    verify_authentication_response,
    verify_registration_response,
)
from webauthn.helpers.cose import COSEAlgorithmIdentifier
from webauthn.helpers.structs import (
    AttestationConveyancePreference,
    AuthenticatorAttachment,
    AuthenticatorSelectionCriteria,
    PublicKeyCredentialDescriptor,
    ResidentKeyRequirement,
    UserVerificationRequirement,
)

from soas_backend.config import settings


def generate_registration(user_id: bytes, username: str, display_name: str) -> dict:
    options = generate_registration_options(
        rp_id=settings.webauthn_rp_id,
        rp_name=settings.webauthn_rp_name,
        user_id=user_id,
        user_name=username,
        user_display_name=display_name,
        attestation=AttestationConveyancePreference.NONE,
        authenticator_selection=AuthenticatorSelectionCriteria(
            authenticator_attachment=AuthenticatorAttachment.PLATFORM,
            resident_key=ResidentKeyRequirement.PREFERRED,
            user_verification=UserVerificationRequirement.REQUIRED,
        ),
        supported_pub_key_algs=[
            COSEAlgorithmIdentifier.ECDSA_SHA_256,
            COSEAlgorithmIdentifier.RSASSA_PKCS1_v1_5_SHA_256,
        ],
    )
    return options


def verify_registration(credential: dict, expected_challenge: bytes) -> dict:
    verification = verify_registration_response(
        credential=credential,
        expected_challenge=expected_challenge,
        expected_rp_id=settings.webauthn_rp_id,
        expected_origin=settings.webauthn_origin,
    )
    return {
        "credential_id": verification.credential_id,
        "credential_public_key": verification.credential_public_key,
        "sign_count": verification.sign_count,
    }


def generate_authentication(credentials: list[dict]) -> dict:
    allow_credentials = [
        PublicKeyCredentialDescriptor(id=cred["credential_id"])
        for cred in credentials
    ]
    options = generate_authentication_options(
        rp_id=settings.webauthn_rp_id,
        allow_credentials=allow_credentials,
        user_verification=UserVerificationRequirement.REQUIRED,
    )
    return options


def verify_authentication(
    credential: dict,
    expected_challenge: bytes,
    credential_public_key: bytes,
    credential_current_sign_count: int,
) -> dict:
    verification = verify_authentication_response(
        credential=credential,
        expected_challenge=expected_challenge,
        expected_rp_id=settings.webauthn_rp_id,
        expected_origin=settings.webauthn_origin,
        credential_public_key=credential_public_key,
        credential_current_sign_count=credential_current_sign_count,
    )
    return {"new_sign_count": verification.new_sign_count}

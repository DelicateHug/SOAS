"""Symmetric encryption for user secret values using Fernet (AES-128-CBC + HMAC)."""

from cryptography.fernet import Fernet

from soas_backend.config import settings

_fernet: Fernet | None = None


def _get_fernet() -> Fernet:
    global _fernet
    if _fernet is None:
        _fernet = Fernet(settings.user_secret_encryption_key.encode())
    return _fernet


def encrypt_value(plaintext: str) -> str:
    """Encrypt a plaintext string. Returns a Fernet token (base64 string)."""
    return _get_fernet().encrypt(plaintext.encode()).decode()


def decrypt_value(token: str) -> str:
    """Decrypt a Fernet token back to plaintext."""
    return _get_fernet().decrypt(token.encode()).decode()

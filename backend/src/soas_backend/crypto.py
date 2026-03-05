"""Symmetric encryption for user secret values.

Provides two layers:
1. Server-level Fernet key (AES-128-CBC + HMAC) — used for wrapping DEKs and
   encrypting shared secrets.
2. Per-user DEK (Data Encryption Key) — random Fernet key wrapped by both a
   password-derived KEK and the server key.  Individual secrets are encrypted
   with the user's DEK.
"""

import base64
import logging
import os
from pathlib import Path

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from soas_backend.config import settings

logger = logging.getLogger(__name__)

_fernet: Fernet | None = None

_KEY_FILE = Path(settings.jwt_private_key_path).parent / "user_secret.key"

# ---------------------------------------------------------------------------
# Server-level Fernet (unchanged from original)
# ---------------------------------------------------------------------------


def _get_fernet() -> Fernet:
    global _fernet
    if _fernet is None:
        key = settings.user_secret_encryption_key
        if not key:
            key = _load_or_generate_key()
        _fernet = Fernet(key.encode())
    return _fernet


def _load_or_generate_key() -> str:
    """Load the encryption key from disk, or generate and persist a new one."""
    if _KEY_FILE.exists():
        return _KEY_FILE.read_text().strip()
    _KEY_FILE.parent.mkdir(parents=True, exist_ok=True)
    key = Fernet.generate_key().decode()
    _KEY_FILE.write_text(key)
    logger.info("Generated new user-secret encryption key at %s", _KEY_FILE)
    return key


def encrypt_value(plaintext: str) -> str:
    """Encrypt a plaintext string with the server key. Returns a Fernet token."""
    return _get_fernet().encrypt(plaintext.encode()).decode()


def decrypt_value(token: str) -> str:
    """Decrypt a Fernet token with the server key back to plaintext."""
    return _get_fernet().decrypt(token.encode()).decode()


# ---------------------------------------------------------------------------
# Per-user DEK helpers
# ---------------------------------------------------------------------------

_PBKDF2_ITERATIONS = 600_000


def generate_dek() -> bytes:
    """Generate a random Fernet key to use as a user's DEK."""
    return Fernet.generate_key()


def generate_salt() -> bytes:
    """Generate a random 16-byte salt for PBKDF2 key derivation."""
    return os.urandom(16)


def derive_kek(password: str, salt: bytes) -> bytes:
    """Derive a Fernet-compatible KEK from a password and salt using PBKDF2."""
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=_PBKDF2_ITERATIONS,
    )
    raw = kdf.derive(password.encode())
    return base64.urlsafe_b64encode(raw)


def wrap_dek(dek: bytes, kek: bytes) -> str:
    """Encrypt (wrap) a DEK with a KEK. Returns a Fernet token string."""
    return Fernet(kek).encrypt(dek).decode()


def unwrap_dek(wrapped: str, kek: bytes) -> bytes:
    """Decrypt (unwrap) a DEK using a KEK. Returns the DEK bytes."""
    return Fernet(kek).decrypt(wrapped.encode())


def wrap_dek_server(dek: bytes) -> str:
    """Wrap a DEK with the server Fernet key."""
    return _get_fernet().encrypt(dek).decode()


def unwrap_dek_server(wrapped: str) -> bytes:
    """Unwrap a DEK from the server Fernet key."""
    return _get_fernet().decrypt(wrapped.encode())


def encrypt_with_dek(plaintext: str, dek: bytes) -> str:
    """Encrypt a plaintext string with a user's DEK."""
    return Fernet(dek).encrypt(plaintext.encode()).decode()


def decrypt_with_dek(token: str, dek: bytes) -> str:
    """Decrypt a Fernet token with a user's DEK."""
    return Fernet(dek).decrypt(token.encode()).decode()


def setup_user_dek(password: str) -> tuple[bytes, bytes, str, str]:
    """Generate a new DEK and wrap it with both password KEK and server key.

    Returns (dek, salt, password_wrapped_dek, server_wrapped_dek).
    """
    dek = generate_dek()
    salt = generate_salt()
    kek = derive_kek(password, salt)
    pw_wrapped = wrap_dek(dek, kek)
    srv_wrapped = wrap_dek_server(dek)
    return dek, salt, pw_wrapped, srv_wrapped

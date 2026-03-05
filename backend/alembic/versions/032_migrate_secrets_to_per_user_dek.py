"""Migrate existing secrets to per-user DEK encryption.

For each user: generate a DEK, wrap with server key, re-encrypt all secrets.
Password wrapping is deferred to first login.

Revision ID: 032
Revises: 031
Create Date: 2026-03-05
"""

import os

import sqlalchemy as sa
from alembic import op

revision = "032"
down_revision = "031"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()

    # Load server key
    key = os.environ.get("USER_SECRET_ENCRYPTION_KEY", "")
    if not key:
        key_path = os.environ.get("USER_SECRET_KEY_PATH", "secrets/user_secret.key")
        if os.path.exists(key_path):
            with open(key_path) as f:
                key = f.read().strip()
    if not key:
        # No key available — skip migration (no secrets to re-encrypt)
        return

    from cryptography.fernet import Fernet

    old_fernet = Fernet(key.encode())
    server_fernet = Fernet(key.encode())

    users = conn.execute(sa.text("SELECT id FROM users WHERE server_wrapped_dek IS NULL")).fetchall()
    for user_row in users:
        user_id = user_row[0]
        dek = Fernet.generate_key()
        user_fernet = Fernet(dek)

        # Wrap DEK with server key
        server_wrapped = server_fernet.encrypt(dek).decode()

        conn.execute(
            sa.text("UPDATE users SET server_wrapped_dek = :sw WHERE id = :uid"),
            {"sw": server_wrapped, "uid": user_id},
        )

        # Re-encrypt secrets from old global key to user DEK
        secrets = conn.execute(
            sa.text("SELECT id, encrypted_value FROM user_secrets WHERE user_id = :uid"),
            {"uid": user_id},
        ).fetchall()

        for secret_row in secrets:
            try:
                plaintext = old_fernet.decrypt(secret_row[1].encode())
                new_encrypted = user_fernet.encrypt(plaintext).decode()
                conn.execute(
                    sa.text("UPDATE user_secrets SET encrypted_value = :ev WHERE id = :sid"),
                    {"ev": new_encrypted, "sid": secret_row[0]},
                )
            except Exception:
                pass  # Skip secrets that can't be decrypted


def downgrade() -> None:
    # Cannot reverse re-encryption without storing the old key mapping
    pass

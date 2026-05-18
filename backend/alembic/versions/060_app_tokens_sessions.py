"""App tokens (6h TTL) and 1:1-bound app sessions with IP binding.

Adds the two tables that back the post-OIDC SOAS-minted session model:
- app_tokens: server-issued token (encrypted at rest), 6h default TTL
- app_sessions: 1:1 with an app_token via UNIQUE(app_token_id), holds the
  HMAC session key (Fernet-wrapped) and the originating IP

Revision ID: 060
Revises: 059
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import INET, UUID

revision = "060"
down_revision = "059"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "app_tokens",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token_hash", sa.String(128), unique=True, nullable=False),
        sa.Column("token_ciphertext", sa.Text, nullable=False),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("issued_via", sa.String(32), nullable=False, server_default=sa.text("'local'")),
        sa.Column("oidc_subject", sa.String(255), nullable=True),
    )
    op.create_index("idx_app_tokens_user_expires", "app_tokens", ["user_id", "expires_at"])
    op.create_index(
        "idx_app_tokens_live",
        "app_tokens",
        ["user_id"],
        postgresql_where=sa.text("revoked_at IS NULL"),
    )

    op.create_table(
        "app_sessions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "app_token_id",
            UUID(as_uuid=True),
            sa.ForeignKey("app_tokens.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("session_key_ciphertext", sa.Text, nullable=False),
        sa.Column("ip_address", INET, nullable=False),
        sa.Column("user_agent", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoke_reason", sa.String(64), nullable=True),
    )
    op.create_index("idx_app_sessions_user", "app_sessions", ["user_id"])
    op.create_index(
        "idx_app_sessions_live",
        "app_sessions",
        ["user_id"],
        postgresql_where=sa.text("revoked_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("idx_app_sessions_live", table_name="app_sessions")
    op.drop_index("idx_app_sessions_user", table_name="app_sessions")
    op.drop_table("app_sessions")

    op.drop_index("idx_app_tokens_live", table_name="app_tokens")
    op.drop_index("idx_app_tokens_user_expires", table_name="app_tokens")
    op.drop_table("app_tokens")

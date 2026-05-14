"""Phase 12: per-user client certs, auth provider columns, auth toggles.

- users.auth_provider ("local" | "entra") + users.oidc_subject (Entra `oid`)
- user_certificates table (one active row per user+purpose)
- Seeded app_settings rows for the new auth toggles

Revision ID: 059
Revises: 058
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "059"
down_revision = "058"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. user_certificates table
    op.create_table(
        "user_certificates",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("purpose", sa.String(16), nullable=False, server_default=sa.text("'web'")),
        sa.Column("serial", sa.String(80), nullable=False),
        sa.Column("fingerprint_sha256", sa.String(64), nullable=False, unique=True),
        sa.Column("common_name", sa.String(200), nullable=False),
        sa.Column("cert_pem", sa.Text, nullable=True),
        sa.Column("not_before", sa.DateTime(timezone=True), nullable=False),
        sa.Column("not_after", sa.DateTime(timezone=True), nullable=False),
        sa.Column("issued_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("downloaded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revocation_reason", sa.String(200), nullable=True),
    )
    op.create_index("idx_user_certificates_user", "user_certificates", ["user_id"])
    op.create_index("idx_user_certificates_fingerprint", "user_certificates", ["fingerprint_sha256"])
    op.create_index("idx_user_certificates_serial", "user_certificates", ["serial"])

    # 2. User columns for the OIDC + cert auth model
    op.add_column(
        "users",
        sa.Column(
            "auth_provider",
            sa.String(32),
            nullable=False,
            server_default=sa.text("'local'"),
        ),
    )
    op.add_column(
        "users",
        sa.Column("oidc_subject", sa.String(128), nullable=True),
    )
    op.create_index(
        "uq_users_oidc_subject",
        "users",
        ["oidc_subject"],
        unique=True,
        postgresql_where=sa.text("oidc_subject IS NOT NULL"),
    )

    # 3. Seed the auth toggle defaults so admin UI has something to show.
    #    Skip rows that already exist (re-run safety).
    op.execute(
        """
        INSERT INTO app_settings (key, value, description)
        VALUES
          ('auth_password_enabled', 'true', 'Allow username + password login.'),
          ('auth_cert_login_enabled', 'true', 'Honor client cert presented at the gateway as an auth factor.'),
          ('auth_oidc_enabled', 'false', 'Enable Microsoft Entra OIDC login.'),
          ('auth_oidc_tenant', '', 'Microsoft Entra tenant id (GUID or domain).'),
          ('auth_oidc_client_id', '', 'Microsoft Entra application (client) id.'),
          ('auth_oidc_redirect_uri', '', 'Public callback URL registered with Entra.'),
          ('auth_cae_cache_seconds', '30', 'How long to cache OIDC CAE validity per user.'),
          ('auth_cae_strict', 'true', 'When the CAE endpoint is unreachable: fail closed (true) or open (false).')
        ON CONFLICT (key) DO NOTHING
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DELETE FROM app_settings
        WHERE key IN (
          'auth_password_enabled',
          'auth_cert_login_enabled',
          'auth_oidc_enabled',
          'auth_oidc_tenant',
          'auth_oidc_client_id',
          'auth_oidc_redirect_uri',
          'auth_cae_cache_seconds',
          'auth_cae_strict'
        )
        """
    )
    op.drop_index("uq_users_oidc_subject", table_name="users")
    op.drop_column("users", "oidc_subject")
    op.drop_column("users", "auth_provider")

    op.drop_index("idx_user_certificates_serial", table_name="user_certificates")
    op.drop_index("idx_user_certificates_fingerprint", table_name="user_certificates")
    op.drop_index("idx_user_certificates_user", table_name="user_certificates")
    op.drop_table("user_certificates")

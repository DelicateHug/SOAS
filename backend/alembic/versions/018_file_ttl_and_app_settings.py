"""File TTL support and app_settings key-value store.

Revision ID: 018
Revises: 017
Create Date: 2026-03-04
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "018"
down_revision = "017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- app_settings key-value store ---
    op.create_table(
        "app_settings",
        sa.Column("key", sa.String(200), primary_key=True),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
    )

    # Seed default TTL setting (90 days)
    op.execute(
        "INSERT INTO app_settings (key, value, description) "
        "VALUES ('file_ttl_days', '90', "
        "'Default TTL in days for uploaded incident files. Set to 0 to disable expiration.')"
    )

    # --- Add expires_at column to incident_files ---
    op.add_column(
        "incident_files",
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "idx_incident_files_expires_at",
        "incident_files",
        ["expires_at"],
        postgresql_where=sa.text("expires_at IS NOT NULL AND is_evidence = false"),
    )


def downgrade() -> None:
    op.drop_index("idx_incident_files_expires_at", table_name="incident_files")
    op.drop_column("incident_files", "expires_at")
    op.drop_table("app_settings")

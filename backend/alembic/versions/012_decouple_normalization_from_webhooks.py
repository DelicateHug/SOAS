"""Decouple normalization rules from webhooks - make rules global.

Revision ID: 012
Revises: 011
Create Date: 2026-03-03
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "012"
down_revision = "011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Drop the compound index on (webhook_id, is_enabled)
    op.drop_index(
        "idx_normalization_rules_webhook_enabled",
        table_name="normalization_rules",
    )

    # Drop the foreign key constraint
    op.drop_constraint(
        "normalization_rules_webhook_id_fkey",
        "normalization_rules",
        type_="foreignkey",
    )

    # Drop the webhook_id column
    op.drop_column("normalization_rules", "webhook_id")

    # Create a new index on is_enabled alone
    op.create_index(
        "idx_normalization_rules_enabled",
        "normalization_rules",
        ["is_enabled"],
    )


def downgrade() -> None:
    # Drop the new index
    op.drop_index(
        "idx_normalization_rules_enabled",
        table_name="normalization_rules",
    )

    # Re-add the webhook_id column (nullable since existing rows won't have a value)
    op.add_column(
        "normalization_rules",
        sa.Column("webhook_id", UUID(as_uuid=True), nullable=True),
    )

    # Re-add the foreign key constraint
    op.create_foreign_key(
        "normalization_rules_webhook_id_fkey",
        "normalization_rules",
        "webhooks",
        ["webhook_id"],
        ["id"],
        ondelete="CASCADE",
    )

    # Re-create the compound index
    op.create_index(
        "idx_normalization_rules_webhook_enabled",
        "normalization_rules",
        ["webhook_id", "is_enabled"],
    )

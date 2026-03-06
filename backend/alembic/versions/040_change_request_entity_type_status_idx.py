"""Add composite index on (entity_type, status) to change_requests.

Revision ID: 040
Revises: 039
"""

from alembic import op

revision = "040"
down_revision = "039"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_change_requests_entity_type_status",
        "change_requests",
        ["entity_type", "status"],
    )


def downgrade() -> None:
    op.drop_index("ix_change_requests_entity_type_status", table_name="change_requests")

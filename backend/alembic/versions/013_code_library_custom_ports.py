"""Add custom input/output port definitions to code library blocks.

Revision ID: 013
Revises: 012
Create Date: 2026-03-03
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "013"
down_revision = "012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "code_library_blocks",
        sa.Column("input_ports", postgresql.JSONB(), nullable=True),
    )
    op.add_column(
        "code_library_blocks",
        sa.Column("output_ports", postgresql.JSONB(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("code_library_blocks", "output_ports")
    op.drop_column("code_library_blocks", "input_ports")

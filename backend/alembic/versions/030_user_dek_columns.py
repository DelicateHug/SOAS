"""Add per-user DEK columns for password-derived secret encryption.

Revision ID: 030
Revises: 029
Create Date: 2026-03-05
"""

from alembic import op
import sqlalchemy as sa

revision = "030"
down_revision = "029"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("dek_salt", sa.LargeBinary(), nullable=True))
    op.add_column("users", sa.Column("password_wrapped_dek", sa.Text(), nullable=True))
    op.add_column("users", sa.Column("server_wrapped_dek", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "server_wrapped_dek")
    op.drop_column("users", "password_wrapped_dek")
    op.drop_column("users", "dek_salt")

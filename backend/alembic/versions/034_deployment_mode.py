"""Add deployment_mode app setting (dev/production).

Revision ID: 034
Revises: 033
Create Date: 2026-03-05
"""

from alembic import op

revision = "034"
down_revision = "033"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        INSERT INTO app_settings (key, value, description)
        VALUES ('deployment_mode', 'development', 'Deployment mode: development or production. Production mode restricts editing — changes must come via git sync.')
        ON CONFLICT (key) DO NOTHING
    """)


def downgrade() -> None:
    op.execute("DELETE FROM app_settings WHERE key = 'deployment_mode'")

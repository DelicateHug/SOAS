"""Phase 5: sla_definitions + sla_snapshots, with three system defaults.

Revision ID: 050
Revises: 049
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "050"
down_revision = "049"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "sla_definitions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("key", sa.String(64), nullable=False, unique=True),
        sa.Column("label", sa.String(200), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("start_column", sa.String(32), nullable=False, server_default=sa.text("'created_at'")),
        sa.Column("end_column", sa.String(32), nullable=False, server_default=sa.text("'resolved_at'")),
        sa.Column("target_seconds", sa.Integer, nullable=False),
        sa.Column("dimension", sa.String(32), nullable=False, server_default=sa.text("'(global)'")),
        sa.Column("is_enabled", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "sla_snapshots",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("sla_key", sa.String(64), nullable=False),
        sa.Column("dim_value", sa.String(200), nullable=False, server_default=sa.text("'(global)'")),
        sa.Column("captured_for", sa.Date, nullable=False),
        sa.Column("total_count", sa.Integer, nullable=False, server_default=sa.text("0")),
        sa.Column("compliant_count", sa.Integer, nullable=False, server_default=sa.text("0")),
        sa.Column("compliance_pct", sa.Float, nullable=False, server_default=sa.text("0")),
        sa.Column("p50_seconds", sa.Float, nullable=True),
        sa.Column("p95_seconds", sa.Float, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("sla_key", "dim_value", "captured_for", name="uq_sla_snapshot_day"),
    )
    op.create_index("idx_sla_snapshots_key_day", "sla_snapshots", ["sla_key", "captured_for"])

    # Seed three classic SLAs: MTTI (time to investigate), MTTR (time to resolve),
    # MTTA (time to close). These map to the columns already on the incidents table.
    op.execute("""
        INSERT INTO sla_definitions (key, label, description, start_column, end_column, target_seconds, dimension)
        VALUES
          ('mtti', 'MTTI — time to investigate', 'Detection to investigation start', 'created_at', 'detected_at', 900, 'severity'),
          ('mttr', 'MTTR — time to resolve', 'Creation to resolution', 'created_at', 'resolved_at', 14400, 'severity'),
          ('mtta', 'MTTA — time to acknowledge / close', 'Creation to close', 'created_at', 'closed_at', 86400, 'severity')
        ON CONFLICT (key) DO NOTHING
    """)


def downgrade() -> None:
    op.drop_index("idx_sla_snapshots_key_day", table_name="sla_snapshots")
    op.drop_table("sla_snapshots")
    op.drop_table("sla_definitions")

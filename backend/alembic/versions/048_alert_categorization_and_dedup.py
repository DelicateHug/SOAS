"""Phase 3: alert_categories, alert_category_rules, incident_templates;
incidents.category_key and incidents.parent_incident_id columns.

Revision ID: 048
Revises: 047
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "048"
down_revision = "047"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "alert_categories",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("key", sa.String(64), nullable=False, unique=True),
        sa.Column("label", sa.String(200), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("default_severity", sa.String(20), nullable=True),
        sa.Column("default_priority", sa.String(20), nullable=True),
        sa.Column("default_automation_id", UUID(as_uuid=True), sa.ForeignKey("automations.id", ondelete="SET NULL"), nullable=True),
        sa.Column("is_system", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("sort_order", sa.Integer, nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "alert_category_rules",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("category_id", UUID(as_uuid=True), sa.ForeignKey("alert_categories.id", ondelete="CASCADE"), nullable=False),
        sa.Column("field", sa.String(200), nullable=False),
        sa.Column("pattern", sa.Text, nullable=False),
        sa.Column("case_sensitive", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("is_enabled", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("sort_order", sa.Integer, nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("idx_alert_category_rules_category", "alert_category_rules", ["category_id"])

    op.create_table(
        "incident_templates",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String(200), nullable=False, unique=True),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("defaults", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # Incident columns for category + dedup parent link
    op.add_column("incidents", sa.Column("category_key", sa.String(64), nullable=True))
    op.add_column(
        "incidents",
        sa.Column("parent_incident_id", UUID(as_uuid=True), sa.ForeignKey("incidents.id", ondelete="SET NULL"), nullable=True),
    )
    op.create_index("idx_incidents_category", "incidents", ["category_key"])
    op.create_index("idx_incidents_parent", "incidents", ["parent_incident_id"])

    # Seed a handful of system categories matching case-managment's buckets.
    op.execute("""
        INSERT INTO alert_categories (key, label, description, is_system, sort_order)
        VALUES
          ('powershell_lotl', 'PowerShell LotL', 'Living-off-the-land PowerShell activity', true, 10),
          ('brute_force_auth', 'Brute-force authentication', 'Repeated failed logins / password spray', true, 20),
          ('lateral_movement', 'Lateral movement', 'East-west traversal between hosts or accounts', true, 30),
          ('malware_endpoint', 'Malware on endpoint', 'EDR-flagged malicious binary or process tree', true, 40),
          ('data_exfiltration', 'Data exfiltration', 'Outbound transfer of sensitive data', true, 50),
          ('network_firewall', 'Network / firewall', 'Suspicious network connection or firewall hit', true, 60),
          ('impossible_travel', 'Impossible travel', 'Identity sign-ins from geographically impossible locations', true, 70),
          ('other', 'Other / uncategorized', 'Did not match any classifier rule', true, 999)
        ON CONFLICT (key) DO NOTHING
    """)


def downgrade() -> None:
    op.drop_index("idx_incidents_parent", table_name="incidents")
    op.drop_index("idx_incidents_category", table_name="incidents")
    op.drop_column("incidents", "parent_incident_id")
    op.drop_column("incidents", "category_key")
    op.drop_table("incident_templates")
    op.drop_index("idx_alert_category_rules_category", table_name="alert_category_rules")
    op.drop_table("alert_category_rules")
    op.drop_table("alert_categories")

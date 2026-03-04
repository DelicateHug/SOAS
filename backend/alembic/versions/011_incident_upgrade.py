"""Incident upgrade: notes, files, evidence, webhook sources, source automations.

Revision ID: 011
Revises: 010
Create Date: 2026-03-03
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "011"
down_revision = "010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- webhook_sources ---
    op.create_table(
        "webhook_sources",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String(200), unique=True, nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("icon", sa.String(100), nullable=True),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # --- source_automations ---
    op.create_table(
        "source_automations",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("source_id", UUID(as_uuid=True), sa.ForeignKey("webhook_sources.id", ondelete="CASCADE"), nullable=False),
        sa.Column("automation_id", UUID(as_uuid=True), sa.ForeignKey("automations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("run_order", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("source_id", "automation_id", name="uq_source_automation"),
    )
    op.create_index("idx_source_automations_source", "source_automations", ["source_id"])

    # --- incident_notes ---
    op.create_table(
        "incident_notes",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("incident_id", UUID(as_uuid=True), sa.ForeignKey("incidents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("is_evidence", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("updated_by", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("idx_incident_notes_incident", "incident_notes", ["incident_id"])
    op.create_index("idx_incident_notes_evidence", "incident_notes", ["incident_id", "is_evidence"])

    # --- incident_files ---
    op.create_table(
        "incident_files",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("incident_id", UUID(as_uuid=True), sa.ForeignKey("incidents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("filename", sa.String(500), nullable=False),
        sa.Column("storage_path", sa.String(1000), nullable=False),
        sa.Column("content_type", sa.String(200), nullable=False),
        sa.Column("file_size", sa.BigInteger(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_evidence", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("uploaded_by", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("idx_incident_files_incident", "incident_files", ["incident_id"])
    op.create_index("idx_incident_files_evidence", "incident_files", ["incident_id", "is_evidence"])

    # --- Add is_evidence to timeline_entries ---
    op.add_column(
        "timeline_entries",
        sa.Column("is_evidence", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )

    # --- Add source_id to webhooks ---
    op.add_column(
        "webhooks",
        sa.Column("source_id", UUID(as_uuid=True), sa.ForeignKey("webhook_sources.id", ondelete="SET NULL"), nullable=True),
    )

    # --- Seed RBAC permissions ---
    op.execute("""
        INSERT INTO permissions (id, resource, action, description)
        VALUES
            (gen_random_uuid(), 'incident_note', 'create', 'Create incident notes'),
            (gen_random_uuid(), 'incident_note', 'read', 'View incident notes'),
            (gen_random_uuid(), 'incident_note', 'update', 'Update incident notes'),
            (gen_random_uuid(), 'incident_note', 'delete', 'Delete incident notes'),
            (gen_random_uuid(), 'incident_file', 'upload', 'Upload incident files'),
            (gen_random_uuid(), 'incident_file', 'read', 'View incident files'),
            (gen_random_uuid(), 'incident_file', 'delete', 'Delete incident files'),
            (gen_random_uuid(), 'webhook_source', 'create', 'Create webhook sources'),
            (gen_random_uuid(), 'webhook_source', 'read', 'View webhook sources'),
            (gen_random_uuid(), 'webhook_source', 'update', 'Update webhook sources'),
            (gen_random_uuid(), 'webhook_source', 'delete', 'Delete webhook sources')
        ON CONFLICT (resource, action) DO NOTHING
    """)

    # Grant all new permissions to admin
    op.execute("""
        INSERT INTO role_permissions (role_id, permission_id)
        SELECT r.id, p.id
        FROM roles r
        CROSS JOIN permissions p
        WHERE r.name = 'admin'
          AND p.resource IN ('incident_note', 'incident_file', 'webhook_source')
        ON CONFLICT DO NOTHING
    """)

    # Grant note/file read + create to SOC analyst roles
    op.execute("""
        INSERT INTO role_permissions (role_id, permission_id)
        SELECT r.id, p.id
        FROM roles r
        CROSS JOIN permissions p
        WHERE r.name IN ('soc_analyst_l1', 'soc_analyst_l2', 'soc_analyst_l3', 'soc_manager')
          AND (
              (p.resource IN ('incident_note', 'incident_file') AND p.action IN ('read', 'create'))
              OR (p.resource = 'incident_file' AND p.action = 'upload')
              OR (p.resource = 'incident_note' AND p.action = 'update')
              OR (p.resource = 'webhook_source' AND p.action = 'read')
          )
        ON CONFLICT DO NOTHING
    """)

    # Grant delete to L2+ analysts and managers
    op.execute("""
        INSERT INTO role_permissions (role_id, permission_id)
        SELECT r.id, p.id
        FROM roles r
        CROSS JOIN permissions p
        WHERE r.name IN ('soc_analyst_l2', 'soc_analyst_l3', 'soc_manager')
          AND p.resource IN ('incident_note', 'incident_file')
          AND p.action = 'delete'
        ON CONFLICT DO NOTHING
    """)


def downgrade() -> None:
    op.drop_column("webhooks", "source_id")
    op.drop_column("timeline_entries", "is_evidence")
    op.drop_index("idx_incident_files_evidence", table_name="incident_files")
    op.drop_index("idx_incident_files_incident", table_name="incident_files")
    op.drop_table("incident_files")
    op.drop_index("idx_incident_notes_evidence", table_name="incident_notes")
    op.drop_index("idx_incident_notes_incident", table_name="incident_notes")
    op.drop_table("incident_notes")
    op.drop_index("idx_source_automations_source", table_name="source_automations")
    op.drop_table("source_automations")
    op.drop_table("webhook_sources")
    op.execute("""
        DELETE FROM permissions WHERE resource IN ('incident_note', 'incident_file', 'webhook_source')
    """)

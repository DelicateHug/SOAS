"""Add form definitions and form submissions tables.

Revision ID: 016
Revises: 015
Create Date: 2026-03-04
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "016"
down_revision = "015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- form_definitions ---
    op.create_table(
        "form_definitions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String(300), unique=True, nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("fields", JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("updated_by", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("idx_form_definitions_name", "form_definitions", ["name"])
    op.create_index("idx_form_definitions_active", "form_definitions", ["is_active"])

    # --- form_submissions ---
    op.create_table(
        "form_submissions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("incident_id", UUID(as_uuid=True), sa.ForeignKey("incidents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("form_definition_id", UUID(as_uuid=True), sa.ForeignKey("form_definitions.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("data", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("is_evidence", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("submitted_by", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("idx_form_submissions_incident", "form_submissions", ["incident_id"])
    op.create_index("idx_form_submissions_form", "form_submissions", ["form_definition_id"])
    op.create_index("idx_form_submissions_evidence", "form_submissions", ["incident_id", "is_evidence"])

    # --- Seed RBAC permissions ---
    op.execute("""
        INSERT INTO permissions (id, resource, action, description)
        VALUES
            (gen_random_uuid(), 'form_definition', 'create', 'Create form definitions'),
            (gen_random_uuid(), 'form_definition', 'read', 'View form definitions'),
            (gen_random_uuid(), 'form_definition', 'update', 'Update form definitions'),
            (gen_random_uuid(), 'form_definition', 'delete', 'Delete form definitions'),
            (gen_random_uuid(), 'form_submission', 'create', 'Submit forms on incidents'),
            (gen_random_uuid(), 'form_submission', 'read', 'View form submissions'),
            (gen_random_uuid(), 'form_submission', 'update', 'Update form submissions'),
            (gen_random_uuid(), 'form_submission', 'delete', 'Delete form submissions')
        ON CONFLICT (resource, action) DO NOTHING
    """)

    # Grant all to admin
    op.execute("""
        INSERT INTO role_permissions (role_id, permission_id)
        SELECT r.id, p.id
        FROM roles r
        CROSS JOIN permissions p
        WHERE r.name = 'admin'
          AND p.resource IN ('form_definition', 'form_submission')
        ON CONFLICT DO NOTHING
    """)

    # Grant form_definition read + form_submission read/create to SOC analyst roles
    op.execute("""
        INSERT INTO role_permissions (role_id, permission_id)
        SELECT r.id, p.id
        FROM roles r
        CROSS JOIN permissions p
        WHERE r.name IN ('soc_analyst_l1', 'soc_analyst_l2', 'soc_analyst_l3', 'soc_manager')
          AND (
              (p.resource = 'form_definition' AND p.action = 'read')
              OR (p.resource = 'form_submission' AND p.action IN ('read', 'create'))
          )
        ON CONFLICT DO NOTHING
    """)

    # Grant form_submission update (evidence toggle) and delete to L2+
    op.execute("""
        INSERT INTO role_permissions (role_id, permission_id)
        SELECT r.id, p.id
        FROM roles r
        CROSS JOIN permissions p
        WHERE r.name IN ('soc_analyst_l2', 'soc_analyst_l3', 'soc_manager')
          AND p.resource = 'form_submission'
          AND p.action IN ('update', 'delete')
        ON CONFLICT DO NOTHING
    """)


def downgrade() -> None:
    op.drop_index("idx_form_submissions_evidence", table_name="form_submissions")
    op.drop_index("idx_form_submissions_form", table_name="form_submissions")
    op.drop_index("idx_form_submissions_incident", table_name="form_submissions")
    op.drop_table("form_submissions")
    op.drop_index("idx_form_definitions_active", table_name="form_definitions")
    op.drop_index("idx_form_definitions_name", table_name="form_definitions")
    op.drop_table("form_definitions")
    op.execute("DELETE FROM permissions WHERE resource IN ('form_definition', 'form_submission')")

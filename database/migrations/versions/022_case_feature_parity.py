"""Case feature parity: notes, files, form submissions tables + RBAC.

Revision ID: 022
Revises: 021
Create Date: 2026-03-04
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "022"
down_revision = "021"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- case_notes ---
    op.create_table(
        "case_notes",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "case_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("cases.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("is_evidence", sa.Boolean(), server_default="false", nullable=False),
        sa.Column(
            "created_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column(
            "updated_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("idx_case_notes_case", "case_notes", ["case_id"])
    op.create_index("idx_case_notes_evidence", "case_notes", ["case_id", "is_evidence"])

    # --- case_files ---
    op.create_table(
        "case_files",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "case_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("cases.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("filename", sa.String(500), nullable=False),
        sa.Column("storage_path", sa.String(1000), nullable=False),
        sa.Column("content_type", sa.String(200), nullable=False),
        sa.Column("file_size", sa.BigInteger(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_evidence", sa.Boolean(), server_default="false", nullable=False),
        sa.Column(
            "uploaded_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("idx_case_files_case", "case_files", ["case_id"])
    op.create_index("idx_case_files_evidence", "case_files", ["case_id", "is_evidence"])

    # --- case_form_submissions ---
    op.create_table(
        "case_form_submissions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "case_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("cases.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "form_definition_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("form_definitions.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("data", postgresql.JSONB(), server_default="{}", nullable=False),
        sa.Column("is_evidence", sa.Boolean(), server_default="false", nullable=False),
        sa.Column(
            "submitted_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("idx_case_form_submissions_case", "case_form_submissions", ["case_id"])
    op.create_index(
        "idx_case_form_submissions_form", "case_form_submissions", ["form_definition_id"]
    )
    op.create_index(
        "idx_case_form_submissions_evidence",
        "case_form_submissions",
        ["case_id", "is_evidence"],
    )

    # --- Index on execution_logs.case_id (column already exists) ---
    op.create_index("idx_executions_case", "execution_logs", ["case_id"])

    # --- Seed RBAC permissions ---
    op.execute(
        """
        INSERT INTO permissions (id, resource, action, description) VALUES
            (gen_random_uuid(), 'case_note', 'create', 'Create case notes'),
            (gen_random_uuid(), 'case_note', 'read',   'View case notes'),
            (gen_random_uuid(), 'case_note', 'update', 'Update case notes'),
            (gen_random_uuid(), 'case_note', 'delete', 'Delete case notes'),
            (gen_random_uuid(), 'case_file', 'read',   'View case files'),
            (gen_random_uuid(), 'case_file', 'upload', 'Upload case files'),
            (gen_random_uuid(), 'case_file', 'delete', 'Delete case files'),
            (gen_random_uuid(), 'case_form_submission', 'create', 'Submit case forms'),
            (gen_random_uuid(), 'case_form_submission', 'read',   'View case form submissions'),
            (gen_random_uuid(), 'case_form_submission', 'delete', 'Delete case form submissions')
        ON CONFLICT (resource, action) DO NOTHING
        """
    )

    # Grant all case_note / case_file / case_form_submission to admin + soc_manager
    op.execute(
        """
        INSERT INTO role_permissions (role_id, permission_id)
        SELECT r.id, p.id
        FROM roles r
        CROSS JOIN permissions p
        WHERE r.name IN ('admin', 'soc_manager')
          AND p.resource IN ('case_note', 'case_file', 'case_form_submission')
        ON CONFLICT DO NOTHING
        """
    )

    # Grant CRUD (except delete) to analyst roles
    op.execute(
        """
        INSERT INTO role_permissions (role_id, permission_id)
        SELECT r.id, p.id
        FROM roles r
        CROSS JOIN permissions p
        WHERE r.name IN ('soc_analyst_l1', 'soc_analyst_l2', 'soc_analyst_l3')
          AND p.resource IN ('case_note', 'case_file', 'case_form_submission')
          AND p.action NOT IN ('delete')
        ON CONFLICT DO NOTHING
        """
    )

    # Grant read-only to viewer
    op.execute(
        """
        INSERT INTO role_permissions (role_id, permission_id)
        SELECT r.id, p.id
        FROM roles r
        CROSS JOIN permissions p
        WHERE r.name = 'viewer'
          AND p.resource IN ('case_note', 'case_file', 'case_form_submission')
          AND p.action = 'read'
        ON CONFLICT DO NOTHING
        """
    )


def downgrade() -> None:
    # Remove role_permissions
    op.execute(
        """
        DELETE FROM role_permissions
        WHERE permission_id IN (
            SELECT id FROM permissions
            WHERE resource IN ('case_note', 'case_file', 'case_form_submission')
        )
        """
    )
    op.execute(
        "DELETE FROM permissions WHERE resource IN ('case_note', 'case_file', 'case_form_submission')"
    )

    op.drop_index("idx_executions_case", table_name="execution_logs")

    op.drop_index("idx_case_form_submissions_evidence", table_name="case_form_submissions")
    op.drop_index("idx_case_form_submissions_form", table_name="case_form_submissions")
    op.drop_index("idx_case_form_submissions_case", table_name="case_form_submissions")
    op.drop_table("case_form_submissions")

    op.drop_index("idx_case_files_evidence", table_name="case_files")
    op.drop_index("idx_case_files_case", table_name="case_files")
    op.drop_table("case_files")

    op.drop_index("idx_case_notes_evidence", table_name="case_notes")
    op.drop_index("idx_case_notes_case", table_name="case_notes")
    op.drop_table("case_notes")

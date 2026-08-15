"""Re-grant SOC analyst L1/L2/L3 roles to match the three case-management tiers.

- Tier 1 (L1): Read + comment. Read everywhere they need to see, plus add notes on
  cases and incidents. No status changes, no playbooks.
- Tier 2 (L2): Status + playbooks. Update cases/incidents, run automations, upload files,
  mark evidence, fill forms. Cannot delete or change settings.
- Tier 3 (L3): Settings + danger zone. Delete cases/notes/files, manage automations and
  variables, manage webhooks, view roles/teams/users. Stops short of admin.

Also seeds case_note and case_file permissions which are referenced by route handlers
but were never inserted by migration 001 (they were added piecemeal in later migrations
for some resources and missed for others).

Revision ID: 061
Revises: 060
"""

from alembic import op

revision = "061"
down_revision = "060"
branch_labels = None
depends_on = None


# ---------------------------------------------------------------------------
# Tier definitions — each tier is the union of the previous tier plus its own delta
# ---------------------------------------------------------------------------

_T1_PERMS = [
    ("case", "read"),
    ("case_note", "read"),
    ("case_note", "create"),
    ("case_file", "read"),
    ("incident", "read"),
    ("incident_note", "read"),
    ("incident_note", "create"),
    ("timeline", "read"),
    ("wiki", "read"),
    ("dashboard", "read"),
    ("execution", "read"),
    ("automation", "read"),
]

_T2_DELTA = [
    ("case", "create"),
    ("case", "update"),
    ("case_note", "update"),
    ("case_file", "upload"),
    ("incident", "update"),
    ("incident", "assign"),
    ("automation", "execute"),
    ("case_form_submission", "create"),
    ("incident_form_submission", "create"),
    ("timeline", "create"),
]

_T3_DELTA = [
    ("case", "delete"),
    ("case_note", "delete"),
    ("case_file", "delete"),
    ("automation", "create"),
    ("automation", "update"),
    ("automation", "delete"),
    ("soas_variable", "read"),
    ("soas_variable", "create"),
    ("soas_variable", "update"),
    ("soas_variable", "delete"),
    ("webhook", "read"),
    ("webhook", "create"),
    ("webhook", "update"),
    ("webhook", "delete"),
    ("role", "read"),
    ("team", "read"),
    ("team", "create"),
    ("user", "read"),
    ("execution", "cancel"),
]


def _t2_perms() -> list[tuple[str, str]]:
    return _T1_PERMS + _T2_DELTA


def _t3_perms() -> list[tuple[str, str]]:
    return _T1_PERMS + _T2_DELTA + _T3_DELTA


def _values_clause(perms: list[tuple[str, str]]) -> str:
    return ", ".join(f"('{r}', '{a}')" for r, a in perms)


def _all_referenced_perms() -> list[tuple[str, str]]:
    """Every (resource, action) referenced by any tier — used to ensure they all exist."""
    seen: set[tuple[str, str]] = set()
    for p in _t3_perms():
        seen.add(p)
    return sorted(seen)


def upgrade() -> None:
    # 1. Make sure every permission referenced below exists. Most do (from 001); the
    #    case_note / case_file / incident_note / wiki / form_submission / etc. ones may
    #    have been added piecemeal elsewhere or not at all.
    values = ", ".join(
        f"(gen_random_uuid(), '{r}', '{a}', 'auto-seeded by tier rework')"
        for r, a in _all_referenced_perms()
    )
    op.execute(
        f"""
        INSERT INTO permissions (id, resource, action, description) VALUES
        {values}
        ON CONFLICT (resource, action) DO NOTHING
        """
    )

    # 2. Wipe existing grants for the three tier roles. Custom roles untouched.
    op.execute(
        """
        DELETE FROM role_permissions
        WHERE role_id IN (
            SELECT id FROM roles
            WHERE name IN ('soc_analyst_l1', 'soc_analyst_l2', 'soc_analyst_l3')
        )
        """
    )

    # 3. Re-insert grants per tier.
    for role_name, perms in (
        ("soc_analyst_l1", _T1_PERMS),
        ("soc_analyst_l2", _t2_perms()),
        ("soc_analyst_l3", _t3_perms()),
    ):
        values = _values_clause(perms)
        op.execute(
            f"""
            INSERT INTO role_permissions (role_id, permission_id)
            SELECT r.id, p.id
            FROM roles r
            JOIN permissions p ON (p.resource, p.action) IN ({values})
            WHERE r.name = '{role_name}'
            ON CONFLICT DO NOTHING
            """
        )


def downgrade() -> None:
    # Restore the migration-001 grants for the three analyst tiers.
    op.execute(
        """
        DELETE FROM role_permissions
        WHERE role_id IN (
            SELECT id FROM roles
            WHERE name IN ('soc_analyst_l1', 'soc_analyst_l2', 'soc_analyst_l3')
        )
        """
    )
    op.execute(
        """
        INSERT INTO role_permissions (role_id, permission_id)
        SELECT r.id, p.id FROM roles r CROSS JOIN permissions p
        WHERE r.name = 'soc_analyst_l3'
          AND p.resource IN ('incident', 'case', 'automation', 'execution', 'timeline', 'dashboard')
        ON CONFLICT DO NOTHING
        """
    )
    op.execute(
        """
        INSERT INTO role_permissions (role_id, permission_id)
        SELECT r.id, p.id FROM roles r CROSS JOIN permissions p
        WHERE r.name = 'soc_analyst_l2'
          AND (
            (p.resource = 'incident' AND p.action IN ('create', 'read', 'update', 'assign'))
            OR (p.resource = 'case' AND p.action IN ('create', 'read', 'update'))
            OR (p.resource = 'automation' AND p.action IN ('read', 'execute'))
            OR (p.resource = 'execution' AND p.action = 'read')
            OR (p.resource = 'timeline' AND p.action IN ('create', 'read'))
            OR (p.resource = 'dashboard' AND p.action = 'read')
          )
        ON CONFLICT DO NOTHING
        """
    )
    op.execute(
        """
        INSERT INTO role_permissions (role_id, permission_id)
        SELECT r.id, p.id FROM roles r CROSS JOIN permissions p
        WHERE r.name = 'soc_analyst_l1'
          AND (
            (p.resource = 'incident' AND p.action IN ('create', 'read'))
            OR (p.resource = 'case' AND p.action = 'read')
            OR (p.resource = 'automation' AND p.action = 'read')
            OR (p.resource = 'execution' AND p.action = 'read')
            OR (p.resource = 'timeline' AND p.action = 'read')
            OR (p.resource = 'dashboard' AND p.action = 'read')
          )
        ON CONFLICT DO NOTHING
        """
    )

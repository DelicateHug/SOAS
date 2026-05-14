"""Seed data module - populates default wiki pages, variables, secrets, and automations.

Runs on startup (idempotent). Uses app_settings.seed_version to track state.
"""

import logging
import os
import uuid
from pathlib import Path
from uuid import UUID

import yaml
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from soas_backend.database import async_session
from soas_backend.models.app_setting import AppSetting
from soas_backend.models.automation import Automation
from soas_backend.models.incident_variable import IncidentVariable
from soas_backend.models.user import User
from soas_backend.models.user_secret import UserSecret
from soas_backend.models.wiki import WikiPage
from soas_backend.services.automation_service import AutomationService
from soas_backend.services.incident_variable_service import IncidentVariableService
from soas_backend.services.user_secret_service import UserSecretService
from soas_backend.services.wiki_service import WikiService

logger = logging.getLogger(__name__)

CURRENT_SEED_VERSION = "3"


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

async def seed_defaults() -> None:
    """Run all seed functions if not already seeded.

    The MCP bot + service token seeder always runs regardless of seed_version, because
    rotating the token (e.g. operator deletes the secret file) shouldn't require bumping
    the version. It's idempotent and cheap.
    """
    async with async_session() as db:
        # Always-on: ensure the MCP bot exists and a token is available on disk for the
        # MCP container. Runs in its own try/except so a one-off failure never blocks
        # other seeding.
        try:
            await _seed_mcp_bot_safe(db)
            await db.commit()
        except Exception:
            await db.rollback()
            logger.warning("MCP bot seeding failed (non-fatal)", exc_info=True)

        try:
            result = await db.execute(
                select(AppSetting).where(AppSetting.key == "seed_version")
            )
            setting = result.scalar_one_or_none()

            if setting and setting.value >= CURRENT_SEED_VERSION:
                logger.info("Seed data already applied (v%s), skipping.", setting.value)
                return

            # Need at least one user for created_by references
            admin_result = await db.execute(
                select(User).order_by(User.created_at).limit(1)
            )
            admin_user = admin_result.scalar_one_or_none()
            if not admin_user:
                logger.info("No users yet - seeding deferred until first user registers.")
                return

            uid = admin_user.id
            logger.info("Seeding default data (created_by=%s)...", admin_user.username)

            await _seed_wiki_pages(db, uid)
            await _seed_incident_variables(db, uid)
            await _seed_user_secrets(db, uid)
            await _seed_automations(db, uid)
            await _seed_login_security_settings(db)

            # Mark seed version
            if setting:
                setting.value = CURRENT_SEED_VERSION
            else:
                db.add(AppSetting(
                    key="seed_version",
                    value=CURRENT_SEED_VERSION,
                    description="Tracks which seed data version has been applied",
                ))

            await db.commit()
            logger.info("Seed data applied successfully (v%s).", CURRENT_SEED_VERSION)
        except Exception:
            await db.rollback()
            logger.exception("Failed to apply seed data")


# ---------------------------------------------------------------------------
# MCP bot + service token (always-on, idempotent)
# ---------------------------------------------------------------------------

async def _seed_mcp_bot_safe(db: AsyncSession) -> None:
    """Wrap the MCP bot seeder. Imported here to avoid a hard dependency on the seed_mcp
    module at import time of seed.py — if the MCP module is removed in some deployment,
    seeding still works."""
    try:
        from soas_backend.seed_mcp import seed_mcp_bot
    except ImportError:
        logger.info("seed_mcp module unavailable; skipping MCP bot seed.")
        return
    raw = await seed_mcp_bot(db)
    if raw:
        # Operators see the token in container logs — safe in dev, redact in prod logs.
        logger.info("MCP service token issued. First chars: %s…", raw[:12])


# ---------------------------------------------------------------------------
# Login security settings
# ---------------------------------------------------------------------------

async def _seed_login_security_settings(db: AsyncSession) -> None:
    """Seed default login security app_settings (idempotent)."""
    defaults = [
        ("max_failed_login_attempts", "5", "Max failed login attempts before lockout (0 = no lockout)"),
        ("failed_login_lockout_minutes", "30", "Minutes to lock an account after max failed attempts"),
    ]
    for key, value, description in defaults:
        existing = await db.execute(
            select(AppSetting).where(AppSetting.key == key)
        )
        if existing.scalar_one_or_none() is None:
            db.add(AppSetting(key=key, value=value, description=description))
    await db.flush()


# ---------------------------------------------------------------------------
# Wiki pages - loaded from wiki/ directory
# ---------------------------------------------------------------------------

WIKI_DIR = Path(os.environ.get("WIKI_DIR", "/app/wiki"))


def _load_wiki_pages() -> tuple[list[dict], list[dict], list[dict]]:
    """Load wiki pages from markdown files with YAML frontmatter.

    Returns (app_pages, category_pages, node_pages).
    """
    app_pages: list[dict] = []
    category_pages: list[dict] = []
    node_pages: list[dict] = []

    subdirs = {"app": app_pages, "categories": category_pages, "nodes": node_pages}

    for subdir, target_list in subdirs.items():
        folder = WIKI_DIR / subdir
        if not folder.exists():
            logger.warning("Wiki seed folder not found: %s", folder)
            continue
        for md_file in sorted(folder.glob("*.md")):
            text = md_file.read_text(encoding="utf-8")
            page = _parse_wiki_file(text)
            if page:
                target_list.append(page)

    return app_pages, category_pages, node_pages


def _parse_wiki_file(text: str) -> dict | None:
    """Parse a markdown file with YAML frontmatter into a page dict."""
    if not text.startswith("---"):
        return None
    parts = text.split("---", 2)
    if len(parts) < 3:
        return None
    meta = yaml.safe_load(parts[1])
    if not meta or "slug" not in meta:
        return None
    content = parts[2].strip()
    return {
        "title": meta.get("title", ""),
        "slug": meta["slug"],
        "content": content,
        "icon": meta.get("icon"),
        "tags": meta.get("tags", []),
        "parent_slug": meta.get("parent_slug"),
        "linked_node_type": meta.get("linked_node_type"),
    }



# ---------------------------------------------------------------------------
# Incident variables
# ---------------------------------------------------------------------------

_INCIDENT_VARIABLES: list[dict] = [
    {"name": "severity_override", "description": "Override the auto-detected severity level", "default_enabled": True, "sensitive": False},
    {"name": "analyst_notes", "description": "Free-form notes from the assigned analyst", "default_enabled": True, "sensitive": False},
    {"name": "escalation_level", "description": "Current escalation tier (1-3)", "default_enabled": True, "sensitive": False},
    {"name": "triage_verdict", "description": "Triage outcome: true_positive, false_positive, benign", "default_enabled": True, "sensitive": False},
    {"name": "affected_hosts", "description": "Comma-separated list of affected hostnames/IPs", "default_enabled": True, "sensitive": False},
    {"name": "containment_status", "description": "Whether containment actions have been taken", "default_enabled": False, "sensitive": False},
    {"name": "ioc_indicators", "description": "Indicators of compromise discovered during analysis", "default_enabled": False, "sensitive": False},
    {"name": "remediation_steps", "description": "Steps taken or planned for remediation", "default_enabled": False, "sensitive": False},
]


# ---------------------------------------------------------------------------
# User secrets
# ---------------------------------------------------------------------------

_USER_SECRETS: list[dict] = [
    {"name": "EXAMPLE_API_KEY", "description": "Example API key for testing HTTP Request nodes (replace with real value)", "value": "replace-me", "sensitive": True},
    {"name": "WEBHOOK_SECRET", "description": "Secret for webhook signature verification", "value": "replace-me", "sensitive": True},
    {"name": "VIRUSTOTAL_API_KEY", "description": "VirusTotal API key for threat intelligence lookups", "value": "", "sensitive": True},
    {"name": "SLACK_WEBHOOK_URL", "description": "Slack webhook URL for notifications", "value": "", "sensitive": False},
]


# ---------------------------------------------------------------------------
# Automations
# ---------------------------------------------------------------------------

def _make_id() -> str:
    return str(uuid.uuid4())


def _hello_world_graph() -> dict:
    start_id = _make_id()
    print_id = _make_id()
    end_id = _make_id()
    return {
        "metadata": {"name": "Hello World", "description": "Simple example automation", "version": 1},
        "nodes": [
            {"id": start_id, "type": "start", "name": "Start", "position": {"x": 100, "y": 200}, "properties": {}, "input_ports": [], "output_ports": [{"name": "exec_out", "type": "FLOW"}]},
            {"id": print_id, "type": "print", "name": "Print Greeting", "position": {"x": 400, "y": 200}, "properties": {"message": "Hello from SOC on a Stick!"}, "input_ports": [{"name": "exec_in", "type": "FLOW"}, {"name": "value", "type": "ANY"}], "output_ports": [{"name": "exec_out", "type": "FLOW"}]},
            {"id": end_id, "type": "end", "name": "End", "position": {"x": 700, "y": 200}, "properties": {}, "input_ports": [{"name": "exec_in", "type": "FLOW"}, {"name": "result", "type": "ANY"}], "output_ports": []},
        ],
        "edges": [
            {"id": _make_id(), "source": start_id, "sourceHandle": "exec_out", "target": print_id, "targetHandle": "exec_in"},
            {"id": _make_id(), "source": print_id, "sourceHandle": "exec_out", "target": end_id, "targetHandle": "exec_in"},
        ],
    }


def _ip_lookup_graph() -> dict:
    start_id = _make_id()
    http_id = _make_id()
    parse_id = _make_id()
    print_id = _make_id()
    end_id = _make_id()
    return {
        "metadata": {"name": "IP Lookup", "description": "Look up IP geolocation info", "version": 1},
        "nodes": [
            {"id": start_id, "type": "start", "name": "Start", "position": {"x": 100, "y": 200}, "properties": {}, "input_ports": [], "output_ports": [{"name": "exec_out", "type": "FLOW"}]},
            {"id": http_id, "type": "http_request", "name": "Lookup IP", "position": {"x": 400, "y": 200},
             "properties": {"url": "http://ip-api.com/json/8.8.8.8", "method": "GET", "headers": "{}", "body": ""},
             "input_ports": [{"name": "exec_in", "type": "FLOW"}, {"name": "url", "type": "STRING"}, {"name": "body", "type": "ANY"}],
             "output_ports": [{"name": "exec_out", "type": "FLOW"}, {"name": "response", "type": "DICT"}, {"name": "status_code", "type": "INTEGER"}, {"name": "body", "type": "ANY"}]},
            {"id": parse_id, "type": "json_parse", "name": "Parse Response", "position": {"x": 700, "y": 200},
             "properties": {},
             "input_ports": [{"name": "exec_in", "type": "FLOW"}, {"name": "input", "type": "STRING"}],
             "output_ports": [{"name": "exec_out", "type": "FLOW"}, {"name": "output", "type": "ANY"}]},
            {"id": print_id, "type": "print", "name": "Print Result", "position": {"x": 1000, "y": 200},
             "properties": {"message": ""},
             "input_ports": [{"name": "exec_in", "type": "FLOW"}, {"name": "value", "type": "ANY"}],
             "output_ports": [{"name": "exec_out", "type": "FLOW"}]},
            {"id": end_id, "type": "end", "name": "End", "position": {"x": 1300, "y": 200}, "properties": {},
             "input_ports": [{"name": "exec_in", "type": "FLOW"}, {"name": "result", "type": "ANY"}], "output_ports": []},
        ],
        "edges": [
            {"id": _make_id(), "source": start_id, "sourceHandle": "exec_out", "target": http_id, "targetHandle": "exec_in"},
            {"id": _make_id(), "source": http_id, "sourceHandle": "exec_out", "target": parse_id, "targetHandle": "exec_in"},
            {"id": _make_id(), "source": http_id, "sourceHandle": "body", "target": parse_id, "targetHandle": "input"},
            {"id": _make_id(), "source": parse_id, "sourceHandle": "exec_out", "target": print_id, "targetHandle": "exec_in"},
            {"id": _make_id(), "source": parse_id, "sourceHandle": "output", "target": print_id, "targetHandle": "value"},
            {"id": _make_id(), "source": print_id, "sourceHandle": "exec_out", "target": end_id, "targetHandle": "exec_in"},
        ],
    }


def _incident_triage_graph() -> dict:
    start_id = _make_id()
    get_data_id = _make_id()
    if_id = _make_id()
    set_var_id = _make_id()
    print_low_id = _make_id()
    end_high_id = _make_id()
    end_low_id = _make_id()
    return {
        "metadata": {"name": "Incident Triage", "description": "Basic incident triage with severity check", "version": 1},
        "nodes": [
            {"id": start_id, "type": "start", "name": "Start", "position": {"x": 100, "y": 300}, "properties": {},
             "input_ports": [], "output_ports": [{"name": "exec_out", "type": "FLOW"}]},
            {"id": get_data_id, "type": "get_incident_data", "name": "Get Incident", "position": {"x": 400, "y": 300},
             "properties": {},
             "input_ports": [{"name": "exec_in", "type": "FLOW"}],
             "output_ports": [{"name": "exec_out", "type": "FLOW"}, {"name": "data", "type": "DICT"}]},
            {"id": if_id, "type": "if", "name": "Is Critical?", "position": {"x": 700, "y": 300},
             "properties": {"operator": "equals", "compare_value": "critical"},
             "input_ports": [{"name": "exec_in", "type": "FLOW"}, {"name": "value", "type": "ANY"}, {"name": "condition", "type": "ANY"}],
             "output_ports": [{"name": "true", "type": "FLOW"}, {"name": "false", "type": "FLOW"}, {"name": "result", "type": "BOOLEAN"}]},
            {"id": set_var_id, "type": "set_incident_var", "name": "Set Escalation", "position": {"x": 1000, "y": 150},
             "properties": {"variable_name": "escalation_level"},
             "input_ports": [{"name": "exec_in", "type": "FLOW"}, {"name": "value", "type": "ANY", "inline_value": "3"}],
             "output_ports": [{"name": "exec_out", "type": "FLOW"}]},
            {"id": print_low_id, "type": "print", "name": "Log Low", "position": {"x": 1000, "y": 450},
             "properties": {"message": "Non-critical incident - standard triage."},
             "input_ports": [{"name": "exec_in", "type": "FLOW"}, {"name": "value", "type": "ANY"}],
             "output_ports": [{"name": "exec_out", "type": "FLOW"}]},
            {"id": end_high_id, "type": "end", "name": "End (High)", "position": {"x": 1300, "y": 150}, "properties": {},
             "input_ports": [{"name": "exec_in", "type": "FLOW"}, {"name": "result", "type": "ANY"}], "output_ports": []},
            {"id": end_low_id, "type": "end", "name": "End (Low)", "position": {"x": 1300, "y": 450}, "properties": {},
             "input_ports": [{"name": "exec_in", "type": "FLOW"}, {"name": "result", "type": "ANY"}], "output_ports": []},
        ],
        "edges": [
            {"id": _make_id(), "source": start_id, "sourceHandle": "exec_out", "target": get_data_id, "targetHandle": "exec_in"},
            {"id": _make_id(), "source": get_data_id, "sourceHandle": "exec_out", "target": if_id, "targetHandle": "exec_in"},
            {"id": _make_id(), "source": if_id, "sourceHandle": "true", "target": set_var_id, "targetHandle": "exec_in"},
            {"id": _make_id(), "source": if_id, "sourceHandle": "false", "target": print_low_id, "targetHandle": "exec_in"},
            {"id": _make_id(), "source": set_var_id, "sourceHandle": "exec_out", "target": end_high_id, "targetHandle": "exec_in"},
            {"id": _make_id(), "source": print_low_id, "sourceHandle": "exec_out", "target": end_low_id, "targetHandle": "exec_in"},
        ],
    }


_AUTOMATIONS: list[dict] = [
    {
        "name": "Hello World",
        "description": "A simple example automation that prints a greeting. Great for testing that execution works.",
        "graph_data": _hello_world_graph(),
        "tags": ["example", "getting-started"],
    },
    {
        "name": "IP Lookup",
        "description": "Demonstrates HTTP requests and JSON parsing by looking up geolocation data for an IP address.",
        "graph_data": _ip_lookup_graph(),
        "tags": ["example", "network"],
    },
    {
        "name": "Incident Triage",
        "description": "Example incident triage workflow with conditional logic. Checks severity and sets escalation level.",
        "graph_data": _incident_triage_graph(),
        "tags": ["example", "incident"],
    },
]


# ---------------------------------------------------------------------------
# Seeder functions
# ---------------------------------------------------------------------------

async def _seed_wiki_pages(db: AsyncSession, created_by: UUID) -> None:
    """Seed wiki pages from markdown files in the wiki/ directory."""
    wiki_svc = WikiService(db)
    app_pages, category_pages, node_pages = _load_wiki_pages()

    if not app_pages and not category_pages and not node_pages:
        logger.warning("No wiki seed files found in %s", WIKI_DIR)
        return

    # Track slug -> page_id for parent resolution
    slug_to_id: dict[str, UUID] = {}

    async def _upsert_page(page_def: dict) -> None:
        slug = page_def["slug"]
        existing = await db.execute(
            select(WikiPage.id).where(WikiPage.slug == slug)
        )
        existing_id = existing.scalar_one_or_none()
        if existing_id:
            slug_to_id[slug] = existing_id
            return

        parent_id = slug_to_id.get(page_def.get("parent_slug") or "")
        page = await wiki_svc.create(
            title=page_def["title"],
            slug=slug,
            content=page_def.get("content", ""),
            created_by=created_by,
            parent_id=parent_id,
            tags=page_def.get("tags", []),
            icon=page_def.get("icon"),
            linked_node_type=page_def.get("linked_node_type"),
        )
        slug_to_id[slug] = page.id
        logger.info("  Wiki: %s", page_def["title"])

    for page_def in app_pages:
        await _upsert_page(page_def)
    for page_def in category_pages:
        await _upsert_page(page_def)
    for page_def in node_pages:
        await _upsert_page(page_def)

    await db.flush()


async def _seed_incident_variables(db: AsyncSession, created_by: UUID) -> None:
    """Seed default incident variable definitions."""
    svc = IncidentVariableService(db)
    for var_def in _INCIDENT_VARIABLES:
        existing = await svc.get_by_name(var_def["name"])
        if existing:
            continue
        await svc.create(
            name=var_def["name"],
            created_by=created_by,
            description=var_def.get("description"),
            default_enabled=var_def.get("default_enabled", True),
            sensitive=var_def.get("sensitive", False),
        )
        logger.info("  IncidentVar: %s", var_def["name"])
    await db.flush()


async def _seed_user_secrets(db: AsyncSession, created_by: UUID) -> None:
    """Seed example user secrets for the admin user."""
    svc = UserSecretService(db)
    for secret_def in _USER_SECRETS:
        existing = await svc.get_by_name_for_user(created_by, secret_def["name"])
        if existing:
            continue
        await svc.create(
            user_id=created_by,
            name=secret_def["name"],
            value=secret_def.get("value", ""),
            description=secret_def.get("description"),
            sensitive=secret_def.get("sensitive", False),
        )
        logger.info("  Secret: %s", secret_def["name"])
    await db.flush()


async def _seed_automations(db: AsyncSession, created_by: UUID) -> None:
    """Seed example automations."""
    svc = AutomationService(db)
    for auto_def in _AUTOMATIONS:
        existing = await db.execute(
            select(Automation.id).where(Automation.name == auto_def["name"])
        )
        if existing.scalar_one_or_none():
            continue
        await svc.create(
            name=auto_def["name"],
            created_by=created_by,
            description=auto_def.get("description"),
            graph_data=auto_def.get("graph_data"),
            tags=auto_def.get("tags", []),
        )
        logger.info("  Automation: %s", auto_def["name"])
    await db.flush()

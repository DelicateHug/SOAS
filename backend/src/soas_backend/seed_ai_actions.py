"""Seed default AI actions for each page surface.

Each action is a `(page_key, label, description, system_prompt)` tuple. The
AIActionsBar component auto-hides on pages with no actions, so the rollout is
zero-risk if the seeds fail.

System prompts are intentionally short — they describe the *intent*; the
context the route layer passes (incident id, title, etc.) fills in the rest.
The backend's `ai_subprocess` shells out to the local `claude` CLI by default.
"""

from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from soas_backend.models.ai import AIAction

logger = logging.getLogger(__name__)


DEFAULTS: list[dict] = [
    # Incident detail
    {
        "page_key": "incident_detail",
        "label": "Summarize",
        "icon": "Sparkles",
        "description": "Produce a one-paragraph brief on this incident.",
        "system_prompt": (
            "You are a SOC analyst. Given an incident's title, severity, status, and tags, "
            "produce a tight one-paragraph brief (4 sentences max) covering: what we know, "
            "what's unclear, and a recommended next step. Be concrete."
        ),
        "context_fields": ["incident_id", "title", "severity", "status", "tags"],
        "sort_order": 10,
    },
    {
        "page_key": "incident_detail",
        "label": "Next steps",
        "icon": "Sparkles",
        "description": "Suggest concrete next steps for triage.",
        "system_prompt": (
            "You are a senior SOC analyst mentoring a tier-1. Given the incident metadata, "
            "list the next 3-5 concrete triage steps as a numbered list. Each step must "
            "include the *tool* or *query* to run."
        ),
        "context_fields": ["incident_id", "title", "severity", "status", "tags"],
        "sort_order": 20,
    },
    # Case detail
    {
        "page_key": "case_detail",
        "label": "Summarize",
        "icon": "Sparkles",
        "description": "One-paragraph case status brief.",
        "system_prompt": (
            "You are a SOC lead. Given a case title, status, and priority, produce a "
            "one-paragraph status brief suitable for a daily stand-up. Mention any obvious "
            "blockers."
        ),
        "context_fields": ["case_id", "title", "status", "priority"],
        "sort_order": 10,
    },
    {
        "page_key": "case_detail",
        "label": "Draft closing note",
        "icon": "Sparkles",
        "description": "Draft a closing note for the case.",
        "system_prompt": (
            "Draft a 2-paragraph case closing note. Cover: root cause, containment, lessons "
            "learned. Use neutral, factual language."
        ),
        "context_fields": ["case_id", "title", "status", "priority"],
        "sort_order": 20,
    },
    # Automation detail
    {
        "page_key": "automation_detail",
        "label": "Explain",
        "icon": "Sparkles",
        "description": "Plain-English explanation of what this automation does.",
        "system_prompt": (
            "Given an automation's name, description, status, and tags, write a 3-sentence "
            "plain-English explanation suitable for a non-developer SOC analyst."
        ),
        "context_fields": ["automation_id", "name", "status", "tags"],
        "sort_order": 10,
    },
    {
        "page_key": "automation_detail",
        "label": "Suggest improvements",
        "icon": "Sparkles",
        "description": "Suggest improvements to this automation.",
        "system_prompt": (
            "You are a senior SOAR engineer reviewing a colleague's automation. Suggest 2-3 "
            "concrete improvements (error handling, idempotency, observability). Be specific."
        ),
        "context_fields": ["automation_id", "name", "status", "tags"],
        "sort_order": 20,
    },
    # Wiki view + editor
    {
        "page_key": "wiki_page_view",
        "label": "Summarize",
        "icon": "Sparkles",
        "description": "Condense this wiki page to 3 bullets.",
        "system_prompt": (
            "Summarize the wiki page identified by its slug and title into 3 bullet points "
            "for a teammate skimming for the takeaway."
        ),
        "context_fields": ["slug", "title", "tags"],
        "sort_order": 10,
    },
    {
        "page_key": "wiki_page_editor",
        "label": "Rewrite for clarity",
        "icon": "Sparkles",
        "description": "Rewrite the draft for clarity and concision.",
        "system_prompt": (
            "You are a technical editor. Rewrite the draft for clarity and concision while "
            "preserving every factual claim. Use plain English, short sentences, active voice."
        ),
        "context_fields": ["slug", "title"],
        "sort_order": 10,
    },
    # Saved queries (build query with AI)
    {
        "page_key": "saved_queries",
        "label": "Build query from prose",
        "icon": "Sparkles",
        "description": "Generate a SQL/KQL/LEQL query from a natural-language description.",
        "system_prompt": (
            "You are a SIEM hunting expert. Given a prose description, draft the most "
            "idiomatic query for the SOAS incidents/cases schema (Postgres SQL by default). "
            "Output only the query, no commentary."
        ),
        "context_fields": [],
        "sort_order": 10,
    },
    # Reports
    {
        "page_key": "reports",
        "label": "Draft section",
        "icon": "Sparkles",
        "description": "Draft a new report section from a prompt.",
        "system_prompt": (
            "Draft a report section in 2-3 short paragraphs. The section should read like an "
            "executive summary — factual, no fluff."
        ),
        "context_fields": [],
        "sort_order": 10,
    },
    # Code library
    {
        "page_key": "code_library",
        "label": "Suggest block",
        "icon": "Sparkles",
        "description": "Suggest a code block to write.",
        "system_prompt": (
            "Given a desired behaviour, propose a Python code block for the SOAS graph "
            "compiler. Use inputs.get('name') and outputs['name'] = value conventions. "
            "Keep it under 30 lines."
        ),
        "context_fields": ["language"],
        "sort_order": 10,
    },
    {
        "page_key": "code_block_editor",
        "label": "Explain code",
        "icon": "Sparkles",
        "description": "Plain-English explanation of the current code.",
        "system_prompt": (
            "Explain in 2-3 sentences what this code block does and what its inputs/outputs are. "
            "Plain English, no jargon."
        ),
        "context_fields": ["name", "language"],
        "sort_order": 10,
    },
    {
        "page_key": "code_block_editor",
        "label": "Add error handling",
        "icon": "Sparkles",
        "description": "Suggest where error handling should be added.",
        "system_prompt": (
            "Review this Python code block for missing error handling. Suggest 2-3 specific "
            "try/except boundaries or input validations, and explain why each matters."
        ),
        "context_fields": ["name", "language"],
        "sort_order": 20,
    },
    # Dashboards
    {
        "page_key": "dashboard_edit",
        "label": "Suggest widgets",
        "icon": "Sparkles",
        "description": "Suggest widgets that would fit this dashboard.",
        "system_prompt": (
            "Given the dashboard name and current widget count, propose 3 widget ideas that "
            "would complement what's there. For each: title, widget type, and one-line rationale."
        ),
        "context_fields": ["dashboard_id", "name", "widget_count"],
        "sort_order": 10,
    },
]


async def seed_ai_actions(db: AsyncSession) -> None:
    """Insert default AI actions if they don't already exist (matched by page_key + label)."""
    inserted = 0
    for spec in DEFAULTS:
        result = await db.execute(
            select(AIAction).where(
                AIAction.page_key == spec["page_key"],
                AIAction.label == spec["label"],
            )
        )
        if result.scalar_one_or_none() is not None:
            continue
        db.add(
            AIAction(
                page_key=spec["page_key"],
                label=spec["label"],
                icon=spec.get("icon"),
                description=spec.get("description"),
                system_prompt=spec["system_prompt"],
                context_fields=spec.get("context_fields", []),
                allowed_mcp_tools=spec.get("allowed_mcp_tools", []),
                result_kind=spec.get("result_kind", "markdown"),
                sort_order=spec.get("sort_order", 100),
                is_enabled=True,
            )
        )
        inserted += 1
    logger.info("seed_ai_actions: inserted %d default AI actions", inserted)

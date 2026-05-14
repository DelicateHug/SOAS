"""AI features API (Phase 8).

Four surfaces, one router:
  - /ai/chats           — persistent case chats (CRUD + send-message)
  - /ai/actions         — list AI Actions for a page + execute one
  - /ai/query-builder   — generate a SQL/LEQL/KQL query from prompt
  - /ai/widget-builder  — generate a widget config from prompt

All four use ai_subprocess.ClaudeCLIRunner (user-driven). Workers use
ai_api.AnthropicAPIRunner via separate worker tasks (Phase 8 future
work).
"""

from __future__ import annotations

import json
import re
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from soas_backend.api.deps import get_current_user, require_role
from soas_backend.database import get_db
from soas_backend.models.ai import AIAction, CaseAIChat
from soas_backend.models.user import User
from soas_backend.services.ai_subprocess import ClaudeCLIError, ClaudeCLIRunner

router = APIRouter(prefix="/ai", tags=["ai"])


# ---------------------------------------------------------------------------
# Case AI Chats
# ---------------------------------------------------------------------------


class ChatRead(BaseModel):
    id: UUID
    case_id: UUID | None
    incident_id: UUID | None
    owner_id: UUID
    name: str
    transcript: list[dict[str, Any]]
    model: str | None
    tags: list[str]
    is_favorite: bool
    is_archived: bool
    token_total: int

    model_config = {"from_attributes": True}


class ChatCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    case_id: UUID | None = None
    incident_id: UUID | None = None
    model: str | None = "sonnet"


class ChatSend(BaseModel):
    content: str = Field(min_length=1, max_length=8000)
    model: str | None = None


@router.get("/chats", response_model=list[ChatRead])
async def list_chats(
    case_id: UUID | None = None,
    incident_id: UUID | None = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    q = select(CaseAIChat).where(CaseAIChat.owner_id == current_user.id).order_by(CaseAIChat.updated_at.desc())
    if case_id:
        q = q.where(CaseAIChat.case_id == case_id)
    if incident_id:
        q = q.where(CaseAIChat.incident_id == incident_id)
    rs = await db.execute(q)
    return list(rs.scalars().all())


@router.post("/chats", response_model=ChatRead, status_code=201)
async def create_chat(
    body: ChatCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    chat = CaseAIChat(
        name=body.name,
        case_id=body.case_id,
        incident_id=body.incident_id,
        owner_id=current_user.id,
        model=body.model,
        transcript=[],
    )
    db.add(chat)
    await db.flush()
    return chat


@router.get("/chats/{chat_id}", response_model=ChatRead)
async def get_chat(
    chat_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    rs = await db.execute(select(CaseAIChat).where(CaseAIChat.id == chat_id))
    chat = rs.scalar_one_or_none()
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")
    if chat.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not the owner")
    return chat


@router.post("/chats/{chat_id}/send", response_model=ChatRead)
async def send_message(
    chat_id: UUID,
    body: ChatSend,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    rs = await db.execute(select(CaseAIChat).where(CaseAIChat.id == chat_id))
    chat = rs.scalar_one_or_none()
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")
    if chat.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not the owner")

    from datetime import datetime, timezone

    now_iso = datetime.now(timezone.utc).isoformat()
    user_turn = {"role": "user", "content": body.content, "ts": now_iso}
    # Run the CLI with the last ~20 turns as prompt context.
    history_str = "\n".join(
        f"{t.get('role', '?')}: {t.get('content', '')}" for t in chat.transcript[-20:]
    )
    prompt = (
        f"You are an AI assistant in a SOC analyst chat. Continue the conversation.\n\n"
        f"--- Prior history ---\n{history_str}\n\n"
        f"--- New user message ---\n{body.content}\n"
    )
    runner = ClaudeCLIRunner(db)
    try:
        result = await runner.run(
            prompt=prompt,
            model=body.model or chat.model or "sonnet",
            caller="case_chat",
            user_id=current_user.id,
            target_id=chat.id,
            target_kind="case_ai_chat",
        )
    except ClaudeCLIError as e:
        raise HTTPException(status_code=502, detail=str(e))

    assistant_turn = {"role": "assistant", "content": result["content"], "ts": now_iso}
    chat.transcript = (chat.transcript or []) + [user_turn, assistant_turn]
    chat.token_total += int(result["usage"].get("input_tokens", 0) + result["usage"].get("output_tokens", 0))
    chat.model = result["model"]
    await db.flush()
    return chat


@router.delete("/chats/{chat_id}", status_code=204)
async def delete_chat(
    chat_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    rs = await db.execute(select(CaseAIChat).where(CaseAIChat.id == chat_id))
    chat = rs.scalar_one_or_none()
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")
    if chat.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not the owner")
    await db.delete(chat)


# ---------------------------------------------------------------------------
# AI Actions
# ---------------------------------------------------------------------------


class ActionRead(BaseModel):
    id: UUID
    page_key: str
    label: str
    icon: str | None
    description: str | None
    context_fields: list[str]
    result_kind: str
    is_enabled: bool

    model_config = {"from_attributes": True}


class ActionExecute(BaseModel):
    context: dict[str, Any] = Field(default_factory=dict)


@router.get("/actions", response_model=list[ActionRead])
async def list_actions(
    page_key: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    rs = await db.execute(
        select(AIAction)
        .where(AIAction.page_key == page_key, AIAction.is_enabled.is_(True))
        .order_by(AIAction.sort_order.asc())
    )
    return list(rs.scalars().all())


@router.post("/actions/{action_id}/execute")
async def execute_action(
    action_id: UUID,
    body: ActionExecute,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    rs = await db.execute(select(AIAction).where(AIAction.id == action_id))
    action = rs.scalar_one_or_none()
    if not action:
        raise HTTPException(status_code=404, detail="Action not found")
    if not action.is_enabled:
        raise HTTPException(status_code=400, detail="Action is disabled")

    # Interpolate {field} placeholders from body.context
    prompt = action.system_prompt
    for field in (action.context_fields or []):
        if field in body.context:
            prompt = prompt.replace("{" + field + "}", str(body.context[field]))

    runner = ClaudeCLIRunner(db)
    try:
        result = await runner.run(
            prompt=prompt,
            model=action.model or "sonnet",
            caller="ai_action",
            allowed_tools=action.allowed_mcp_tools or [],
            user_id=current_user.id,
            target_id=action.id,
            target_kind="ai_action",
        )
    except ClaudeCLIError as e:
        raise HTTPException(status_code=502, detail=str(e))

    return {
        "result_kind": action.result_kind,
        "content": result["content"],
        "usage": result["usage"],
        "model": result["model"],
    }


# ---------------------------------------------------------------------------
# Query Builder + Widget Builder (one-shot)
# ---------------------------------------------------------------------------


class GenerateRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=4000)
    target_type: str  # "incidents_sql", "leql", "kql", "widget"
    model: str | None = "sonnet"


@router.post("/query-builder")
async def query_builder(
    body: GenerateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if body.target_type not in ("incidents_sql", "leql", "kql"):
        raise HTTPException(status_code=400, detail="target_type must be one of incidents_sql, leql, kql")

    system = {
        "incidents_sql": (
            "You generate read-only SELECT statements against the SOAS incidents table. "
            "Columns include: id, title, summary, severity, status, source, created_at, "
            "category_key, metadata (jsonb). Use ${var} for parameter placeholders. "
            "Reply with ONLY the SQL string, no commentary, no code fences."
        ),
        "leql": (
            "You generate LEQL queries for log search. Reply with ONLY the query, no commentary."
        ),
        "kql": (
            "You generate Microsoft Defender KQL queries. Reply with ONLY the query, no commentary."
        ),
    }[body.target_type]

    runner = ClaudeCLIRunner(db)
    try:
        result = await runner.run(
            prompt=f"User intent: {body.prompt}",
            system=system,
            model=body.model or "sonnet",
            caller="query_builder",
            user_id=current_user.id,
        )
    except ClaudeCLIError as e:
        raise HTTPException(status_code=502, detail=str(e))
    return {"query": result["content"].strip(), "usage": result["usage"], "model": result["model"]}


@router.post("/widget-builder")
async def widget_builder(
    body: GenerateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if body.target_type != "widget":
        raise HTTPException(status_code=400, detail="target_type must be 'widget'")

    system = (
        "You generate a JSON config for a SOAS dashboard widget. "
        "Output ONLY valid JSON with these keys: widget_type, config. "
        "widget_type is one of: counter, top_n, timeseries, pie, stacked_bar, table, "
        "duration_stat, ratio. config keys are: source (one of: incidents, cases, "
        "token_usage, artifact_changes, executions), time_range (one of: last_24h, "
        "last_7d, last_30d, last_90d), dimension (a column on that source), bucket "
        "(for timeseries: hour, day, week, month), filters (dict). Do not include "
        "any commentary."
    )

    runner = ClaudeCLIRunner(db)
    try:
        result = await runner.run(
            prompt=f"User intent: {body.prompt}",
            system=system,
            model=body.model or "sonnet",
            caller="widget_builder",
            user_id=current_user.id,
        )
    except ClaudeCLIError as e:
        raise HTTPException(status_code=502, detail=str(e))

    # Best-effort: strip code fences and parse
    text = result["content"].strip()
    text = re.sub(r"^```(json)?", "", text).strip()
    text = re.sub(r"```$", "", text).strip()
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        parsed = None
    return {
        "raw": result["content"],
        "parsed": parsed,
        "usage": result["usage"],
        "model": result["model"],
    }


# ---------------------------------------------------------------------------
# AI Actions admin (admin-only CRUD)
# ---------------------------------------------------------------------------


class ActionCreate(BaseModel):
    page_key: str
    label: str
    icon: str | None = None
    description: str | None = None
    system_prompt: str
    allowed_mcp_tools: list[str] = Field(default_factory=list)
    context_fields: list[str] = Field(default_factory=list)
    result_kind: str = "markdown"
    model: str | None = "sonnet"
    sort_order: int = 100


class ActionUpdate(BaseModel):
    label: str | None = None
    description: str | None = None
    system_prompt: str | None = None
    allowed_mcp_tools: list[str] | None = None
    context_fields: list[str] | None = None
    result_kind: str | None = None
    model: str | None = None
    is_enabled: bool | None = None
    sort_order: int | None = None


@router.get("/actions-admin", response_model=list[ActionRead])
async def list_all_actions(
    _: dict = Depends(require_role("admin", "soc_manager")),
    db: AsyncSession = Depends(get_db),
):
    rs = await db.execute(select(AIAction).order_by(AIAction.page_key.asc(), AIAction.sort_order.asc()))
    return list(rs.scalars().all())


@router.post("/actions-admin", response_model=ActionRead, status_code=201)
async def create_action(
    body: ActionCreate,
    _: dict = Depends(require_role("admin", "soc_manager")),
    db: AsyncSession = Depends(get_db),
):
    a = AIAction(**body.model_dump())
    db.add(a)
    await db.flush()
    return a


@router.patch("/actions-admin/{action_id}", response_model=ActionRead)
async def update_action(
    action_id: UUID,
    body: ActionUpdate,
    _: dict = Depends(require_role("admin", "soc_manager")),
    db: AsyncSession = Depends(get_db),
):
    rs = await db.execute(select(AIAction).where(AIAction.id == action_id))
    a = rs.scalar_one_or_none()
    if not a:
        raise HTTPException(status_code=404, detail="Action not found")
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(a, k, v)
    await db.flush()
    return a


@router.delete("/actions-admin/{action_id}", status_code=204)
async def delete_action(
    action_id: UUID,
    _: dict = Depends(require_role("admin", "soc_manager")),
    db: AsyncSession = Depends(get_db),
):
    rs = await db.execute(select(AIAction).where(AIAction.id == action_id))
    a = rs.scalar_one_or_none()
    if not a:
        raise HTTPException(status_code=404, detail="Action not found")
    await db.delete(a)

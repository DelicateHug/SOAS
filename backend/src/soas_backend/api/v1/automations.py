"""Automation CRUD and execution endpoints."""

import asyncio
import json
import logging
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from fastapi.security import HTTPAuthorizationCredentials

from soas_backend.api.deps import (
    _pick_default_team_id,
    get_current_user,
    get_user_teams,
    require_permission,
    security,
)
from soas_backend.database import get_db
from soas_backend.models.user import User
from soas_backend.models.automation import Automation
from soas_backend.services.automation_service import AutomationService
from soas_backend.services.audit import audit
from soas_backend.services.rbac_service import RBACService
from soas_backend.services.version_service import VersionService
from soas_shared.schemas.automation import (
    AutomationCreate,
    AutomationExecuteRequest,
    AutomationListItem,
    AutomationPermissionRead,
    AutomationPermissionSet,
    AutomationRead,
    AutomationUpdate,
)
from soas_shared.schemas.common import PaginatedResponse, PaginationMeta
from soas_shared.schemas.user import UserBrief
from soas_shared.schemas.version import AutomationVersionRead, VersionCreate, VersionUpdate, VersionRead

router = APIRouter(prefix="/automations", tags=["automations"])


# ------------------------------------------------------------------
# Request / response schemas for new endpoints
# ------------------------------------------------------------------


class GraphSaveRequest(BaseModel):
    """Request body for saving a graph from the web editor."""

    graph_data: dict[str, Any] = Field(..., description="Graph JSON from the editor")


class GraphSaveResponse(BaseModel):
    id: UUID
    name: str
    status: str
    version: int
    message: str


class MockIncident(BaseModel):
    """Mock incident data for test runs."""
    title: str = "Test Incident"
    severity: str = "medium"
    status: str = "investigating"
    tags: list[str] = []
    custom_vars: dict[str, Any] = {}


class TestRunRequest(BaseModel):
    """Request body for a compile-and-execute test run."""

    graph_data: dict[str, Any] = Field(..., description="Graph JSON to compile and run")
    parameters: dict[str, Any] = {}
    incident_id: UUID | None = None
    mock_incident: MockIncident | None = None
    timeout_seconds: int = Field(default=60, ge=5, le=300)


class TestRunResponse(BaseModel):
    execution_id: str
    status: str
    celery_task_id: str | None = None
    compile_errors: list[str] = []


def _user_brief(user) -> UserBrief | None:
    if user is None:
        return None
    return UserBrief(id=user.id, username=user.username, display_name=user.display_name)


def _version_read(v) -> VersionRead:
    return VersionRead(
        id=v.id,
        version_number=v.version_number,
        name=v.name,
        description=v.description,
        created_by=_user_brief(v.creator),
        created_at=v.created_at,
    )


@router.get("", response_model=PaginatedResponse[AutomationListItem])
async def list_automations(
    automation_status: str | None = Query(None, alias="status"),
    team_id: UUID | None = None,
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=1, le=100),
    _: dict = Depends(require_permission("automation", "read")),
    user_teams: list | None = Depends(get_user_teams),
    db: AsyncSession = Depends(get_db),
):
    svc = AutomationService(db)
    automations, total = await svc.list_automations(
        automation_status, page, per_page,
        user_teams=user_teams, team_id=team_id,
    )

    return PaginatedResponse(
        data=[
            AutomationListItem(
                id=a.id,
                name=a.name,
                description=a.description,
                status=a.status,
                version=a.version,
                created_by=_user_brief(a.creator),
                tags=a.tags or [],
                parameters=a.parameters or [],
                created_at=a.created_at,
                updated_at=a.updated_at,
                team_id=a.team_id,
            )
            for a in automations
        ],
        meta=PaginationMeta(
            total=total,
            page=page,
            per_page=per_page,
            total_pages=(total + per_page - 1) // per_page if total else 0,
        ),
    )


@router.post("", response_model=AutomationRead, status_code=status.HTTP_201_CREATED)
@audit(
    "automation.created",
    target_kind="automation",
    extract_target=lambda r: getattr(r, "id", None),
    extract_label=lambda r: getattr(r, "name", None),
)
async def create_automation(
    body: AutomationCreate,
    current_user: User = Depends(get_current_user),
    _: dict = Depends(require_permission("automation", "create")),
    user_teams: list | None = Depends(get_user_teams),
    db: AsyncSession = Depends(get_db),
):
    effective_team_id = body.team_id
    if effective_team_id is None:
        effective_team_id = await _pick_default_team_id(db, current_user.id, user_teams)

    svc = AutomationService(db)
    automation = await svc.create(
        name=body.name,
        created_by=current_user.id,
        description=body.description,
        graph_data=body.graph_data,
        parameters=[p.model_dump() for p in body.parameters] if body.parameters else [],
        timeout_seconds=body.timeout_seconds,
        tags=body.tags,
        team_id=effective_team_id,
    )
    automation = await svc.get(automation.id)
    return AutomationRead(
        id=automation.id,
        name=automation.name,
        description=automation.description,
        status=automation.status,
        graph_file=automation.graph_file,
        script_hash=automation.script_hash,
        version=automation.version,
        parameters=automation.parameters or [],
        timeout_seconds=automation.timeout_seconds,
        created_by=_user_brief(automation.creator),
        tags=automation.tags or [],
        documentation=automation.documentation,
        team_id=automation.team_id,
        created_at=automation.created_at,
        updated_at=automation.updated_at,
    )


@router.post("/upload", response_model=AutomationRead, status_code=status.HTTP_201_CREATED)
async def upload_vpy(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    _: dict = Depends(require_permission("automation", "create")),
    db: AsyncSession = Depends(get_db),
):
    """Upload a .vpy file to create an automation and compile it."""
    if not file.filename or not file.filename.endswith(".vpy"):
        raise HTTPException(status_code=400, detail="File must be a .vpy file")

    content = await file.read()
    try:
        graph_data = json.loads(content)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON in .vpy file")

    name = graph_data.get("metadata", {}).get("name", file.filename.replace(".vpy", ""))
    description = graph_data.get("metadata", {}).get("description")

    svc = AutomationService(db)
    automation = await svc.create(
        name=name,
        created_by=current_user.id,
        description=description,
        graph_data=graph_data,
        graph_file=file.filename,
    )
    automation = await svc.get(automation.id)
    return AutomationRead(
        id=automation.id,
        name=automation.name,
        description=automation.description,
        status=automation.status,
        graph_file=automation.graph_file,
        script_hash=automation.script_hash,
        version=automation.version,
        parameters=automation.parameters or [],
        timeout_seconds=automation.timeout_seconds,
        created_by=_user_brief(automation.creator),
        tags=automation.tags or [],
        team_id=automation.team_id,
        created_at=automation.created_at,
        updated_at=automation.updated_at,
    )


@router.get("/addable", response_model=list[AutomationListItem])
async def list_addable_automations(
    current_user: User = Depends(get_current_user),
    _: dict = Depends(require_permission("automation", "read")),
    db: AsyncSession = Depends(get_db),
    exclude_id: UUID | None = Query(None, description="Automation ID to exclude (prevent self-referencing)"),
):
    """List active automations the current user can embed via Run Automation node."""
    svc = AutomationService(db)
    automations = await svc.list_addable_automations(current_user.id, exclude_id=exclude_id)
    return [
        AutomationListItem(
            id=a.id,
            name=a.name,
            description=a.description,
            status=a.status,
            version=a.version,
            created_by=_user_brief(a.creator),
            tags=a.tags or [],
            parameters=a.parameters or [],
            team_id=a.team_id,
            created_at=a.created_at,
            updated_at=a.updated_at,
        )
        for a in automations
    ]


@router.get("/dependency-graph")
async def get_dependency_graph(
    automation_id: UUID | None = Query(None, description="Focus on this automation's connected subgraph"),
    _: dict = Depends(require_permission("automation", "read")),
    db: AsyncSession = Depends(get_db),
):
    svc = AutomationService(db)
    return await svc.get_dependency_graph(focus_id=automation_id)


@router.get("/{automation_id}", response_model=AutomationRead)
async def get_automation(
    automation_id: UUID,
    _: dict = Depends(require_permission("automation", "read")),
    user_teams: list | None = Depends(get_user_teams),
    db: AsyncSession = Depends(get_db),
):
    svc = AutomationService(db)
    automation = await svc.get(automation_id)
    if not automation:
        raise HTTPException(status_code=404, detail="Automation not found")

    # Team visibility check
    if user_teams is not None and automation.team_id is not None:
        team_ids = [t["id"] for t in user_teams]
        if str(automation.team_id) not in team_ids:
            raise HTTPException(status_code=404, detail="Automation not found")

    return AutomationRead(
        id=automation.id,
        name=automation.name,
        description=automation.description,
        status=automation.status,
        graph_file=automation.graph_file,
        graph_data=automation.graph_data,
        script_hash=automation.script_hash,
        version=automation.version,
        parameters=automation.parameters or [],
        timeout_seconds=automation.timeout_seconds,
        created_by=_user_brief(automation.creator),
        tags=automation.tags or [],
        documentation=automation.documentation,
        team_id=automation.team_id,
        created_at=automation.created_at,
        updated_at=automation.updated_at,
    )


@router.patch("/{automation_id}", response_model=AutomationRead)
@audit(
    "automation.updated",
    target_kind="automation",
    extract_target=lambda r: getattr(r, "id", None),
    extract_label=lambda r: getattr(r, "name", None),
)
async def update_automation(
    automation_id: UUID,
    body: AutomationUpdate,
    _: dict = Depends(require_permission("automation", "update")),
    db: AsyncSession = Depends(get_db),
):
    svc = AutomationService(db)
    automation = await svc.update(
        automation_id,
        name=body.name,
        description=body.description,
        status=body.status,
        parameters=[p.model_dump() for p in body.parameters] if body.parameters is not None else None,
        timeout_seconds=body.timeout_seconds,
        tags=body.tags,
        documentation=body.documentation,
    )
    if not automation:
        raise HTTPException(status_code=404, detail="Automation not found")

    # Re-fetch with eager-loaded relationships to avoid MissingGreenlet
    automation = await svc.get(automation_id)

    return AutomationRead(
        id=automation.id,
        name=automation.name,
        description=automation.description,
        status=automation.status,
        graph_file=automation.graph_file,
        script_hash=automation.script_hash,
        version=automation.version,
        parameters=automation.parameters or [],
        timeout_seconds=automation.timeout_seconds,
        created_by=_user_brief(automation.creator),
        tags=automation.tags or [],
        documentation=automation.documentation,
        team_id=automation.team_id,
        created_at=automation.created_at,
        updated_at=automation.updated_at,
    )


@router.delete("/{automation_id}", status_code=status.HTTP_204_NO_CONTENT)
@audit("automation.deleted", target_kind="automation", severity="warn")
async def delete_automation(
    automation_id: UUID,
    _: dict = Depends(require_permission("automation", "delete")),
    db: AsyncSession = Depends(get_db),
):
    svc = AutomationService(db)
    deleted = await svc.delete(automation_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Automation not found")


@router.post("/{automation_id}/execute", status_code=status.HTTP_202_ACCEPTED)
@audit("automation.executed", target_kind="automation")
async def execute_automation(
    automation_id: UUID,
    body: AutomationExecuteRequest,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    current_user: User = Depends(get_current_user),
    _: dict = Depends(require_permission("automation", "execute")),
    db: AsyncSession = Depends(get_db),
):
    # Check automation-specific RBAC
    rbac = RBACService(db)
    if not await rbac.check_automation_permission(current_user.id, automation_id):
        raise HTTPException(
            status_code=403,
            detail="Your role does not have permission to execute this automation",
        )

    svc = AutomationService(db)
    try:
        execution = await svc.execute(
            automation_id=automation_id,
            triggered_by=current_user.id,
            parameters=body.parameters,
            incident_id=body.incident_id,
            case_id=body.case_id,
            api_token=credentials.credentials,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {
        "execution_id": str(execution.id),
        "status": execution.status,
        "celery_task_id": execution.celery_task_id,
    }


@router.get("/{automation_id}/permissions", response_model=list[AutomationPermissionRead])
async def get_automation_permissions(
    automation_id: UUID,
    _: dict = Depends(require_permission("automation", "read")),
    db: AsyncSession = Depends(get_db),
):
    svc = AutomationService(db)
    perms = await svc.get_permissions(automation_id)
    return [
        AutomationPermissionRead(
            automation_id=p.automation_id,
            role_id=p.role_id,
            role_name=p.role.name,
            can_read=p.can_read,
            can_execute=p.can_execute,
            can_edit=p.can_edit,
            can_add=p.can_add,
        )
        for p in perms
    ]


@router.put("/{automation_id}/permissions")
async def set_automation_permissions(
    automation_id: UUID,
    body: list[AutomationPermissionSet],
    current_user: User = Depends(get_current_user),
    _: dict = Depends(require_permission("automation", "update")),
    db: AsyncSession = Depends(get_db),
):
    svc = AutomationService(db)
    await svc.set_permissions(
        automation_id,
        [p.model_dump() for p in body],
        granted_by=current_user.id,
    )
    return {"message": "Permissions updated"}


@router.put("/{automation_id}/graph", response_model=GraphSaveResponse)
async def save_graph(
    automation_id: UUID,
    body: GraphSaveRequest,
    current_user: User = Depends(get_current_user),
    _: dict = Depends(require_permission("automation", "update")),
    db: AsyncSession = Depends(get_db),
):
    """Save graph JSON from the web editor and trigger recompilation.

    Overwrites the existing ``graph_data``, bumps the version, and
    dispatches the ``soas.compile_graph`` Celery task.
    """
    svc = AutomationService(db)
    automation = await svc.get(automation_id)
    if not automation:
        raise HTTPException(status_code=404, detail="Automation not found")

    # Validate graph schema before saving
    from visualpython2.schema.graph_schema import GraphDataSchema

    try:
        GraphDataSchema(**body.graph_data)
    except Exception as exc:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid graph data: {exc}",
        )

    automation.graph_data = body.graph_data
    automation.version += 1

    # Extract name/description from graph metadata if present
    meta = body.graph_data.get("metadata", {})
    if meta.get("name"):
        automation.name = meta["name"]
    if meta.get("description"):
        automation.description = meta["description"]

    await db.flush()

    # Extract and save dependencies
    await svc.extract_and_save_dependencies(automation_id, body.graph_data)

    # Auto-save version snapshot
    vsvc = VersionService(db)
    await vsvc.save_automation_version(automation, current_user.id)

    # Dispatch recompilation (best-effort – don't let broker issues block save)
    compile_dispatched = True
    try:
        loop = asyncio.get_running_loop()
        await asyncio.wait_for(
            loop.run_in_executor(
                None, svc._dispatch_compile, str(automation.id), body.graph_data
            ),
            timeout=5.0,
        )
    except Exception:
        logging.getLogger(__name__).warning(
            "Compile dispatch failed for automation %s", automation_id, exc_info=True
        )
        compile_dispatched = False

    msg = (
        "Graph saved, compilation dispatched"
        if compile_dispatched
        else "Graph saved, but compilation dispatch failed (Celery/Redis may be unavailable)"
    )
    return GraphSaveResponse(
        id=automation.id,
        name=automation.name,
        status=automation.status,
        version=automation.version,
        message=msg,
    )


@router.post("/{automation_id}/test-run", response_model=TestRunResponse)
async def test_run(
    automation_id: UUID,
    body: TestRunRequest,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    current_user: User = Depends(get_current_user),
    _: dict = Depends(require_permission("automation", "execute")),
    db: AsyncSession = Depends(get_db),
):
    """Compile graph and execute in a single step for testing.

    Validates the graph, saves it as the current graph_data, dispatches
    compilation, and immediately queues execution.  Useful for the
    web editor's "Run" button.
    """
    svc = AutomationService(db)
    automation = await svc.get(automation_id)
    if not automation:
        raise HTTPException(status_code=404, detail="Automation not found")

    # Validate graph schema
    from visualpython2.schema.graph_schema import GraphDataSchema
    from visualpython2.compiler.code_generator import CodeGenerator
    from visualpython2.nodes.registry import NodeRegistry
    from visualpython2.serialization.graph_serializer import GraphSerializer

    try:
        GraphDataSchema(**body.graph_data)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Invalid graph data: {exc}")

    # Attempt a local compile-preview to catch errors before dispatching
    compile_errors: list[str] = []
    try:
        registry = NodeRegistry()
        registry.register_default_nodes()
        serializer = GraphSerializer(registry)
        graph = serializer.deserialize(body.graph_data)
        generator = CodeGenerator(graph)
        gen_result = generator.generate()
        if not gen_result.success:
            compile_errors = gen_result.errors
    except Exception as exc:
        compile_errors.append(str(exc))

    if compile_errors:
        return TestRunResponse(
            execution_id="",
            status="compile_error",
            compile_errors=compile_errors,
        )

    # Save the graph
    automation.graph_data = body.graph_data
    automation.version += 1
    await db.flush()

    # Extract and save dependencies
    await svc.extract_and_save_dependencies(automation_id, body.graph_data)

    # Dispatch single test_run_graph task (compiles in-process then executes)
    import json as json_mod
    import uuid as uuid_mod

    from sqlalchemy import select as sa_select
    from soas_backend.celery_proxy import get_celery
    from soas_backend.config import settings
    from soas_backend.models.execution import ExecutionLog
    from soas_backend.models.role import UserRole

    celery = get_celery()

    # Handle mock incident: write to Redis with TTL
    incident_id_for_task = str(body.incident_id) if body.incident_id else None
    if body.mock_incident:
        from soas_backend.api.deps import get_redis_pool

        mock_id = str(uuid_mod.uuid4())
        r = await get_redis_pool()
        redis_key = f"incident:{mock_id}:data"
        mock_data = {
            "id": mock_id,
            "title": body.mock_incident.title,
            "severity": body.mock_incident.severity,
            "status": body.mock_incident.status,
            "tags": body.mock_incident.tags,
            "metadata": body.mock_incident.custom_vars,
            **body.mock_incident.custom_vars,
        }
        pipe = r.pipeline()
        for k, v in mock_data.items():
            pipe.hset(redis_key, k, json_mod.dumps(v, default=str))
        pipe.expire(redis_key, 600)  # 10 min TTL
        await pipe.execute()
        await r.aclose()
        incident_id_for_task = mock_id

    # Get current user's role IDs for SOAS variable permission resolution
    role_result = await db.execute(
        sa_select(UserRole.role_id).where(UserRole.user_id == current_user.id)
    )
    user_role_ids = [str(row.role_id) for row in role_result.all()]

    # Create execution log
    execution = ExecutionLog(
        automation_id=automation_id,
        triggered_by=current_user.id,
        incident_id=body.incident_id,  # Store real incident_id (not mock)
        parameters=body.parameters,
        status="pending",
    )
    db.add(execution)
    await db.flush()

    # Dispatch test_run_graph which compiles and runs in a single task
    task = celery.send_task(
        "soas.test_run_graph",
        args=[
            str(execution.id),
            str(automation_id),
            body.graph_data,
            body.parameters,
        ],
        kwargs={
            "incident_id": incident_id_for_task,
            "timeout_seconds": automation.timeout_seconds or 300,
            "user_role_ids": user_role_ids,
            "api_token": credentials.credentials,
            "triggering_user_id": str(current_user.id),
        },
    )
    execution.celery_task_id = task.id
    execution.status = "queued"
    await db.flush()

    # Also dispatch background compilation to persist the compiled script
    svc._dispatch_compile(str(automation.id), body.graph_data)

    return TestRunResponse(
        execution_id=str(execution.id),
        status=execution.status,
        celery_task_id=task.id,
    )


# ------------------------------------------------------------------
# Version control endpoints
# ------------------------------------------------------------------


@router.get("/{automation_id}/versions", response_model=list[VersionRead])
async def list_automation_versions(
    automation_id: UUID,
    _: dict = Depends(require_permission("automation", "read")),
    db: AsyncSession = Depends(get_db),
):
    svc = VersionService(db)
    versions = await svc.list_automation_versions(automation_id)
    return [_version_read(v) for v in versions]


@router.post("/{automation_id}/versions", response_model=VersionRead, status_code=status.HTTP_201_CREATED)
async def create_automation_version(
    automation_id: UUID,
    body: VersionCreate,
    current_user: User = Depends(get_current_user),
    _: dict = Depends(require_permission("automation", "update")),
    db: AsyncSession = Depends(get_db),
):
    auto_svc = AutomationService(db)
    automation = await auto_svc.get(automation_id)
    if not automation:
        raise HTTPException(status_code=404, detail="Automation not found")

    svc = VersionService(db)
    version = await svc.create_automation_version(
        automation, current_user.id, name=body.name, description=body.description
    )
    return _version_read(version)


@router.patch("/{automation_id}/versions/{version_number}", response_model=VersionRead)
async def update_automation_version(
    automation_id: UUID,
    version_number: int,
    body: VersionUpdate,
    _: dict = Depends(require_permission("automation", "update")),
    db: AsyncSession = Depends(get_db),
):
    svc = VersionService(db)
    version = await svc.update_automation_version_meta(
        automation_id, version_number, name=body.name, description=body.description
    )
    if not version:
        raise HTTPException(status_code=404, detail="Version not found")
    return _version_read(version)


@router.post("/{automation_id}/versions/{version_number}/restore", response_model=AutomationRead)
async def restore_automation_version(
    automation_id: UUID,
    version_number: int,
    current_user: User = Depends(get_current_user),
    _: dict = Depends(require_permission("automation", "update")),
    db: AsyncSession = Depends(get_db),
):
    auto_svc = AutomationService(db)
    automation = await auto_svc.get(automation_id)
    if not automation:
        raise HTTPException(status_code=404, detail="Automation not found")

    svc = VersionService(db)
    automation = await svc.restore_automation_version(automation, version_number)
    if not automation:
        raise HTTPException(status_code=404, detail="Version not found")

    # Re-fetch with relationships
    automation = await auto_svc.get(automation_id)
    return AutomationRead(
        id=automation.id,
        name=automation.name,
        description=automation.description,
        status=automation.status,
        graph_file=automation.graph_file,
        graph_data=automation.graph_data,
        script_hash=automation.script_hash,
        version=automation.version,
        parameters=automation.parameters or [],
        timeout_seconds=automation.timeout_seconds,
        created_by=_user_brief(automation.creator),
        tags=automation.tags or [],
        documentation=automation.documentation,
        team_id=automation.team_id,
        created_at=automation.created_at,
        updated_at=automation.updated_at,
    )


# ------------------------------------------------------------------
# Dependency tracking endpoints
# ------------------------------------------------------------------


@router.get("/{automation_id}/dependencies")
async def get_automation_dependencies(
    automation_id: UUID,
    _: dict = Depends(require_permission("automation", "read")),
    db: AsyncSession = Depends(get_db),
):
    svc = AutomationService(db)
    automation = await svc.get(automation_id)
    if not automation:
        raise HTTPException(status_code=404, detail="Automation not found")

    deps = await svc.get_dependencies(automation_id)
    reverse_deps = await svc.get_reverse_dependencies(automation_id)

    from sqlalchemy import select as sa_select
    from soas_backend.models.code_library import CodeLibraryBlock

    # Batch-fetch automation names
    auto_dep_ids = [d.dependency_id for d in deps if d.dependency_type == "automation"]
    auto_names: dict = {}
    if auto_dep_ids:
        result = await db.execute(
            sa_select(Automation.id, Automation.name).where(Automation.id.in_(auto_dep_ids))
        )
        auto_names = {row.id: row.name for row in result.all()}

    # Batch-fetch code block names
    cb_dep_ids = [d.dependency_id for d in deps if d.dependency_type == "code_block"]
    cb_names: dict = {}
    if cb_dep_ids:
        result = await db.execute(
            sa_select(CodeLibraryBlock.id, CodeLibraryBlock.name).where(
                CodeLibraryBlock.id.in_(cb_dep_ids)
            )
        )
        cb_names = {row.id: row.name for row in result.all()}

    dep_items = []
    for d in deps:
        if d.dependency_type == "automation":
            name = auto_names.get(d.dependency_id)
        elif d.dependency_type == "code_block":
            name = cb_names.get(d.dependency_id)
        else:
            name = None
        dep_items.append({
            "id": str(d.dependency_id),
            "type": d.dependency_type,
            "name": name,
        })

    # Batch-fetch reverse dependency automation names
    rev_auto_ids = [d.automation_id for d in reverse_deps]
    rev_names: dict = {}
    if rev_auto_ids:
        result = await db.execute(
            sa_select(Automation.id, Automation.name).where(Automation.id.in_(rev_auto_ids))
        )
        rev_names = {row.id: row.name for row in result.all()}

    rev_items = []
    for d in reverse_deps:
        rev_items.append({
            "id": str(d.automation_id),
            "type": "automation",
            "name": rev_names.get(d.automation_id),
        })

    return {
        "dependencies": dep_items,
        "dependents": rev_items,
    }

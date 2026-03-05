"""Automation business logic - registration, compilation, execution dispatch."""

from typing import Any
from uuid import UUID

from soas_backend.celery_proxy import get_celery
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from soas_backend.config import settings
from soas_backend.models.automation import Automation, AutomationDependency, AutomationPermission
from soas_backend.models.execution import ExecutionLog
from soas_backend.models.role import UserRole
from soas_backend.models.trigger_log import AutomationTriggerLog


class AutomationService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(
        self,
        name: str,
        created_by: UUID,
        description: str | None = None,
        graph_data: dict[str, Any] | None = None,
        graph_file: str | None = None,
        parameters: list[dict[str, Any]] | None = None,
        timeout_seconds: int = 300,
        tags: list[str] | None = None,
    ) -> Automation:
        automation = Automation(
            name=name,
            description=description,
            graph_data=graph_data,
            graph_file=graph_file,
            parameters=parameters or [],
            timeout_seconds=timeout_seconds,
            created_by=created_by,
            tags=tags or [],
            status="draft",
        )
        self.db.add(automation)
        await self.db.flush()

        # Auto-assign execute+edit permissions for all of the creator's roles
        user_roles = await self.db.execute(
            select(UserRole.role_id).where(UserRole.user_id == created_by)
        )
        for (role_id,) in user_roles.all():
            self.db.add(
                AutomationPermission(
                    automation_id=automation.id,
                    role_id=role_id,
                    can_read=True,
                    can_execute=True,
                    can_edit=True,
                    can_add=True,
                    granted_by=created_by,
                )
            )
        await self.db.flush()

        # If graph_data provided, dispatch compilation task
        if graph_data:
            self._dispatch_compile(str(automation.id), graph_data)

        return automation

    async def get(self, automation_id: UUID) -> Automation | None:
        result = await self.db.execute(
            select(Automation)
            .options(
                selectinload(Automation.creator),
                selectinload(Automation.permissions).selectinload(AutomationPermission.role),
            )
            .where(Automation.id == automation_id)
        )
        return result.scalar_one_or_none()

    async def get_basic(self, automation_id: UUID) -> Automation | None:
        """Fetch automation without eager-loading relationships."""
        result = await self.db.execute(
            select(Automation).where(Automation.id == automation_id)
        )
        return result.scalar_one_or_none()

    async def list_automations(
        self,
        status: str | None = None,
        page: int = 1,
        per_page: int = 25,
    ) -> tuple[list[Automation], int]:
        # Build filter conditions once, reuse for count and data queries
        conditions = []
        if status:
            conditions.append(Automation.status == status)

        count_query = select(func.count(Automation.id))
        for cond in conditions:
            count_query = count_query.where(cond)
        total = (await self.db.execute(count_query)).scalar() or 0

        query = (
            select(Automation)
            .options(selectinload(Automation.creator))
            .order_by(Automation.created_at.desc())
            .offset((page - 1) * per_page)
            .limit(per_page)
        )
        for cond in conditions:
            query = query.where(cond)

        result = await self.db.execute(query)
        return list(result.scalars().all()), total

    async def update(
        self,
        automation_id: UUID,
        name: str | None = None,
        description: str | None = None,
        status: str | None = None,
        parameters: list[dict[str, Any]] | None = None,
        timeout_seconds: int | None = None,
        tags: list[str] | None = None,
        documentation: str | None = None,
    ) -> Automation | None:
        automation = await self.get_basic(automation_id)
        if not automation:
            return None

        if name is not None:
            automation.name = name
        if description is not None:
            automation.description = description
        if status is not None:
            automation.status = status
        if parameters is not None:
            automation.parameters = parameters
        if timeout_seconds is not None:
            automation.timeout_seconds = timeout_seconds
        if tags is not None:
            automation.tags = tags
        if documentation is not None:
            automation.documentation = documentation

        await self.db.flush()
        return automation

    async def delete(self, automation_id: UUID) -> bool:
        from sqlalchemy import delete as sa_delete

        automation = await self.get_basic(automation_id)
        if not automation:
            return False
        # Delete referencing rows that lack ON DELETE CASCADE
        await self.db.execute(
            sa_delete(ExecutionLog).where(ExecutionLog.automation_id == automation_id)
        )
        await self.db.execute(
            sa_delete(AutomationTriggerLog).where(
                AutomationTriggerLog.automation_id == automation_id
            )
        )
        await self.db.delete(automation)
        await self.db.flush()
        return True

    async def execute(
        self,
        automation_id: UUID,
        triggered_by: UUID,
        parameters: dict[str, Any] | None = None,
        incident_id: UUID | None = None,
        case_id: UUID | None = None,
        api_token: str | None = None,
    ) -> ExecutionLog:
        automation = await self.get_basic(automation_id)
        if not automation:
            raise ValueError("Automation not found")
        if automation.status != "active":
            raise ValueError(f"Automation is {automation.status}, must be active to execute")
        if not automation.script_path:
            raise ValueError("Automation has no compiled script")

        execution = ExecutionLog(
            automation_id=automation_id,
            triggered_by=triggered_by,
            incident_id=incident_id,
            case_id=case_id,
            parameters=parameters or {},
            status="pending",
        )
        self.db.add(execution)
        await self.db.flush()

        # Dispatch Celery task
        celery = get_celery()
        kwargs = {}
        if api_token:
            kwargs["api_token"] = api_token
        task = celery.send_task(
            "soas.run_automation",
            args=[str(execution.id), str(automation_id), parameters or {}],
            kwargs=kwargs,
        )
        execution.celery_task_id = task.id
        execution.status = "queued"
        await self.db.flush()

        return execution

    async def set_permissions(
        self,
        automation_id: UUID,
        permissions: list[dict],
        granted_by: UUID,
    ) -> None:
        # Remove existing permissions
        result = await self.db.execute(
            select(AutomationPermission).where(
                AutomationPermission.automation_id == automation_id
            )
        )
        for ap in result.scalars().all():
            await self.db.delete(ap)

        # Add new permissions
        for perm in permissions:
            self.db.add(
                AutomationPermission(
                    automation_id=automation_id,
                    role_id=perm["role_id"],
                    can_read=perm.get("can_read", False),
                    can_execute=perm.get("can_execute", True),
                    can_edit=perm.get("can_edit", False),
                    can_add=perm.get("can_add", False),
                    granted_by=granted_by,
                )
            )
        await self.db.flush()

    async def get_permissions(self, automation_id: UUID) -> list[AutomationPermission]:
        result = await self.db.execute(
            select(AutomationPermission)
            .options(selectinload(AutomationPermission.role))
            .where(AutomationPermission.automation_id == automation_id)
        )
        return list(result.scalars().all())

    async def list_addable_automations(
        self, user_id: UUID, exclude_id: UUID | None = None
    ) -> list[Automation]:
        """List active automations the user can embed via Run Automation node.

        Requires both can_read and can_add permissions on the automation.
        Optionally excludes a specific automation (to prevent self-referencing).
        """
        user_roles = await self.db.execute(
            select(UserRole.role_id).where(UserRole.user_id == user_id)
        )
        role_ids = [r for (r,) in user_roles.all()]
        if not role_ids:
            return []

        query = (
            select(Automation)
            .join(AutomationPermission)
            .options(selectinload(Automation.creator))
            .where(
                AutomationPermission.role_id.in_(role_ids),
                AutomationPermission.can_add.is_(True),
                AutomationPermission.can_read.is_(True),
                Automation.status == "active",
            )
            .distinct()
            .order_by(Automation.name)
        )
        if exclude_id is not None:
            query = query.where(Automation.id != exclude_id)

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def extract_and_save_dependencies(self, automation_id: UUID, graph_data: dict) -> None:
        """Parse graph_data to find dependencies and save to automation_dependencies table."""
        from sqlalchemy import delete as sa_delete

        # Clear existing dependencies
        await self.db.execute(
            sa_delete(AutomationDependency).where(AutomationDependency.automation_id == automation_id)
        )

        deps = self._extract_dependencies(graph_data)
        for dep in deps:
            self.db.add(AutomationDependency(
                automation_id=automation_id,
                dependency_type=dep["type"],
                dependency_id=dep["id"],
            ))
        await self.db.flush()

    @staticmethod
    def _extract_dependencies(graph_data: dict) -> list[dict]:
        """Extract automation and code block dependencies from graph nodes."""
        deps = []
        seen = set()
        for node in graph_data.get("nodes", []):
            props = node.get("properties", {})
            node_type = node.get("type", "")

            # Sub-automation references
            if node_type == "run_automation" and props.get("automation_id"):
                dep_id = str(props["automation_id"])
                key = ("automation", dep_id)
                if key not in seen:
                    seen.add(key)
                    deps.append({"type": "automation", "id": dep_id})

            # Code library block references
            if node_type == "code" and props.get("_library_block_id"):
                dep_id = str(props["_library_block_id"])
                key = ("code_block", dep_id)
                if key not in seen:
                    seen.add(key)
                    deps.append({"type": "code_block", "id": dep_id})

        return deps

    async def get_dependencies(self, automation_id: UUID) -> list[AutomationDependency]:
        """Get dependencies (what this automation uses)."""
        result = await self.db.execute(
            select(AutomationDependency).where(AutomationDependency.automation_id == automation_id)
        )
        return list(result.scalars().all())

    async def get_reverse_dependencies(self, automation_id: UUID) -> list[AutomationDependency]:
        """Get reverse dependencies (what depends on this automation)."""
        result = await self.db.execute(
            select(AutomationDependency).where(
                AutomationDependency.dependency_type == "automation",
                AutomationDependency.dependency_id == automation_id,
            )
        )
        return list(result.scalars().all())

    async def get_dependency_graph(self, focus_id: UUID | None = None) -> dict:
        """Get dependency graph, optionally filtered to the connected subgraph of focus_id."""
        # Get all automations (basic info)
        auto_result = await self.db.execute(
            select(Automation).options(selectinload(Automation.creator))
        )
        automations = auto_result.scalars().all()
        auto_map = {a.id: a for a in automations}

        # Get all dependencies
        dep_result = await self.db.execute(select(AutomationDependency))
        deps = dep_result.scalars().all()

        # If focus_id given, traverse to find reachable nodes
        if focus_id is not None:
            # Build adjacency in both directions
            forward: dict[UUID, list[UUID]] = {}  # automation -> its dependencies
            reverse: dict[UUID, list[UUID]] = {}  # dependency -> automations that use it
            for d in deps:
                forward.setdefault(d.automation_id, []).append(d.dependency_id)
                reverse.setdefault(d.dependency_id, []).append(d.automation_id)

            # BFS from focus_id in both directions
            reachable: set[UUID] = set()
            queue = [focus_id]
            reachable.add(focus_id)
            while queue:
                current = queue.pop()
                for neighbor in forward.get(current, []):
                    if neighbor not in reachable:
                        reachable.add(neighbor)
                        queue.append(neighbor)
                for neighbor in reverse.get(current, []):
                    if neighbor not in reachable:
                        reachable.add(neighbor)
                        queue.append(neighbor)

            # Filter deps to only those between reachable nodes
            deps = [d for d in deps if d.automation_id in reachable and d.dependency_id in reachable]
            automations = [a for a in automations if a.id in reachable]

        nodes = []
        for a in automations:
            nodes.append({
                "id": str(a.id),
                "type": "automation",
                "name": a.name,
                "status": a.status,
                "version": a.version,
            })

        # Collect code block IDs from dependencies
        code_block_ids = set()
        for d in deps:
            if d.dependency_type == "code_block":
                code_block_ids.add(d.dependency_id)

        if code_block_ids:
            from soas_backend.models.code_library import CodeLibraryBlock
            cb_result = await self.db.execute(
                select(CodeLibraryBlock).where(CodeLibraryBlock.id.in_(code_block_ids))
            )
            for cb in cb_result.scalars().all():
                nodes.append({
                    "id": str(cb.id),
                    "type": "code_block",
                    "name": cb.name,
                    "language": cb.language,
                    "version": cb.version,
                })

        edges = []
        for d in deps:
            edges.append({
                "source": str(d.automation_id),
                "target": str(d.dependency_id),
                "type": d.dependency_type,
            })

        return {"nodes": nodes, "edges": edges}

    def _dispatch_compile(self, automation_id: str, graph_json: dict) -> None:
        celery = get_celery()
        celery.send_task("soas.compile_graph", args=[automation_id, graph_json])

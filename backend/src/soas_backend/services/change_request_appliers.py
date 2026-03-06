"""Appliers that write approved change request snapshots to live entities.

Each applier handles create/update/delete for one entity type,
reusing the same field mappings as the git serializers.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Coroutine
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


async def _apply_automation(
    db: AsyncSession, snapshot: dict, entity_id: UUID | None, action: str, user_id: UUID
) -> None:
    from soas_backend.models.automation import Automation

    if action == "delete":
        result = await db.execute(select(Automation).where(Automation.id == entity_id))
        obj = result.scalar_one_or_none()
        if obj:
            await db.delete(obj)
        return

    if action == "create":
        db.add(Automation(
            name=snapshot.get("name"),
            description=snapshot.get("description"),
            status=snapshot.get("status", "draft"),
            graph_data=snapshot.get("graph_data"),
            parameters=snapshot.get("parameters", []),
            timeout_seconds=snapshot.get("timeout_seconds", 300),
            max_retries=snapshot.get("max_retries", 0),
            tags=snapshot.get("tags", []),
            trigger_tags=snapshot.get("trigger_tags", []),
            is_trigger_enabled=snapshot.get("is_trigger_enabled", False),
            documentation=snapshot.get("documentation"),
            created_by=user_id,
        ))
        return

    # update
    result = await db.execute(select(Automation).where(Automation.id == entity_id))
    obj = result.scalar_one_or_none()
    if not obj:
        raise ValueError(f"Automation {entity_id} not found")
    obj.name = snapshot.get("name", obj.name)
    obj.description = snapshot.get("description")
    obj.status = snapshot.get("status", obj.status)
    obj.graph_data = snapshot.get("graph_data", obj.graph_data)
    obj.parameters = snapshot.get("parameters", obj.parameters)
    obj.timeout_seconds = snapshot.get("timeout_seconds", obj.timeout_seconds)
    obj.max_retries = snapshot.get("max_retries", obj.max_retries)
    obj.tags = snapshot.get("tags", obj.tags)
    obj.trigger_tags = snapshot.get("trigger_tags", obj.trigger_tags)
    obj.is_trigger_enabled = snapshot.get("is_trigger_enabled", obj.is_trigger_enabled)
    obj.documentation = snapshot.get("documentation")


async def _apply_wiki_page(
    db: AsyncSession, snapshot: dict, entity_id: UUID | None, action: str, user_id: UUID
) -> None:
    from soas_backend.models.wiki import WikiPage

    if action == "delete":
        result = await db.execute(select(WikiPage).where(WikiPage.id == entity_id))
        obj = result.scalar_one_or_none()
        if obj:
            await db.delete(obj)
        return

    if action == "create":
        db.add(WikiPage(
            title=snapshot.get("title"),
            slug=snapshot.get("slug"),
            content=snapshot.get("content"),
            tags=snapshot.get("tags", []),
            sort_order=snapshot.get("sort_order", 0),
            icon=snapshot.get("icon"),
            status=snapshot.get("status", "published"),
            created_by=user_id,
        ))
        return

    result = await db.execute(select(WikiPage).where(WikiPage.id == entity_id))
    obj = result.scalar_one_or_none()
    if not obj:
        raise ValueError(f"WikiPage {entity_id} not found")
    obj.title = snapshot.get("title", obj.title)
    obj.slug = snapshot.get("slug", obj.slug)
    obj.content = snapshot.get("content", obj.content)
    obj.tags = snapshot.get("tags", obj.tags)
    obj.sort_order = snapshot.get("sort_order", obj.sort_order)
    obj.icon = snapshot.get("icon")
    obj.status = snapshot.get("status", obj.status)
    obj.updated_by = user_id


async def _apply_code_library(
    db: AsyncSession, snapshot: dict, entity_id: UUID | None, action: str, user_id: UUID
) -> None:
    from soas_backend.models.code_library import CodeLibraryBlock

    if action == "delete":
        result = await db.execute(select(CodeLibraryBlock).where(CodeLibraryBlock.id == entity_id))
        obj = result.scalar_one_or_none()
        if obj:
            await db.delete(obj)
        return

    if action == "create":
        db.add(CodeLibraryBlock(
            name=snapshot.get("name"),
            description=snapshot.get("description"),
            code=snapshot.get("code", ""),
            language=snapshot.get("language", "python"),
            is_public=snapshot.get("is_public", False),
            tags=snapshot.get("tags", []),
            input_ports=snapshot.get("input_ports"),
            output_ports=snapshot.get("output_ports"),
            created_by=user_id,
        ))
        return

    result = await db.execute(select(CodeLibraryBlock).where(CodeLibraryBlock.id == entity_id))
    obj = result.scalar_one_or_none()
    if not obj:
        raise ValueError(f"CodeLibraryBlock {entity_id} not found")
    obj.name = snapshot.get("name", obj.name)
    obj.description = snapshot.get("description")
    obj.code = snapshot.get("code", obj.code)
    obj.language = snapshot.get("language", obj.language)
    obj.is_public = snapshot.get("is_public", obj.is_public)
    obj.tags = snapshot.get("tags", obj.tags)
    obj.input_ports = snapshot.get("input_ports")
    obj.output_ports = snapshot.get("output_ports")


async def _apply_soas_variable(
    db: AsyncSession, snapshot: dict, entity_id: UUID | None, action: str, user_id: UUID
) -> None:
    from soas_backend.models.soas_variable import SOASVariable

    if action == "delete":
        result = await db.execute(select(SOASVariable).where(SOASVariable.id == entity_id))
        obj = result.scalar_one_or_none()
        if obj:
            await db.delete(obj)
        return

    if action == "create":
        db.add(SOASVariable(
            name=snapshot.get("name"),
            description=snapshot.get("description"),
            value=snapshot.get("value", ""),
            is_secret=snapshot.get("is_secret", False),
            created_by=user_id,
        ))
        return

    result = await db.execute(select(SOASVariable).where(SOASVariable.id == entity_id))
    obj = result.scalar_one_or_none()
    if not obj:
        raise ValueError(f"SOASVariable {entity_id} not found")
    obj.name = snapshot.get("name", obj.name)
    obj.description = snapshot.get("description")
    obj.value = snapshot.get("value", obj.value)
    obj.is_secret = snapshot.get("is_secret", obj.is_secret)


async def _apply_incident_variable(
    db: AsyncSession, snapshot: dict, entity_id: UUID | None, action: str, user_id: UUID
) -> None:
    from soas_backend.models.incident_variable import IncidentVariable

    if action == "delete":
        result = await db.execute(select(IncidentVariable).where(IncidentVariable.id == entity_id))
        obj = result.scalar_one_or_none()
        if obj:
            await db.delete(obj)
        return

    if action == "create":
        db.add(IncidentVariable(
            name=snapshot.get("name"),
            description=snapshot.get("description"),
            default_enabled=snapshot.get("default_enabled", True),
            created_by=user_id,
        ))
        return

    result = await db.execute(select(IncidentVariable).where(IncidentVariable.id == entity_id))
    obj = result.scalar_one_or_none()
    if not obj:
        raise ValueError(f"IncidentVariable {entity_id} not found")
    obj.name = snapshot.get("name", obj.name)
    obj.description = snapshot.get("description")
    obj.default_enabled = snapshot.get("default_enabled", obj.default_enabled)


async def _apply_role(
    db: AsyncSession, snapshot: dict, entity_id: UUID | None, action: str, user_id: UUID
) -> None:
    from soas_backend.models.role import Permission, Role, RolePermission

    if action == "delete":
        result = await db.execute(select(Role).where(Role.id == entity_id))
        obj = result.scalar_one_or_none()
        if obj:
            await db.delete(obj)
        return

    if action == "create":
        role = Role(
            name=snapshot.get("name"),
            display_name=snapshot.get("display_name"),
            description=snapshot.get("description"),
            is_system=snapshot.get("is_system", False),
        )
        db.add(role)
        await db.flush()
        # Assign permissions
        all_perms = await db.execute(select(Permission))
        perm_map = {f"{p.resource}:{p.action}": p.id for p in all_perms.scalars().all()}
        for ps in snapshot.get("permissions", []):
            pid = perm_map.get(ps)
            if pid:
                db.add(RolePermission(role_id=role.id, permission_id=pid))
        return

    result = await db.execute(select(Role).where(Role.id == entity_id))
    obj = result.scalar_one_or_none()
    if not obj:
        raise ValueError(f"Role {entity_id} not found")
    obj.display_name = snapshot.get("display_name", obj.display_name)
    obj.description = snapshot.get("description")


async def _apply_form_definition(
    db: AsyncSession, snapshot: dict, entity_id: UUID | None, action: str, user_id: UUID
) -> None:
    from soas_backend.models.form_definition import FormDefinition

    if action == "delete":
        result = await db.execute(select(FormDefinition).where(FormDefinition.id == entity_id))
        obj = result.scalar_one_or_none()
        if obj:
            await db.delete(obj)
        return

    if action == "create":
        db.add(FormDefinition(
            name=snapshot.get("name"),
            description=snapshot.get("description"),
            fields=snapshot.get("fields", []),
            is_active=snapshot.get("is_active", True),
            created_by=user_id,
        ))
        return

    result = await db.execute(select(FormDefinition).where(FormDefinition.id == entity_id))
    obj = result.scalar_one_or_none()
    if not obj:
        raise ValueError(f"FormDefinition {entity_id} not found")
    obj.name = snapshot.get("name", obj.name)
    obj.description = snapshot.get("description")
    obj.fields = snapshot.get("fields", obj.fields)
    obj.is_active = snapshot.get("is_active", obj.is_active)


async def _apply_webhook_source(
    db: AsyncSession, snapshot: dict, entity_id: UUID | None, action: str, user_id: UUID
) -> None:
    from soas_backend.models.webhook_source import WebhookSource

    if action == "delete":
        result = await db.execute(select(WebhookSource).where(WebhookSource.id == entity_id))
        obj = result.scalar_one_or_none()
        if obj:
            await db.delete(obj)
        return

    if action == "create":
        db.add(WebhookSource(
            name=snapshot.get("name"),
            description=snapshot.get("description"),
            icon=snapshot.get("icon"),
            created_by=user_id,
        ))
        return

    result = await db.execute(select(WebhookSource).where(WebhookSource.id == entity_id))
    obj = result.scalar_one_or_none()
    if not obj:
        raise ValueError(f"WebhookSource {entity_id} not found")
    obj.name = snapshot.get("name", obj.name)
    obj.description = snapshot.get("description")
    obj.icon = snapshot.get("icon")


async def _apply_webhook(
    db: AsyncSession, snapshot: dict, entity_id: UUID | None, action: str, user_id: UUID
) -> None:
    from soas_backend.models.webhook import Webhook

    if action == "delete":
        result = await db.execute(select(Webhook).where(Webhook.id == entity_id))
        obj = result.scalar_one_or_none()
        if obj:
            await db.delete(obj)
        return

    if action == "create":
        db.add(Webhook(
            name=snapshot.get("name"),
            url=snapshot.get("url"),
            events=snapshot.get("events", []),
            is_active=snapshot.get("is_active", True),
            secret=snapshot.get("secret"),
            created_by=user_id,
        ))
        return

    result = await db.execute(select(Webhook).where(Webhook.id == entity_id))
    obj = result.scalar_one_or_none()
    if not obj:
        raise ValueError(f"Webhook {entity_id} not found")
    obj.name = snapshot.get("name", obj.name)
    obj.url = snapshot.get("url", obj.url)
    obj.events = snapshot.get("events", obj.events)
    obj.is_active = snapshot.get("is_active", obj.is_active)


async def _apply_normalization(
    db: AsyncSession, snapshot: dict, entity_id: UUID | None, action: str, user_id: UUID
) -> None:
    from soas_backend.models.normalization import NormalizationGroup, NormalizationRule

    if action == "delete":
        result = await db.execute(select(NormalizationGroup).where(NormalizationGroup.id == entity_id))
        obj = result.scalar_one_or_none()
        if obj:
            await db.delete(obj)
        return

    if action == "create":
        group = NormalizationGroup(
            name=snapshot.get("name"),
            display_name=snapshot.get("display_name"),
            description=snapshot.get("description"),
            icon=snapshot.get("icon"),
            display_order=snapshot.get("display_order", 0),
        )
        db.add(group)
        await db.flush()
        for rule_data in snapshot.get("rules", []):
            db.add(NormalizationRule(
                group_id=group.id,
                source_path=rule_data["source_path"],
                target_field=rule_data["target_field"],
                transform_type=rule_data.get("transform_type", "direct"),
                transform_config=rule_data.get("transform_config", {}),
                is_required=rule_data.get("is_required", False),
                default_value=rule_data.get("default_value"),
                display_order=rule_data.get("display_order", 0),
                is_enabled=rule_data.get("is_enabled", True),
            ))
        return

    result = await db.execute(select(NormalizationGroup).where(NormalizationGroup.id == entity_id))
    obj = result.scalar_one_or_none()
    if not obj:
        raise ValueError(f"NormalizationGroup {entity_id} not found")
    obj.display_name = snapshot.get("display_name", obj.display_name)
    obj.description = snapshot.get("description")
    obj.icon = snapshot.get("icon")
    obj.display_order = snapshot.get("display_order", obj.display_order)


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

ApplierFunc = Callable[[AsyncSession, dict, UUID | None, str, UUID], Coroutine[Any, Any, None]]

async def _apply_user_role(
    db: AsyncSession, snapshot: dict, entity_id: UUID | None, action: str, user_id: UUID
) -> None:
    from soas_backend.models.role import UserRole
    from sqlalchemy import delete as sql_delete

    target_user_id = UUID(snapshot["user_id"])
    role_id = UUID(snapshot["role_id"])

    if action == "delete":
        await db.execute(
            sql_delete(UserRole).where(
                UserRole.user_id == target_user_id,
                UserRole.role_id == role_id,
            )
        )
        return

    # create — skip if already assigned
    existing = await db.execute(
        select(UserRole).where(
            UserRole.user_id == target_user_id,
            UserRole.role_id == role_id,
        )
    )
    if not existing.scalar_one_or_none():
        db.add(UserRole(user_id=target_user_id, role_id=role_id, assigned_by=user_id))


APPLIER_REGISTRY: dict[str, ApplierFunc] = {
    "automation": _apply_automation,
    "wiki_page": _apply_wiki_page,
    "code_library": _apply_code_library,
    "soas_variable": _apply_soas_variable,
    "incident_variable": _apply_incident_variable,
    "role": _apply_role,
    "user_role": _apply_user_role,
    "form_definition": _apply_form_definition,
    "webhook_source": _apply_webhook_source,
    "webhook": _apply_webhook,
    "normalization": _apply_normalization,
}

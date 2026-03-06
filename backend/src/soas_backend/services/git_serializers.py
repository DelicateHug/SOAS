"""Entity serializers for Git sync.

Each serializer converts DB entities to/from file-friendly formats.
Wiki pages use Markdown with YAML frontmatter; everything else uses JSON.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import UUID

import mistune
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from soas_backend.models.app_setting import AppSetting
from soas_backend.models.automation import Automation
from soas_backend.models.code_library import CodeLibraryBlock
from soas_backend.models.form_definition import FormDefinition
from soas_backend.models.incident_variable import IncidentVariable
from soas_backend.models.normalization import NormalizationGroup, NormalizationRule
from soas_backend.models.role import Permission, Role, RolePermission
from soas_backend.models.soas_variable import SOASVariable
from soas_backend.models.webhook_source import SourceAutomation, WebhookSource
from soas_backend.models.wiki import WikiPage

logger = logging.getLogger(__name__)

SECRET_PLACEHOLDER = "__SECRET__"

_md_renderer = mistune.create_markdown()


def _html_to_markdown(html: str) -> str:
    """Convert HTML (from Tiptap editor) to Markdown for git storage."""
    if not html:
        return ""
    text = html
    # Headings
    for level in range(6, 0, -1):
        prefix = "#" * level
        text = re.sub(rf"<h{level}[^>]*>(.*?)</h{level}>", rf"{prefix} \1", text, flags=re.DOTALL)
    # Bold / italic / strikethrough / code
    text = re.sub(r"<strong>(.*?)</strong>", r"**\1**", text, flags=re.DOTALL)
    text = re.sub(r"<em>(.*?)</em>", r"*\1*", text, flags=re.DOTALL)
    text = re.sub(r"<s>(.*?)</s>", r"~~\1~~", text, flags=re.DOTALL)
    text = re.sub(r"<code>(.*?)</code>", r"`\1`", text, flags=re.DOTALL)
    # Code blocks
    text = re.sub(
        r'<pre><code(?:\s+class="language-(\w+)")?>(.*?)</code></pre>',
        lambda m: f"```{m.group(1) or ''}\n{m.group(2)}\n```",
        text, flags=re.DOTALL,
    )
    # Links and images
    text = re.sub(r'<a[^>]*href="([^"]*)"[^>]*>(.*?)</a>', r"[\2](\1)", text, flags=re.DOTALL)
    text = re.sub(r'<img[^>]*src="([^"]*)"[^>]*alt="([^"]*)"[^>]*/?\s*>', r"![\2](\1)", text)
    # Lists
    text = re.sub(r"<li>(.*?)</li>", r"- \1", text, flags=re.DOTALL)
    text = re.sub(r"</?[uo]l[^>]*>", "", text)
    # Blockquotes
    text = re.sub(r"<blockquote>(.*?)</blockquote>", lambda m: "\n".join(f"> {l}" for l in m.group(1).strip().split("\n")), text, flags=re.DOTALL)
    # Horizontal rules
    text = re.sub(r"<hr\s*/?>", "---", text)
    # Paragraphs and line breaks
    text = re.sub(r"<br\s*/?>", "\n", text)
    text = re.sub(r"<p>(.*?)</p>", r"\1\n", text, flags=re.DOTALL)
    # Strip remaining HTML tags
    text = re.sub(r"<[^>]+>", "", text)
    # Decode HTML entities
    import html as html_mod
    text = html_mod.unescape(text)
    # Clean up extra blank lines
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _markdown_to_html(md: str) -> str:
    """Convert Markdown to HTML for Tiptap/DB storage."""
    if not md:
        return ""
    return _md_renderer(md).strip()

_cached_system_user_id: UUID | None = None


async def _get_system_user_id(db: AsyncSession) -> UUID | None:
    """Get an admin user's ID to use as created_by for git-synced entities."""
    global _cached_system_user_id
    if _cached_system_user_id:
        return _cached_system_user_id
    from soas_backend.models.user import User
    from soas_backend.models.role import UserRole, Role as RoleModel
    # Try to find an admin user
    result = await db.execute(
        select(User.id)
        .join(UserRole, User.id == UserRole.user_id)
        .join(RoleModel, UserRole.role_id == RoleModel.id)
        .where(RoleModel.name == "admin")
        .limit(1)
    )
    row = result.first()
    if row:
        _cached_system_user_id = row[0]
        return _cached_system_user_id
    # Fallback: first user
    result = await db.execute(select(User.id).limit(1))
    row = result.first()
    if row:
        _cached_system_user_id = row[0]
        return _cached_system_user_id
    return None


def _safe_filename(name: str) -> str:
    """Sanitize a string to be safe for filenames."""
    name = re.sub(r'[<>:"/\\|?*]', "_", name)
    name = name.strip(". ")
    return name or "unnamed"


def _uuid_str(val: Any) -> str | None:
    if val is None:
        return None
    return str(val)


# ---------------------------------------------------------------------------
# Automation
# ---------------------------------------------------------------------------

class AutomationSerializer:
    directory = "automations"

    @staticmethod
    def filename(automation: Automation) -> str:
        return f"{_safe_filename(automation.name)}.json"

    @staticmethod
    def serialize(automation: Automation) -> dict:
        return {
            "id": _uuid_str(automation.id),
            "name": automation.name,
            "description": automation.description,
            "status": automation.status,
            "graph_data": automation.graph_data,
            "parameters": automation.parameters,
            "timeout_seconds": automation.timeout_seconds,
            "max_retries": automation.max_retries,
            "version": automation.version,
            "tags": automation.tags or [],
            "trigger_tags": automation.trigger_tags or [],
            "is_trigger_enabled": automation.is_trigger_enabled,
            "documentation": automation.documentation,
        }

    @staticmethod
    async def export_all(db: AsyncSession, base_path: Path) -> int:
        result = await db.execute(select(Automation).order_by(Automation.name))
        automations = list(result.scalars().all())
        out_dir = base_path / AutomationSerializer.directory
        out_dir.mkdir(parents=True, exist_ok=True)
        for a in automations:
            fp = out_dir / AutomationSerializer.filename(a)
            fp.write_text(json.dumps(AutomationSerializer.serialize(a), indent=2, default=str), encoding="utf-8")
        return len(automations)

    @staticmethod
    async def import_all(db: AsyncSession, base_path: Path, last_sync_at: datetime | None = None) -> int:
        in_dir = base_path / AutomationSerializer.directory
        if not in_dir.exists():
            return 0
        count = 0
        for fp in in_dir.glob("*.json"):
            data = json.loads(fp.read_text(encoding="utf-8"))
            name = data.get("name")
            if not name:
                continue
            result = await db.execute(select(Automation).where(Automation.name == name))
            existing = result.scalar_one_or_none()
            if existing:
                # Last-write-wins: skip if DB entity was modified after last sync
                updated_at = getattr(existing, "updated_at", None)
                if last_sync_at and updated_at and updated_at > last_sync_at:
                    logger.debug("Git sync: skipping automation '%s' (DB is newer)", name)
                    continue
                existing.description = data.get("description")
                existing.status = data.get("status", "draft")
                existing.graph_data = data.get("graph_data")
                existing.parameters = data.get("parameters", [])
                existing.timeout_seconds = data.get("timeout_seconds", 300)
                existing.max_retries = data.get("max_retries", 0)
                existing.tags = data.get("tags", [])
                existing.trigger_tags = data.get("trigger_tags", [])
                existing.is_trigger_enabled = data.get("is_trigger_enabled", False)
                existing.documentation = data.get("documentation")
            else:
                user_id = await _get_system_user_id(db)
                if user_id:
                    db.add(Automation(
                        name=name,
                        description=data.get("description"),
                        status=data.get("status", "draft"),
                        graph_data=data.get("graph_data"),
                        parameters=data.get("parameters", []),
                        timeout_seconds=data.get("timeout_seconds", 300),
                        max_retries=data.get("max_retries", 0),
                        tags=data.get("tags", []),
                        trigger_tags=data.get("trigger_tags", []),
                        is_trigger_enabled=data.get("is_trigger_enabled", False),
                        documentation=data.get("documentation"),
                        created_by=user_id,
                    ))
                    logger.info("Git sync: created automation '%s'", name)
            count += 1
        return count


# ---------------------------------------------------------------------------
# Wiki
# ---------------------------------------------------------------------------

class WikiSerializer:
    directory = "wiki"

    @staticmethod
    def filename(page: WikiPage) -> str:
        return f"{_safe_filename(page.slug)}.md"

    @staticmethod
    def serialize(page: WikiPage) -> str:
        """Serialize to markdown with YAML frontmatter."""
        # Build parent slug reference
        parent_slug = None
        if page.parent:
            parent_slug = page.parent.slug

        frontmatter = {
            "id": _uuid_str(page.id),
            "title": page.title,
            "slug": page.slug,
            "tags": page.tags or [],
            "sort_order": page.sort_order,
            "icon": page.icon,
            "parent_slug": parent_slug,
            "status": page.status,
            "version": page.version,
        }
        # Simple YAML-like frontmatter (avoid pyyaml dependency)
        lines = ["---"]
        for k, v in frontmatter.items():
            if isinstance(v, list):
                lines.append(f"{k}: {json.dumps(v)}")
            elif v is None:
                lines.append(f"{k}: null")
            else:
                lines.append(f"{k}: {json.dumps(v)}")
        lines.append("---")
        lines.append("")
        # Convert HTML content to Markdown for human-readable git files
        lines.append(_html_to_markdown(page.content or ""))
        return "\n".join(lines)

    @staticmethod
    def _parse_frontmatter(text: str) -> tuple[dict, str]:
        """Parse YAML frontmatter and markdown content."""
        if not text.startswith("---"):
            return {}, text
        parts = text.split("---", 2)
        if len(parts) < 3:
            return {}, text
        meta_str = parts[1].strip()
        content = parts[2].strip()
        meta: dict = {}
        for line in meta_str.split("\n"):
            if ":" not in line:
                continue
            key, val = line.split(":", 1)
            key = key.strip()
            val = val.strip()
            try:
                meta[key] = json.loads(val)
            except (json.JSONDecodeError, ValueError):
                meta[key] = val if val != "null" else None
        return meta, content

    @staticmethod
    async def export_all(db: AsyncSession, base_path: Path) -> int:
        result = await db.execute(
            select(WikiPage).options(selectinload(WikiPage.parent)).order_by(WikiPage.slug)
        )
        pages = list(result.scalars().all())
        out_dir = base_path / WikiSerializer.directory
        out_dir.mkdir(parents=True, exist_ok=True)
        for p in pages:
            fp = out_dir / WikiSerializer.filename(p)
            fp.write_text(WikiSerializer.serialize(p), encoding="utf-8")
        return len(pages)

    @staticmethod
    async def import_all(db: AsyncSession, base_path: Path, last_sync_at: datetime | None = None) -> int:
        in_dir = base_path / WikiSerializer.directory
        if not in_dir.exists():
            return 0
        count = 0
        for fp in in_dir.glob("*.md"):
            text = fp.read_text(encoding="utf-8")
            meta, content = WikiSerializer._parse_frontmatter(text)
            slug = meta.get("slug")
            if not slug:
                # Derive slug from filename for files without frontmatter
                slug = fp.stem
                content = text  # entire file is content
            # Convert markdown content to HTML for Tiptap/DB
            html_content = _markdown_to_html(content)
            result = await db.execute(select(WikiPage).where(WikiPage.slug == slug))
            existing = result.scalar_one_or_none()
            if existing:
                # Last-write-wins: skip if DB entity was modified after last sync
                updated_at = getattr(existing, "updated_at", None)
                if last_sync_at and updated_at and updated_at > last_sync_at:
                    logger.debug("Git sync: skipping wiki page '%s' (DB is newer)", slug)
                    continue
                existing.title = meta.get("title", existing.title)
                existing.content = html_content
                existing.tags = meta.get("tags", existing.tags)
                existing.sort_order = meta.get("sort_order", existing.sort_order)
                existing.icon = meta.get("icon")
                existing.status = meta.get("status", existing.status)
            else:
                user_id = await _get_system_user_id(db)
                if user_id:
                    db.add(WikiPage(
                        title=meta.get("title", slug),
                        slug=slug,
                        content=html_content,
                        tags=meta.get("tags", []),
                        sort_order=meta.get("sort_order", 0),
                        icon=meta.get("icon"),
                        status=meta.get("status", "published"),
                        created_by=user_id,
                    ))
                    logger.info("Git sync: created wiki page '%s'", slug)
            count += 1
        return count


# ---------------------------------------------------------------------------
# Code Library
# ---------------------------------------------------------------------------

class CodeLibrarySerializer:
    directory = "code_library"

    @staticmethod
    def filename(block: CodeLibraryBlock) -> str:
        return f"{_safe_filename(block.name)}.json"

    @staticmethod
    def serialize(block: CodeLibraryBlock) -> dict:
        return {
            "id": _uuid_str(block.id),
            "name": block.name,
            "description": block.description,
            "code": block.code,
            "language": block.language,
            "version": block.version,
            "is_public": block.is_public,
            "tags": block.tags or [],
            "input_ports": block.input_ports,
            "output_ports": block.output_ports,
        }

    @staticmethod
    async def export_all(db: AsyncSession, base_path: Path) -> int:
        result = await db.execute(select(CodeLibraryBlock).order_by(CodeLibraryBlock.name))
        blocks = list(result.scalars().all())
        out_dir = base_path / CodeLibrarySerializer.directory
        out_dir.mkdir(parents=True, exist_ok=True)
        for b in blocks:
            fp = out_dir / CodeLibrarySerializer.filename(b)
            fp.write_text(json.dumps(CodeLibrarySerializer.serialize(b), indent=2, default=str), encoding="utf-8")
        return len(blocks)

    @staticmethod
    async def import_all(db: AsyncSession, base_path: Path, last_sync_at: datetime | None = None) -> int:
        in_dir = base_path / CodeLibrarySerializer.directory
        if not in_dir.exists():
            return 0
        count = 0
        for fp in in_dir.glob("*.json"):
            data = json.loads(fp.read_text(encoding="utf-8"))
            name = data.get("name")
            if not name:
                continue
            result = await db.execute(select(CodeLibraryBlock).where(CodeLibraryBlock.name == name))
            existing = result.scalar_one_or_none()
            if existing:
                updated_at = getattr(existing, "updated_at", None)
                if last_sync_at and updated_at and updated_at > last_sync_at:
                    logger.debug("Git sync: skipping code block '%s' (DB is newer)", name)
                    continue
                existing.description = data.get("description")
                existing.code = data.get("code", "")
                existing.language = data.get("language", "python")
                existing.is_public = data.get("is_public", False)
                existing.tags = data.get("tags", [])
                existing.input_ports = data.get("input_ports")
                existing.output_ports = data.get("output_ports")
            else:
                user_id = await _get_system_user_id(db)
                if user_id:
                    db.add(CodeLibraryBlock(
                        name=name,
                        description=data.get("description"),
                        code=data.get("code", ""),
                        language=data.get("language", "python"),
                        is_public=data.get("is_public", False),
                        tags=data.get("tags", []),
                        input_ports=data.get("input_ports"),
                        output_ports=data.get("output_ports"),
                        created_by=user_id,
                    ))
                    logger.info("Git sync: created code block '%s'", name)
            count += 1
        return count


# ---------------------------------------------------------------------------
# App Settings (bulk)
# ---------------------------------------------------------------------------

class AppSettingsSerializer:
    directory = "settings"

    @staticmethod
    async def export_all(db: AsyncSession, base_path: Path) -> int:
        result = await db.execute(select(AppSetting).order_by(AppSetting.key))
        settings = list(result.scalars().all())
        out_dir = base_path / AppSettingsSerializer.directory
        out_dir.mkdir(parents=True, exist_ok=True)
        data: dict[str, Any] = {}
        for s in settings:
            # Skip git sync auth token (it's a secret)
            if s.key == "git_sync_auth_token":
                data[s.key] = SECRET_PLACEHOLDER
            else:
                data[s.key] = s.value
        fp = out_dir / "app_settings.json"
        fp.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
        return len(settings)

    @staticmethod
    async def import_all(db: AsyncSession, base_path: Path, last_sync_at: datetime | None = None) -> int:
        fp = base_path / AppSettingsSerializer.directory / "app_settings.json"
        if not fp.exists():
            return 0
        data = json.loads(fp.read_text(encoding="utf-8"))
        count = 0
        for key, value in data.items():
            if value == SECRET_PLACEHOLDER:
                continue
            result = await db.execute(select(AppSetting).where(AppSetting.key == key))
            existing = result.scalar_one_or_none()
            if existing:
                updated_at = getattr(existing, "updated_at", None)
                if last_sync_at and updated_at and updated_at > last_sync_at:
                    continue
                existing.value = str(value)
            else:
                db.add(AppSetting(key=key, value=str(value)))
            count += 1
        return count


# ---------------------------------------------------------------------------
# Roles (with permissions)
# ---------------------------------------------------------------------------

class RoleSerializer:
    directory = "roles"

    @staticmethod
    def filename(role: Role) -> str:
        return f"{_safe_filename(role.name)}.json"

    @staticmethod
    def serialize(role: Role, permission_strings: list[str]) -> dict:
        return {
            "id": _uuid_str(role.id),
            "name": role.name,
            "display_name": role.display_name,
            "description": role.description,
            "is_system": role.is_system,
            "permissions": sorted(permission_strings),
        }

    @staticmethod
    async def export_all(db: AsyncSession, base_path: Path) -> int:
        result = await db.execute(
            select(Role).options(
                selectinload(Role.role_permissions).selectinload(RolePermission.permission)
            ).order_by(Role.name)
        )
        roles = list(result.scalars().all())
        out_dir = base_path / RoleSerializer.directory
        out_dir.mkdir(parents=True, exist_ok=True)
        for r in roles:
            perms = [
                f"{rp.permission.resource}:{rp.permission.action}"
                for rp in r.role_permissions
                if rp.permission
            ]
            fp = out_dir / RoleSerializer.filename(r)
            fp.write_text(json.dumps(RoleSerializer.serialize(r, perms), indent=2, default=str), encoding="utf-8")
        return len(roles)

    @staticmethod
    async def import_all(db: AsyncSession, base_path: Path, last_sync_at: datetime | None = None) -> int:
        in_dir = base_path / RoleSerializer.directory
        if not in_dir.exists():
            return 0
        count = 0
        for fp in in_dir.glob("*.json"):
            data = json.loads(fp.read_text(encoding="utf-8"))
            name = data.get("name")
            if not name:
                continue
            result = await db.execute(
                select(Role).options(selectinload(Role.role_permissions)).where(Role.name == name)
            )
            existing = result.scalar_one_or_none()
            if existing:
                updated_at = getattr(existing, "updated_at", None)
                if last_sync_at and updated_at and updated_at > last_sync_at:
                    logger.debug("Git sync: skipping role '%s' (DB is newer)", name)
                    count += 1
                    continue
                existing.display_name = data.get("display_name", existing.display_name)
                existing.description = data.get("description")

                # Sync permissions
                desired_perms = set(data.get("permissions", []))
                # Load all permissions to map resource:action -> id
                all_perms_result = await db.execute(select(Permission))
                perm_map = {
                    f"{p.resource}:{p.action}": p.id
                    for p in all_perms_result.scalars().all()
                }
                # Current permissions
                current_perms = {
                    rp.permission_id for rp in existing.role_permissions
                }
                # Resolve desired
                desired_ids = set()
                for ps in desired_perms:
                    pid = perm_map.get(ps)
                    if pid:
                        desired_ids.add(pid)

                # Add missing
                for pid in desired_ids - current_perms:
                    db.add(RolePermission(role_id=existing.id, permission_id=pid))
                # Remove extra
                for rp in list(existing.role_permissions):
                    if rp.permission_id not in desired_ids:
                        await db.delete(rp)
            else:
                new_role = Role(
                    name=name,
                    display_name=data.get("display_name", name),
                    description=data.get("description"),
                    is_system=data.get("is_system", False),
                )
                db.add(new_role)
                await db.flush()
                # Assign permissions
                all_perms_result = await db.execute(select(Permission))
                perm_map = {
                    f"{p.resource}:{p.action}": p.id
                    for p in all_perms_result.scalars().all()
                }
                for ps in data.get("permissions", []):
                    pid = perm_map.get(ps)
                    if pid:
                        db.add(RolePermission(role_id=new_role.id, permission_id=pid))
                logger.info("Git sync: created role '%s'", name)
            count += 1
        return count


# ---------------------------------------------------------------------------
# Form Definitions
# ---------------------------------------------------------------------------

class FormDefinitionSerializer:
    directory = "form_definitions"

    @staticmethod
    def filename(fd: FormDefinition) -> str:
        return f"{_safe_filename(fd.name)}.json"

    @staticmethod
    def serialize(fd: FormDefinition) -> dict:
        return {
            "id": _uuid_str(fd.id),
            "name": fd.name,
            "description": fd.description,
            "fields": fd.fields,
            "is_active": fd.is_active,
        }

    @staticmethod
    async def export_all(db: AsyncSession, base_path: Path) -> int:
        result = await db.execute(select(FormDefinition).order_by(FormDefinition.name))
        items = list(result.scalars().all())
        out_dir = base_path / FormDefinitionSerializer.directory
        out_dir.mkdir(parents=True, exist_ok=True)
        for fd in items:
            fp = out_dir / FormDefinitionSerializer.filename(fd)
            fp.write_text(json.dumps(FormDefinitionSerializer.serialize(fd), indent=2, default=str), encoding="utf-8")
        return len(items)

    @staticmethod
    async def import_all(db: AsyncSession, base_path: Path, last_sync_at: datetime | None = None) -> int:
        in_dir = base_path / FormDefinitionSerializer.directory
        if not in_dir.exists():
            return 0
        count = 0
        for fp in in_dir.glob("*.json"):
            data = json.loads(fp.read_text(encoding="utf-8"))
            name = data.get("name")
            if not name:
                continue
            result = await db.execute(select(FormDefinition).where(FormDefinition.name == name))
            existing = result.scalar_one_or_none()
            if existing:
                updated_at = getattr(existing, "updated_at", None)
                if last_sync_at and updated_at and updated_at > last_sync_at:
                    logger.debug("Git sync: skipping form definition '%s' (DB is newer)", name)
                    continue
                existing.description = data.get("description")
                existing.fields = data.get("fields", [])
                existing.is_active = data.get("is_active", True)
            else:
                user_id = await _get_system_user_id(db)
                if user_id:
                    db.add(FormDefinition(
                        name=name,
                        description=data.get("description"),
                        fields=data.get("fields", []),
                        is_active=data.get("is_active", True),
                        created_by=user_id,
                    ))
                    logger.info("Git sync: created form definition '%s'", name)
            count += 1
        return count


# ---------------------------------------------------------------------------
# SOAS Variables
# ---------------------------------------------------------------------------

class SOASVariableSerializer:
    directory = "variables"

    @staticmethod
    def filename(var: SOASVariable) -> str:
        return f"{_safe_filename(var.name)}.json"

    @staticmethod
    def serialize(var: SOASVariable) -> dict:
        return {
            "id": _uuid_str(var.id),
            "name": var.name,
            "description": var.description,
            "value": SECRET_PLACEHOLDER if var.is_secret else var.value,
            "is_secret": var.is_secret,
        }

    @staticmethod
    async def export_all(db: AsyncSession, base_path: Path) -> int:
        result = await db.execute(select(SOASVariable).order_by(SOASVariable.name))
        items = list(result.scalars().all())
        out_dir = base_path / SOASVariableSerializer.directory
        out_dir.mkdir(parents=True, exist_ok=True)
        for v in items:
            fp = out_dir / SOASVariableSerializer.filename(v)
            fp.write_text(json.dumps(SOASVariableSerializer.serialize(v), indent=2, default=str), encoding="utf-8")
        return len(items)

    @staticmethod
    async def import_all(db: AsyncSession, base_path: Path, last_sync_at: datetime | None = None) -> int:
        in_dir = base_path / SOASVariableSerializer.directory
        if not in_dir.exists():
            return 0
        count = 0
        for fp in in_dir.glob("*.json"):
            data = json.loads(fp.read_text(encoding="utf-8"))
            name = data.get("name")
            if not name:
                continue
            result = await db.execute(select(SOASVariable).where(SOASVariable.name == name))
            existing = result.scalar_one_or_none()
            if existing:
                updated_at = getattr(existing, "updated_at", None)
                if last_sync_at and updated_at and updated_at > last_sync_at:
                    logger.debug("Git sync: skipping variable '%s' (DB is newer)", name)
                    continue
                existing.description = data.get("description")
                # Only update value if it's not the secret placeholder
                val = data.get("value")
                if val != SECRET_PLACEHOLDER:
                    existing.value = val
                existing.is_secret = data.get("is_secret", existing.is_secret)
            else:
                val = data.get("value", "")
                if val == SECRET_PLACEHOLDER:
                    val = ""
                user_id = await _get_system_user_id(db)
                if user_id:
                    db.add(SOASVariable(
                        name=name,
                        description=data.get("description"),
                        value=val,
                        is_secret=data.get("is_secret", False),
                        created_by=user_id,
                    ))
                    logger.info("Git sync: created variable '%s'", name)
            count += 1
        return count


# ---------------------------------------------------------------------------
# Normalization (groups + rules in one file)
# ---------------------------------------------------------------------------

class NormalizationSerializer:
    directory = "normalization"

    @staticmethod
    async def export_all(db: AsyncSession, base_path: Path) -> int:
        result = await db.execute(
            select(NormalizationGroup)
            .options(selectinload(NormalizationGroup.rules))
            .order_by(NormalizationGroup.display_order)
        )
        groups = list(result.scalars().all())
        out_dir = base_path / NormalizationSerializer.directory
        out_dir.mkdir(parents=True, exist_ok=True)
        data = []
        for g in groups:
            group_data = {
                "id": _uuid_str(g.id),
                "name": g.name,
                "display_name": g.display_name,
                "description": g.description,
                "icon": g.icon,
                "display_order": g.display_order,
                "rules": [
                    {
                        "id": _uuid_str(r.id),
                        "source_path": r.source_path,
                        "target_field": r.target_field,
                        "transform_type": r.transform_type,
                        "transform_config": r.transform_config,
                        "is_required": r.is_required,
                        "default_value": r.default_value,
                        "display_order": r.display_order,
                        "is_enabled": r.is_enabled,
                    }
                    for r in sorted(g.rules, key=lambda x: x.display_order)
                ],
            }
            data.append(group_data)
        fp = out_dir / "groups.json"
        fp.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
        return len(groups)

    @staticmethod
    async def import_all(db: AsyncSession, base_path: Path, last_sync_at: datetime | None = None) -> int:
        fp = base_path / NormalizationSerializer.directory / "groups.json"
        if not fp.exists():
            return 0
        data = json.loads(fp.read_text(encoding="utf-8"))
        count = 0
        for group_data in data:
            name = group_data.get("name")
            if not name:
                continue
            result = await db.execute(
                select(NormalizationGroup)
                .options(selectinload(NormalizationGroup.rules))
                .where(NormalizationGroup.name == name)
            )
            existing = result.scalar_one_or_none()
            if existing:
                updated_at = getattr(existing, "updated_at", None)
                if last_sync_at and updated_at and updated_at > last_sync_at:
                    logger.debug("Git sync: skipping normalization group '%s' (DB is newer)", name)
                    count += 1
                    continue
                existing.display_name = group_data.get("display_name", existing.display_name)
                existing.description = group_data.get("description")
                existing.icon = group_data.get("icon")
                existing.display_order = group_data.get("display_order", existing.display_order)

                # Sync rules by target_field + source_path
                incoming_rules = group_data.get("rules", [])
                existing_map = {
                    (r.source_path, r.target_field): r for r in existing.rules
                }
                for rule_data in incoming_rules:
                    key = (rule_data["source_path"], rule_data["target_field"])
                    if key in existing_map:
                        er = existing_map[key]
                        er.transform_type = rule_data.get("transform_type", er.transform_type)
                        er.transform_config = rule_data.get("transform_config", er.transform_config)
                        er.is_required = rule_data.get("is_required", er.is_required)
                        er.default_value = rule_data.get("default_value")
                        er.display_order = rule_data.get("display_order", er.display_order)
                        er.is_enabled = rule_data.get("is_enabled", er.is_enabled)
                    else:
                        new_rule = NormalizationRule(
                            group_id=existing.id,
                            source_path=rule_data["source_path"],
                            target_field=rule_data["target_field"],
                            transform_type=rule_data.get("transform_type", "direct"),
                            transform_config=rule_data.get("transform_config", {}),
                            is_required=rule_data.get("is_required", False),
                            default_value=rule_data.get("default_value"),
                            display_order=rule_data.get("display_order", 0),
                            is_enabled=rule_data.get("is_enabled", True),
                        )
                        db.add(new_rule)
            else:
                new_group = NormalizationGroup(
                    name=name,
                    display_name=group_data.get("display_name", name),
                    description=group_data.get("description"),
                    icon=group_data.get("icon"),
                    display_order=group_data.get("display_order", 0),
                )
                db.add(new_group)
                await db.flush()
                for rule_data in group_data.get("rules", []):
                    new_rule = NormalizationRule(
                        group_id=new_group.id,
                        source_path=rule_data["source_path"],
                        target_field=rule_data["target_field"],
                        transform_type=rule_data.get("transform_type", "direct"),
                        transform_config=rule_data.get("transform_config", {}),
                        is_required=rule_data.get("is_required", False),
                        default_value=rule_data.get("default_value"),
                        display_order=rule_data.get("display_order", 0),
                        is_enabled=rule_data.get("is_enabled", True),
                    )
                    db.add(new_rule)
            count += 1
        return count


# ---------------------------------------------------------------------------
# Webhook Sources
# ---------------------------------------------------------------------------

class WebhookSourceSerializer:
    directory = "webhook_sources"

    @staticmethod
    def filename(source: WebhookSource) -> str:
        return f"{_safe_filename(source.name)}.json"

    @staticmethod
    def serialize(source: WebhookSource) -> dict:
        automations = []
        for sa in sorted(source.automations, key=lambda x: x.run_order):
            automations.append({
                "automation_id": _uuid_str(sa.automation_id),
                "is_enabled": sa.is_enabled,
                "run_order": sa.run_order,
            })
        return {
            "id": _uuid_str(source.id),
            "name": source.name,
            "description": source.description,
            "icon": source.icon,
            "automations": automations,
        }

    @staticmethod
    async def export_all(db: AsyncSession, base_path: Path) -> int:
        result = await db.execute(
            select(WebhookSource)
            .options(selectinload(WebhookSource.automations))
            .order_by(WebhookSource.name)
        )
        sources = list(result.scalars().all())
        out_dir = base_path / WebhookSourceSerializer.directory
        out_dir.mkdir(parents=True, exist_ok=True)
        for s in sources:
            fp = out_dir / WebhookSourceSerializer.filename(s)
            fp.write_text(json.dumps(WebhookSourceSerializer.serialize(s), indent=2, default=str), encoding="utf-8")
        return len(sources)

    @staticmethod
    async def import_all(db: AsyncSession, base_path: Path, last_sync_at: datetime | None = None) -> int:
        in_dir = base_path / WebhookSourceSerializer.directory
        if not in_dir.exists():
            return 0
        count = 0
        for fp in in_dir.glob("*.json"):
            data = json.loads(fp.read_text(encoding="utf-8"))
            name = data.get("name")
            if not name:
                continue
            result = await db.execute(
                select(WebhookSource)
                .options(selectinload(WebhookSource.automations))
                .where(WebhookSource.name == name)
            )
            existing = result.scalar_one_or_none()
            if existing:
                updated_at = getattr(existing, "updated_at", None)
                if last_sync_at and updated_at and updated_at > last_sync_at:
                    logger.debug("Git sync: skipping webhook source '%s' (DB is newer)", name)
                    continue
                existing.description = data.get("description")
                existing.icon = data.get("icon")
            else:
                user_id = await _get_system_user_id(db)
                if user_id:
                    db.add(WebhookSource(
                        name=name,
                        description=data.get("description"),
                        icon=data.get("icon"),
                        created_by=user_id,
                    ))
                    logger.info("Git sync: created webhook source '%s'", name)
            count += 1
        return count


# ---------------------------------------------------------------------------
# Incident Variables
# ---------------------------------------------------------------------------

class IncidentVariableSerializer:
    directory = "incident_variables"

    @staticmethod
    def filename(var: IncidentVariable) -> str:
        return f"{_safe_filename(var.name)}.json"

    @staticmethod
    def serialize(var: IncidentVariable) -> dict:
        return {
            "id": _uuid_str(var.id),
            "name": var.name,
            "description": var.description,
            "default_enabled": var.default_enabled,
        }

    @staticmethod
    async def export_all(db: AsyncSession, base_path: Path) -> int:
        result = await db.execute(select(IncidentVariable).order_by(IncidentVariable.name))
        items = list(result.scalars().all())
        out_dir = base_path / IncidentVariableSerializer.directory
        out_dir.mkdir(parents=True, exist_ok=True)
        for v in items:
            fp = out_dir / IncidentVariableSerializer.filename(v)
            fp.write_text(json.dumps(IncidentVariableSerializer.serialize(v), indent=2, default=str), encoding="utf-8")
        return len(items)

    @staticmethod
    async def import_all(db: AsyncSession, base_path: Path, last_sync_at: datetime | None = None) -> int:
        in_dir = base_path / IncidentVariableSerializer.directory
        if not in_dir.exists():
            return 0
        count = 0
        for fp in in_dir.glob("*.json"):
            data = json.loads(fp.read_text(encoding="utf-8"))
            name = data.get("name")
            if not name:
                continue
            result = await db.execute(select(IncidentVariable).where(IncidentVariable.name == name))
            existing = result.scalar_one_or_none()
            if existing:
                updated_at = getattr(existing, "updated_at", None)
                if last_sync_at and updated_at and updated_at > last_sync_at:
                    logger.debug("Git sync: skipping incident variable '%s' (DB is newer)", name)
                    continue
                existing.description = data.get("description")
                existing.default_enabled = data.get("default_enabled", True)
            else:
                user_id = await _get_system_user_id(db)
                if user_id:
                    db.add(IncidentVariable(
                        name=name,
                        description=data.get("description"),
                        default_enabled=data.get("default_enabled", True),
                        created_by=user_id,
                    ))
                    logger.info("Git sync: created incident variable '%s'", name)
            count += 1
        return count


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

class UserRoleSerializer:
    """Serializer for user_role change request snapshots.

    Writes one file per *user* (``{username}.json``) to the ``users/``
    directory.  The file contains a ``roles`` list so that all role
    assignments for a user live in a single file.

    Not used in full_sync (role assignments are managed via CRs only),
    but used for per-entity branch commits.
    """

    directory = "users"

    @staticmethod
    def filename(snapshot: dict) -> str:
        target = _safe_filename(snapshot.get("target_username", "unknown"))
        return f"{target}.json"

    @staticmethod
    def serialize(snapshot: dict) -> dict:
        return {
            "user_id": snapshot.get("user_id"),
            "role_id": snapshot.get("role_id"),
            "role_name": snapshot.get("role_name"),
            "role_display_name": snapshot.get("role_display_name"),
            "target_username": snapshot.get("target_username"),
        }

    @staticmethod
    def merge_into_file(existing: dict | None, snapshot: dict, action: str) -> dict:
        """Merge a role action into an existing user roles file.

        *existing* is the parsed JSON of the current file (or ``None``).
        Returns the updated dict to be written back.
        """
        if existing is None:
            existing = {
                "user_id": snapshot.get("user_id"),
                "target_username": snapshot.get("target_username"),
                "roles": [],
            }

        roles: list[dict] = existing.get("roles", [])
        role_id = snapshot.get("role_id")

        if action == "delete":
            roles = [r for r in roles if r.get("role_id") != role_id]
        else:
            # Upsert: replace if exists, append if new
            found = False
            for i, r in enumerate(roles):
                if r.get("role_id") == role_id:
                    roles[i] = {
                        "role_id": role_id,
                        "role_name": snapshot.get("role_name"),
                        "role_display_name": snapshot.get("role_display_name"),
                    }
                    found = True
                    break
            if not found:
                roles.append({
                    "role_id": role_id,
                    "role_name": snapshot.get("role_name"),
                    "role_display_name": snapshot.get("role_display_name"),
                })

        # Sort by role_name for deterministic output (helps git diffs)
        roles.sort(key=lambda r: r.get("role_name", ""))

        existing["roles"] = roles
        return existing

    # No export_all / import_all — user_role is not part of full_sync.
    # The entity is written via export_one() during CR draft creation.


SERIALIZER_REGISTRY: dict[str, type] = {
    "automations": AutomationSerializer,
    "wiki": WikiSerializer,
    "code_library": CodeLibrarySerializer,
    "settings": AppSettingsSerializer,
    "roles": RoleSerializer,
    "form_definitions": FormDefinitionSerializer,
    "variables": SOASVariableSerializer,
    "normalization": NormalizationSerializer,
    "webhook_sources": WebhookSourceSerializer,
    "incident_variables": IncidentVariableSerializer,
    "users": UserRoleSerializer,
}

# Maps change_request entity_type names → serializer registry keys
ENTITY_TYPE_TO_SERIALIZER_KEY: dict[str, str] = {
    "automation": "automations",
    "wiki_page": "wiki",
    "code_library": "code_library",
    "soas_variable": "variables",
    "incident_variable": "incident_variables",
    "role": "roles",
    "form_definition": "form_definitions",
    "webhook_source": "webhook_sources",
    "normalization": "normalization",
    "app_settings": "settings",
    "user_role": "users",
}


# ---------------------------------------------------------------------------
# Single-entity read / write helpers (for branch versioning)
# ---------------------------------------------------------------------------


def _snapshot_filename(entity_type: str, snapshot: dict) -> str:
    """Derive a filename from a snapshot dict based on entity type."""
    if entity_type == "wiki_page":
        slug = snapshot.get("slug") or snapshot.get("title", "untitled")
        return f"{_safe_filename(slug)}.md"
    # Most JSON entity types use "name" as the key
    name = snapshot.get("name") or snapshot.get("title") or str(snapshot.get("id", "unnamed"))
    return f"{_safe_filename(name)}.json"


def _serializer_dir(entity_type: str) -> str:
    """Get the directory name for a given entity type."""
    key = ENTITY_TYPE_TO_SERIALIZER_KEY.get(entity_type, entity_type)
    cls = SERIALIZER_REGISTRY.get(key)
    if cls and hasattr(cls, "directory"):
        return cls.directory
    return key


def export_one(
    entity_type: str,
    snapshot: dict,
    base_path: Path,
    *,
    action: str = "create",
) -> Path:
    """Write a single entity snapshot to a file on disk.

    Works for all JSON-based entity types and wiki (markdown).
    Returns the path of the written file.
    """
    directory = _serializer_dir(entity_type)
    out_dir = base_path / directory
    out_dir.mkdir(parents=True, exist_ok=True)

    if entity_type == "user_role":
        filename = UserRoleSerializer.filename(snapshot)
    else:
        filename = _snapshot_filename(entity_type, snapshot)
    fp = out_dir / filename

    if entity_type == "user_role":
        # Read-merge-write: read existing file (from dev base), merge the
        # new role into it, then write back.  This avoids git conflicts
        # when multiple role CRs for the same user merge sequentially.
        existing = None
        if fp.exists():
            try:
                existing = json.loads(fp.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                existing = None
        merged = UserRoleSerializer.merge_into_file(existing, snapshot, action)
        fp.write_text(json.dumps(merged, indent=2, default=str), encoding="utf-8")
    elif entity_type == "wiki_page":
        # Write markdown with YAML frontmatter
        meta = {k: v for k, v in snapshot.items() if k != "content"}
        lines = ["---"]
        for k, v in meta.items():
            if isinstance(v, list):
                lines.append(f"{k}: {json.dumps(v)}")
            elif v is None:
                lines.append(f"{k}: null")
            else:
                lines.append(f"{k}: {json.dumps(v)}")
        lines.append("---")
        lines.append("")
        lines.append(_html_to_markdown(snapshot.get("content", "")))
        fp.write_text("\n".join(lines), encoding="utf-8")
    elif entity_type == "normalization":
        # Normalization uses a single groups.json file
        fp = out_dir / "groups.json"
        fp.write_text(json.dumps(snapshot, indent=2, default=str), encoding="utf-8")
    elif entity_type == "app_settings":
        fp = out_dir / "app_settings.json"
        fp.write_text(json.dumps(snapshot, indent=2, default=str), encoding="utf-8")
    else:
        # Standard JSON entity
        fp.write_text(json.dumps(snapshot, indent=2, default=str), encoding="utf-8")

    return fp


def read_one(entity_type: str, entity_id: str, base_path: Path) -> dict | None:
    """Read a single entity from files by scanning for its ID.

    Returns the parsed snapshot dict or ``None`` if not found.
    """
    directory = _serializer_dir(entity_type)
    in_dir = base_path / directory
    if not in_dir.exists():
        return None

    entity_id_str = str(entity_id)

    if entity_type == "wiki_page":
        for fp in in_dir.glob("*.md"):
            text = fp.read_text(encoding="utf-8")
            meta, content = WikiSerializer._parse_frontmatter(text)
            if meta.get("id") == entity_id_str:
                meta["content"] = _markdown_to_html(content)
                return meta
        return None

    if entity_type == "normalization":
        fp = in_dir / "groups.json"
        if not fp.exists():
            return None
        data = json.loads(fp.read_text(encoding="utf-8"))
        # Normalization is a list of groups; find by ID
        if isinstance(data, list):
            for group in data:
                if group.get("id") == entity_id_str:
                    return group
        return data if isinstance(data, dict) else None

    if entity_type == "app_settings":
        fp = in_dir / "app_settings.json"
        if not fp.exists():
            return None
        return json.loads(fp.read_text(encoding="utf-8"))

    # Standard JSON entity: scan all .json files
    for fp in in_dir.glob("*.json"):
        data = json.loads(fp.read_text(encoding="utf-8"))
        if data.get("id") == entity_id_str:
            return data

    return None


def read_all_of_type(entity_type: str, base_path: Path) -> list[dict]:
    """Read all entities of a type from files.  Returns list of snapshots."""
    directory = _serializer_dir(entity_type)
    in_dir = base_path / directory
    if not in_dir.exists():
        return []

    results: list[dict] = []

    if entity_type == "wiki_page":
        for fp in sorted(in_dir.glob("*.md")):
            text = fp.read_text(encoding="utf-8")
            meta, content = WikiSerializer._parse_frontmatter(text)
            if meta:
                meta["content"] = _markdown_to_html(content)
                results.append(meta)
        return results

    if entity_type in ("normalization", "app_settings"):
        fname = "groups.json" if entity_type == "normalization" else "app_settings.json"
        fp = in_dir / fname
        if fp.exists():
            data = json.loads(fp.read_text(encoding="utf-8"))
            if isinstance(data, list):
                return data
            return [data] if data else []
        return []

    for fp in sorted(in_dir.glob("*.json")):
        data = json.loads(fp.read_text(encoding="utf-8"))
        results.append(data)
    return results

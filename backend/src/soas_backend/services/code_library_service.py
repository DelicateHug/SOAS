"""Code Library business logic."""

from uuid import UUID

from sqlalchemy import and_, delete, exists, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from soas_backend.models.code_library import (
    CodeLibraryBlock,
    CodeLibraryFavorite,
    CodeLibraryPermission,
    CodeLibraryUserBlockAssignment,
    CodeLibraryUserCategory,
)
from soas_backend.models.role import UserRole


class CodeLibraryService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(
        self,
        name: str,
        created_by: UUID,
        code: str = "",
        language: str = "python",
        description: str | None = None,
        is_public: bool = False,
        tags: list[str] | None = None,
        input_ports: list[dict] | None = None,
        output_ports: list[dict] | None = None,
    ) -> CodeLibraryBlock:
        block = CodeLibraryBlock(
            name=name,
            description=description,
            code=code,
            language=language,
            is_public=is_public,
            tags=tags or [],
            input_ports=input_ports,
            output_ports=output_ports,
            created_by=created_by,
        )
        self.db.add(block)
        await self.db.flush()

        # Auto-assign read+use permissions for creator's roles
        user_roles = await self.db.execute(
            select(UserRole.role_id).where(UserRole.user_id == created_by)
        )
        for (role_id,) in user_roles.all():
            self.db.add(
                CodeLibraryPermission(
                    block_id=block.id,
                    role_id=role_id,
                    can_read=True,
                    can_edit=True,
                    can_use=True,
                    granted_by=created_by,
                )
            )
        await self.db.flush()
        return block

    async def get(self, block_id: UUID) -> CodeLibraryBlock | None:
        result = await self.db.execute(
            select(CodeLibraryBlock)
            .options(selectinload(CodeLibraryBlock.creator))
            .where(CodeLibraryBlock.id == block_id)
        )
        return result.scalar_one_or_none()

    async def list_blocks(
        self,
        user_id: UUID,
        search: str | None = None,
        language: str | None = None,
        page: int = 1,
        per_page: int = 50,
    ) -> tuple[list[CodeLibraryBlock], int]:
        """List blocks visible to the user (own + public + permitted)."""
        # Get user's role IDs
        role_result = await self.db.execute(
            select(UserRole.role_id).where(UserRole.user_id == user_id)
        )
        user_role_ids = [r for (r,) in role_result.all()]

        # Visibility: own OR public OR has permission via role
        visibility = or_(
            CodeLibraryBlock.created_by == user_id,
            CodeLibraryBlock.is_public.is_(True),
        )
        if user_role_ids:
            has_perm = exists(
                select(CodeLibraryPermission.block_id).where(
                    and_(
                        CodeLibraryPermission.block_id == CodeLibraryBlock.id,
                        CodeLibraryPermission.role_id.in_(user_role_ids),
                        CodeLibraryPermission.can_read.is_(True),
                    )
                )
            )
            visibility = or_(visibility, has_perm)

        query = select(CodeLibraryBlock).options(
            selectinload(CodeLibraryBlock.creator)
        ).where(visibility)

        if search:
            pattern = f"%{search}%"
            query = query.where(
                or_(
                    CodeLibraryBlock.name.ilike(pattern),
                    CodeLibraryBlock.description.ilike(pattern),
                )
            )
        if language:
            query = query.where(CodeLibraryBlock.language == language)

        # Count
        count_q = select(func.count()).select_from(query.subquery())
        total = (await self.db.execute(count_q)).scalar() or 0

        # Paginate
        query = query.order_by(CodeLibraryBlock.updated_at.desc())
        query = query.offset((page - 1) * per_page).limit(per_page)
        result = await self.db.execute(query)
        blocks = list(result.scalars().all())

        return blocks, total

    async def update(self, block_id: UUID, **kwargs) -> CodeLibraryBlock | None:
        block = await self.get(block_id)
        if not block:
            return None

        for key, value in kwargs.items():
            if value is not None and hasattr(block, key):
                setattr(block, key, value)

        # Bump version on code changes
        if "code" in kwargs and kwargs["code"] is not None:
            block.version += 1

        await self.db.flush()
        return block

    async def delete(self, block_id: UUID) -> bool:
        block = await self.get(block_id)
        if not block:
            return False
        await self.db.delete(block)
        await self.db.flush()
        return True

    async def set_permissions(
        self,
        block_id: UUID,
        permissions: list[dict],
        granted_by: UUID,
    ) -> None:
        # Remove existing permissions
        await self.db.execute(
            delete(CodeLibraryPermission).where(
                CodeLibraryPermission.block_id == block_id
            )
        )
        # Add new ones
        for perm in permissions:
            self.db.add(
                CodeLibraryPermission(
                    block_id=block_id,
                    role_id=perm["role_id"],
                    can_read=perm.get("can_read", True),
                    can_edit=perm.get("can_edit", False),
                    can_use=perm.get("can_use", True),
                    granted_by=granted_by,
                )
            )
        await self.db.flush()

    async def get_permissions(self, block_id: UUID) -> list[CodeLibraryPermission]:
        result = await self.db.execute(
            select(CodeLibraryPermission)
            .options(selectinload(CodeLibraryPermission.role))
            .where(CodeLibraryPermission.block_id == block_id)
        )
        return list(result.scalars().all())

    async def toggle_favorite(self, user_id: UUID, block_id: UUID) -> bool:
        """Toggle favorite state. Returns new favorited state."""
        existing = await self.db.execute(
            select(CodeLibraryFavorite).where(
                and_(
                    CodeLibraryFavorite.user_id == user_id,
                    CodeLibraryFavorite.block_id == block_id,
                )
            )
        )
        fav = existing.scalar_one_or_none()
        if fav:
            await self.db.delete(fav)
            await self.db.flush()
            return False
        else:
            self.db.add(CodeLibraryFavorite(user_id=user_id, block_id=block_id))
            await self.db.flush()
            return True

    async def is_favorited(self, user_id: UUID, block_id: UUID) -> bool:
        result = await self.db.execute(
            select(exists(
                select(CodeLibraryFavorite).where(
                    and_(
                        CodeLibraryFavorite.user_id == user_id,
                        CodeLibraryFavorite.block_id == block_id,
                    )
                )
            ))
        )
        return result.scalar() or False

    async def get_user_favorites(self, user_id: UUID) -> set[UUID]:
        result = await self.db.execute(
            select(CodeLibraryFavorite.block_id).where(
                CodeLibraryFavorite.user_id == user_id
            )
        )
        return {r for (r,) in result.all()}

    # ---- Categories ----

    async def get_user_categories(self, user_id: UUID) -> list[CodeLibraryUserCategory]:
        result = await self.db.execute(
            select(CodeLibraryUserCategory)
            .where(CodeLibraryUserCategory.user_id == user_id)
            .order_by(CodeLibraryUserCategory.sort_order)
        )
        return list(result.scalars().all())

    async def create_category(
        self,
        user_id: UUID,
        name: str,
        parent_id: UUID | None = None,
        sort_order: int = 0,
    ) -> CodeLibraryUserCategory:
        cat = CodeLibraryUserCategory(
            user_id=user_id,
            name=name,
            parent_id=parent_id,
            sort_order=sort_order,
        )
        self.db.add(cat)
        await self.db.flush()
        return cat

    async def update_category(
        self,
        category_id: UUID,
        user_id: UUID,
        **kwargs,
    ) -> CodeLibraryUserCategory | None:
        result = await self.db.execute(
            select(CodeLibraryUserCategory).where(
                and_(
                    CodeLibraryUserCategory.id == category_id,
                    CodeLibraryUserCategory.user_id == user_id,
                )
            )
        )
        cat = result.scalar_one_or_none()
        if not cat:
            return None
        for key, value in kwargs.items():
            if value is not None and hasattr(cat, key):
                setattr(cat, key, value)
        await self.db.flush()
        return cat

    async def delete_category(self, category_id: UUID, user_id: UUID) -> bool:
        result = await self.db.execute(
            select(CodeLibraryUserCategory).where(
                and_(
                    CodeLibraryUserCategory.id == category_id,
                    CodeLibraryUserCategory.user_id == user_id,
                )
            )
        )
        cat = result.scalar_one_or_none()
        if not cat:
            return False
        await self.db.delete(cat)
        await self.db.flush()
        return True

    async def assign_block_to_category(
        self,
        user_id: UUID,
        block_id: UUID,
        category_id: UUID | None,
    ) -> None:
        # Upsert assignment
        existing = await self.db.execute(
            select(CodeLibraryUserBlockAssignment).where(
                and_(
                    CodeLibraryUserBlockAssignment.user_id == user_id,
                    CodeLibraryUserBlockAssignment.block_id == block_id,
                )
            )
        )
        assignment = existing.scalar_one_or_none()
        if assignment:
            assignment.category_id = category_id
        else:
            self.db.add(
                CodeLibraryUserBlockAssignment(
                    user_id=user_id,
                    block_id=block_id,
                    category_id=category_id,
                )
            )
        await self.db.flush()

    async def get_user_block_assignments(self, user_id: UUID) -> dict[UUID, UUID | None]:
        """Returns {block_id: category_id} for this user."""
        result = await self.db.execute(
            select(
                CodeLibraryUserBlockAssignment.block_id,
                CodeLibraryUserBlockAssignment.category_id,
            ).where(CodeLibraryUserBlockAssignment.user_id == user_id)
        )
        return {row[0]: row[1] for row in result.all()}

    # Default ports for backward compatibility with blocks that have no custom ports
    DEFAULT_INPUT_PORTS = [
        {"name": "exec_in", "type": "FLOW", "description": "Execution input"},
        {"name": "value", "type": "ANY", "description": "Input value"},
    ]
    DEFAULT_OUTPUT_PORTS = [
        {"name": "exec_out", "type": "FLOW", "description": "Execution output"},
        {"name": "result", "type": "ANY", "description": "Result value"},
    ]

    async def get_palette_blocks(self, user_id: UUID) -> list[dict]:
        """Return blocks formatted as NodeCatalogEntry-compatible dicts."""
        blocks, _ = await self.list_blocks(user_id, per_page=500)
        favorites = await self.get_user_favorites(user_id)
        assignments = await self.get_user_block_assignments(user_id)
        categories = await self.get_user_categories(user_id)

        # Build category path lookup
        cat_map = {c.id: c for c in categories}

        def get_category_path(cat_id: UUID | None) -> str | None:
            if not cat_id or cat_id not in cat_map:
                return None
            parts = []
            current = cat_map.get(cat_id)
            depth = 0
            while current and depth < 5:
                parts.append(current.name)
                current = cat_map.get(current.parent_id) if current.parent_id else None
                depth += 1
            parts.reverse()
            return " > ".join(parts) if parts else None

        entries = []
        for block in blocks:
            cat_id = assignments.get(block.id)
            subcategory = get_category_path(cat_id)
            creator_name = ""
            if block.creator:
                creator_name = getattr(block.creator, "display_name", "") or getattr(block.creator, "username", "")

            entries.append({
                "type": "code",
                "name": block.name,
                "category": "Custom",
                "subcategory": subcategory,
                "color": "#4CAF50",
                "description": block.description or "",
                "icon": None,
                "input_ports": block.input_ports if block.input_ports is not None else self.DEFAULT_INPUT_PORTS,
                "output_ports": block.output_ports if block.output_ports is not None else self.DEFAULT_OUTPUT_PORTS,
                "properties": [
                    {"name": "language", "type": "string", "default_value": block.language, "ui_type": "select"},
                    {"name": "code", "type": "string", "default_value": block.code, "ui_type": "code"},
                    {"name": "description", "type": "string", "default_value": block.description or ""},
                    {"name": "_library_block_id", "type": "string", "default_value": str(block.id)},
                    {"name": "_library_block_version", "type": "integer", "default_value": block.version},
                ],
                "is_library_block": True,
                "library_block_id": str(block.id),
                "library_block_version": block.version,
                "is_favorited": block.id in favorites,
                "creator_name": creator_name,
            })

        return entries

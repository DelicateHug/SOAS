"""Wiki CRUD service."""

import re
import unicodedata
from uuid import UUID

from sqlalchemy import func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from soas_backend.models.wiki import WikiPage, WikiPagePermission, WikiPageVersion

MAX_VERSIONS = 30


def _slugify(value: str) -> str:
    """Convert a string to a URL-friendly slug."""
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    value = re.sub(r"[^\w\s-]", "", value.lower())
    return re.sub(r"[-\s]+", "-", value).strip("-")


class WikiService:
    def __init__(self, db: AsyncSession):
        self.db = db

    # ─── Slug generation ───

    async def _generate_slug(self, title: str, exclude_id: UUID | None = None) -> str:
        """Generate a unique slug from title, appending -2, -3, etc. on collision."""
        base_slug = _slugify(title)
        if not base_slug:
            base_slug = "page"
        slug = base_slug
        counter = 1

        while True:
            query = select(WikiPage.id).where(WikiPage.slug == slug)
            if exclude_id:
                query = query.where(WikiPage.id != exclude_id)
            result = await self.db.execute(query)
            if result.scalar_one_or_none() is None:
                return slug
            counter += 1
            slug = f"{base_slug}-{counter}"

    # ─── Base query ───

    def _base_query(self):
        return select(WikiPage).options(
            selectinload(WikiPage.creator),
            selectinload(WikiPage.updater),
            selectinload(WikiPage.permissions),
        )

    # ─── CRUD ───

    async def create(
        self,
        title: str,
        created_by: UUID,
        content: str | None = None,
        parent_id: UUID | None = None,
        tags: list[str] | None = None,
        status: str = "published",
        icon: str | None = None,
        slug: str | None = None,
        linked_node_type: str | None = None,
        team_id: UUID | None = None,
    ) -> WikiPage:
        if slug:
            # Verify uniqueness of provided slug
            existing = await self.db.execute(
                select(WikiPage.id).where(WikiPage.slug == slug)
            )
            if existing.scalar_one_or_none() is not None:
                slug = await self._generate_slug(title)
        else:
            slug = await self._generate_slug(title)

        page = WikiPage(
            title=title,
            slug=slug,
            content=content,
            parent_id=parent_id,
            tags=tags or [],
            status=status,
            icon=icon,
            linked_node_type=linked_node_type,
            created_by=created_by,
            team_id=team_id,
        )
        self.db.add(page)
        await self.db.flush()

        # Save initial version
        await self._save_version(page, created_by, change_summary="Initial creation")

        return await self.get(page.id)

    async def get(self, page_id: UUID) -> WikiPage | None:
        result = await self.db.execute(
            self._base_query().where(WikiPage.id == page_id)
        )
        return result.scalar_one_or_none()

    async def get_by_slug(self, slug: str) -> WikiPage | None:
        result = await self.db.execute(
            self._base_query().where(WikiPage.slug == slug)
        )
        return result.scalar_one_or_none()

    async def list_pages(
        self,
        parent_id: UUID | None = None,
        filter_root: bool = False,
        status: str | None = None,
        tag: str | None = None,
        search: str | None = None,
        page: int = 1,
        per_page: int = 25,
        user_teams: list[dict] | None = None,
        team_id: UUID | None = None,
    ) -> tuple[list[WikiPage], int]:
        query = self._base_query()

        if filter_root:
            query = query.where(WikiPage.parent_id.is_(None))
        elif parent_id is not None:
            query = query.where(WikiPage.parent_id == parent_id)

        if status:
            query = query.where(WikiPage.status == status)
        if tag:
            query = query.where(WikiPage.tags.any(tag))
        if search:
            query = query.where(WikiPage.title.ilike(f"%{search}%"))

        # Team scoping — always include unscoped (NULL team_id) pages
        if team_id:
            query = query.where(
                or_(WikiPage.team_id == team_id, WikiPage.team_id.is_(None))
            )
        elif user_teams is not None:
            team_ids = [UUID(t["id"]) for t in user_teams]
            query = query.where(
                or_(WikiPage.team_id.in_(team_ids), WikiPage.team_id.is_(None))
            )

        count_query = select(func.count()).select_from(query.subquery())
        total = (await self.db.execute(count_query)).scalar() or 0

        query = query.order_by(WikiPage.sort_order, WikiPage.title)
        query = query.offset((page - 1) * per_page).limit(per_page)

        result = await self.db.execute(query)
        return list(result.scalars().unique().all()), total

    async def get_child_count(self, page_id: UUID) -> int:
        result = await self.db.execute(
            select(func.count()).where(WikiPage.parent_id == page_id)
        )
        return result.scalar() or 0

    async def update(
        self,
        page_id: UUID,
        updated_by: UUID,
        change_summary: str | None = None,
        **fields,
    ) -> WikiPage | None:
        page = await self.get(page_id)
        if not page:
            return None

        # Handle slug update
        if "slug" in fields and fields["slug"] is not None:
            new_slug = fields["slug"]
            existing = await self.db.execute(
                select(WikiPage.id).where(
                    WikiPage.slug == new_slug, WikiPage.id != page_id
                )
            )
            if existing.scalar_one_or_none() is not None:
                fields["slug"] = await self._generate_slug(
                    fields.get("title", page.title), exclude_id=page_id
                )

        for key, value in fields.items():
            if key == "change_summary":
                continue
            if hasattr(page, key):
                setattr(page, key, value)

        page.version += 1
        page.updated_by = updated_by
        await self.db.flush()

        # Auto-save version snapshot
        await self._save_version(page, updated_by, change_summary=change_summary)

        return await self.get(page_id)

    async def delete(self, page_id: UUID) -> bool:
        page = await self.get(page_id)
        if not page:
            return False
        await self.db.delete(page)
        await self.db.flush()
        return True

    # ─── Node type linking ───

    async def get_node_type_slug_map(self) -> dict[str, str]:
        """Return {node_type: slug} for all wiki pages linked to a node type."""
        result = await self.db.execute(
            select(WikiPage.linked_node_type, WikiPage.slug).where(
                WikiPage.linked_node_type.isnot(None)
            )
        )
        return {row[0]: row[1] for row in result}

    # ─── Tree ───

    async def get_tree(
        self,
        user_teams: list[dict] | None = None,
        team_id: UUID | None = None,
    ) -> list[WikiPage]:
        """Get all pages with minimal fields for building the sidebar tree."""
        query = select(WikiPage)

        # Team scoping — always include unscoped (NULL team_id) pages
        if team_id:
            query = query.where(
                or_(WikiPage.team_id == team_id, WikiPage.team_id.is_(None))
            )
        elif user_teams is not None:
            team_ids = [UUID(t["id"]) for t in user_teams]
            query = query.where(
                or_(WikiPage.team_id.in_(team_ids), WikiPage.team_id.is_(None))
            )

        query = query.order_by(WikiPage.sort_order, WikiPage.title)
        result = await self.db.execute(query)
        return list(result.scalars().unique().all())

    # ─── Breadcrumbs ───

    async def get_breadcrumbs(self, page_id: UUID) -> list[dict]:
        """Walk the parent chain using a recursive CTE."""
        result = await self.db.execute(
            text(
                """
                WITH RECURSIVE ancestors AS (
                    SELECT id, title, slug, parent_id, 0 AS depth
                    FROM wiki_pages WHERE id = :page_id
                    UNION ALL
                    SELECT wp.id, wp.title, wp.slug, wp.parent_id, a.depth + 1
                    FROM wiki_pages wp JOIN ancestors a ON wp.id = a.parent_id
                )
                SELECT id, title, slug FROM ancestors ORDER BY depth DESC
                """
            ),
            {"page_id": str(page_id)},
        )
        return [{"id": row.id, "title": row.title, "slug": row.slug} for row in result]

    # ─── Full-text search ───

    async def search_fulltext(
        self,
        query: str,
        page: int = 1,
        per_page: int = 20,
        user_teams: list[dict] | None = None,
        team_id: UUID | None = None,
    ) -> tuple[list[dict], int]:
        """Full-text search using PostgreSQL tsvector/tsquery."""
        # Build team scoping clause
        team_clause = ""
        team_params: dict = {}
        if team_id:
            team_clause = " AND team_id = :team_id"
            team_params["team_id"] = str(team_id)
        elif user_teams is not None:
            t_ids = [t["id"] for t in user_teams]
            if t_ids:
                team_clause = " AND (team_id = ANY(:team_ids) OR team_id IS NULL)"
                team_params["team_ids"] = t_ids
            else:
                team_clause = " AND team_id IS NULL"

        sql_count = text(
            f"""
            SELECT count(*)
            FROM wiki_pages
            WHERE to_tsvector('english', title || ' ' || coalesce(content, ''))
                  @@ plainto_tsquery('english', :query)
              AND status != 'archived'
              {team_clause}
            """
        )
        total = (await self.db.execute(sql_count, {"query": query, **team_params})).scalar() or 0

        sql = text(
            f"""
            SELECT id, title, slug, tags, updated_at,
                   ts_headline('english', coalesce(content, ''),
                               plainto_tsquery('english', :query),
                               'MaxWords=30, MinWords=15') AS snippet,
                   ts_rank(to_tsvector('english', title || ' ' || coalesce(content, '')),
                           plainto_tsquery('english', :query)) AS rank
            FROM wiki_pages
            WHERE to_tsvector('english', title || ' ' || coalesce(content, ''))
                  @@ plainto_tsquery('english', :query)
              AND status != 'archived'
              {team_clause}
            ORDER BY rank DESC
            OFFSET :offset LIMIT :limit
            """
        )
        result = await self.db.execute(
            sql,
            {
                "query": query,
                "offset": (page - 1) * per_page,
                "limit": per_page,
                **team_params,
            },
        )
        rows = [
            {
                "id": row.id,
                "title": row.title,
                "slug": row.slug,
                "snippet": row.snippet or "",
                "tags": row.tags or [],
                "updated_at": row.updated_at,
            }
            for row in result
        ]
        return rows, total

    # ─── Permissions ───

    async def get_permissions(self, page_id: UUID) -> list[WikiPagePermission]:
        result = await self.db.execute(
            select(WikiPagePermission)
            .where(WikiPagePermission.page_id == page_id)
            .options(selectinload(WikiPagePermission.role))
        )
        return list(result.scalars().all())

    async def set_permissions(
        self, page_id: UUID, permissions: list[dict], granted_by: UUID
    ) -> None:
        # Delete existing permissions for this page
        existing = await self.get_permissions(page_id)
        for perm in existing:
            await self.db.delete(perm)
        await self.db.flush()

        # Create new permissions
        for perm_data in permissions:
            perm = WikiPagePermission(
                page_id=page_id,
                role_id=perm_data["role_id"],
                can_read=perm_data.get("can_read", True),
                can_edit=perm_data.get("can_edit", False),
                granted_by=granted_by,
            )
            self.db.add(perm)
        await self.db.flush()

    # ─── Versions ───

    async def list_versions(self, page_id: UUID) -> list[WikiPageVersion]:
        result = await self.db.execute(
            select(WikiPageVersion)
            .where(WikiPageVersion.page_id == page_id)
            .options(selectinload(WikiPageVersion.creator))
            .order_by(WikiPageVersion.version_number.desc())
        )
        return list(result.scalars().all())

    async def get_version(
        self, page_id: UUID, version_number: int
    ) -> WikiPageVersion | None:
        result = await self.db.execute(
            select(WikiPageVersion)
            .where(
                WikiPageVersion.page_id == page_id,
                WikiPageVersion.version_number == version_number,
            )
            .options(selectinload(WikiPageVersion.creator))
        )
        return result.scalar_one_or_none()

    async def _save_version(
        self, page: WikiPage, created_by: UUID, change_summary: str | None = None
    ) -> WikiPageVersion:
        """Snapshot the current page state as a version."""
        version = WikiPageVersion(
            page_id=page.id,
            version_number=page.version,
            title=page.title,
            content=page.content,
            tags=list(page.tags) if page.tags else None,
            change_summary=change_summary,
            created_by=created_by,
        )
        self.db.add(version)
        await self.db.flush()

        # Prune old versions
        result = await self.db.execute(
            select(WikiPageVersion)
            .where(WikiPageVersion.page_id == page.id)
            .order_by(WikiPageVersion.version_number.desc())
            .offset(MAX_VERSIONS)
        )
        for old_version in result.scalars().all():
            await self.db.delete(old_version)
        await self.db.flush()

        return version

    async def restore_version(
        self, page_id: UUID, version_number: int, restored_by: UUID
    ) -> WikiPage | None:
        """Restore page content from a version snapshot."""
        version = await self.get_version(page_id, version_number)
        if not version:
            return None

        page = await self.get(page_id)
        if not page:
            return None

        return await self.update(
            page_id,
            updated_by=restored_by,
            title=version.title or page.title,
            content=version.content,
            tags=list(version.tags) if version.tags else page.tags,
            change_summary=f"Restored from version {version_number}",
        )

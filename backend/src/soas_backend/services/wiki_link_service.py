"""Extract and persist wiki backlinks from page content."""

from __future__ import annotations

import re
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from soas_backend.models.wiki import WikiPage
from soas_backend.models.wiki_link import WikiPageLink

# [[slug]] or [[slug|display text]]
LINK_RE = re.compile(r"\[\[([^\]|]+?)(?:\|[^\]]*?)?\]\]")


class WikiLinkService:
    def __init__(self, db: AsyncSession):
        self.db = db

    @staticmethod
    def extract_slugs(content: str | None) -> list[str]:
        if not content:
            return []
        # Deduplicate while preserving order
        seen: dict[str, None] = {}
        for m in LINK_RE.finditer(content):
            slug = m.group(1).strip()
            if slug and slug not in seen:
                seen[slug] = None
        return list(seen)

    async def refresh_for_page(self, page_id: UUID, content: str | None) -> int:
        slugs = self.extract_slugs(content)
        # Replace-all: drop existing rows, then re-insert.
        await self.db.execute(delete(WikiPageLink).where(WikiPageLink.source_page_id == page_id))
        if not slugs:
            return 0
        # Resolve target pages by slug (best-effort).
        rs = await self.db.execute(
            select(WikiPage.id, WikiPage.slug).where(WikiPage.slug.in_(slugs))
        )
        slug_to_id = {row.slug: row.id for row in rs.all()}
        for slug in slugs:
            self.db.add(WikiPageLink(
                source_page_id=page_id,
                target_slug=slug,
                target_page_id=slug_to_id.get(slug),
            ))
        await self.db.flush()
        return len(slugs)

    async def backlinks_for(self, page_id: UUID) -> list[dict]:
        rs = await self.db.execute(
            select(WikiPageLink, WikiPage.title, WikiPage.slug)
            .join(WikiPage, WikiPage.id == WikiPageLink.source_page_id)
            .where(WikiPageLink.target_page_id == page_id)
        )
        out: list[dict] = []
        for link, title, slug in rs.all():
            out.append({
                "source_page_id": str(link.source_page_id),
                "source_title": title,
                "source_slug": slug,
                "target_slug": link.target_slug,
            })
        return out

"""Wiki CRUD endpoints with creator-override permissions."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from soas_backend.api.deps import get_current_user, get_user_teams, require_permission
from soas_backend.auth.jwt import decode_access_token
from soas_backend.database import get_db
from soas_backend.models.user import User
from soas_backend.services.wiki_service import WikiService
from soas_shared.schemas.common import PaginatedResponse, PaginationMeta
from soas_shared.schemas.wiki import (
    WikiPageBreadcrumb,
    WikiPageCreate,
    WikiPageListItem,
    WikiPagePermissionRead,
    WikiPagePermissionSet,
    WikiPageRead,
    WikiPageTreeNode,
    WikiPageUpdate,
    WikiPageVersionRead,
    WikiSearchResult,
)
from soas_shared.schemas.user import UserBrief

router = APIRouter(prefix="/wiki", tags=["wiki"])
security = HTTPBearer()


# ─── Helpers ───


def _user_brief(user) -> UserBrief | None:
    if user is None:
        return None
    return UserBrief(id=user.id, username=user.username, display_name=user.display_name)


def _has_permission(credentials: HTTPAuthorizationCredentials, permission: str) -> bool:
    """Check if JWT contains a specific permission without raising."""
    payload = decode_access_token(credentials.credentials)
    if payload is None:
        return False
    return permission in payload.get("permissions", [])


async def _page_to_read(page, svc: WikiService) -> WikiPageRead:
    child_count = await svc.get_child_count(page.id)
    return WikiPageRead(
        id=page.id,
        title=page.title,
        slug=page.slug,
        content=page.content,
        parent_id=page.parent_id,
        sort_order=page.sort_order,
        tags=page.tags or [],
        status=page.status,
        version=page.version,
        icon=page.icon,
        linked_node_type=page.linked_node_type,
        created_by=_user_brief(page.creator),
        updated_by=_user_brief(page.updater),
        child_count=child_count,
        team_id=page.team_id,
        created_at=page.created_at,
        updated_at=page.updated_at,
    )


async def _page_to_list_item(page, svc: WikiService) -> WikiPageListItem:
    child_count = await svc.get_child_count(page.id)
    return WikiPageListItem(
        id=page.id,
        title=page.title,
        slug=page.slug,
        parent_id=page.parent_id,
        sort_order=page.sort_order,
        tags=page.tags or [],
        status=page.status,
        version=page.version,
        icon=page.icon,
        linked_node_type=page.linked_node_type,
        created_by=_user_brief(page.creator),
        updated_by=_user_brief(page.updater),
        child_count=child_count,
        team_id=page.team_id,
        created_at=page.created_at,
        updated_at=page.updated_at,
    )


def _build_tree(pages) -> list[WikiPageTreeNode]:
    """Build a nested tree from a flat list of pages."""
    nodes: dict[str, WikiPageTreeNode] = {}
    for p in pages:
        nodes[str(p.id)] = WikiPageTreeNode(
            id=p.id,
            title=p.title,
            slug=p.slug,
            icon=p.icon,
            sort_order=p.sort_order,
            status=p.status,
            children=[],
        )

    roots = []
    for p in pages:
        node = nodes[str(p.id)]
        if p.parent_id and str(p.parent_id) in nodes:
            nodes[str(p.parent_id)].children.append(node)
        else:
            roots.append(node)

    return roots


# ─── Core CRUD ───


@router.get("", response_model=PaginatedResponse[WikiPageListItem])
async def list_wiki_pages(
    parent_id: UUID | None = Query(None),
    root: bool = Query(False, description="Filter to root-level pages only"),
    wiki_status: str | None = Query(None, alias="status"),
    tag: str | None = Query(None),
    search: str | None = Query(None),
    team_id: UUID | None = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=1, le=100),
    _: dict = Depends(require_permission("wiki", "read")),
    user_teams: list | None = Depends(get_user_teams),
    db: AsyncSession = Depends(get_db),
):
    svc = WikiService(db)
    pages, total = await svc.list_pages(
        parent_id=parent_id,
        filter_root=root,
        status=wiki_status,
        tag=tag,
        search=search,
        page=page,
        per_page=per_page,
        user_teams=user_teams,
        team_id=team_id,
    )

    items = [await _page_to_list_item(p, svc) for p in pages]
    return PaginatedResponse(
        data=items,
        meta=PaginationMeta(
            total=total,
            page=page,
            per_page=per_page,
            total_pages=(total + per_page - 1) // per_page if total else 0,
        ),
    )


@router.get("/tree", response_model=list[WikiPageTreeNode])
async def get_wiki_tree(
    team_id: UUID | None = Query(None),
    _: dict = Depends(require_permission("wiki", "read")),
    user_teams: list | None = Depends(get_user_teams),
    db: AsyncSession = Depends(get_db),
):
    svc = WikiService(db)
    pages = await svc.get_tree(user_teams=user_teams, team_id=team_id)
    return _build_tree(pages)


@router.get("/search", response_model=PaginatedResponse[WikiSearchResult])
async def search_wiki(
    q: str = Query(min_length=1),
    team_id: UUID | None = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    _: dict = Depends(require_permission("wiki", "read")),
    user_teams: list | None = Depends(get_user_teams),
    db: AsyncSession = Depends(get_db),
):
    svc = WikiService(db)
    results, total = await svc.search_fulltext(
        q, page=page, per_page=per_page,
        user_teams=user_teams, team_id=team_id,
    )
    return PaginatedResponse(
        data=[WikiSearchResult(**r) for r in results],
        meta=PaginationMeta(
            total=total,
            page=page,
            per_page=per_page,
            total_pages=(total + per_page - 1) // per_page if total else 0,
        ),
    )


@router.post("", response_model=WikiPageRead, status_code=status.HTTP_201_CREATED)
async def create_wiki_page(
    body: WikiPageCreate,
    current_user: User = Depends(get_current_user),
    _: dict = Depends(require_permission("wiki", "create")),
    db: AsyncSession = Depends(get_db),
):
    svc = WikiService(db)
    page = await svc.create(
        title=body.title,
        created_by=current_user.id,
        content=body.content,
        parent_id=body.parent_id,
        tags=body.tags,
        status=body.status,
        icon=body.icon,
        slug=body.slug,
        linked_node_type=body.linked_node_type,
        team_id=body.team_id,
    )
    return await _page_to_read(page, svc)


@router.get("/by-slug/{slug:path}", response_model=WikiPageRead)
async def get_wiki_page_by_slug(
    slug: str,
    _: dict = Depends(require_permission("wiki", "read")),
    user_teams: list | None = Depends(get_user_teams),
    db: AsyncSession = Depends(get_db),
):
    svc = WikiService(db)
    page = await svc.get_by_slug(slug)
    if not page:
        raise HTTPException(status_code=404, detail="Wiki page not found")

    # Team visibility check
    if user_teams is not None and page.team_id is not None:
        team_ids = [t["id"] for t in user_teams]
        if str(page.team_id) not in team_ids:
            raise HTTPException(status_code=404, detail="Wiki page not found")

    return await _page_to_read(page, svc)


@router.get("/{page_id}", response_model=WikiPageRead)
async def get_wiki_page(
    page_id: UUID,
    _: dict = Depends(require_permission("wiki", "read")),
    user_teams: list | None = Depends(get_user_teams),
    db: AsyncSession = Depends(get_db),
):
    svc = WikiService(db)
    page = await svc.get(page_id)
    if not page:
        raise HTTPException(status_code=404, detail="Wiki page not found")

    # Team visibility check
    if user_teams is not None and page.team_id is not None:
        team_ids = [t["id"] for t in user_teams]
        if str(page.team_id) not in team_ids:
            raise HTTPException(status_code=404, detail="Wiki page not found")

    return await _page_to_read(page, svc)


@router.patch("/{page_id}", response_model=WikiPageRead)
async def update_wiki_page(
    page_id: UUID,
    body: WikiPageUpdate,
    current_user: User = Depends(get_current_user),
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
):
    svc = WikiService(db)
    page = await svc.get(page_id)
    if not page:
        raise HTTPException(status_code=404, detail="Wiki page not found")

    # Creator override: skip permission check if user is the creator
    if page.created_by != current_user.id:
        if not _has_permission(credentials, "wiki:update"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Missing permission: wiki:update",
            )

    fields = body.model_dump(exclude_unset=True)
    change_summary = fields.pop("change_summary", None)
    page = await svc.update(page_id, updated_by=current_user.id, change_summary=change_summary, **fields)
    return await _page_to_read(page, svc)


@router.delete("/{page_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_wiki_page(
    page_id: UUID,
    current_user: User = Depends(get_current_user),
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
):
    svc = WikiService(db)
    page = await svc.get(page_id)
    if not page:
        raise HTTPException(status_code=404, detail="Wiki page not found")

    if page.created_by != current_user.id:
        if not _has_permission(credentials, "wiki:delete"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Missing permission: wiki:delete",
            )

    await svc.delete(page_id)
    return None


# ─── Breadcrumbs ───


@router.get("/{page_id}/breadcrumbs", response_model=list[WikiPageBreadcrumb])
async def get_wiki_breadcrumbs(
    page_id: UUID,
    _: dict = Depends(require_permission("wiki", "read")),
    db: AsyncSession = Depends(get_db),
):
    svc = WikiService(db)
    page = await svc.get(page_id)
    if not page:
        raise HTTPException(status_code=404, detail="Wiki page not found")

    crumbs = await svc.get_breadcrumbs(page_id)
    return [WikiPageBreadcrumb(**c) for c in crumbs]


# ─── Versions ───


@router.get("/{page_id}/versions", response_model=list[WikiPageVersionRead])
async def list_wiki_versions(
    page_id: UUID,
    _: dict = Depends(require_permission("wiki", "read")),
    db: AsyncSession = Depends(get_db),
):
    svc = WikiService(db)
    page = await svc.get(page_id)
    if not page:
        raise HTTPException(status_code=404, detail="Wiki page not found")

    versions = await svc.list_versions(page_id)
    return [
        WikiPageVersionRead(
            id=v.id,
            page_id=v.page_id,
            version_number=v.version_number,
            title=v.title,
            content=v.content,
            tags=v.tags,
            change_summary=v.change_summary,
            created_by=_user_brief(v.creator),
            created_at=v.created_at,
        )
        for v in versions
    ]


@router.get("/{page_id}/versions/{version_number}", response_model=WikiPageVersionRead)
async def get_wiki_version(
    page_id: UUID,
    version_number: int,
    _: dict = Depends(require_permission("wiki", "read")),
    db: AsyncSession = Depends(get_db),
):
    svc = WikiService(db)
    version = await svc.get_version(page_id, version_number)
    if not version:
        raise HTTPException(status_code=404, detail="Version not found")

    return WikiPageVersionRead(
        id=version.id,
        page_id=version.page_id,
        version_number=version.version_number,
        title=version.title,
        content=version.content,
        tags=version.tags,
        change_summary=version.change_summary,
        created_by=_user_brief(version.creator),
        created_at=version.created_at,
    )


@router.post("/{page_id}/versions/{version_number}/restore", response_model=WikiPageRead)
async def restore_wiki_version(
    page_id: UUID,
    version_number: int,
    current_user: User = Depends(get_current_user),
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
):
    svc = WikiService(db)
    page = await svc.get(page_id)
    if not page:
        raise HTTPException(status_code=404, detail="Wiki page not found")

    if page.created_by != current_user.id:
        if not _has_permission(credentials, "wiki:update"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Missing permission: wiki:update",
            )

    restored = await svc.restore_version(page_id, version_number, current_user.id)
    if not restored:
        raise HTTPException(status_code=404, detail="Version not found")
    return await _page_to_read(restored, svc)


# ─── Permissions ───


@router.get("/{page_id}/permissions", response_model=list[WikiPagePermissionRead])
async def get_wiki_permissions(
    page_id: UUID,
    _: dict = Depends(require_permission("wiki", "read")),
    db: AsyncSession = Depends(get_db),
):
    svc = WikiService(db)
    page = await svc.get(page_id)
    if not page:
        raise HTTPException(status_code=404, detail="Wiki page not found")

    perms = await svc.get_permissions(page_id)
    return [
        WikiPagePermissionRead(
            page_id=p.page_id,
            role_id=p.role_id,
            role_name=p.role.display_name if p.role else str(p.role_id),
            can_read=p.can_read,
            can_edit=p.can_edit,
        )
        for p in perms
    ]


@router.put("/{page_id}/permissions", status_code=status.HTTP_200_OK)
async def set_wiki_permissions(
    page_id: UUID,
    body: list[WikiPagePermissionSet],
    current_user: User = Depends(get_current_user),
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
):
    svc = WikiService(db)
    page = await svc.get(page_id)
    if not page:
        raise HTTPException(status_code=404, detail="Wiki page not found")

    if page.created_by != current_user.id:
        if not _has_permission(credentials, "wiki:update"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Missing permission: wiki:update",
            )

    await svc.set_permissions(
        page_id,
        [p.model_dump() for p in body],
        granted_by=current_user.id,
    )
    return {"message": "Permissions updated"}

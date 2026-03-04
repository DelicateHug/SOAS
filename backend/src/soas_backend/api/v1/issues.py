"""Issue CRUD endpoints with creator-override permissions."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from soas_backend.api.deps import get_current_user, require_permission
from soas_backend.auth.jwt import decode_access_token
from soas_backend.database import get_db
from soas_backend.models.user import User
from soas_backend.services.issue_service import IssueService
from soas_shared.schemas.common import PaginatedResponse, PaginationMeta
from soas_shared.schemas.issue import (
    GraphIssueItem,
    IssueChecklistItemCreate,
    IssueChecklistItemRead,
    IssueChecklistItemUpdate,
    IssueCreate,
    IssueLinkCreate,
    IssueLinkRead,
    IssueListItem,
    IssueNoteCreate,
    IssueNoteRead,
    IssueNoteUpdate,
    IssueRead,
    IssueUpdate,
)
from soas_shared.schemas.user import UserBrief

router = APIRouter(prefix="/issues", tags=["issues"])
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


async def _issue_to_read(issue, svc: IssueService) -> IssueRead:
    resolved_links = await svc.resolve_link_names(issue.links)
    return IssueRead(
        id=issue.id,
        title=issue.title,
        description=issue.description,
        status=issue.status,
        assigned_to=_user_brief(issue.owner),
        created_by=_user_brief(issue.creator),
        closed_at=issue.closed_at,
        graph_annotation=issue.graph_annotation,
        links=[
            IssueLinkRead(
                id=lk["id"],
                target_type=lk["target_type"],
                target_id=lk["target_id"],
                target_name=lk["target_name"],
            )
            for lk in resolved_links
        ],
        note_count=len(issue.notes),
        checklist_total=len(issue.checklist_items),
        checklist_checked=sum(1 for ci in issue.checklist_items if ci.is_checked),
        created_at=issue.created_at,
        updated_at=issue.updated_at,
    )


def _issue_to_list_item(issue) -> IssueListItem:
    return IssueListItem(
        id=issue.id,
        title=issue.title,
        status=issue.status,
        assigned_to=_user_brief(issue.owner),
        created_by=_user_brief(issue.creator),
        link_count=len(issue.links),
        note_count=len(issue.notes),
        checklist_total=len(issue.checklist_items),
        checklist_checked=sum(1 for ci in issue.checklist_items if ci.is_checked),
        created_at=issue.created_at,
        updated_at=issue.updated_at,
    )


def _note_to_read(note) -> IssueNoteRead:
    return IssueNoteRead(
        id=note.id,
        issue_id=note.issue_id,
        content=note.content,
        is_evidence=note.is_evidence,
        created_by=_user_brief(note.creator),
        updated_by=_user_brief(note.updater),
        created_at=note.created_at,
        updated_at=note.updated_at,
    )


def _checklist_item_to_read(item) -> IssueChecklistItemRead:
    return IssueChecklistItemRead(
        id=item.id,
        content=item.content,
        is_checked=item.is_checked,
        sort_order=item.sort_order,
        created_by=_user_brief(item.creator),
        created_at=item.created_at,
    )


# ─── Core Issue CRUD ───


@router.get("", response_model=PaginatedResponse[IssueListItem])
async def list_issues(
    issue_status: str | None = Query(None, alias="status"),
    assigned_to: UUID | None = Query(None),
    target_type: str | None = Query(None),
    target_id: UUID | None = Query(None),
    search: str | None = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=1, le=100),
    _: dict = Depends(require_permission("issue", "read")),
    db: AsyncSession = Depends(get_db),
):
    svc = IssueService(db)
    issues, total = await svc.list_issues(
        status=issue_status,
        assigned_to=assigned_to,
        target_type=target_type,
        target_id=target_id,
        search=search,
        page=page,
        per_page=per_page,
    )

    return PaginatedResponse(
        data=[_issue_to_list_item(i) for i in issues],
        meta=PaginationMeta(
            total=total,
            page=page,
            per_page=per_page,
            total_pages=(total + per_page - 1) // per_page if total else 0,
        ),
    )


@router.post("", response_model=IssueRead, status_code=status.HTTP_201_CREATED)
async def create_issue(
    body: IssueCreate,
    current_user: User = Depends(get_current_user),
    _: dict = Depends(require_permission("issue", "create")),
    db: AsyncSession = Depends(get_db),
):
    svc = IssueService(db)
    issue = await svc.create(
        title=body.title,
        created_by=current_user.id,
        description=body.description,
        assigned_to=body.assigned_to,
        graph_annotation=body.graph_annotation.model_dump() if body.graph_annotation else None,
        links=[lk.model_dump() for lk in body.links] if body.links else None,
    )
    return await _issue_to_read(issue, svc)


@router.get("/{issue_id}", response_model=IssueRead)
async def get_issue(
    issue_id: UUID,
    _: dict = Depends(require_permission("issue", "read")),
    db: AsyncSession = Depends(get_db),
):
    svc = IssueService(db)
    issue = await svc.get(issue_id)
    if not issue:
        raise HTTPException(status_code=404, detail="Issue not found")
    return await _issue_to_read(issue, svc)


@router.patch("/{issue_id}", response_model=IssueRead)
async def update_issue(
    issue_id: UUID,
    body: IssueUpdate,
    current_user: User = Depends(get_current_user),
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
):
    svc = IssueService(db)
    issue = await svc.get(issue_id)
    if not issue:
        raise HTTPException(status_code=404, detail="Issue not found")

    # Creator override: skip permission check if user is the creator
    if issue.created_by != current_user.id:
        if not _has_permission(credentials, "issue:update"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Missing permission: issue:update",
            )

    fields = body.model_dump(exclude_unset=True)
    if "graph_annotation" in fields and fields["graph_annotation"] is not None:
        fields["graph_annotation"] = body.graph_annotation.model_dump()
    issue = await svc.update(issue_id, **fields)
    return await _issue_to_read(issue, svc)


@router.delete("/{issue_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_issue(
    issue_id: UUID,
    current_user: User = Depends(get_current_user),
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
):
    svc = IssueService(db)
    issue = await svc.get(issue_id)
    if not issue:
        raise HTTPException(status_code=404, detail="Issue not found")

    if issue.created_by != current_user.id:
        if not _has_permission(credentials, "issue:delete"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Missing permission: issue:delete",
            )

    await svc.delete(issue_id)
    return None


# ─── Links ───


@router.post(
    "/{issue_id}/links",
    response_model=IssueLinkRead,
    status_code=status.HTTP_201_CREATED,
)
async def add_issue_link(
    issue_id: UUID,
    body: IssueLinkCreate,
    current_user: User = Depends(get_current_user),
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
):
    svc = IssueService(db)
    issue = await svc.get(issue_id)
    if not issue:
        raise HTTPException(status_code=404, detail="Issue not found")

    if issue.created_by != current_user.id:
        if not _has_permission(credentials, "issue:update"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Missing permission: issue:update",
            )

    link = await svc.add_link(issue_id, body.target_type, body.target_id)
    name = await svc._resolve_target_name(link.target_type, link.target_id)
    return IssueLinkRead(
        id=link.id,
        target_type=link.target_type,
        target_id=link.target_id,
        target_name=name,
    )


@router.delete(
    "/{issue_id}/links/{link_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_issue_link(
    issue_id: UUID,
    link_id: UUID,
    current_user: User = Depends(get_current_user),
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
):
    svc = IssueService(db)
    issue = await svc.get(issue_id)
    if not issue:
        raise HTTPException(status_code=404, detail="Issue not found")

    if issue.created_by != current_user.id:
        if not _has_permission(credentials, "issue:update"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Missing permission: issue:update",
            )

    link = await svc.get_link(link_id)
    if not link or link.issue_id != issue_id:
        raise HTTPException(status_code=404, detail="Link not found")

    await svc.remove_link(link_id)
    return None


# ─── Reverse lookups ───


@router.get("/by-target/{target_type}/{target_id}", response_model=list[IssueListItem])
async def get_issues_for_target(
    target_type: str,
    target_id: UUID,
    _: dict = Depends(require_permission("issue", "read")),
    db: AsyncSession = Depends(get_db),
):
    svc = IssueService(db)
    issues = await svc.get_issues_for_target(target_type, target_id)
    return [_issue_to_list_item(i) for i in issues]


# ─── Notes ───


@router.get("/{issue_id}/notes", response_model=list[IssueNoteRead])
async def list_issue_notes(
    issue_id: UUID,
    _: dict = Depends(require_permission("issue", "read")),
    db: AsyncSession = Depends(get_db),
):
    svc = IssueService(db)
    notes = await svc.list_notes(issue_id)
    return [_note_to_read(n) for n in notes]


@router.post(
    "/{issue_id}/notes",
    response_model=IssueNoteRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_issue_note(
    issue_id: UUID,
    body: IssueNoteCreate,
    current_user: User = Depends(get_current_user),
    _: dict = Depends(require_permission("issue", "create")),
    db: AsyncSession = Depends(get_db),
):
    svc = IssueService(db)
    issue = await svc.get(issue_id)
    if not issue:
        raise HTTPException(status_code=404, detail="Issue not found")

    note = await svc.create_note(
        issue_id=issue_id,
        content=body.content,
        created_by=current_user.id,
    )
    return _note_to_read(note)


@router.patch("/{issue_id}/notes/{note_id}", response_model=IssueNoteRead)
async def update_issue_note(
    issue_id: UUID,
    note_id: UUID,
    body: IssueNoteUpdate,
    current_user: User = Depends(get_current_user),
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
):
    svc = IssueService(db)
    note = await svc.get_note(note_id)
    if not note or note.issue_id != issue_id:
        raise HTTPException(status_code=404, detail="Note not found")

    # Note creator or issue:update permission
    if note.created_by != current_user.id:
        if not _has_permission(credentials, "issue:update"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Missing permission: issue:update",
            )

    update_fields = body.model_dump(exclude_unset=True)
    note = await svc.update_note(note_id, updated_by=current_user.id, **update_fields)
    return _note_to_read(note)


@router.delete(
    "/{issue_id}/notes/{note_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_issue_note(
    issue_id: UUID,
    note_id: UUID,
    current_user: User = Depends(get_current_user),
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
):
    svc = IssueService(db)
    note = await svc.get_note(note_id)
    if not note or note.issue_id != issue_id:
        raise HTTPException(status_code=404, detail="Note not found")

    if note.created_by != current_user.id:
        if not _has_permission(credentials, "issue:delete"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Missing permission: issue:delete",
            )

    await svc.delete_note(note_id)
    return None


@router.post("/{issue_id}/notes/{note_id}/evidence", response_model=IssueNoteRead)
async def toggle_issue_note_evidence(
    issue_id: UUID,
    note_id: UUID,
    current_user: User = Depends(get_current_user),
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
):
    svc = IssueService(db)
    issue = await svc.get(issue_id)
    if not issue:
        raise HTTPException(status_code=404, detail="Issue not found")

    note = await svc.get_note(note_id)
    if not note or note.issue_id != issue_id:
        raise HTTPException(status_code=404, detail="Note not found")

    # Issue creator or issue:update permission
    if issue.created_by != current_user.id:
        if not _has_permission(credentials, "issue:update"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Missing permission: issue:update",
            )

    note = await svc.toggle_evidence(note_id)
    return _note_to_read(note)


# ─── Checklist ───


@router.get("/{issue_id}/checklist", response_model=list[IssueChecklistItemRead])
async def list_issue_checklist(
    issue_id: UUID,
    _: dict = Depends(require_permission("issue", "read")),
    db: AsyncSession = Depends(get_db),
):
    svc = IssueService(db)
    items = await svc.list_checklist(issue_id)
    return [_checklist_item_to_read(it) for it in items]


@router.post(
    "/{issue_id}/checklist",
    response_model=IssueChecklistItemRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_issue_checklist_item(
    issue_id: UUID,
    body: IssueChecklistItemCreate,
    current_user: User = Depends(get_current_user),
    _: dict = Depends(require_permission("issue", "read")),
    db: AsyncSession = Depends(get_db),
):
    """Any authenticated user with issue:read can add checklist items."""
    svc = IssueService(db)
    issue = await svc.get(issue_id)
    if not issue:
        raise HTTPException(status_code=404, detail="Issue not found")

    item = await svc.create_checklist_item(
        issue_id=issue_id,
        content=body.content,
        created_by=current_user.id,
        sort_order=body.sort_order,
    )
    return _checklist_item_to_read(item)


@router.patch("/{issue_id}/checklist/{item_id}", response_model=IssueChecklistItemRead)
async def update_issue_checklist_item(
    issue_id: UUID,
    item_id: UUID,
    body: IssueChecklistItemUpdate,
    current_user: User = Depends(get_current_user),
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
):
    svc = IssueService(db)
    item = await svc.get_checklist_item(item_id)
    if not item or item.issue_id != issue_id:
        raise HTTPException(status_code=404, detail="Checklist item not found")

    # Item creator or issue:update permission
    if item.created_by != current_user.id:
        if not _has_permission(credentials, "issue:update"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Missing permission: issue:update",
            )

    fields = body.model_dump(exclude_unset=True)
    item = await svc.update_checklist_item(item_id, **fields)
    return _checklist_item_to_read(item)


@router.delete(
    "/{issue_id}/checklist/{item_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_issue_checklist_item(
    issue_id: UUID,
    item_id: UUID,
    current_user: User = Depends(get_current_user),
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
):
    svc = IssueService(db)
    item = await svc.get_checklist_item(item_id)
    if not item or item.issue_id != issue_id:
        raise HTTPException(status_code=404, detail="Checklist item not found")

    if item.created_by != current_user.id:
        if not _has_permission(credentials, "issue:delete"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Missing permission: issue:delete",
            )

    await svc.delete_checklist_item(item_id)
    return None


@router.put("/{issue_id}/checklist/reorder", status_code=status.HTTP_200_OK)
async def reorder_issue_checklist(
    issue_id: UUID,
    item_ids: list[UUID],
    current_user: User = Depends(get_current_user),
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
):
    svc = IssueService(db)
    issue = await svc.get(issue_id)
    if not issue:
        raise HTTPException(status_code=404, detail="Issue not found")

    if issue.created_by != current_user.id:
        if not _has_permission(credentials, "issue:update"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Missing permission: issue:update",
            )

    await svc.reorder_checklist(issue_id, item_ids)
    return {"message": "Checklist reordered"}


# ─── Graph issues (for automation graph overlay) ───


@router.get(
    "/automation-graph/{automation_id}",
    response_model=list[GraphIssueItem],
)
async def get_automation_graph_issues(
    automation_id: UUID,
    _: dict = Depends(require_permission("issue", "read")),
    db: AsyncSession = Depends(get_db),
):
    svc = IssueService(db)
    issues = await svc.get_issues_for_automation_graph(automation_id)
    return [
        GraphIssueItem(
            id=i.id,
            title=i.title,
            description=i.description,
            status=i.status,
            assigned_to=_user_brief(i.owner),
            graph_annotation=i.graph_annotation,
            created_at=i.created_at,
            updated_at=i.updated_at,
        )
        for i in issues
    ]

"""Team management routes."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from soas_backend.api.deps import get_current_user, get_db, get_user_teams, require_permission
from soas_backend.models.user import User
from soas_backend.services.team_service import TeamService
from soas_shared.schemas.common import PaginatedResponse, PaginationMeta
from soas_shared.schemas.team import (
    RoleBrief,
    TeamCreate,
    TeamMemberAdd,
    TeamMemberRead,
    TeamMemberUpdate,
    TeamRead,
    TeamUpdate,
)

router = APIRouter(prefix="/teams", tags=["teams"])


@router.get("", response_model=PaginatedResponse[TeamRead])
async def list_teams(
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=1, le=100),
    _: dict = Depends(require_permission("team", "read")),
    user_teams: list | None = Depends(get_user_teams),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = TeamService(db)
    # Always scoped to the current user's teams — no "all teams" view
    items, total = await svc.list_teams(user_id=current_user.id, page=page, per_page=per_page)

    return PaginatedResponse(
        data=[TeamRead(**item) for item in items],
        meta=PaginationMeta(
            total=total,
            page=page,
            per_page=per_page,
            total_pages=(total + per_page - 1) // per_page if total > 0 else 0,
        ),
    )


@router.post("", response_model=TeamRead, status_code=status.HTTP_201_CREATED)
async def create_team(
    body: TeamCreate,
    _: dict = Depends(require_permission("team", "create")),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = TeamService(db)
    team = await svc.create(
        name=body.name,
        display_name=body.display_name,
        description=body.description,
        created_by=current_user.id,
    )
    # Re-fetch to get member count
    items, _ = await svc.list_teams(user_id=current_user.id, page=1, per_page=1)
    for item in items:
        if item["id"] == team.id:
            return TeamRead(**item)
    # Fallback
    return TeamRead(
        id=team.id,
        name=team.name,
        display_name=team.display_name,
        description=team.description,
        is_default=team.is_default,
        member_count=1,
        created_at=team.created_at,
        updated_at=team.updated_at,
    )


@router.get("/{team_id}", response_model=TeamRead)
async def get_team(
    team_id: UUID,
    _: dict = Depends(require_permission("team", "read")),
    user_teams: list | None = Depends(get_user_teams),
    db: AsyncSession = Depends(get_db),
):
    svc = TeamService(db)
    team = await svc.get(team_id)
    if team is None:
        raise HTTPException(status_code=404, detail="Team not found")

    # Non-admin must be a member
    if user_teams is not None:
        team_ids = [t["id"] for t in user_teams]
        if str(team_id) not in team_ids:
            raise HTTPException(status_code=404, detail="Team not found")

    return TeamRead(
        id=team.id,
        name=team.name,
        display_name=team.display_name,
        description=team.description,
        is_default=team.is_default,
        member_count=len(team.memberships),
        created_at=team.created_at,
        updated_at=team.updated_at,
    )


@router.patch("/{team_id}", response_model=TeamRead)
async def update_team(
    team_id: UUID,
    body: TeamUpdate,
    current_user: User = Depends(get_current_user),
    user_teams: list | None = Depends(get_user_teams),
    db: AsyncSession = Depends(get_db),
):
    svc = TeamService(db)

    # Must be team owner or admin
    if user_teams is not None:
        if not await svc.is_owner(team_id, current_user.id):
            raise HTTPException(status_code=403, detail="Only team owners can update the team")

    team = await svc.update(
        team_id,
        display_name=body.display_name,
        description=body.description if body.description is not None else ...,
    )
    if team is None:
        raise HTTPException(status_code=404, detail="Team not found")

    items, _ = await svc.list_teams(page=1, per_page=1000)
    for item in items:
        if item["id"] == team.id:
            return TeamRead(**item)

    raise HTTPException(status_code=404, detail="Team not found")


@router.delete("/{team_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_team(
    team_id: UUID,
    _: dict = Depends(require_permission("team", "delete")),
    db: AsyncSession = Depends(get_db),
):
    svc = TeamService(db)
    if not await svc.delete(team_id):
        raise HTTPException(status_code=400, detail="Cannot delete this team (default team or not found)")


# ---- Members ----


@router.get("/{team_id}/members", response_model=list[TeamMemberRead])
async def list_members(
    team_id: UUID,
    _: dict = Depends(require_permission("team", "read")),
    user_teams: list | None = Depends(get_user_teams),
    db: AsyncSession = Depends(get_db),
):
    # Non-admin must be a member
    if user_teams is not None:
        team_ids = [t["id"] for t in user_teams]
        if str(team_id) not in team_ids:
            raise HTTPException(status_code=404, detail="Team not found")

    svc = TeamService(db)
    members = await svc.get_members(team_id)
    return [
        TeamMemberRead(
            user_id=m.user_id,
            username=m.user.username,
            display_name=m.user.display_name,
            roles=[
                RoleBrief(id=r.role.id, name=r.role.name, display_name=r.role.display_name)
                for r in m.roles
            ],
            team_role=m.team_role,
            joined_at=m.joined_at,
        )
        for m in members
    ]


@router.post("/{team_id}/members", response_model=TeamMemberRead, status_code=status.HTTP_201_CREATED)
async def add_member(
    team_id: UUID,
    body: TeamMemberAdd,
    current_user: User = Depends(get_current_user),
    user_teams: list | None = Depends(get_user_teams),
    db: AsyncSession = Depends(get_db),
):
    svc = TeamService(db)

    # Must be team owner or have manage_members permission
    if user_teams is not None:
        if not await svc.is_owner(team_id, current_user.id):
            raise HTTPException(status_code=403, detail="Only team owners can add members")

    try:
        membership = await svc.add_member(
            team_id=team_id,
            user_id=body.user_id,
            role_ids=body.role_ids,
            team_role=body.team_role,
            added_by=current_user.id,
        )
    except Exception:
        raise HTTPException(status_code=400, detail="Failed to add member (already exists or invalid)")

    # Reload with relationships
    members = await svc.get_members(team_id)
    for m in members:
        if m.user_id == body.user_id:
            return TeamMemberRead(
                user_id=m.user_id,
                username=m.user.username,
                display_name=m.user.display_name,
                roles=[
                    RoleBrief(id=r.role.id, name=r.role.name, display_name=r.role.display_name)
                    for r in m.roles
                ],
                team_role=m.team_role,
                joined_at=m.joined_at,
            )

    raise HTTPException(status_code=500, detail="Failed to load member")


@router.patch("/{team_id}/members/{user_id}", response_model=TeamMemberRead)
async def update_member(
    team_id: UUID,
    user_id: UUID,
    body: TeamMemberUpdate,
    current_user: User = Depends(get_current_user),
    user_teams: list | None = Depends(get_user_teams),
    db: AsyncSession = Depends(get_db),
):
    svc = TeamService(db)

    if user_teams is not None:
        if not await svc.is_owner(team_id, current_user.id):
            raise HTTPException(status_code=403, detail="Only team owners can update members")

    membership = await svc.update_member(
        team_id=team_id,
        user_id=user_id,
        role_ids=body.role_ids,
        team_role=body.team_role,
    )
    if membership is None:
        raise HTTPException(status_code=404, detail="Member not found")

    members = await svc.get_members(team_id)
    for m in members:
        if m.user_id == user_id:
            return TeamMemberRead(
                user_id=m.user_id,
                username=m.user.username,
                display_name=m.user.display_name,
                roles=[
                    RoleBrief(id=r.role.id, name=r.role.name, display_name=r.role.display_name)
                    for r in m.roles
                ],
                team_role=m.team_role,
                joined_at=m.joined_at,
            )

    raise HTTPException(status_code=404, detail="Member not found")


@router.delete("/{team_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_member(
    team_id: UUID,
    user_id: UUID,
    current_user: User = Depends(get_current_user),
    user_teams: list | None = Depends(get_user_teams),
    db: AsyncSession = Depends(get_db),
):
    svc = TeamService(db)

    if user_teams is not None:
        if not await svc.is_owner(team_id, current_user.id):
            raise HTTPException(status_code=403, detail="Only team owners can remove members")

    if not await svc.remove_member(team_id, user_id):
        raise HTTPException(status_code=404, detail="Member not found")

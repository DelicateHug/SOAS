"""Team variable endpoints — nested under /teams/{team_id}/variables."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from soas_backend.api.deps import get_current_user, get_db, get_user_teams
from soas_backend.models.user import User
from soas_backend.services.team_service import TeamService
from soas_backend.services.team_variable_service import TeamVariableService
from soas_shared.schemas.common import PaginatedResponse, PaginationMeta
from soas_shared.schemas.team_variable import (
    TeamVariableCreate,
    TeamVariablePermissionEntry,
    TeamVariablePermissionUpdate,
    TeamVariableRead,
    TeamVariableUpdate,
)

router = APIRouter(prefix="/teams/{team_id}/variables", tags=["team-variables"])


async def _check_team_access(
    team_id: UUID,
    user_teams: list | None,
    db: AsyncSession,
) -> None:
    """Verify the user is a member of this team (admin bypasses)."""
    if user_teams is not None:
        team_ids = [t["id"] for t in user_teams]
        if str(team_id) not in team_ids:
            raise HTTPException(status_code=404, detail="Team not found")


def _to_read(v, mask_secret: bool = False) -> TeamVariableRead:
    return TeamVariableRead(
        id=v.id,
        team_id=v.team_id,
        name=v.name,
        description=v.description,
        value="***" if (v.is_secret and mask_secret) else v.value,
        is_secret=v.is_secret,
        created_by=v.created_by,
        updated_by=v.updated_by,
        created_at=v.created_at,
        updated_at=v.updated_at,
    )


@router.get("", response_model=PaginatedResponse[TeamVariableRead])
async def list_team_variables(
    team_id: UUID,
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    user_teams: list | None = Depends(get_user_teams),
    db: AsyncSession = Depends(get_db),
):
    await _check_team_access(team_id, user_teams, db)
    svc = TeamVariableService(db)
    variables, total = await svc.list_variables(team_id, page, per_page)

    return PaginatedResponse(
        data=[_to_read(v) for v in variables],
        meta=PaginationMeta(
            total=total,
            page=page,
            per_page=per_page,
            total_pages=(total + per_page - 1) // per_page if total else 0,
        ),
    )


@router.post("", response_model=TeamVariableRead, status_code=201)
async def create_team_variable(
    team_id: UUID,
    body: TeamVariableCreate,
    current_user: User = Depends(get_current_user),
    user_teams: list | None = Depends(get_user_teams),
    db: AsyncSession = Depends(get_db),
):
    await _check_team_access(team_id, user_teams, db)

    # Must be team owner or admin to create variables
    if user_teams is not None:
        team_svc = TeamService(db)
        if not await team_svc.is_owner(team_id, current_user.id):
            raise HTTPException(status_code=403, detail="Only team owners can create variables")

    svc = TeamVariableService(db)
    existing = await svc.get_by_name(team_id, body.name)
    if existing:
        raise HTTPException(status_code=409, detail=f"Variable '{body.name}' already exists in this team")

    variable = await svc.create(
        team_id=team_id,
        name=body.name,
        value=body.value,
        description=body.description,
        is_secret=body.is_secret,
        created_by=current_user.id,
    )
    return _to_read(variable)


@router.get("/{variable_id}", response_model=TeamVariableRead)
async def get_team_variable(
    team_id: UUID,
    variable_id: UUID,
    current_user: User = Depends(get_current_user),
    user_teams: list | None = Depends(get_user_teams),
    db: AsyncSession = Depends(get_db),
):
    await _check_team_access(team_id, user_teams, db)
    svc = TeamVariableService(db)
    variable = await svc.get(variable_id)
    if not variable or variable.team_id != team_id:
        raise HTTPException(status_code=404, detail="Variable not found")
    return _to_read(variable)


@router.patch("/{variable_id}", response_model=TeamVariableRead)
async def update_team_variable(
    team_id: UUID,
    variable_id: UUID,
    body: TeamVariableUpdate,
    current_user: User = Depends(get_current_user),
    user_teams: list | None = Depends(get_user_teams),
    db: AsyncSession = Depends(get_db),
):
    await _check_team_access(team_id, user_teams, db)

    if user_teams is not None:
        team_svc = TeamService(db)
        if not await team_svc.is_owner(team_id, current_user.id):
            raise HTTPException(status_code=403, detail="Only team owners can update variables")

    svc = TeamVariableService(db)
    variable = await svc.get(variable_id)
    if not variable or variable.team_id != team_id:
        raise HTTPException(status_code=404, detail="Variable not found")

    kwargs: dict = {"updated_by": current_user.id}
    if body.value is not None:
        kwargs["value"] = body.value
    if body.description is not None:
        kwargs["description"] = body.description
    if body.is_secret is not None:
        kwargs["is_secret"] = body.is_secret

    variable = await svc.update(variable_id, **kwargs)
    if not variable:
        raise HTTPException(status_code=404, detail="Variable not found")
    return _to_read(variable)


@router.delete("/{variable_id}", status_code=204)
async def delete_team_variable(
    team_id: UUID,
    variable_id: UUID,
    current_user: User = Depends(get_current_user),
    user_teams: list | None = Depends(get_user_teams),
    db: AsyncSession = Depends(get_db),
):
    await _check_team_access(team_id, user_teams, db)

    if user_teams is not None:
        team_svc = TeamService(db)
        if not await team_svc.is_owner(team_id, current_user.id):
            raise HTTPException(status_code=403, detail="Only team owners can delete variables")

    svc = TeamVariableService(db)
    variable = await svc.get(variable_id)
    if not variable or variable.team_id != team_id:
        raise HTTPException(status_code=404, detail="Variable not found")

    await svc.delete_variable(variable_id)


@router.get("/{variable_id}/permissions", response_model=list[TeamVariablePermissionEntry])
async def get_variable_permissions(
    team_id: UUID,
    variable_id: UUID,
    current_user: User = Depends(get_current_user),
    user_teams: list | None = Depends(get_user_teams),
    db: AsyncSession = Depends(get_db),
):
    await _check_team_access(team_id, user_teams, db)
    svc = TeamVariableService(db)
    variable = await svc.get(variable_id)
    if not variable or variable.team_id != team_id:
        raise HTTPException(status_code=404, detail="Variable not found")

    perms = await svc.get_permissions(variable_id)
    return [
        TeamVariablePermissionEntry(
            role_id=p.role_id,
            role_name=p.role.name if p.role else None,
            can_read=p.can_read,
            can_write=p.can_write,
        )
        for p in perms
    ]


@router.patch("/{variable_id}/permissions")
async def set_variable_permissions(
    team_id: UUID,
    variable_id: UUID,
    body: TeamVariablePermissionUpdate,
    current_user: User = Depends(get_current_user),
    user_teams: list | None = Depends(get_user_teams),
    db: AsyncSession = Depends(get_db),
):
    await _check_team_access(team_id, user_teams, db)

    if user_teams is not None:
        team_svc = TeamService(db)
        if not await team_svc.is_owner(team_id, current_user.id):
            raise HTTPException(status_code=403, detail="Only team owners can manage variable permissions")

    svc = TeamVariableService(db)
    variable = await svc.get(variable_id)
    if not variable or variable.team_id != team_id:
        raise HTTPException(status_code=404, detail="Variable not found")

    await svc.set_permissions(
        variable_id,
        [p.model_dump() for p in body.permissions],
        granted_by=current_user.id,
    )
    return {"message": "Permissions updated"}

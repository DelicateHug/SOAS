"""Team management service."""

from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from soas_backend.models.role import Role, UserRole
from soas_backend.models.team import Team, TeamMembership, TeamMembershipRole
from soas_backend.models.user import User


class TeamService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(
        self,
        name: str,
        display_name: str,
        created_by: UUID,
        description: str | None = None,
    ) -> Team:
        team = Team(
            name=name,
            display_name=display_name,
            description=description,
            created_by=created_by,
        )
        self.db.add(team)
        await self.db.flush()

        # Add creator as owner with their global roles
        membership = TeamMembership(
            user_id=created_by,
            team_id=team.id,
            team_role="owner",
            added_by=created_by,
        )
        self.db.add(membership)
        await self.db.flush()

        # Copy user's global roles to team membership
        role_ids = await self._get_user_global_role_ids(created_by)
        for role_id in role_ids:
            self.db.add(TeamMembershipRole(
                user_id=created_by, team_id=team.id, role_id=role_id,
            ))
        await self.db.flush()

        return team

    async def get(self, team_id: UUID) -> Team | None:
        result = await self.db.execute(
            select(Team)
            .options(selectinload(Team.memberships).selectinload(TeamMembership.user))
            .where(Team.id == team_id)
        )
        return result.scalar_one_or_none()

    async def list_teams(
        self,
        user_id: UUID | None = None,
        page: int = 1,
        per_page: int = 25,
    ) -> tuple[list[dict], int]:
        """List teams. If user_id is provided, only their teams. Otherwise all."""
        count_query = select(func.count(Team.id))
        data_query = select(Team).order_by(Team.display_name)

        if user_id is not None:
            count_query = count_query.join(TeamMembership).where(TeamMembership.user_id == user_id)
            data_query = data_query.join(TeamMembership).where(TeamMembership.user_id == user_id)

        total = (await self.db.execute(count_query)).scalar() or 0

        result = await self.db.execute(
            data_query.offset((page - 1) * per_page).limit(per_page)
        )
        teams = result.scalars().all()

        # Get member counts
        items = []
        for team in teams:
            mc = (await self.db.execute(
                select(func.count()).select_from(TeamMembership).where(TeamMembership.team_id == team.id)
            )).scalar() or 0
            items.append({
                "id": team.id,
                "name": team.name,
                "display_name": team.display_name,
                "description": team.description,
                "is_default": team.is_default,
                "member_count": mc,
                "created_at": team.created_at,
                "updated_at": team.updated_at,
            })

        return items, total

    async def update(
        self,
        team_id: UUID,
        display_name: str | None = None,
        description: str | None = ...,
    ) -> Team | None:
        team = await self.db.get(Team, team_id)
        if team is None:
            return None
        if display_name is not None:
            team.display_name = display_name
        if description is not ...:
            team.description = description
        await self.db.flush()
        return team

    async def delete(self, team_id: UUID) -> bool:
        team = await self.db.get(Team, team_id)
        if team is None:
            return False
        if team.is_default:
            return False
        await self.db.delete(team)
        await self.db.flush()
        return True

    # ---- Membership ----

    async def get_members(
        self, team_id: UUID
    ) -> list[TeamMembership]:
        result = await self.db.execute(
            select(TeamMembership)
            .options(
                selectinload(TeamMembership.user),
                selectinload(TeamMembership.roles).selectinload(TeamMembershipRole.role),
            )
            .where(TeamMembership.team_id == team_id)
            .order_by(TeamMembership.joined_at)
        )
        return list(result.scalars().all())

    async def add_member(
        self,
        team_id: UUID,
        user_id: UUID,
        role_ids: list[UUID],
        team_role: str = "member",
        added_by: UUID | None = None,
    ) -> TeamMembership:
        membership = TeamMembership(
            user_id=user_id,
            team_id=team_id,
            team_role=team_role,
            added_by=added_by,
        )
        self.db.add(membership)
        await self.db.flush()

        for role_id in role_ids:
            self.db.add(TeamMembershipRole(
                user_id=user_id, team_id=team_id, role_id=role_id,
            ))
        await self.db.flush()

        return membership

    async def remove_member(self, team_id: UUID, user_id: UUID) -> bool:
        result = await self.db.execute(
            select(TeamMembership).where(
                TeamMembership.team_id == team_id,
                TeamMembership.user_id == user_id,
            )
        )
        membership = result.scalar_one_or_none()
        if membership is None:
            return False
        # Roles cascade-delete via relationship
        await self.db.delete(membership)
        await self.db.flush()
        return True

    async def update_member(
        self,
        team_id: UUID,
        user_id: UUID,
        role_ids: list[UUID] | None = None,
        team_role: str | None = None,
    ) -> TeamMembership | None:
        result = await self.db.execute(
            select(TeamMembership).where(
                TeamMembership.team_id == team_id,
                TeamMembership.user_id == user_id,
            )
        )
        membership = result.scalar_one_or_none()
        if membership is None:
            return None
        if team_role is not None:
            membership.team_role = team_role
        if role_ids is not None:
            # Replace all roles
            await self.db.execute(
                delete(TeamMembershipRole).where(
                    TeamMembershipRole.user_id == user_id,
                    TeamMembershipRole.team_id == team_id,
                )
            )
            for role_id in role_ids:
                self.db.add(TeamMembershipRole(
                    user_id=user_id, team_id=team_id, role_id=role_id,
                ))
        await self.db.flush()
        return membership

    async def is_member(self, team_id: UUID, user_id: UUID) -> bool:
        result = await self.db.execute(
            select(func.count()).select_from(TeamMembership).where(
                TeamMembership.team_id == team_id,
                TeamMembership.user_id == user_id,
            )
        )
        return (result.scalar() or 0) > 0

    async def is_owner(self, team_id: UUID, user_id: UUID) -> bool:
        result = await self.db.execute(
            select(TeamMembership).where(
                TeamMembership.team_id == team_id,
                TeamMembership.user_id == user_id,
                TeamMembership.team_role == "owner",
            )
        )
        return result.scalar_one_or_none() is not None

    async def get_user_team_memberships(self, user_id: UUID) -> list[dict]:
        """Get all team memberships for a user, formatted for JWT claims."""
        result = await self.db.execute(
            select(TeamMembership)
            .options(
                selectinload(TeamMembership.team),
                selectinload(TeamMembership.roles).selectinload(TeamMembershipRole.role),
            )
            .where(TeamMembership.user_id == user_id)
        )
        memberships = result.scalars().all()

        return [
            {
                "id": str(m.team.id),
                "name": m.team.name,
                "roles": [r.role.name for r in m.roles],
                "team_role": m.team_role,
            }
            for m in memberships
        ]

    async def _get_user_global_role_ids(self, user_id: UUID) -> list[UUID]:
        """Get all of the user's global role IDs."""
        result = await self.db.execute(
            select(UserRole.role_id).where(UserRole.user_id == user_id)
        )
        role_ids = list(result.scalars().all())
        if role_ids:
            return role_ids

        # Fallback to viewer
        result = await self.db.execute(
            select(Role.id).where(Role.name == "viewer").limit(1)
        )
        viewer_id = result.scalar_one_or_none()
        return [viewer_id] if viewer_id else []

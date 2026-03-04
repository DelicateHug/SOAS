"""RBAC service - role and permission management."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from soas_backend.models.automation import AutomationPermission
from soas_backend.models.role import Permission, Role, RolePermission, UserRole


class RBACService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_user_roles(self, user_id: UUID) -> list[UUID]:
        result = await self.db.execute(
            select(UserRole.role_id).where(UserRole.user_id == user_id)
        )
        return list(result.scalars().all())

    async def check_permission(self, user_id: UUID, resource: str, action: str) -> bool:
        """Check if user has a specific resource:action permission via any of their roles."""
        result = await self.db.execute(
            select(RolePermission)
            .join(UserRole, UserRole.role_id == RolePermission.role_id)
            .join(Permission, Permission.id == RolePermission.permission_id)
            .where(
                UserRole.user_id == user_id,
                Permission.resource == resource,
                Permission.action == action,
            )
        )
        return result.first() is not None

    async def check_automation_permission(
        self, user_id: UUID, automation_id: UUID
    ) -> bool:
        """Check if user's roles grant execute access to a specific automation."""
        user_role_ids = await self.get_user_roles(user_id)
        if not user_role_ids:
            return False

        result = await self.db.execute(
            select(AutomationPermission).where(
                AutomationPermission.automation_id == automation_id,
                AutomationPermission.role_id.in_(user_role_ids),
                AutomationPermission.can_execute.is_(True),
            )
        )
        return result.first() is not None

    async def get_all_roles(self) -> list[Role]:
        result = await self.db.execute(
            select(Role)
            .options(
                selectinload(Role.role_permissions).selectinload(RolePermission.permission)
            )
            .order_by(Role.name)
        )
        return list(result.scalars().all())

    async def get_all_permissions(self) -> list[Permission]:
        result = await self.db.execute(
            select(Permission).order_by(Permission.resource, Permission.action)
        )
        return list(result.scalars().all())

    async def create_role(
        self,
        name: str,
        display_name: str,
        description: str | None,
        permission_ids: list[UUID],
    ) -> Role:
        role = Role(name=name, display_name=display_name, description=description)
        self.db.add(role)
        await self.db.flush()

        for perm_id in permission_ids:
            self.db.add(RolePermission(role_id=role.id, permission_id=perm_id))

        await self.db.flush()
        return role

    async def update_role_permissions(
        self, role_id: UUID, permission_ids: list[UUID]
    ) -> None:
        # Remove existing permissions
        result = await self.db.execute(
            select(RolePermission).where(RolePermission.role_id == role_id)
        )
        for rp in result.scalars().all():
            await self.db.delete(rp)

        # Add new permissions
        for perm_id in permission_ids:
            self.db.add(RolePermission(role_id=role_id, permission_id=perm_id))

        await self.db.flush()

    async def assign_role_to_user(
        self, user_id: UUID, role_id: UUID, assigned_by: UUID | None = None
    ) -> None:
        self.db.add(
            UserRole(user_id=user_id, role_id=role_id, assigned_by=assigned_by)
        )
        await self.db.flush()

    async def remove_role_from_user(self, user_id: UUID, role_id: UUID) -> bool:
        result = await self.db.execute(
            select(UserRole).where(
                UserRole.user_id == user_id, UserRole.role_id == role_id
            )
        )
        ur = result.scalar_one_or_none()
        if ur:
            await self.db.delete(ur)
            return True
        return False

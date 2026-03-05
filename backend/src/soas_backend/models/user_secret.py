"""User secret model - per-user encrypted key-value secrets."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from soas_backend.database import Base


class UserSecret(Base):
    __tablename__ = "user_secrets"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    encrypted_value: Mapped[str] = mapped_column(Text, nullable=False)
    sensitive: Mapped[bool] = mapped_column(Boolean, server_default="false", nullable=False)
    is_shared: Mapped[bool] = mapped_column(Boolean, server_default="false", nullable=False)
    server_encrypted_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(),
    )

    owner = relationship("User", foreign_keys=[user_id])
    share_permissions: Mapped[list["SharedSecretPermission"]] = relationship(
        back_populates="secret", cascade="all, delete-orphan",
    )

    __table_args__ = (
        UniqueConstraint("user_id", "name", name="uq_user_secrets_user_name"),
    )


class SharedSecretPermission(Base):
    __tablename__ = "shared_secret_permissions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    secret_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("user_secrets.id", ondelete="CASCADE"), nullable=False,
    )
    role_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("roles.id", ondelete="CASCADE"), nullable=False,
    )
    can_read: Mapped[bool] = mapped_column(Boolean, server_default="true", nullable=False)

    secret: Mapped["UserSecret"] = relationship(back_populates="share_permissions")
    role = relationship("Role", foreign_keys=[role_id])

    __table_args__ = (
        UniqueConstraint("secret_id", "role_id", name="uq_shared_secret_perm_secret_role"),
    )

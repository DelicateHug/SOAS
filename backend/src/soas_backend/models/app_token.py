"""App tokens — short-lived SOAS-minted credentials issued after upstream auth (OIDC/local).

The app token is the durable identity SOAS itself trusts after Microsoft (or local password)
has validated the user. It lasts 6 hours and is always paired 1:1 with an AppSession that
carries the HMAC key used to sign requests.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from soas_backend.database import Base


class AppToken(Base):
    __tablename__ = "app_tokens"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    token_hash: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    token_ciphertext: Mapped[str] = mapped_column(Text, nullable=False)
    issued_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    issued_via: Mapped[str] = mapped_column(String(32), nullable=False, default="local")
    oidc_subject: Mapped[str | None] = mapped_column(String(255), nullable=True)

    user = relationship("User", foreign_keys=[user_id])

    __table_args__ = (
        Index("idx_app_tokens_user_expires", "user_id", "expires_at"),
    )

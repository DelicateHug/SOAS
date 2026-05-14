"""UserCertificate — public metadata for a per-user client certificate.

The private key is generated server-side at issue time, bundled into a
one-time-download PKCS#12, and immediately discarded. Only the public
cert + fingerprint + serial are persisted.

Purposes encode where the cert is used:
  - "web"  — browser-side mTLS to the SOAS gateway
  - "mcp"  — Claude Code / IDE MCP client
  - "cli"  — operator CLI / scripts

One *active* (not-revoked) cert per (user, purpose).
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from soas_backend.database import Base


class UserCertificate(Base):
    __tablename__ = "user_certificates"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    purpose: Mapped[str] = mapped_column(String(16), nullable=False, default="web")
    # Hex-encoded X.509 serial number
    serial: Mapped[str] = mapped_column(String(80), nullable=False)
    # Hex-encoded SHA-256 fingerprint of the DER-encoded cert
    fingerprint_sha256: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    common_name: Mapped[str] = mapped_column(String(200), nullable=False)
    # PEM of the public cert. Useful for re-issuing the .p12 if the
    # operator caches the original passphrase; we never persist key material.
    cert_pem: Mapped[str | None] = mapped_column(Text, nullable=True)
    not_before: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    not_after: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    issued_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    issued_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    downloaded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revocation_reason: Mapped[str | None] = mapped_column(String(200), nullable=True)

    user = relationship("User", foreign_keys=[user_id])
    issuer = relationship("User", foreign_keys=[issued_by])

    __table_args__ = (
        Index("idx_user_certificates_user", "user_id"),
        Index("idx_user_certificates_fingerprint", "fingerprint_sha256"),
        Index("idx_user_certificates_serial", "serial"),
        # No DB-level unique on (user, purpose, active) because a NULL revoked_at
        # represents "active" and SQL doesn't unique-on-null usefully across
        # backends. The service layer enforces the invariant.
    )

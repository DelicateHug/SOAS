"""RegisteredAgent — the declared roster of running SOAS instances.

An agent is identified by a stable `agenttype_id` of the form
`<role>_<n>` (e.g. `worker_001`, `backend_002`). Restarts of the same
agenttype_id extend the same lifetime; logs and metrics are correlated
under the same identifier, so deploy/restart cycles don't create a
parallel data stream.

The instance reports its version on every heartbeat so that a sudden
behavior change (alert spike, error rate jump) can be correlated with
a deploy.

Status is derived from the most recent instance_metric_samples row:
  - 'alive'   — last_seen within fresh_seconds
  - 'stale'   — last_seen within fresh_seconds*3
  - 'missing' — older or never reported
"""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from soas_backend.database import Base


class RegisteredAgent(Base):
    __tablename__ = "registered_agents"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # Stable identifier; format: <role>_<digits>, e.g. worker_001
    agenttype_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    label: Mapped[str | None] = mapped_column(String(200), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    fresh_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=60)
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        Index("idx_registered_agents_role", "role"),
    )

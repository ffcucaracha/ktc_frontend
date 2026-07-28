from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.time import utc_now
from app.db.base import Base
from app.models.enums import SimulationCommandStatus


class SimulationCommand(Base):
    __tablename__ = "simulation_commands"
    __table_args__ = (
        CheckConstraint(
            "status in ('pending', 'accepted', 'rejected', 'failed')",
            name="ck_simulation_commands_status",
        ),
        Index("ix_simulation_commands_command_id", "command_id", unique=True),
        Index("ix_simulation_commands_session_created_at", "session_id", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), primary_key=True, default=uuid4)
    session_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("simulation_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    command_id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), nullable=False)
    equipment_id: Mapped[str] = mapped_column(String(100), nullable=False)
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    payload: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False, default=dict)
    status: Mapped[SimulationCommandStatus] = mapped_column(String(20), nullable=False)
    external_error_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    external_error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

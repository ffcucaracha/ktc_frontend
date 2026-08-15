from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.time import utc_now
from app.db.base import Base
from app.models.enums import SimulationSessionStatus, TrainingSessionMode


class SimulationSession(Base):
    __tablename__ = "simulation_sessions"
    __table_args__ = (
        CheckConstraint(
            "status in ('creating', 'active', 'stopping', 'completed', 'failed')",
            name="ck_simulation_sessions_status",
        ),
        CheckConstraint(
            "mode in ('training', 'exam')",
            name="ck_simulation_sessions_mode",
        ),
        Index("ix_simulation_sessions_operator_status", "operator_id", "status"),
        Index("ix_simulation_sessions_simulator_definition_id", "simulator_definition_id"),
        Index("ix_simulation_sessions_training_scenario_id", "training_scenario_id"),
        Index("ix_simulation_sessions_external_session_id", "external_session_id", unique=True),
    )

    id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), primary_key=True, default=uuid4)
    operator_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    simulator_definition_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("simulator_definitions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    training_scenario_id: Mapped[UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("training_scenarios.id", ondelete="SET NULL"),
        nullable=True,
    )
    mode: Mapped[TrainingSessionMode] = mapped_column(
        String(20), nullable=False, default=TrainingSessionMode.TRAINING
    )
    external_session_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[SimulationSessionStatus] = mapped_column(String(20), nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_state: Mapped[dict[str, object] | None] = mapped_column(JSONB, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, Integer, String, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.time import utc_now
from app.db.base import Base


class SimulationEvent(Base):
    __tablename__ = "simulation_events"
    __table_args__ = (
        Index("ix_simulation_events_session_created_at", "session_id", "created_at"),
        Index("ix_simulation_events_session_simulation_time", "session_id", "simulation_time_ms"),
        Index("ix_simulation_events_session_event_type", "session_id", "event_type"),
        Index(
            "uq_simulation_events_snapshot_revision",
            "session_id",
            "revision",
            unique=True,
            postgresql_where=text("event_type = 'state.snapshot' AND revision IS NOT NULL"),
        ),
    )

    id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), primary_key=True, default=uuid4)
    session_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("simulation_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    revision: Mapped[int | None] = mapped_column(Integer, nullable=True)
    simulation_time_ms: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    payload: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )

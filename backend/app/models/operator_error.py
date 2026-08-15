from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.time import utc_now
from app.db.base import Base
from app.models.enums import OperatorErrorSource, OperatorErrorType


class OperatorError(Base):
    __tablename__ = "operator_errors"
    __table_args__ = (
        Index("ix_operator_errors_session_created_at", "session_id", "created_at"),
        Index("ix_operator_errors_session_type", "session_id", "error_type"),
    )

    id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), primary_key=True, default=uuid4)
    session_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("simulation_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    scenario_expected_action_id: Mapped[UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("scenario_expected_actions.id", ondelete="SET NULL"),
        nullable=True,
    )
    error_type: Mapped[OperatorErrorType] = mapped_column(String(32), nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False, default="warning")
    occurred_at_ms: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    evidence: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False, default=dict)
    causal_chain: Mapped[list[dict[str, object]]] = mapped_column(JSONB, nullable=False, default=list)
    source: Mapped[OperatorErrorSource] = mapped_column(
        String(20), nullable=False, default=OperatorErrorSource.RULE
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)

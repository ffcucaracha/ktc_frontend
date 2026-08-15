from uuid import UUID, uuid4

from sqlalchemy import BigInteger, ForeignKey, Index, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ScenarioExpectedAction(Base):
    __tablename__ = "scenario_expected_actions"
    __table_args__ = (
        Index(
            "ix_scenario_expected_actions_scenario_order",
            "scenario_id",
            "order_index",
            unique=True,
        ),
        Index("ix_scenario_expected_actions_scenario_step", "scenario_id", "step_code", unique=True),
    )

    id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), primary_key=True, default=uuid4)
    scenario_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("training_scenarios.id", ondelete="CASCADE"),
        nullable=False,
    )
    step_code: Mapped[str] = mapped_column(String(100), nullable=False)
    equipment_id: Mapped[str] = mapped_column(String(100), nullable=False)
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    payload_constraints: Mapped[dict[str, object] | None] = mapped_column(JSONB, nullable=True)
    condition: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False, default=dict)
    allowed_delay_ms: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    severity_if_missed: Mapped[str] = mapped_column(String(20), nullable=False, default="warning")
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)

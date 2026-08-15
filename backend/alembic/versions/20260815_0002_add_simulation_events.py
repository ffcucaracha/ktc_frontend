"""Add simulation timeline events.

Revision ID: 20260815_0002
Revises: 20260713_0001
Create Date: 2026-08-15
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260815_0002"
down_revision: str | None = "20260713_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "simulation_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=True),
        sa.Column("simulation_time_ms", sa.BigInteger(), nullable=True),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["simulation_sessions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_simulation_events_session_created_at",
        "simulation_events",
        ["session_id", "created_at"],
    )
    op.create_index(
        "ix_simulation_events_session_simulation_time",
        "simulation_events",
        ["session_id", "simulation_time_ms"],
    )
    op.create_index(
        "ix_simulation_events_session_event_type",
        "simulation_events",
        ["session_id", "event_type"],
    )
    op.create_index(
        "uq_simulation_events_snapshot_revision",
        "simulation_events",
        ["session_id", "revision"],
        unique=True,
        postgresql_where=sa.text("event_type = 'state.snapshot' AND revision IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_simulation_events_snapshot_revision", table_name="simulation_events")
    op.drop_index("ix_simulation_events_session_event_type", table_name="simulation_events")
    op.drop_index("ix_simulation_events_session_simulation_time", table_name="simulation_events")
    op.drop_index("ix_simulation_events_session_created_at", table_name="simulation_events")
    op.drop_table("simulation_events")

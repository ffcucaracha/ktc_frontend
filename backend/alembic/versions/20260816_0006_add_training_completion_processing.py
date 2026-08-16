"""Add durable processing state for training completion events.

Revision ID: 20260816_0006
Revises: 20260816_0005
Create Date: 2026-08-16
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260816_0006"
down_revision: str | None = "20260816_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "training_completion_processing",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("result", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status in ('pending', 'failed', 'completed')",
            name="ck_training_completion_processing_status",
        ),
        sa.CheckConstraint("attempts >= 0", name="ck_training_completion_processing_attempts"),
        sa.ForeignKeyConstraint(["event_id"], ["simulation_events.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["session_id"], ["simulation_sessions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("event_id", name="uq_training_completion_processing_event"),
    )
    op.create_index(
        "ix_training_completion_processing_session_id",
        "training_completion_processing",
        ["session_id"],
    )
    op.create_index(
        "ix_training_completion_processing_status_attempts",
        "training_completion_processing",
        ["status", "attempts"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_training_completion_processing_status_attempts",
        table_name="training_completion_processing",
    )
    op.drop_index(
        "ix_training_completion_processing_session_id",
        table_name="training_completion_processing",
    )
    op.drop_table("training_completion_processing")

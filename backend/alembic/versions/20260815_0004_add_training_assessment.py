"""Add deterministic training assessment tables.

Revision ID: 20260815_0004
Revises: 20260815_0003
Create Date: 2026-08-15
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260815_0004"
down_revision: str | None = "20260815_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "training_results",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("scenario_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("max_score", sa.Float(), nullable=False),
        sa.Column("reaction_time_ms", sa.Integer(), nullable=True),
        sa.Column("error_count", sa.Integer(), nullable=False),
        sa.Column("critical_error_count", sa.Integer(), nullable=False),
        sa.Column("sequence_score", sa.Float(), nullable=False),
        sa.Column("reaction_score", sa.Float(), nullable=False),
        sa.Column("safety_score", sa.Float(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("summary", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("status in ('provisional', 'final')", name="ck_training_results_status"),
        sa.ForeignKeyConstraint(["scenario_id"], ["training_scenarios.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["session_id"], ["simulation_sessions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("session_id", name="uq_training_results_session_id"),
    )
    op.create_index("ix_training_results_scenario_id", "training_results", ["scenario_id"])

    op.create_table(
        "operator_errors",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("scenario_expected_action_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("error_type", sa.String(length=32), nullable=False),
        sa.Column("severity", sa.String(length=20), nullable=False),
        sa.Column("occurred_at_ms", sa.BigInteger(), nullable=True),
        sa.Column("evidence", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("causal_chain", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("source", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "error_type in ('WRONG_ACTION', 'LATE_ACTION', 'MISSED_ACTION', 'WRONG_SEQUENCE')",
            name="ck_operator_errors_error_type",
        ),
        sa.CheckConstraint("source in ('rule', 'ml')", name="ck_operator_errors_source"),
        sa.ForeignKeyConstraint(
            ["scenario_expected_action_id"],
            ["scenario_expected_actions.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(["session_id"], ["simulation_sessions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_operator_errors_session_created_at",
        "operator_errors",
        ["session_id", "created_at"],
    )
    op.create_index(
        "ix_operator_errors_session_type",
        "operator_errors",
        ["session_id", "error_type"],
    )


def downgrade() -> None:
    op.drop_index("ix_operator_errors_session_type", table_name="operator_errors")
    op.drop_index("ix_operator_errors_session_created_at", table_name="operator_errors")
    op.drop_table("operator_errors")
    op.drop_index("ix_training_results_scenario_id", table_name="training_results")
    op.drop_table("training_results")

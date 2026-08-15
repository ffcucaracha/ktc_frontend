"""Add training scenarios and session mode.

Revision ID: 20260815_0003
Revises: 20260815_0002
Create Date: 2026-08-15
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260815_0003"
down_revision: str | None = "20260815_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "training_scenarios",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("code", sa.String(length=100), nullable=False),
        sa.Column("simulator_definition_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("difficulty", sa.String(length=20), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("config", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "difficulty in ('basic', 'medium', 'advanced')",
            name="ck_training_scenarios_difficulty",
        ),
        sa.ForeignKeyConstraint(
            ["simulator_definition_id"],
            ["simulator_definitions.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_training_scenarios_code", "training_scenarios", ["code"], unique=True)
    op.create_index(
        "ix_training_scenarios_simulator_active",
        "training_scenarios",
        ["simulator_definition_id", "is_active"],
    )

    op.create_table(
        "scenario_expected_actions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("scenario_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("step_code", sa.String(length=100), nullable=False),
        sa.Column("equipment_id", sa.String(length=100), nullable=False),
        sa.Column("action", sa.String(length=50), nullable=False),
        sa.Column("payload_constraints", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("condition", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("allowed_delay_ms", sa.BigInteger(), nullable=True),
        sa.Column("severity_if_missed", sa.String(length=20), nullable=False),
        sa.Column("order_index", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["scenario_id"], ["training_scenarios.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_scenario_expected_actions_scenario_order",
        "scenario_expected_actions",
        ["scenario_id", "order_index"],
        unique=True,
    )
    op.create_index(
        "ix_scenario_expected_actions_scenario_step",
        "scenario_expected_actions",
        ["scenario_id", "step_code"],
        unique=True,
    )

    op.add_column(
        "simulation_sessions",
        sa.Column("training_scenario_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "simulation_sessions",
        sa.Column("mode", sa.String(length=20), nullable=False, server_default="training"),
    )
    op.create_foreign_key(
        "fk_simulation_sessions_training_scenario_id",
        "simulation_sessions",
        "training_scenarios",
        ["training_scenario_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_check_constraint(
        "ck_simulation_sessions_mode",
        "simulation_sessions",
        "mode in ('training', 'exam')",
    )
    op.create_index(
        "ix_simulation_sessions_training_scenario_id",
        "simulation_sessions",
        ["training_scenario_id"],
    )
    op.alter_column("simulation_sessions", "mode", server_default=None)


def downgrade() -> None:
    op.drop_index("ix_simulation_sessions_training_scenario_id", table_name="simulation_sessions")
    op.drop_constraint("ck_simulation_sessions_mode", "simulation_sessions", type_="check")
    op.drop_constraint(
        "fk_simulation_sessions_training_scenario_id",
        "simulation_sessions",
        type_="foreignkey",
    )
    op.drop_column("simulation_sessions", "mode")
    op.drop_column("simulation_sessions", "training_scenario_id")

    op.drop_index(
        "ix_scenario_expected_actions_scenario_step",
        table_name="scenario_expected_actions",
    )
    op.drop_index(
        "ix_scenario_expected_actions_scenario_order",
        table_name="scenario_expected_actions",
    )
    op.drop_table("scenario_expected_actions")

    op.drop_index("ix_training_scenarios_simulator_active", table_name="training_scenarios")
    op.drop_index("ix_training_scenarios_code", table_name="training_scenarios")
    op.drop_table("training_scenarios")

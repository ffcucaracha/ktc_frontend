"""Initial domain models.

Revision ID: 20260713_0001
Revises:
Create Date: 2026-07-13
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260713_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("username", sa.String(length=64), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("role in ('admin', 'operator')", name="ck_users_role"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_users_username", "users", ["username"], unique=True)

    op.create_table(
        "simulator_definitions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("external_id", sa.String(length=128), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("visualization_type", sa.String(length=64), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_simulator_definitions_code",
        "simulator_definitions",
        ["code"],
        unique=True,
    )
    op.create_index(
        "ix_simulator_definitions_is_active",
        "simulator_definitions",
        ["is_active"],
        unique=False,
    )

    op.create_table(
        "refresh_tokens",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("token_hash", sa.Text(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("replaced_by_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["replaced_by_id"], ["refresh_tokens.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_refresh_tokens_expires_at", "refresh_tokens", ["expires_at"])
    op.create_index("ix_refresh_tokens_token_hash", "refresh_tokens", ["token_hash"], unique=True)
    op.create_index("ix_refresh_tokens_user_id", "refresh_tokens", ["user_id"])

    op.create_table(
        "login_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("username_entered", sa.String(length=64), nullable=False),
        sa.Column("success", sa.Boolean(), nullable=False),
        sa.Column("failure_reason", sa.String(length=50), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ip_address", postgresql.INET(), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "failure_reason is null or failure_reason in ('invalid_credentials', 'inactive_user')",
            name="ck_login_events_failure_reason",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_login_events_user_occurred_at",
        "login_events",
        ["user_id", "occurred_at"],
    )
    op.create_index(
        "ix_login_events_username_occurred_at",
        "login_events",
        ["username_entered", "occurred_at"],
    )

    op.create_table(
        "simulation_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("operator_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("simulator_definition_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("external_session_id", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_state", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("error_code", sa.String(length=100), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status in ('creating', 'active', 'stopping', 'completed', 'failed')",
            name="ck_simulation_sessions_status",
        ),
        sa.ForeignKeyConstraint(["operator_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["simulator_definition_id"],
            ["simulator_definitions.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_simulation_sessions_external_session_id",
        "simulation_sessions",
        ["external_session_id"],
        unique=True,
    )
    op.create_index(
        "ix_simulation_sessions_operator_status",
        "simulation_sessions",
        ["operator_id", "status"],
    )
    op.create_index(
        "ix_simulation_sessions_simulator_definition_id",
        "simulation_sessions",
        ["simulator_definition_id"],
    )

    op.create_table(
        "simulation_commands",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("command_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("equipment_id", sa.String(length=100), nullable=False),
        sa.Column("action", sa.String(length=50), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("external_error_code", sa.String(length=100), nullable=True),
        sa.Column("external_error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status in ('pending', 'accepted', 'rejected', 'failed')",
            name="ck_simulation_commands_status",
        ),
        sa.ForeignKeyConstraint(["session_id"], ["simulation_sessions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_simulation_commands_command_id",
        "simulation_commands",
        ["command_id"],
        unique=True,
    )
    op.create_index(
        "ix_simulation_commands_session_created_at",
        "simulation_commands",
        ["session_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_simulation_commands_session_created_at", table_name="simulation_commands")
    op.drop_index("ix_simulation_commands_command_id", table_name="simulation_commands")
    op.drop_table("simulation_commands")

    op.drop_index(
        "ix_simulation_sessions_simulator_definition_id",
        table_name="simulation_sessions",
    )
    op.drop_index("ix_simulation_sessions_operator_status", table_name="simulation_sessions")
    op.drop_index("ix_simulation_sessions_external_session_id", table_name="simulation_sessions")
    op.drop_table("simulation_sessions")

    op.drop_index("ix_login_events_username_occurred_at", table_name="login_events")
    op.drop_index("ix_login_events_user_occurred_at", table_name="login_events")
    op.drop_table("login_events")

    op.drop_index("ix_refresh_tokens_user_id", table_name="refresh_tokens")
    op.drop_index("ix_refresh_tokens_token_hash", table_name="refresh_tokens")
    op.drop_index("ix_refresh_tokens_expires_at", table_name="refresh_tokens")
    op.drop_table("refresh_tokens")

    op.drop_index("ix_simulator_definitions_is_active", table_name="simulator_definitions")
    op.drop_index("ix_simulator_definitions_code", table_name="simulator_definitions")
    op.drop_table("simulator_definitions")

    op.drop_index("ix_users_username", table_name="users")
    op.drop_table("users")

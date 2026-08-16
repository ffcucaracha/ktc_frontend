"""Add persistent operator skill profiles.

Revision ID: 20260816_0005
Revises: 20260815_0004
Create Date: 2026-08-16
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260816_0005"
down_revision: str | None = "20260815_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "operator_skill_profiles",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("operator_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("skill_code", sa.String(length=64), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("sample_count", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("score >= 0 AND score <= 100", name="ck_operator_skill_profiles_score"),
        sa.CheckConstraint("sample_count >= 0", name="ck_operator_skill_profiles_sample_count"),
        sa.ForeignKeyConstraint(["operator_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("operator_id", "skill_code", name="uq_operator_skill_profiles_operator_skill"),
    )
    op.create_index(
        "ix_operator_skill_profiles_operator_id",
        "operator_skill_profiles",
        ["operator_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_operator_skill_profiles_operator_id", table_name="operator_skill_profiles")
    op.drop_table("operator_skill_profiles")

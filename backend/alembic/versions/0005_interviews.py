"""AI mock interviews: one row per interview, many per analysis

Revision ID: 0005
Revises: 0004
Create Date: 2026-11-03
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "interviews",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "analysis_id", UUID(as_uuid=True), sa.ForeignKey("analyses.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("status", sa.String(12), nullable=False, server_default=sa.text("'active'")),
        sa.Column("interviewer", sa.String(20), nullable=False),
        sa.Column("question_count", sa.SmallInteger, nullable=False),
        sa.Column("current_question", sa.SmallInteger, nullable=False, server_default=sa.text("1")),
        sa.Column("follow_ups", sa.SmallInteger, nullable=False, server_default=sa.text("0")),
        sa.Column("plan", JSONB, nullable=False),
        sa.Column("turns", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("feedback", JSONB),
        sa.Column("engine", sa.String(60), nullable=False),
        sa.Column("duration_seconds", sa.Integer),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint("status IN ('active', 'completed')", name="ck_interview_status"),
        sa.CheckConstraint("question_count BETWEEN 10 AND 15", name="ck_interview_count"),
    )
    op.create_index("idx_interviews_analysis_date", "interviews", ["analysis_id", sa.text("created_at DESC")])


def downgrade() -> None:
    op.drop_table("interviews")

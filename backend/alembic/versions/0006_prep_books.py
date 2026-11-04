"""Interview prep books: categorised scenario questions per analysis

Revision ID: 0006
Revises: 0005
Create Date: 2026-11-04
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "prep_books",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "analysis_id", UUID(as_uuid=True), sa.ForeignKey("analyses.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("status", sa.String(12), nullable=False, server_default=sa.text("'queued'")),
        sa.Column("per_category", sa.SmallInteger, nullable=False),
        sa.Column("current_step", sa.String(20)),
        sa.Column("content", JSONB),
        sa.Column("engine", sa.String(60)),
        sa.Column("error", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint("status IN ('queued', 'running', 'done', 'failed')", name="ck_prep_status"),
        sa.CheckConstraint("per_category BETWEEN 3 AND 10", name="ck_prep_per_category"),
    )
    op.create_index("idx_prep_books_user_date", "prep_books", ["user_id", sa.text("created_at DESC")])


def downgrade() -> None:
    op.drop_table("prep_books")

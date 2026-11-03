"""Keep analyses when their resume or JD is deleted (history must survive)

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-03
"""
from collections.abc import Sequence

from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_FKS = (("resume_id", "resumes"), ("jd_id", "job_descriptions"))


def upgrade() -> None:
    for column, table in _FKS:
        op.drop_constraint(f"analyses_{column}_fkey", "analyses", type_="foreignkey")
        op.alter_column("analyses", column, nullable=True)
        op.create_foreign_key(f"analyses_{column}_fkey", "analyses", table, [column], ["id"], ondelete="SET NULL")


def downgrade() -> None:
    op.execute("DELETE FROM analyses WHERE resume_id IS NULL OR jd_id IS NULL")
    for column, table in _FKS:
        op.drop_constraint(f"analyses_{column}_fkey", "analyses", type_="foreignkey")
        op.alter_column("analyses", column, nullable=False)
        op.create_foreign_key(f"analyses_{column}_fkey", "analyses", table, [column], ["id"], ondelete="CASCADE")

"""Store uploaded resume files in Postgres (hosted disks are wiped on redeploy)

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-03
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("resumes", sa.Column("file_data", sa.LargeBinary))


def downgrade() -> None:
    op.drop_column("resumes", "file_data")

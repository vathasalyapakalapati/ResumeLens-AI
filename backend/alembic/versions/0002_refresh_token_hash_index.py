"""Unique index on refresh_tokens.token_hash (looked up on every refresh and logout)

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-03
"""
from collections.abc import Sequence

from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index("idx_refresh_tokens_hash", "refresh_tokens", ["token_hash"], unique=True)


def downgrade() -> None:
    op.drop_index("idx_refresh_tokens_hash", table_name="refresh_tokens")

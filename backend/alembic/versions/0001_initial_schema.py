"""Initial schema: users, refresh_tokens, resumes, job_descriptions, analyses, suggestions

Revision ID: 0001
Revises:
Create Date: 2026-11-03
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

EMBED_DIM = 768  # frozen here on purpose; a new size needs a new migration


def _id() -> sa.Column:
    return sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()"))


def _owner() -> sa.Column:
    return sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)


def _created() -> sa.Column:
    return sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now())


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "users",
        _id(),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column("password_hash", sa.Text, nullable=False),
        sa.Column("full_name", sa.String(120)),
        sa.Column("is_verified", sa.Boolean, nullable=False, server_default=sa.text("false")),
        _created(),
        sa.Column("last_login_at", sa.DateTime(timezone=True)),
    )

    op.create_table(
        "refresh_tokens",
        _id(),
        _owner(),
        sa.Column("token_hash", sa.Text, nullable=False),
        sa.Column("user_agent", sa.Text),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        _created(),
    )

    op.create_table(
        "resumes",
        _id(),
        _owner(),
        sa.Column("title", sa.String(150), nullable=False),
        sa.Column("file_name", sa.String(255)),
        sa.Column("blob_path", sa.Text),
        sa.Column("raw_text", sa.Text, nullable=False),
        sa.Column("parsed", JSONB),
        sa.Column("embedding", Vector(EMBED_DIM)),
        sa.Column("version", sa.Integer, nullable=False, server_default=sa.text("1")),
        sa.Column("parent_id", UUID(as_uuid=True), sa.ForeignKey("resumes.id")),
        _created(),
    )

    op.create_table(
        "job_descriptions",
        _id(),
        _owner(),
        sa.Column("title", sa.String(150)),
        sa.Column("company", sa.String(150)),
        sa.Column("source", sa.String(10), nullable=False),
        sa.Column("raw_text", sa.Text, nullable=False),
        sa.Column("parsed", JSONB),
        sa.Column("embedding", Vector(EMBED_DIM)),
        _created(),
        sa.CheckConstraint("source IN ('upload', 'paste')", name="ck_jd_source"),
    )

    op.create_table(
        "analyses",
        _id(),
        _owner(),
        sa.Column("resume_id", UUID(as_uuid=True), sa.ForeignKey("resumes.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "jd_id", UUID(as_uuid=True), sa.ForeignKey("job_descriptions.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("status", sa.String(12), nullable=False, server_default=sa.text("'queued'")),
        sa.Column("current_step", sa.String(20)),
        sa.Column("overall_score", sa.SmallInteger),
        sa.Column("sub_scores", JSONB),
        sa.Column("report", JSONB),
        sa.Column("model", sa.String(60)),
        sa.Column("prompt_version", sa.String(20)),
        sa.Column("error", sa.Text),
        _created(),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint("status IN ('queued', 'running', 'done', 'failed')", name="ck_analysis_status"),
        sa.CheckConstraint("overall_score BETWEEN 0 AND 100", name="ck_analysis_score"),
    )

    op.create_table(
        "suggestions",
        _id(),
        sa.Column(
            "analysis_id", UUID(as_uuid=True), sa.ForeignKey("analyses.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("kind", sa.String(10), nullable=False),
        sa.Column("section", sa.String(50)),
        sa.Column("original_text", sa.Text),
        sa.Column("suggested_text", sa.Text, nullable=False),
        sa.Column("evidence_line", sa.String(10)),
        sa.Column("impact", sa.String(6)),
        sa.Column("status", sa.String(10), nullable=False, server_default=sa.text("'open'")),
        sa.CheckConstraint("kind IN ('reword', 'gap', 'format')", name="ck_suggestion_kind"),
        sa.CheckConstraint("impact IN ('high', 'medium', 'low')", name="ck_suggestion_impact"),
        sa.CheckConstraint("status IN ('open', 'accepted', 'dismissed')", name="ck_suggestion_status"),
    )

    op.create_index("idx_analyses_user_date", "analyses", ["user_id", sa.text("created_at DESC")])
    op.create_index("idx_resumes_user_date", "resumes", ["user_id", sa.text("created_at DESC")])
    op.create_index("idx_jds_user_date", "job_descriptions", ["user_id", sa.text("created_at DESC")])


def downgrade() -> None:
    for table in ("suggestions", "analyses", "job_descriptions", "resumes", "refresh_tokens", "users"):
        op.drop_table(table)

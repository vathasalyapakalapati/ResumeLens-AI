"""ORM models for the six tables in the spec. Every row belongs to a user."""

import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    SmallInteger,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from .config import EMBED_DIM
from .db import Base


def _id() -> Mapped[uuid.UUID]:
    return mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))


def _owner() -> Mapped[uuid.UUID]:
    return mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)


def _created() -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = _id()
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)  # stored lower-case
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)  # Argon2, never plain text
    full_name: Mapped[str | None] = mapped_column(String(120))
    is_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    created_at: Mapped[datetime] = _created()
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"
    __table_args__ = (Index("idx_refresh_tokens_hash", "token_hash", unique=True),)

    id: Mapped[uuid.UUID] = _id()
    user_id: Mapped[uuid.UUID] = _owner()
    token_hash: Mapped[str] = mapped_column(Text, nullable=False)  # hash of the token, not the token
    user_agent: Mapped[str | None] = mapped_column(Text)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))  # set on logout
    created_at: Mapped[datetime] = _created()


class Resume(Base):
    __tablename__ = "resumes"
    __table_args__ = (Index("idx_resumes_user_date", "user_id", text("created_at DESC")),)

    id: Mapped[uuid.UUID] = _id()
    user_id: Mapped[uuid.UUID] = _owner()
    title: Mapped[str] = mapped_column(String(150), nullable=False)
    file_name: Mapped[str | None] = mapped_column(String(255))
    blob_path: Mapped[str | None] = mapped_column(Text)  # legacy: files saved on local disk before 0004
    # The original upload. Kept in Postgres because hosted disks are wiped on redeploy.
    # Deferred: only loaded when the file is downloaded.
    file_data: Mapped[bytes | None] = mapped_column(LargeBinary, deferred=True)
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    parsed: Mapped[dict | None] = mapped_column(JSONB)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBED_DIM))
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
    parent_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("resumes.id"))
    created_at: Mapped[datetime] = _created()


class JobDescription(Base):
    __tablename__ = "job_descriptions"
    __table_args__ = (
        CheckConstraint("source IN ('upload', 'paste')", name="ck_jd_source"),
        Index("idx_jds_user_date", "user_id", text("created_at DESC")),
    )

    id: Mapped[uuid.UUID] = _id()
    user_id: Mapped[uuid.UUID] = _owner()
    title: Mapped[str | None] = mapped_column(String(150))
    company: Mapped[str | None] = mapped_column(String(150))
    source: Mapped[str] = mapped_column(String(10), nullable=False)
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    parsed: Mapped[dict | None] = mapped_column(JSONB)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBED_DIM))
    created_at: Mapped[datetime] = _created()


class Analysis(Base):
    __tablename__ = "analyses"
    __table_args__ = (
        CheckConstraint("status IN ('queued', 'running', 'done', 'failed')", name="ck_analysis_status"),
        CheckConstraint("overall_score BETWEEN 0 AND 100", name="ck_analysis_score"),
        Index("idx_analyses_user_date", "user_id", text("created_at DESC")),
    )

    id: Mapped[uuid.UUID] = _id()
    user_id: Mapped[uuid.UUID] = _owner()
    # SET NULL, not CASCADE: deleting a resume or JD must not erase history. The report keeps a
    # snapshot of their titles and of every line it cites.
    resume_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("resumes.id", ondelete="SET NULL")
    )
    jd_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("job_descriptions.id", ondelete="SET NULL")
    )
    status: Mapped[str] = mapped_column(String(12), nullable=False, server_default=text("'queued'"))
    current_step: Mapped[str | None] = mapped_column(String(20))  # drives the progress stepper
    overall_score: Mapped[int | None] = mapped_column(SmallInteger)
    sub_scores: Mapped[dict | None] = mapped_column(JSONB)
    report: Mapped[dict | None] = mapped_column(JSONB)
    model: Mapped[str | None] = mapped_column(String(60))
    prompt_version: Mapped[str | None] = mapped_column(String(20))
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = _created()
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Suggestion(Base):
    __tablename__ = "suggestions"
    __table_args__ = (
        CheckConstraint("kind IN ('reword', 'gap', 'format')", name="ck_suggestion_kind"),
        CheckConstraint("impact IN ('high', 'medium', 'low')", name="ck_suggestion_impact"),
        CheckConstraint("status IN ('open', 'accepted', 'dismissed')", name="ck_suggestion_status"),
    )

    id: Mapped[uuid.UUID] = _id()
    analysis_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("analyses.id", ondelete="CASCADE"), nullable=False
    )
    kind: Mapped[str] = mapped_column(String(10), nullable=False)
    section: Mapped[str | None] = mapped_column(String(50))
    original_text: Mapped[str | None] = mapped_column(Text)
    suggested_text: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_line: Mapped[str | None] = mapped_column(String(10))  # e.g. 'L14'
    impact: Mapped[str | None] = mapped_column(String(6))
    status: Mapped[str] = mapped_column(String(10), nullable=False, server_default=text("'open'"))

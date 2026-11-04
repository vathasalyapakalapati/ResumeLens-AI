"""Interview prep books API: generate from an analysis, poll, list, view, download (PDF/Markdown), delete."""

import logging
import uuid
from datetime import UTC, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from . import prep_engine
from .auth import current_user
from .db import SessionLocal, get_db
from .models import Analysis, JobDescription, PrepBook, Resume, User

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["prep"])

Db = Annotated[Session, Depends(get_db)]
Me = Annotated[User, Depends(current_user)]


class PrepIn(BaseModel):
    per_category: int = Field(default=6, ge=3, le=10)


class PrepSummary(BaseModel):
    id: uuid.UUID
    analysis_id: uuid.UUID
    status: Literal["queued", "running", "done", "failed"]
    per_category: int
    question_count: int
    role: str | None
    company: str | None
    resume_title: str | None
    match_score: int | None
    created_at: datetime


class PrepDetail(PrepSummary):
    current_step: str | None
    error: str | None
    engine: str | None
    content: dict | None
    completed_at: datetime | None


def _summary(p: PrepBook, a: Analysis) -> dict:
    report = a.report or {}
    return {
        "id": p.id,
        "analysis_id": p.analysis_id,
        "status": p.status,
        "per_category": p.per_category,
        "question_count": sum(len(s["questions"]) for s in (p.content or {}).get("categories", [])),
        "role": (report.get("jd") or {}).get("title"),
        "company": (report.get("jd") or {}).get("company"),
        "resume_title": (report.get("resume") or {}).get("title"),
        "match_score": a.overall_score,
        "created_at": p.created_at,
    }


def _detail(p: PrepBook, a: Analysis) -> PrepDetail:
    return PrepDetail(
        **_summary(p, a), current_step=p.current_step, error=p.error, engine=p.engine, content=p.content, completed_at=p.completed_at
    )


def _owned(db: Session, prep_id: uuid.UUID, user: User) -> tuple[PrepBook, Analysis]:
    p = db.get(PrepBook, prep_id)
    if p is None or p.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found")
    return p, db.get(Analysis, p.analysis_id)


def _lines(parsed: dict | None) -> list[dict]:
    return list((parsed or {}).get("lines", []))


def generate(prep_id: uuid.UUID) -> None:
    """Background job: build the prep book, recording progress per category."""

    def step(key: str) -> None:
        with SessionLocal() as db:
            p = db.get(PrepBook, prep_id)
            p.status, p.current_step = "running", key
            db.commit()

    try:
        with SessionLocal() as db:
            p = db.get(PrepBook, prep_id)
            a = db.get(Analysis, p.analysis_id)
            report = a.report or {}
            resume = db.get(Resume, a.resume_id) if a.resume_id else None
            jd = db.get(JobDescription, a.jd_id) if a.jd_id else None
            # Full text when the sources still exist, else the lines the report saved.
            resume_lines = _lines(resume.parsed) if resume else [{"id": k, "text": v} for k, v in report.get("resume_lines", {}).items()]
            jd_lines = _lines(jd.parsed) if jd else [{"id": k, "text": v} for k, v in report.get("jd_lines", {}).items()]
            per_category = p.per_category
        content, engine = prep_engine.build(report, resume_lines, jd_lines, per_category, on_step=step)
        with SessionLocal() as db:
            p = db.get(PrepBook, prep_id)
            p.status, p.current_step, p.content, p.engine = "done", None, content, engine
            p.completed_at = datetime.now(UTC)
            db.commit()
    except Exception:
        log.exception("prep book %s failed", prep_id)
        with SessionLocal() as db:
            p = db.get(PrepBook, prep_id)
            if p is not None:
                p.status, p.current_step = "failed", None
                p.error = "Something went wrong while generating the prep book. Please try again."
                p.completed_at = datetime.now(UTC)
                db.commit()


@router.post("/analyses/{analysis_id}/prep", response_model=PrepDetail, status_code=status.HTTP_202_ACCEPTED)
def create_prep(analysis_id: uuid.UUID, body: PrepIn, background: BackgroundTasks, db: Db, user: Me) -> PrepDetail:
    a = db.get(Analysis, analysis_id)
    if a is None or a.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Analysis not found")
    if a.status != "done" or not a.report:
        raise HTTPException(status.HTTP_409_CONFLICT, "The analysis must finish before a prep book can be made")
    p = PrepBook(user_id=user.id, analysis_id=a.id, per_category=body.per_category)
    db.add(p)
    db.commit()
    background.add_task(generate, p.id)
    return _detail(p, a)


@router.get("/prep", response_model=list[PrepSummary])
def list_prep(db: Db, user: Me) -> list[dict]:
    rows = db.execute(
        select(PrepBook, Analysis)
        .join(Analysis, Analysis.id == PrepBook.analysis_id)
        .where(PrepBook.user_id == user.id)
        .order_by(PrepBook.created_at.desc())
    ).all()
    return [_summary(p, a) for p, a in rows]


@router.get("/prep/{prep_id}", response_model=PrepDetail)
def get_prep(prep_id: uuid.UUID, db: Db, user: Me) -> PrepDetail:
    p, a = _owned(db, prep_id, user)
    return _detail(p, a)


@router.get("/prep/{prep_id}/download")
def download_prep(
    prep_id: uuid.UUID, db: Db, user: Me, format: Annotated[Literal["pdf", "md"], Query()] = "pdf"
) -> Response:
    p, _ = _owned(db, prep_id, user)
    if p.status != "done" or not p.content:
        raise HTTPException(status.HTTP_409_CONFLICT, "The prep book isn't ready yet")
    slug = "".join(ch if ch.isalnum() else "-" for ch in (p.content.get("role") or "role").lower()).strip("-")[:40]
    name = f"interview-prep-{slug or 'role'}.{format}"
    if format == "pdf":
        body, media = prep_engine.to_pdf(p.content), "application/pdf"
    else:
        body, media = prep_engine.to_markdown(p.content).encode(), "text/markdown; charset=utf-8"
    return Response(body, media_type=media, headers={"Content-Disposition": f'attachment; filename="{name}"'})


@router.delete("/prep/{prep_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_prep(prep_id: uuid.UUID, db: Db, user: Me) -> None:
    p, _ = _owned(db, prep_id, user)
    db.delete(p)
    db.commit()

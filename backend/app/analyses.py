"""Start an analysis (resume x JD), poll it, list history, delete it."""

import uuid
from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session, aliased

from .auth import current_user
from .db import get_db
from .models import Analysis, JobDescription, Resume, User
from .scoring.pipeline import run_analysis

router = APIRouter(prefix="/api/analyses", tags=["analyses"])

Db = Annotated[Session, Depends(get_db)]
Me = Annotated[User, Depends(current_user)]


class AnalysisIn(BaseModel):
    resume_id: uuid.UUID
    jd_id: uuid.UUID


class AnalysisSummary(BaseModel):
    id: uuid.UUID
    status: Literal["queued", "running", "done", "failed"]
    overall_score: int | None
    verdict: str | None
    resume_id: uuid.UUID | None  # None once that resume was deleted
    resume_title: str | None
    jd_id: uuid.UUID | None
    jd_title: str | None
    jd_company: str | None
    created_at: datetime


class AnalysisDetail(AnalysisSummary):
    current_step: str | None
    error: str | None
    sub_scores: dict | None
    report: dict | None
    model: str | None
    completed_at: datetime | None


def _summary(a: Analysis, resume_title: str | None, jd_title: str | None, jd_company: str | None) -> dict:
    snap = a.report or {}
    return {
        "id": a.id,
        "status": a.status,
        "overall_score": a.overall_score,
        "verdict": snap.get("verdict"),
        "resume_id": a.resume_id,
        # Live titles when the source still exists, else the snapshot taken when it was scored.
        "resume_title": resume_title or (snap.get("resume") or {}).get("title"),
        "jd_id": a.jd_id,
        "jd_title": jd_title or (snap.get("jd") or {}).get("title"),
        "jd_company": jd_company or (snap.get("jd") or {}).get("company"),
        "created_at": a.created_at,
    }


def _owned(db: Session, analysis_id: uuid.UUID, user: User) -> Analysis:
    a = db.get(Analysis, analysis_id)
    if a is None or a.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found")
    return a


def _detail(db: Session, a: Analysis) -> AnalysisDetail:
    resume = db.get(Resume, a.resume_id) if a.resume_id else None
    jd = db.get(JobDescription, a.jd_id) if a.jd_id else None
    return AnalysisDetail(
        **_summary(a, resume and resume.title, jd and jd.title, jd and jd.company),
        current_step=a.current_step,
        error=a.error,
        sub_scores=a.sub_scores,
        report=a.report,
        model=a.model,
        completed_at=a.completed_at,
    )


@router.post("", response_model=AnalysisDetail, status_code=status.HTTP_202_ACCEPTED)
def start_analysis(body: AnalysisIn, background: BackgroundTasks, db: Db, user: Me) -> AnalysisDetail:
    resume = db.get(Resume, body.resume_id)
    jd = db.get(JobDescription, body.jd_id)
    if resume is None or resume.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Resume not found")
    if jd is None or jd.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Job description not found")
    a = Analysis(user_id=user.id, resume_id=resume.id, jd_id=jd.id, status="queued")
    db.add(a)
    db.commit()
    background.add_task(run_analysis, a.id)
    return _detail(db, a)


@router.get("", response_model=list[AnalysisSummary])
def list_analyses(db: Db, user: Me) -> list[dict]:
    R, J = aliased(Resume), aliased(JobDescription)
    rows = db.execute(
        select(Analysis, R.title, J.title, J.company)
        .outerjoin(R, R.id == Analysis.resume_id)
        .outerjoin(J, J.id == Analysis.jd_id)
        .where(Analysis.user_id == user.id)
        .order_by(Analysis.created_at.desc())
    ).all()
    return [_summary(a, rt, jt, jc) for a, rt, jt, jc in rows]


@router.get("/{analysis_id}", response_model=AnalysisDetail)
def get_analysis(analysis_id: uuid.UUID, db: Db, user: Me) -> AnalysisDetail:
    return _detail(db, _owned(db, analysis_id, user))


@router.delete("/{analysis_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_analysis(analysis_id: uuid.UUID, db: Db, user: Me) -> None:
    db.delete(_owned(db, analysis_id, user))
    db.commit()

"""AI mock interview API. Start one from a finished analysis, send answers, finish, download the transcript.

Video and audio recordings stay in the browser. The server only ever stores text.
"""

import uuid
from datetime import UTC, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from . import ai
from . import interview_engine as engine
from .auth import current_user
from .db import get_db
from .models import Analysis, Interview, JobDescription, Resume, User

router = APIRouter(prefix="/api", tags=["interviews"])

Db = Annotated[Session, Depends(get_db)]
Me = Annotated[User, Depends(current_user)]

MAX_AUDIO_BYTES = 20 * 1024 * 1024  # Groq's free tier accepts up to 25 MB per request


# ---------- schemas ----------


class InterviewIn(BaseModel):
    question_count: int = Field(default=12, ge=10, le=15)
    interviewer: Literal["maya", "james"] = "maya"


class AnswerIn(BaseModel):
    text: str = Field(default="", max_length=20_000)
    elapsed: float | None = Field(default=None, ge=0, le=6 * 3600)  # seconds since the recording started


class FinishIn(BaseModel):
    elapsed: float | None = Field(default=None, ge=0, le=6 * 3600)


class Turn(BaseModel):
    role: Literal["interviewer", "candidate"]
    kind: Literal["question", "follow_up", "closing", "answer"]
    q: int
    text: str
    t: float


class InterviewSummary(BaseModel):
    id: uuid.UUID
    analysis_id: uuid.UUID
    status: Literal["active", "completed"]
    interviewer: str
    question_count: int
    answered: int
    overall_score: int | None
    duration_seconds: int | None
    created_at: datetime


class InterviewDetail(InterviewSummary):
    interviewer_name: str
    interviewer_title: str
    candidate_name: str
    current_question: int
    done: bool  # all questions asked; only finishing is left
    turns: list[Turn]
    questions: list[str]  # the planned questions, without the spoken lead-ins
    feedback: dict | None
    engine: str
    role: str | None
    company: str | None
    resume_title: str | None


class AnswerOut(BaseModel):
    turn: Turn  # what the interviewer says next
    done: bool
    current_question: int


class Config(BaseModel):
    ai: bool
    transcription: Literal["groq", "browser"]


# ---------- helpers ----------


def _candidate(user: User) -> str:
    return (user.full_name or "").split(" ")[0] or "Candidate"


def _answered(iv: Interview) -> int:
    return len({t["q"] for t in iv.turns if t["role"] == "candidate" and t["text"].strip()})


def _summary(iv: Interview) -> dict:
    return {
        "id": iv.id,
        "analysis_id": iv.analysis_id,
        "status": iv.status,
        "interviewer": iv.interviewer,
        "question_count": iv.question_count,
        "answered": _answered(iv),
        "overall_score": (iv.feedback or {}).get("overall_score"),
        "duration_seconds": iv.duration_seconds,
        "created_at": iv.created_at,
    }


def _detail(iv: Interview, analysis: Analysis, user: User) -> InterviewDetail:
    persona = engine.PERSONAS[iv.interviewer]
    report = analysis.report or {}
    return InterviewDetail(
        **_summary(iv),
        interviewer_name=persona.name,
        interviewer_title=persona.title,
        candidate_name=_candidate(user),
        current_question=iv.current_question,
        done=iv.current_question > iv.question_count,
        turns=iv.turns,
        questions=[q["text"] for q in iv.plan],
        feedback=iv.feedback,
        engine=iv.engine,
        role=(report.get("jd") or {}).get("title"),
        company=(report.get("jd") or {}).get("company"),
        resume_title=(report.get("resume") or {}).get("title"),
    )


def _owned(db: Session, interview_id: uuid.UUID, user: User) -> tuple[Interview, Analysis]:
    iv = db.get(Interview, interview_id)
    if iv is None or iv.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found")
    return iv, db.get(Analysis, iv.analysis_id)


def _elapsed(iv: Interview, client: float | None) -> float:
    if client is not None:
        return round(client, 1)
    return round((datetime.now(UTC) - iv.created_at).total_seconds(), 1)


def _lines(parsed: dict | None) -> list[dict]:
    return list((parsed or {}).get("lines", []))


# ---------- routes ----------


@router.get("/interviews/config", response_model=Config)
def config(_: Me) -> Config:
    """What the browser should use: AI questions or scripted, and Whisper or browser speech recognition."""
    return Config(ai=ai.chat_available(), transcription="groq" if ai.transcription_available() else "browser")


@router.post("/analyses/{analysis_id}/interviews", response_model=InterviewDetail, status_code=201)
def start_interview(analysis_id: uuid.UUID, body: InterviewIn, db: Db, user: Me) -> InterviewDetail:
    analysis = db.get(Analysis, analysis_id)
    if analysis is None or analysis.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Analysis not found")
    if analysis.status != "done" or not analysis.report:
        raise HTTPException(status.HTTP_409_CONFLICT, "The analysis must finish before an interview can start")

    report = analysis.report
    resume = db.get(Resume, analysis.resume_id) if analysis.resume_id else None
    jd = db.get(JobDescription, analysis.jd_id) if analysis.jd_id else None
    # Full text when the sources still exist, else just the lines the report saved.
    resume_lines = _lines(resume.parsed) if resume else [{"id": k, "text": v} for k, v in report.get("resume_lines", {}).items()]
    jd_lines = _lines(jd.parsed) if jd else [{"id": k, "text": v} for k, v in report.get("jd_lines", {}).items()]

    plan, engine_used = engine.make_plan(report, resume_lines, jd_lines, body.question_count)
    persona = engine.PERSONAS[body.interviewer]
    first = engine.opening(persona, _candidate(user) if user.full_name else None, report, len(plan), plan[0]["text"])
    iv = Interview(
        user_id=user.id,
        analysis_id=analysis.id,
        interviewer=persona.key,
        question_count=len(plan),
        plan=plan,
        turns=[{"role": "interviewer", "kind": "question", "q": 1, "text": first, "t": 0.0}],
        engine=engine_used,
    )
    db.add(iv)
    db.commit()
    return _detail(iv, analysis, user)


@router.get("/analyses/{analysis_id}/interviews", response_model=list[InterviewSummary])
def list_interviews(analysis_id: uuid.UUID, db: Db, user: Me) -> list[dict]:
    rows = db.scalars(
        select(Interview)
        .where(Interview.analysis_id == analysis_id, Interview.user_id == user.id)
        .order_by(Interview.created_at.desc())
    ).all()
    return [_summary(iv) for iv in rows]


class InterviewListItem(InterviewSummary):
    role: str | None
    company: str | None
    resume_title: str | None
    match_score: int | None  # the analysis score the interview was based on


@router.get("/interviews", response_model=list[InterviewListItem])
def list_all_interviews(db: Db, user: Me) -> list[dict]:
    """Every interview of the user, newest first, with the job and resume it was about."""
    rows = db.execute(
        select(Interview, Analysis.report, Analysis.overall_score)
        .join(Analysis, Analysis.id == Interview.analysis_id)
        .where(Interview.user_id == user.id)
        .order_by(Interview.created_at.desc())
    ).all()
    out = []
    for iv, report, score in rows:
        report = report or {}
        out.append({
            **_summary(iv),
            "role": (report.get("jd") or {}).get("title"),
            "company": (report.get("jd") or {}).get("company"),
            "resume_title": (report.get("resume") or {}).get("title"),
            "match_score": score,
        })
    return out


@router.get("/interviews/{interview_id}", response_model=InterviewDetail)
def get_interview(interview_id: uuid.UUID, db: Db, user: Me) -> InterviewDetail:
    iv, analysis = _owned(db, interview_id, user)
    return _detail(iv, analysis, user)


@router.post("/interviews/{interview_id}/answer", response_model=AnswerOut)
def answer(interview_id: uuid.UUID, body: AnswerIn, db: Db, user: Me) -> AnswerOut:
    iv, _ = _owned(db, interview_id, user)
    q = iv.current_question
    if iv.status != "active" or q > iv.question_count:
        raise HTTPException(status.HTTP_409_CONFLICT, "This interview has no open question")

    t = _elapsed(iv, body.elapsed)
    turns = [*iv.turns, {"role": "candidate", "kind": "answer", "q": q, "text": body.text.strip(), "t": t}]
    persona = engine.PERSONAS[iv.interviewer]
    exchange = [x for x in turns if x["q"] == q]
    ack, follow_up = engine.react(persona, iv.plan[q - 1]["text"], exchange, iv.follow_ups)

    if follow_up and iv.follow_ups < engine.MAX_FOLLOW_UPS:
        nxt = {"role": "interviewer", "kind": "follow_up", "q": q, "text": f"{ack} {follow_up}", "t": t}
        iv.follow_ups += 1
    else:
        iv.follow_ups = 0
        iv.current_question = q + 1
        if q < iv.question_count:
            nxt = {"role": "interviewer", "kind": "question", "q": q + 1, "text": f"{ack} {iv.plan[q]['text']}", "t": t}
        else:
            nxt = {"role": "interviewer", "kind": "closing", "q": 0, "text": f"{ack} {engine.closing()}", "t": t}
    iv.turns = [*turns, nxt]  # reassign so SQLAlchemy sees the JSON change
    db.commit()
    return AnswerOut(turn=nxt, done=iv.current_question > iv.question_count, current_question=iv.current_question)


@router.post("/interviews/{interview_id}/transcribe")
def transcribe(
    interview_id: uuid.UUID, db: Db, user: Me, audio: Annotated[UploadFile, File()]
) -> dict:
    _owned(db, interview_id, user)
    if not ai.transcription_available():
        raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, "Server transcription needs GROQ_API_KEY")
    data = audio.file.read(MAX_AUDIO_BYTES + 1)
    if len(data) > MAX_AUDIO_BYTES:
        raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, "That answer is too long to transcribe in one go")
    if len(data) < 1000:  # a few hundred bytes is just a container header: nothing was said
        return {"text": ""}
    try:
        text = ai.transcribe(data, audio.filename or "answer.webm", audio.content_type or "audio/webm")
    except Exception:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "Transcription failed. Please try answering again.") from None
    return {"text": text}


@router.post("/interviews/{interview_id}/finish", response_model=InterviewDetail)
def finish(interview_id: uuid.UUID, body: FinishIn, db: Db, user: Me) -> InterviewDetail:
    iv, analysis = _owned(db, interview_id, user)
    if iv.status == "completed":
        return _detail(iv, analysis, user)
    iv.feedback = engine.make_feedback(analysis.report or {}, iv.turns, iv.plan)
    iv.status = "completed"
    iv.completed_at = datetime.now(UTC)
    iv.duration_seconds = int(_elapsed(iv, body.elapsed))
    db.commit()
    return _detail(iv, analysis, user)


@router.get("/interviews/{interview_id}/transcript", response_class=PlainTextResponse)
def transcript(
    interview_id: uuid.UUID, db: Db, user: Me, format: Annotated[Literal["txt", "md"], Query()] = "txt"
) -> PlainTextResponse:
    iv, analysis = _owned(db, interview_id, user)
    d = _detail(iv, analysis, user)
    meta = {
        "role": d.role or "the role",
        "company": d.company,
        "resume": d.resume_title or "resume",
        "date": iv.created_at.strftime("%Y-%m-%d %H:%M UTC"),
        "questions": iv.question_count,
        "feedback": iv.feedback,
    }
    body = engine.transcript_text(meta, iv.turns, engine.PERSONAS[iv.interviewer], d.candidate_name, format == "md")
    name = f"interview-{iv.created_at:%Y%m%d-%H%M}.{format}"
    return PlainTextResponse(
        body,
        media_type="text/markdown; charset=utf-8" if format == "md" else "text/plain; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{name}"'},
    )


@router.delete("/interviews/{interview_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_interview(interview_id: uuid.UUID, db: Db, user: Me) -> None:
    iv, _ = _owned(db, interview_id, user)
    db.delete(iv)
    db.commit()

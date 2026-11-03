"""The user's library: resumes (PDF/DOCX upload) and job descriptions (upload or paste).

Every query is filtered by the signed-in user. Someone else's id answers 404, never 403,
so ids can't be probed.
"""

import uuid
from datetime import datetime
from pathlib import PurePath
from typing import Annotated, Literal, TypeVar
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session, load_only

from . import storage
from .auth import current_user
from .config import get_settings
from .db import get_db
from .documents import DocumentError, ParsedDocument, parse_file, parse_text
from .models import JobDescription, Resume, User

router = APIRouter(prefix="/api", tags=["library"])

Db = Annotated[Session, Depends(get_db)]
Me = Annotated[User, Depends(current_user)]

MEDIA_TYPES = {
    "pdf": "application/pdf",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


# ---------- schemas ----------


class Line(BaseModel):
    id: str
    text: str


class ResumeSummary(BaseModel):
    id: uuid.UUID
    title: str
    file_name: str | None
    version: int
    line_count: int
    created_at: datetime


class ResumeDetail(ResumeSummary):
    format: str
    pages: int | None
    warnings: list[str]
    lines: list[Line]


class JdSummary(BaseModel):
    id: uuid.UUID
    title: str | None
    company: str | None
    source: Literal["upload", "paste"]
    line_count: int
    created_at: datetime


class JdDetail(JdSummary):
    lines: list[Line]


class JdPasteIn(BaseModel):
    text: str = Field(min_length=1, max_length=100_000)
    title: str | None = Field(default=None, max_length=150)
    company: str | None = Field(default=None, max_length=150)


# ---------- helpers ----------


def _read_upload(file: UploadFile) -> bytes:
    limit = get_settings().max_upload_mb * 1024 * 1024
    data = file.file.read(limit + 1)
    if len(data) > limit:
        raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, f"File is larger than {get_settings().max_upload_mb} MB")
    if not data:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "The file is empty")
    return data


def _parse_upload(data: bytes, filename: str) -> ParsedDocument:
    try:
        return parse_file(data, filename)
    except DocumentError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from None


def _clean(value: str | None, limit: int) -> str | None:
    value = " ".join((value or "").split())[:limit]
    return value or None


def _safe_name(filename: str | None) -> str:
    # Keep only the last path part, in case a browser sends a full path.
    return PurePath((filename or "upload").replace("\\", "/")).name[:255] or "upload"


T = TypeVar("T", Resume, JobDescription)


def _owned(db: Session, model: type[T], item_id: uuid.UUID, user: User) -> T:
    row = db.get(model, item_id)
    if row is None or row.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found")
    return row


def _line_count(parsed: dict | None) -> int:
    return len((parsed or {}).get("lines", []))


def _resume_summary(r: Resume, line_count: int | None = None) -> ResumeSummary:
    return ResumeSummary(
        id=r.id,
        title=r.title,
        file_name=r.file_name,
        version=r.version,
        line_count=_line_count(r.parsed) if line_count is None else line_count,
        created_at=r.created_at,
    )


def _resume_detail(r: Resume) -> ResumeDetail:
    parsed = r.parsed or {}
    return ResumeDetail(
        **_resume_summary(r).model_dump(),
        format=parsed.get("format", "unknown"),
        pages=parsed.get("pages"),
        warnings=parsed.get("warnings", []),
        lines=parsed.get("lines", []),
    )


def _jd_summary(j: JobDescription, line_count: int | None = None) -> JdSummary:
    return JdSummary(
        id=j.id,
        title=j.title,
        company=j.company,
        source=j.source,
        line_count=_line_count(j.parsed) if line_count is None else line_count,
        created_at=j.created_at,
    )


def _jd_detail(j: JobDescription) -> JdDetail:
    return JdDetail(**_jd_summary(j).model_dump(), lines=(j.parsed or {}).get("lines", []))


_LINES = func.coalesce(func.jsonb_array_length(Resume.parsed["lines"]), 0)
_JD_LINES = func.coalesce(func.jsonb_array_length(JobDescription.parsed["lines"]), 0)


# ---------- resumes ----------


@router.post("/resumes", response_model=ResumeDetail, status_code=status.HTTP_201_CREATED)
def upload_resume(
    db: Db,
    user: Me,
    file: Annotated[UploadFile, File(description="PDF or DOCX, up to 5 MB")],
    title: Annotated[str | None, Form(max_length=150)] = None,
) -> ResumeDetail:
    name = _safe_name(file.filename)
    data = _read_upload(file)
    doc = _parse_upload(data, name)
    if doc.format not in MEDIA_TYPES:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Resumes must be a PDF or DOCX file")

    resume = Resume(
        user_id=user.id,
        title=_clean(title, 150) or _clean(PurePath(name).stem.replace("_", " "), 150) or "Resume",
        file_name=name,
        file_data=data,
        raw_text=doc.text,
        parsed=doc.to_json(),
    )
    db.add(resume)
    db.commit()
    return _resume_detail(resume)


@router.get("/resumes", response_model=list[ResumeSummary])
def list_resumes(db: Db, user: Me) -> list[ResumeSummary]:
    rows = db.execute(
        select(Resume, _LINES)
        .options(load_only(Resume.id, Resume.title, Resume.file_name, Resume.version, Resume.created_at))
        .where(Resume.user_id == user.id)
        .order_by(Resume.created_at.desc())
    ).all()
    return [_resume_summary(r, n) for r, n in rows]


@router.get("/resumes/{resume_id}", response_model=ResumeDetail)
def get_resume(resume_id: uuid.UUID, db: Db, user: Me) -> ResumeDetail:
    return _resume_detail(_owned(db, Resume, resume_id, user))


@router.get("/resumes/{resume_id}/file", response_class=Response)
def download_resume(resume_id: uuid.UUID, db: Db, user: Me) -> Response:
    resume = _owned(db, Resume, resume_id, user)
    fmt = (resume.parsed or {}).get("format", "pdf")
    filename = resume.file_name or f"resume.{fmt}"
    if resume.file_data is not None:
        return Response(
            resume.file_data,
            media_type=MEDIA_TYPES.get(fmt),
            headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"},
        )
    path = storage.open_path(resume.blob_path) if resume.blob_path else None  # uploaded before 0004
    if path is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "The original file is no longer stored")
    return FileResponse(path, media_type=MEDIA_TYPES.get(fmt), filename=filename)


@router.delete("/resumes/{resume_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_resume(resume_id: uuid.UUID, db: Db, user: Me) -> None:
    resume = _owned(db, Resume, resume_id, user)
    # Later versions point at this one; keep them, just detach them.
    db.execute(update(Resume).where(Resume.parent_id == resume.id).values(parent_id=None))
    blob_path = resume.blob_path
    db.delete(resume)
    db.commit()
    storage.delete(blob_path)


# ---------- job descriptions ----------


def _save_jd(db: Session, user: User, doc: ParsedDocument, source: str, title: str | None, company: str | None):
    jd = JobDescription(
        user_id=user.id,
        # No title given: use the JD's first line, which is usually the role name.
        title=_clean(title, 150) or _clean(doc.lines[0], 150),
        company=_clean(company, 150),
        source=source,
        raw_text=doc.text,
        parsed=doc.to_json(),
    )
    db.add(jd)
    db.commit()
    return _jd_detail(jd)


@router.post("/jds", response_model=JdDetail, status_code=status.HTTP_201_CREATED)
def paste_jd(body: JdPasteIn, db: Db, user: Me) -> JdDetail:
    try:
        doc = parse_text(body.text)
    except DocumentError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from None
    return _save_jd(db, user, doc, "paste", body.title, body.company)


@router.post("/jds/upload", response_model=JdDetail, status_code=status.HTTP_201_CREATED)
def upload_jd(
    db: Db,
    user: Me,
    file: Annotated[UploadFile, File(description="PDF, DOCX or TXT, up to 5 MB")],
    title: Annotated[str | None, Form(max_length=150)] = None,
    company: Annotated[str | None, Form(max_length=150)] = None,
) -> JdDetail:
    doc = _parse_upload(_read_upload(file), _safe_name(file.filename))
    return _save_jd(db, user, doc, "upload", title, company)


@router.get("/jds", response_model=list[JdSummary])
def list_jds(db: Db, user: Me) -> list[JdSummary]:
    rows = db.execute(
        select(JobDescription, _JD_LINES)
        .options(
            load_only(
                JobDescription.id,
                JobDescription.title,
                JobDescription.company,
                JobDescription.source,
                JobDescription.created_at,
            )
        )
        .where(JobDescription.user_id == user.id)
        .order_by(JobDescription.created_at.desc())
    ).all()
    return [_jd_summary(j, n) for j, n in rows]


@router.get("/jds/{jd_id}", response_model=JdDetail)
def get_jd(jd_id: uuid.UUID, db: Db, user: Me) -> JdDetail:
    return _jd_detail(_owned(db, JobDescription, jd_id, user))


@router.delete("/jds/{jd_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_jd(jd_id: uuid.UUID, db: Db, user: Me) -> None:
    db.delete(_owned(db, JobDescription, jd_id, user))
    db.commit()

"""Runs one analysis: Parse -> Extract & match -> Score -> Save. Progress is written to
analyses.current_step so the page can show where it is.

Runs in a background thread with its own database session.
"""

import logging
import uuid
from datetime import UTC, datetime

from .. import ai
from ..db import SessionLocal
from ..models import Analysis, JobDescription, Resume
from . import heuristic, llm
from .score import compute, verdict
from .skills import find_skills, resume_skills
from .types import Line, MatchResult

log = logging.getLogger(__name__)

STEPS = ("parse", "match", "score")


def _lines(parsed: dict | None) -> list[Line]:
    return [Line(id=x["id"], text=x["text"]) for x in (parsed or {}).get("lines", [])]


def _set_step(analysis_id: uuid.UUID, step: str) -> None:
    with SessionLocal() as db:
        a = db.get(Analysis, analysis_id)
        a.status, a.current_step = "running", step
        db.commit()


def _match(jd: list[Line], resume: list[Line]) -> MatchResult:
    if ai.chat_available():
        try:
            return llm.run(jd, resume)
        except Exception as exc:  # network, quota, bad JSON: never fail the analysis for it
            log.warning("LLM matcher failed, using built-in: %s", exc)
            result = heuristic.run(jd, resume)
            result.warnings.append("The AI model was unavailable, so the built-in matcher was used.")
            return result
    return heuristic.run(jd, resume)


def _summary(score: int, result: MatchResult, missing_keywords: list[str]) -> str:
    reqs = result.requirements
    must = [r for r in reqs if r.importance == "must"]
    met_must = sum(r.status == "met" for r in must)
    parts = [f"{verdict(score)}: the resume fully meets {met_must} of {len(must)} must-have requirements."]
    gaps = [r.text for r in must if r.status == "missing"][:2]
    if gaps:
        parts.append("Biggest gaps: " + "; ".join(gaps) + ".")
    if missing_keywords:
        parts.append("Keywords to add if you have the experience: " + ", ".join(missing_keywords[:6]) + ".")
    return " ".join(parts)


def build_report(resume: Resume, jd: JobDescription) -> tuple[int, dict, dict, str]:
    resume_lines, jd_lines = _lines(resume.parsed), _lines(jd.parsed)
    result = _match(jd_lines, resume_lines)
    if not result.requirements:
        raise ValueError(
            "Couldn't find any requirements in this job description. "
            "Make sure it includes the requirements or qualifications section."
        )

    jd_skills = find_skills(jd.raw_text)
    have = resume_skills(resume.raw_text)
    matched = [s for s in jd_skills if s in have]
    missing = [s for s in jd_skills if s not in matched]
    score, sub_scores = compute(result.requirements, matched, missing)

    # Snapshot every line the report cites, so history still reads well after edits or deletion.
    by_id = {line.id: line.text for line in resume_lines}
    cited = sorted({e for r in result.requirements for e in r.evidence}, key=lambda x: int(x[1:]))
    jd_by_id = {line.id: line.text for line in jd_lines}

    report = {
        "verdict": verdict(score),
        "summary": result.summary or _summary(score, result, missing),
        "engine": result.engine,
        "warnings": result.warnings,
        "resume": {"id": str(resume.id), "title": resume.title, "file_name": resume.file_name},
        "jd": {"id": str(jd.id), "title": jd.title, "company": jd.company},
        "requirements": [r.to_json() for r in result.requirements],
        "keywords": {"matched": matched, "missing": missing},
        "resume_lines": {lid: by_id[lid] for lid in cited if lid in by_id},
        "jd_lines": {r.jd_line: jd_by_id[r.jd_line] for r in result.requirements if r.jd_line in jd_by_id},
    }
    return score, sub_scores, report, result.engine


def run_analysis(analysis_id: uuid.UUID) -> None:
    try:
        _set_step(analysis_id, "parse")
        with SessionLocal() as db:
            a = db.get(Analysis, analysis_id)
            resume = db.get(Resume, a.resume_id) if a.resume_id else None
            jd = db.get(JobDescription, a.jd_id) if a.jd_id else None
            if resume is None or jd is None:
                raise ValueError("The resume or job description was deleted before the analysis ran.")
            db.expunge_all()

        _set_step(analysis_id, "match")
        score, sub_scores, report, engine = build_report(resume, jd)

        _set_step(analysis_id, "score")
        with SessionLocal() as db:
            a = db.get(Analysis, analysis_id)
            a.status, a.current_step = "done", None
            a.overall_score, a.sub_scores, a.report = score, sub_scores, report
            a.model, a.prompt_version = engine, llm.PROMPT_VERSION if engine != "built-in" else "builtin-v1"
            a.completed_at = datetime.now(UTC)
            db.commit()
    except Exception as exc:
        log.exception("analysis %s failed", analysis_id)
        message = str(exc) if isinstance(exc, ValueError) else "Something went wrong while scoring. Please try again."
        with SessionLocal() as db:
            a = db.get(Analysis, analysis_id)
            if a is not None:
                a.status, a.current_step, a.error = "failed", None, message
                a.completed_at = datetime.now(UTC)
                db.commit()

"""Optional AI matcher (Groq or Gemini, both free tiers). Used when LLM_PROVIDER is set and a
key is present; otherwise the built-in matcher runs.

The model returns requirements with a status and the resume line ids it relied on. We never
trust it blindly: unknown line ids are dropped, and a "met"/"partial" with no valid evidence
is downgraded (the truth guard).
"""

import json

import httpx

from ..config import get_settings
from .types import Line, MatchResult, Requirement

PROMPT_VERSION = "match-v1"
TIMEOUT = 90.0

SYSTEM = """You are an expert technical recruiter and ATS analyst. Compare a resume with a job description.
Both are given as numbered lines (L1, L2, ...). Respond with JSON only, exactly this shape:
{
  "summary": "2-3 sentences: overall fit, biggest strengths, biggest gaps",
  "requirements": [
    {
      "text": "one requirement, rephrased short and specific",
      "jd_line": "the JD line id it comes from, e.g. L7",
      "importance": "must" | "nice",
      "category": "skill" | "experience" | "education" | "other",
      "status": "met" | "partial" | "missing",
      "evidence": ["resume line ids that prove it, e.g. L3"],
      "note": "one short sentence explaining the judgement"
    }
  ]
}
Rules:
- List every distinct requirement in the JD (skills, tools, years of experience, education, domain, soft skills),
  at most 30. Skip company marketing, benefits and legal text.
- "nice" only when the JD marks it preferred/bonus/plus; otherwise "must".
- "met" needs clear proof in the resume; "partial" for related or weaker proof; "missing" when absent.
- Evidence must be resume line ids that actually contain the proof. Never invent ids. Empty list if missing.
- Judge only from the resume text. Do not assume skills that are not written."""


def _numbered(lines: list[Line]) -> str:
    return "\n".join(f"{line.id}: {line.text}" for line in lines)


def _user_prompt(jd: list[Line], resume: list[Line]) -> str:
    return f"JOB DESCRIPTION\n{_numbered(jd)}\n\nRESUME\n{_numbered(resume)}"


def available() -> bool:
    s = get_settings()
    return (s.llm_provider == "groq" and bool(s.groq_api_key)) or (
        s.llm_provider == "gemini" and bool(s.google_api_key)
    )


def _call_groq(user: str) -> tuple[str, str]:
    s = get_settings()
    res = httpx.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={"Authorization": f"Bearer {s.groq_api_key}"},
        json={
            "model": s.groq_model,
            "temperature": 0,
            "response_format": {"type": "json_object"},
            "messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}],
        },
        timeout=TIMEOUT,
    )
    res.raise_for_status()
    return res.json()["choices"][0]["message"]["content"], f"groq:{s.groq_model}"


def _call_gemini(user: str) -> tuple[str, str]:
    s = get_settings()
    res = httpx.post(
        f"https://generativelanguage.googleapis.com/v1beta/models/{s.gemini_model}:generateContent",
        headers={"x-goog-api-key": s.google_api_key},
        json={
            "systemInstruction": {"parts": [{"text": SYSTEM}]},
            "contents": [{"role": "user", "parts": [{"text": user}]}],
            "generationConfig": {"temperature": 0, "responseMimeType": "application/json"},
        },
        timeout=TIMEOUT,
    )
    res.raise_for_status()
    return res.json()["candidates"][0]["content"]["parts"][0]["text"], f"gemini:{s.gemini_model}"


def _pick(value, allowed: tuple[str, ...], default: str) -> str:
    return value if value in allowed else default


def run(jd: list[Line], resume: list[Line]) -> MatchResult:
    """Raises on network/format errors; the caller falls back to the built-in matcher."""
    call = _call_groq if get_settings().llm_provider == "groq" else _call_gemini
    raw, engine = call(_user_prompt(jd, resume))
    data = json.loads(raw)

    jd_ids = {line.id for line in jd}
    resume_ids = {line.id for line in resume}
    dropped = 0
    reqs: list[Requirement] = []
    for item in (data.get("requirements") or [])[:30]:
        text = str(item.get("text") or "").strip()[:300]
        if not text:
            continue
        evidence = [e for e in (item.get("evidence") or []) if isinstance(e, str) and e in resume_ids][:3]
        dropped += len(item.get("evidence") or []) - len(evidence)
        status = _pick(item.get("status"), ("met", "partial", "missing"), "missing")
        note = str(item.get("note") or "").strip()[:300]
        if status != "missing" and not evidence:  # truth guard: no proof, no credit
            status, note = "missing", (note + " (no supporting resume line found)").strip()
        jd_line = item.get("jd_line")
        reqs.append(
            Requirement(
                id=f"R{len(reqs) + 1}",
                text=text,
                jd_line=jd_line if jd_line in jd_ids else None,
                importance=_pick(item.get("importance"), ("must", "nice"), "must"),
                category=_pick(item.get("category"), ("skill", "experience", "education", "other"), "other"),
                status=status,
                evidence=evidence,
                note=note,
            )
        )
    if not reqs:
        raise ValueError("model returned no requirements")
    warnings = [f"Ignored {dropped} evidence reference(s) the model made up."] if dropped else []
    summary = str(data.get("summary") or "").strip()[:800] or None
    return MatchResult(requirements=reqs, engine=engine, summary=summary, warnings=warnings)

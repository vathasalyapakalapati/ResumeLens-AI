"""The score formula. Always plain Python, whichever matcher produced the requirements,
so the same evidence always gives the same number.

overall = 75% requirement fit + 25% keyword coverage
  requirement fit: must-haves weigh 3, nice-to-haves 1; met = full credit, partial = half
  keyword coverage: share of the JD's known skills that appear anywhere in the resume
"""

from .types import Requirement

WEIGHT = {"must": 3, "nice": 1}
CREDIT = {"met": 1.0, "partial": 0.5, "missing": 0.0}
REQUIREMENT_SHARE = 0.75


def _fit(reqs: list[Requirement]) -> float | None:
    total = sum(WEIGHT[r.importance] for r in reqs)
    if not total:
        return None
    return sum(WEIGHT[r.importance] * CREDIT[r.status] for r in reqs) / total


def _pct(value: float | None) -> int | None:
    return None if value is None else round(value * 100)


def compute(reqs: list[Requirement], matched_keywords: list[str], missing_keywords: list[str]) -> tuple[int, dict]:
    fit = _fit(reqs)
    kw_total = len(matched_keywords) + len(missing_keywords)
    keywords = len(matched_keywords) / kw_total if kw_total else None

    if fit is not None and keywords is not None:
        overall = REQUIREMENT_SHARE * fit + (1 - REQUIREMENT_SHARE) * keywords
    else:
        overall = fit if fit is not None else keywords or 0.0

    sub_scores = {
        "must_have": _pct(_fit([r for r in reqs if r.importance == "must"])),
        "nice_to_have": _pct(_fit([r for r in reqs if r.importance == "nice"])),
        "skills": _pct(_fit([r for r in reqs if r.category == "skill"])),
        "experience": _pct(_fit([r for r in reqs if r.category == "experience"])),
        "education": _pct(_fit([r for r in reqs if r.category == "education"])),
        "keywords": _pct(keywords),
    }
    return round(overall * 100), sub_scores


def verdict(score: int) -> str:
    if score >= 80:
        return "Strong match"
    if score >= 60:
        return "Good match"
    if score >= 40:
        return "Partial match"
    return "Weak match"

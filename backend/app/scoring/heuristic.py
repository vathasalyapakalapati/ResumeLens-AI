"""The built-in matcher: no API key, fully deterministic.

1. Extract: find requirement lines in the JD by their section ("Requirements", "Nice to have",
   ...) and classify each as must/nice and skill/experience/education/other.
2. Match: check each requirement against the resume lines and record the evidence line ids.
"""

import re
from datetime import date

from .skills import find_skills, implied_by, mentions
from .types import Category, Line, MatchResult, Requirement, Status

MAX_REQUIREMENTS = 30

# ---------- JD sections ----------

_SECTION_WORDS = {
    "must": (
        "requirement", "qualification", "must have", "must-have", "what you'll need", "what you need",
        "what we're looking for", "what we are looking for", "who you are", "about you", "you have",
        "you bring", "skills", "experience", "competencies", "your profile", "minimum", "basic", "required",
    ),
    "nice": ("nice to have", "nice-to-have", "preferred", "bonus", "plus", "desired", "desirable", "good to have", "extra"),
    "duties": (
        "responsibilit", "what you'll do", "what you will do", "the role", "your role", "duties",
        "day to day", "day-to-day", "you will", "in this role", "key tasks",
    ),
    "ignore": (
        "about us", "about the company", "who we are", "benefit", "perk", "compensation", "salary", "pay range",
        "equal opportunity", "eeo", "why join", "why you'll love", "what we offer", "we offer", "how to apply",
        "location", "our values", "culture",
    ),
}
_NICE_INLINE = re.compile(r"\b(nice to have|preferred|is a plus|a plus|bonus|ideally|desirable|good to have)\b", re.I)
_BULLET = re.compile(r"^\s*([-*•▪◦●‣·o]|\d+[.)])\s+")
_YEARS = re.compile(r"(\d{1,2})\s*(?:\+|plus)?\s*(?:-\s*\d{1,2}\s*)?(?:\+\s*)?years?", re.I)
_DEGREES = [
    ("phd", re.compile(r"\b(ph\.?\s?d|doctorate|doctoral)\b", re.I)),
    ("master", re.compile(r"\b(master'?s?|m\.sc?\.?|msc|m\.?eng|mba|m\.?tech)\b|\bMS (in|of)\b", re.I)),
    (
        "bachelor",
        re.compile(
            r"\b(bachelor'?s?|b\.sc?\.?|bsc|b\.a\.|b\.?eng|b\.?tech|undergraduate degree|degree)\b|\b(BS|BA) (in|of)\b",
            re.I,
        ),
    ),
]
_DEGREE_RANK = {"bachelor": 1, "master": 2, "phd": 3}
_EQUIVALENT = re.compile(r"\bequivalent\b|\bor (relevant |related )?(practical )?experience\b", re.I)


def _heading(text: str) -> str | None:
    """The section a heading line opens, or None if it isn't a heading."""
    t = text.strip().rstrip(":").strip().lower()
    if not t or len(t.split()) > 7 or _BULLET.match(text) or t.endswith("."):
        return None
    looks_like_heading = text.strip().endswith(":") or text.isupper() or len(t.split()) <= 4
    if not looks_like_heading:
        return None
    for section in ("ignore", "nice", "duties", "must"):  # most specific first
        if any(w in t for w in _SECTION_WORDS[section]):
            return section
    return "other" if text.strip().endswith(":") or text.isupper() else None


def _category(text: str, skills: list[str]) -> Category:
    if _YEARS.search(text):
        return "experience"
    if any(p.search(text) for _, p in _DEGREES):
        return "education"
    if skills:
        return "skill"
    return "other"


def extract_requirements(jd: list[Line]) -> list[Requirement]:
    candidates: list[tuple[Line, str]] = []  # (line, section)
    section = "intro"
    saw_requirement_section = False
    for line in jd:
        head = _heading(line.text)
        if head:
            section = head
            saw_requirement_section |= head in ("must", "nice")
            continue
        candidates.append((line, section))

    reqs: list[Requirement] = []
    for line, sec in candidates:
        text = _BULLET.sub("", line.text).strip()
        if len(text) < 2 or sec == "ignore":
            continue
        skills = find_skills(text)
        signal = bool(skills) or bool(_YEARS.search(text)) or any(p.search(text) for _, p in _DEGREES)
        if sec in ("must", "nice"):
            keep = len(text.split()) >= 2 or bool(skills)
        elif sec == "duties" or not saw_requirement_section:
            # Without a requirements section, any line naming a skill/years/degree is a requirement.
            keep = signal and (bool(_BULLET.match(line.text)) or sec == "duties" or len(text.split()) <= 30)
        else:
            keep = False
        if not keep:
            continue
        nice = sec == "nice" or bool(_NICE_INLINE.search(text)) or (sec == "duties" and saw_requirement_section)
        reqs.append(
            Requirement(
                id="",
                text=text[:300],
                jd_line=line.id,
                importance="nice" if nice else "must",
                category=_category(text, skills),
            )
        )

    # Keep the must-haves first if there are too many, then number them.
    reqs = sorted(reqs, key=lambda r: r.importance != "must")[:MAX_REQUIREMENTS]
    reqs.sort(key=lambda r: int((r.jd_line or "L0")[1:]))
    for i, r in enumerate(reqs, start=1):
        r.id = f"R{i}"
    return reqs


# ---------- resume facts ----------

_RANGE = re.compile(
    r"(?:(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\.?\s+|\d{1,2}/)?((?:19|20)\d{2})"
    r"\s*(?:-|–|—|to|until)\s*"
    r"(?:(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\.?\s+|\d{1,2}/)?((?:19|20)\d{2}|present|current|now|today|date)",
    re.I,
)


def _resume_years(resume: list[Line]) -> tuple[float, list[str]]:
    """Years of experience: the larger of any stated "N years" and the merged length of date ranges."""
    stated, stated_lines = 0, []
    for line in resume:
        for m in _YEARS.finditer(line.text):
            n = int(m.group(1))
            if 0 < n <= 50 and "experience" in line.text.lower():
                if n > stated:
                    stated, stated_lines = n, [line.id]
    spans, span_lines = [], []
    this_year = date.today().year
    for line in resume:
        for m in _RANGE.finditer(line.text):
            start = int(m.group(1))
            end = this_year if not m.group(2)[0].isdigit() else int(m.group(2))
            if 1970 <= start <= end <= this_year:
                spans.append((start, end))
                span_lines.append(line.id)
    # Merge overlapping ranges so two concurrent jobs don't double-count.
    merged, cur = 0.0, None
    for start, end in sorted(spans):
        if cur and start <= cur[1]:
            cur = (cur[0], max(cur[1], end))
        else:
            if cur:
                merged += max(cur[1] - cur[0], 0.5)
            cur = (start, end)
    if cur:
        merged += max(cur[1] - cur[0], 0.5)
    if merged >= stated:
        return merged, span_lines[:3]
    return stated, stated_lines


def _resume_degree(resume: list[Line]) -> tuple[str | None, list[str]]:
    best, where = None, []
    for line in resume:
        for name, pattern in _DEGREES:
            if pattern.search(line.text) and (best is None or _DEGREE_RANK[name] > _DEGREE_RANK[best]):
                best, where = name, [line.id]
    return best, where


# ---------- text overlap for "other" requirements ----------

_STOP = set(
    """a an and are as at be by for from has have in into is it its of on or our that the their this to
    we will with you your able ability strong excellent good great proven solid working knowledge understanding
    experience experienced years year plus etc using use including include within across other must should
    would can may well high highly new work team who what how both all any such skills skill""".split()
)


def _words(text: str) -> set[str]:
    out = set()
    for w in re.findall(r"[a-z][a-z0-9+#.]*", text.lower()):
        w = w.strip(".")
        if len(w) < 3 or w in _STOP:
            continue
        for suffix in ("ing", "ed", "es", "s"):
            if w.endswith(suffix) and len(w) - len(suffix) >= 4:
                w = w[: -len(suffix)]
                break
        out.add(w)
    return out


def _best_overlap(text: str, resume: list[Line]) -> tuple[float, list[str]]:
    want = _words(text)
    if not want:
        return 0.0, []
    scored = sorted(((len(want & _words(line.text)) / len(want), line.id) for line in resume), reverse=True)
    best = scored[0][0] if scored else 0.0
    return best, [lid for s, lid in scored[:2] if s >= max(best * 0.8, 0.2)]


# ---------- matching ----------


def _status(credit: float) -> Status:
    return "met" if credit >= 0.85 else "partial" if credit >= 0.35 else "missing"


def match_requirement(req: Requirement, resume: list[Line], years: tuple[float, list[str]], degree) -> None:
    credits: list[float] = []
    evidence: list[str] = []
    notes: list[str] = []

    skills = find_skills(req.text)
    if skills:
        found = {s: [line.id for line in resume if mentions(s, line.text)] for s in skills}
        via: dict[str, str] = {}
        for s in skills:
            if not found[s]:  # e.g. "SQL" proven by a line that says "PostgreSQL"
                for line in resume:
                    child = implied_by(s, line.text)
                    if child:
                        found[s].append(line.id)
                        via[s] = child
        have = [s for s, ids in found.items() if ids]
        lacking = [s for s in skills if s not in have]
        any_of = bool(re.search(r"\bor\b|/|\beither\b|\bone of\b|\bsuch as\b|\be\.g\.|\blike\b", req.text, re.I))
        credits.append(1.0 if (any_of and have) else len(have) / len(skills))
        for s in have:
            evidence.extend(found[s][:2])
        if have:
            notes.append("Found " + ", ".join(f"{s} (via {via[s]})" if s in via else s for s in have))
        if lacking and not (any_of and have):
            notes.append("not found: " + ", ".join(lacking))

    m = _YEARS.search(req.text)
    if m:
        need = int(m.group(1))
        got, where = years
        credits.append(1.0 if got >= need else 0.5 if got >= need * 0.7 else 0.0)
        evidence.extend(where)
        notes.append(f"asks {need}+ years; resume shows about {got:g}" if got else f"asks {need}+ years; no dated experience found")

    wanted = next((name for name, p in _DEGREES if p.search(req.text)), None)
    if wanted:
        got, where = degree
        if got and _DEGREE_RANK[got] >= _DEGREE_RANK[wanted]:
            credits.append(1.0)
        elif got or _EQUIVALENT.search(req.text):
            credits.append(0.5)
        else:
            credits.append(0.0)
        evidence.extend(where)
        notes.append(f"{got} degree found" if got else "no degree found")

    if not credits:  # plain-language requirement: compare words
        ratio, where = _best_overlap(req.text, resume)
        credits.append(1.0 if ratio >= 0.6 else 0.5 if ratio >= 0.3 else 0.0)
        if ratio >= 0.3:
            evidence.extend(where)
            notes.append("similar wording found")
        else:
            notes.append("no similar wording found")

    req.status = _status(sum(credits) / len(credits))
    req.evidence = list(dict.fromkeys(evidence))[:3]  # unique, in order
    note = "; ".join(notes)
    req.note = note[:1].upper() + note[1:] if note else ""


def run(jd: list[Line], resume: list[Line]) -> MatchResult:
    reqs = extract_requirements(jd)
    years = _resume_years(resume)
    degree = _resume_degree(resume)
    for req in reqs:
        match_requirement(req, resume, years, degree)
    return MatchResult(requirements=reqs, engine="built-in")

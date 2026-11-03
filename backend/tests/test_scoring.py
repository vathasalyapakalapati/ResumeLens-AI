"""The built-in matcher and the score formula, without the database."""

from datetime import date

from app.documents import parse_text
from app.scoring import heuristic
from app.scoring.score import compute, verdict
from app.scoring.skills import find_skills
from app.scoring.types import Line, Requirement

JD = """Senior Backend Engineer
Acme Corp is a fast-growing fintech company.
What you'll do:
- Design and build REST APIs with Python and FastAPI
Requirements:
- 5+ years of professional software engineering experience
- Strong Python and SQL skills; PostgreSQL experience
- Experience with Kafka
- Bachelor's degree in Computer Science or equivalent experience
Nice to have:
- Terraform
Benefits:
- Health insurance with Python-themed snacks
"""

RESUME = """Jane Doe
Senior Software Engineer, Globex - Jan 2020 - Present
- Built REST APIs in Python (FastAPI) on Postgres
Software Engineer, Initech - 2017 - 2019
- Wrote SQL reporting pipelines
B.S. in Computer Science, 2017
"""


def lines(text: str) -> list[Line]:
    return [Line(**x) for x in parse_text(text).to_json()["lines"]]


def by_text(reqs, fragment):
    return next(r for r in reqs if fragment in r.text)


def test_extracts_requirements_by_section_and_skips_benefits():
    reqs = heuristic.extract_requirements(lines(JD))
    texts = [r.text for r in reqs]
    assert not any("insurance" in t for t in texts)  # benefits section ignored
    assert by_text(reqs, "Terraform").importance == "nice"
    assert by_text(reqs, "Kafka").importance == "must"
    assert by_text(reqs, "5+ years").category == "experience"
    assert by_text(reqs, "Bachelor").category == "education"
    assert [r.id for r in reqs] == [f"R{i}" for i in range(1, len(reqs) + 1)]


def test_matches_with_evidence_line_ids():
    resume = lines(RESUME)
    reqs = heuristic.run(lines(JD), resume).requirements
    ids = {line.id for line in resume}

    sql = by_text(reqs, "Python and SQL")
    assert sql.status == "met" and sql.evidence and set(sql.evidence) <= ids
    assert by_text(reqs, "Kafka").status == "missing" and by_text(reqs, "Kafka").evidence == []
    years = by_text(reqs, "5+ years")
    expected = (2019 - 2017) + (date.today().year - 2020)  # two jobs, the second ongoing
    assert years.status == "met" and f"about {expected}" in years.note
    assert by_text(reqs, "Bachelor").status == "met"


def test_skill_aliases_and_case_sensitive_words():
    assert find_skills("Postgres, k8s and Node.js") == ["Node.js", "PostgreSQL", "Kubernetes"]
    assert "Go" not in find_skills("ready to go the extra mile")
    assert "Go" in find_skills("services in Go and Rust")
    assert "Java" not in find_skills("JavaScript only")
    assert find_skills("C++ and C#") == ["C++", "C#"]


def test_any_of_requirement_needs_only_one():
    resume = lines("Engineer\nBuilt event pipelines on RabbitMQ for payments")
    reqs = heuristic.run(lines("Requirements:\n- Kafka or RabbitMQ experience"), resume).requirements
    assert reqs[0].status == "met"


def test_score_formula():
    def req(importance, status, category="skill"):
        return Requirement(id="R", text="x", jd_line=None, importance=importance, category=category, status=status)

    reqs = [req("must", "met"), req("must", "missing"), req("nice", "partial", "other")]
    score, subs = compute(reqs, matched_keywords=["Python"], missing_keywords=["Kafka"])
    # fit = (3*1 + 3*0 + 1*0.5) / 7 = 0.5; keywords = 0.5 -> 50
    assert score == 50
    assert subs["must_have"] == 50 and subs["nice_to_have"] == 50 and subs["keywords"] == 50
    assert subs["experience"] is None  # no experience requirements: not applicable, not zero
    assert compute([req("must", "met")], [], [])[0] == 100
    assert verdict(85) == "Strong match" and verdict(30) == "Weak match"


def test_specific_tool_proves_general_skill():
    resume = lines("Engineer\nBuilt reporting on PostgreSQL and BigQuery")
    jd = lines("Data Analyst at Acme\nRequirements:\n- Strong SQL for reporting")
    req = heuristic.run(jd, resume).requirements[0]
    assert req.status == "met" and req.evidence == ["L2"] and "via PostgreSQL" in req.note

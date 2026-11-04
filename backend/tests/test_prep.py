"""Interview prep books: built-in generator, AI path (faked), downloads, privacy."""

import pytest
from conftest import make_pdf

from app import ai, prep_engine

RESUME = [
    "Jane Doe",
    "Senior Software Engineer, Globex - Jan 2020 - Present",
    "- Built REST APIs in Python (FastAPI) on PostgreSQL",
    "- Deployed services with Docker and Kubernetes on AWS",
    "B.S. in Computer Science, 2017",
]
JD = (
    "Backend Engineer\nWe are a fast-paced startup that values ownership and collaboration.\n"
    "Requirements:\n- Python and FastAPI\n- PostgreSQL\n- Kubernetes\n- Kafka\nNice to have:\n- Terraform"
)


@pytest.fixture
def analysis_id(user_client):
    rid = user_client.post("/api/resumes", files={"file": ("cv.pdf", make_pdf(RESUME), "application/pdf")}).json()["id"]
    jid = user_client.post("/api/jds", json={"text": JD, "company": "Acme"}).json()["id"]
    aid = user_client.post("/api/analyses", json={"resume_id": rid, "jd_id": jid}).json()["id"]
    assert user_client.get(f"/api/analyses/{aid}").json()["status"] == "done"
    return aid


@pytest.fixture
def no_ai(monkeypatch):
    monkeypatch.setattr(ai, "chat_available", lambda: False)


def make(client, analysis_id, n=6):
    res = client.post(f"/api/analyses/{analysis_id}/prep", json={"per_category": n})
    assert res.status_code == 202, res.text
    p = client.get(f"/api/prep/{res.json()['id']}").json()  # background task already ran
    assert p["status"] == "done", p
    return p


def test_built_in_prep_book_has_four_categories_tailored_to_the_job(user_client, analysis_id, no_ai):
    p = make(user_client, analysis_id, n=6)
    assert p["engine"] == "built-in" and p["question_count"] == 24
    content = p["content"]
    assert [c["key"] for c in content["categories"]] == ["technical", "system_design", "culture", "behavioral"]
    by = {c["key"]: c["questions"] for c in content["categories"]}
    assert all(len(qs) == 6 for qs in by.values())
    for qs in by.values():
        assert len({q["question"] for q in qs}) == len(qs)  # no repeats
        for q in qs:
            assert q["why"] and q["approach"] and q["difficulty"] in ("easy", "medium", "hard")

    tech = " ".join(q["question"] for q in by["technical"])
    assert "FastAPI" in tech and "Kafka" in tech  # a strength and a gap
    assert any(q["evidence"] for q in by["technical"])
    assert "Kafka" in by["system_design"][0]["question"] and "PostgreSQL" in by["system_design"][0]["question"]
    culture = " ".join(q["question"] for q in by["culture"])
    assert "priorities changed" in culture and "owned end to end" in culture  # JD says fast-paced, ownership
    assert any("Built REST APIs" in q["question"] for q in by["behavioral"])
    cited = {e for qs in by.values() for q in qs for e in q["evidence"]}
    assert cited and cited <= set(content["resume_lines"])
    assert content["role"] == "Backend Engineer" and content["company"] == "Acme"


def test_downloads_pdf_and_markdown(user_client, analysis_id, no_ai):
    p = make(user_client, analysis_id, n=3)
    pdf = user_client.get(f"/api/prep/{p['id']}/download", params={"format": "pdf"})
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")
    assert pdf.headers["content-type"] == "application/pdf"
    assert 'filename="interview-prep-backend-engineer.pdf"' in pdf.headers["content-disposition"]
    md = user_client.get(f"/api/prep/{p['id']}/download", params={"format": "md"})
    assert md.text.startswith("# Interview prep: Backend Engineer at Acme")
    assert "## System design" in md.text and "**How to answer:**" in md.text


def test_pdf_survives_unicode():
    content = {
        "role": "Ingénieur “Backend” — Zürich", "company": "Ąćmé 株式会社", "resume": "CV", "verdict": "Good match",
        "overview": "Résumé → ready…", "tips": ["Use STAR • always"], "resume_lines": {"L1": "Built 💡 things"},
        "categories": [{"key": "technical", "title": "Technical", "description": "d", "questions": [
            {"question": "Why “this”?", "why": "w", "approach": ["a – b"], "difficulty": "easy", "evidence": ["L1"], "focus": "x"}]}],
    }
    assert prep_engine.to_pdf(content).startswith(b"%PDF")


def test_list_and_delete(user_client, analysis_id, no_ai):
    a = make(user_client, analysis_id, n=3)
    b = make(user_client, analysis_id, n=4)
    items = user_client.get("/api/prep").json()
    assert [x["id"] for x in items] == [b["id"], a["id"]]
    assert items[0]["role"] == "Backend Engineer" and items[0]["question_count"] == 16
    assert user_client.delete(f"/api/prep/{a['id']}").status_code == 204
    assert [x["id"] for x in user_client.get("/api/prep").json()] == [b["id"]]


def test_prep_is_private_and_validated(user_client, other_client, analysis_id, no_ai):
    p = make(user_client, analysis_id, n=3)
    assert other_client.post(f"/api/analyses/{analysis_id}/prep", json={}).status_code == 404
    assert other_client.get(f"/api/prep/{p['id']}").status_code == 404
    assert other_client.get(f"/api/prep/{p['id']}/download").status_code == 404
    assert other_client.delete(f"/api/prep/{p['id']}").status_code == 404
    assert other_client.get("/api/prep").json() == []
    for n in (2, 11):
        assert user_client.post(f"/api/analyses/{analysis_id}/prep", json={"per_category": n}).status_code == 422


def test_ai_prep_validates_evidence_and_tops_up(user_client, analysis_id, monkeypatch):
    def fake(system, user, temperature=0.0):
        if "system design" in system:
            raise RuntimeError("rate limited")  # this category must fall back to templates
        return {"questions": [
            {"question": "AI scenario one?", "why": "w", "approach": ["p1", "p2"], "evidence": ["L3", "L999"], "difficulty": "hard", "focus": "FastAPI"},
            {"question": "AI scenario two?", "why": "w", "approach": ["p"], "evidence": [], "difficulty": "weird"},
        ]}

    monkeypatch.setattr(ai, "chat_available", lambda: True)
    monkeypatch.setattr(ai, "chat_json", fake)
    monkeypatch.setattr(ai, "engine_name", lambda: "fake:model")
    p = make(user_client, analysis_id, n=4)
    by = {c["key"]: c["questions"] for c in p["content"]["categories"]}
    tech = by["technical"]
    assert tech[0]["question"] == "AI scenario one?" and tech[0]["evidence"] == ["L3"]  # made-up L999 dropped
    assert tech[1]["difficulty"] == "medium"  # invalid value normalised
    assert len(tech) == 4  # topped up from templates
    assert all("AI scenario" not in q["question"] for q in by["system_design"])
    assert p["engine"] == "built-in + fake:model"
    assert any("System design" in w for w in p["content"]["warnings"])

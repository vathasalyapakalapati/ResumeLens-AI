"""AI mock interviews: scripted (no key) and with a fake AI model, through the API."""

import pytest
from conftest import make_pdf

from app import ai
from app import interview_engine as engine

RESUME = [
    "Jane Doe",
    "Senior Software Engineer, Globex - Jan 2020 - Present",
    "- Built REST APIs in Python (FastAPI) on PostgreSQL",
    "B.S. in Computer Science, 2017",
]
JD = "Backend Engineer\nRequirements:\n- Python and FastAPI\n- PostgreSQL\n- Kafka\nNice to have:\n- Terraform"


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
    monkeypatch.setattr(ai, "transcription_available", lambda: False)


def test_config_reports_what_is_available(user_client, no_ai):
    assert user_client.get("/api/interviews/config").json() == {"ai": False, "transcription": "browser"}


def test_scripted_interview_from_start_to_transcript(user_client, analysis_id, no_ai):
    res = user_client.post(f"/api/analyses/{analysis_id}/interviews", json={"question_count": 10, "interviewer": "james"})
    assert res.status_code == 201, res.text
    iv = res.json()
    assert iv["engine"] == "scripted" and iv["question_count"] == 10
    assert iv["interviewer_name"] == "James" and iv["status"] == "active"
    first = iv["turns"][0]
    assert first["role"] == "interviewer" and first["q"] == 1 and "Backend Engineer" in first["text"]

    # Answer every question; without AI there are no follow-ups, so 10 answers end it.
    for n in range(1, 11):
        out = user_client.post(f"/api/interviews/{iv['id']}/answer", json={"text": f"Answer number {n} " * 8, "elapsed": n * 30}).json()
        assert out["done"] == (n == 10)
        assert out["turn"]["kind"] == ("closing" if n == 10 else "question")
    assert user_client.post(f"/api/interviews/{iv['id']}/answer", json={"text": "extra"}).status_code == 409

    done = user_client.post(f"/api/interviews/{iv['id']}/finish", json={"elapsed": 320}).json()
    assert done["status"] == "completed" and done["duration_seconds"] == 320 and done["answered"] == 10
    assert done["feedback"]["engine"] == "basic" and len(done["feedback"]["questions"]) == 10

    txt = user_client.get(f"/api/interviews/{iv['id']}/transcript")
    assert txt.status_code == 200 and "attachment" in txt.headers["content-disposition"]
    assert "James" in txt.text and "Answer number 3" in txt.text and "[05:00]" in txt.text
    md = user_client.get(f"/api/interviews/{iv['id']}/transcript", params={"format": "md"})
    assert md.text.startswith("# Mock interview: Backend Engineer at Acme")

    listed = user_client.get(f"/api/analyses/{analysis_id}/interviews").json()
    assert [x["id"] for x in listed] == [iv["id"]]


def test_scripted_plan_targets_gaps_and_strengths(user_client, analysis_id, no_ai):
    report = user_client.get(f"/api/analyses/{analysis_id}").json()["report"]
    for n in (10, 12, 15):
        plan = engine.scripted_plan(report, n)
        assert len(plan) == n
        assert plan[0]["focus"] == "warmup" and plan[-1]["focus"] == "closing"
        assert len({q["text"] for q in plan}) == n  # no repeats
    plan = engine.scripted_plan(report, 12)
    assert any(q["focus"] == "gap" and "Kafka" in q["text"] for q in plan)
    assert any(q["focus"] == "strength" and "FastAPI" in q["text"] for q in plan)


def test_many_interviews_per_analysis_and_delete(user_client, analysis_id, no_ai):
    a = user_client.post(f"/api/analyses/{analysis_id}/interviews", json={"question_count": 10}).json()
    b = user_client.post(f"/api/analyses/{analysis_id}/interviews", json={"question_count": 15}).json()
    assert len(user_client.get(f"/api/analyses/{analysis_id}/interviews").json()) == 2
    assert user_client.delete(f"/api/interviews/{a['id']}").status_code == 204
    assert [x["id"] for x in user_client.get(f"/api/analyses/{analysis_id}/interviews").json()] == [b["id"]]


def test_question_count_is_limited_to_10_to_15(user_client, analysis_id):
    for n in (9, 16):
        assert user_client.post(f"/api/analyses/{analysis_id}/interviews", json={"question_count": n}).status_code == 422


def test_interviews_are_private(user_client, other_client, analysis_id, no_ai):
    iv = user_client.post(f"/api/analyses/{analysis_id}/interviews", json={}).json()
    assert other_client.post(f"/api/analyses/{analysis_id}/interviews", json={}).status_code == 404
    for call in (
        lambda: other_client.get(f"/api/interviews/{iv['id']}"),
        lambda: other_client.post(f"/api/interviews/{iv['id']}/answer", json={"text": "hi"}),
        lambda: other_client.get(f"/api/interviews/{iv['id']}/transcript"),
        lambda: other_client.delete(f"/api/interviews/{iv['id']}"),
    ):
        assert call().status_code == 404


def test_ai_interview_asks_at_most_one_follow_up_and_gives_feedback(user_client, analysis_id, monkeypatch):
    calls = []

    def fake_chat(system, user, temperature=0.0):
        calls.append(system[:40])
        if "preparing a realistic mock interview" in system:
            return {"questions": [{"text": f"AI question {i}?", "focus": "technical", "requirement": "R1"} for i in range(1, 13)]}
        if "live spoken mock interview" in system:
            return {"acknowledgement": "I see.", "follow_up": "What was the measurable result?"}
        return {
            "overall_score": 72,
            "summary": "Solid answers.",
            "strengths": ["Clear examples"],
            "improvements": ["Quantify impact"],
            "questions": [{"number": 1, "rating": 4, "comment": "Good."}, {"number": 99, "rating": 5, "comment": "ignored"}],
        }

    monkeypatch.setattr(ai, "chat_available", lambda: True)
    monkeypatch.setattr(ai, "chat_json", fake_chat)
    monkeypatch.setattr(ai, "engine_name", lambda: "fake:model")

    iv = user_client.post(f"/api/analyses/{analysis_id}/interviews", json={"question_count": 12}).json()
    assert iv["engine"] == "fake:model" and "AI question 1?" in iv["turns"][0]["text"]

    first = user_client.post(f"/api/interviews/{iv['id']}/answer", json={"text": "I built it."}).json()
    assert first["turn"]["kind"] == "follow_up" and first["current_question"] == 1
    assert first["turn"]["text"] == "I see. What was the measurable result?"
    second = user_client.post(f"/api/interviews/{iv['id']}/answer", json={"text": "Cut latency 40%."}).json()
    assert second["turn"]["kind"] == "question" and second["current_question"] == 2  # follow-up cap reached
    assert "AI question 2?" in second["turn"]["text"]

    done = user_client.post(f"/api/interviews/{iv['id']}/finish", json={}).json()
    fb = done["feedback"]
    assert fb["overall_score"] == 72 and fb["engine"] == "fake:model"
    assert [q["number"] for q in fb["questions"]] == [1]  # unknown question numbers dropped


def test_ai_failure_falls_back_to_scripted(user_client, analysis_id, monkeypatch):
    def broken(*_, **__):
        raise RuntimeError("quota exceeded")

    monkeypatch.setattr(ai, "chat_available", lambda: True)
    monkeypatch.setattr(ai, "chat_json", broken)
    iv = user_client.post(f"/api/analyses/{analysis_id}/interviews", json={"question_count": 10}).json()
    assert iv["engine"] == "scripted"
    out = user_client.post(f"/api/interviews/{iv['id']}/answer", json={"text": "My answer"}).json()
    assert out["turn"]["kind"] == "question"


def test_transcribe_without_key_is_reported(user_client, analysis_id, no_ai):
    iv = user_client.post(f"/api/analyses/{analysis_id}/interviews", json={}).json()
    res = user_client.post(f"/api/interviews/{iv['id']}/transcribe", files={"audio": ("a.webm", b"x" * 5000, "audio/webm")})
    assert res.status_code == 501


def test_transcribe_uses_groq_whisper(user_client, analysis_id, no_ai, monkeypatch):
    seen = {}

    def fake_transcribe(audio, filename, content_type):
        seen.update(size=len(audio), name=filename, type=content_type)
        return "I led the migration."

    monkeypatch.setattr(ai, "transcription_available", lambda: True)
    monkeypatch.setattr(ai, "transcribe", fake_transcribe)
    iv = user_client.post(f"/api/analyses/{analysis_id}/interviews", json={}).json()
    res = user_client.post(f"/api/interviews/{iv['id']}/transcribe", files={"audio": ("a.webm", b"x" * 5000, "audio/webm")})
    assert res.json() == {"text": "I led the migration."}
    assert seen == {"size": 5000, "name": "a.webm", "type": "audio/webm"}
    tiny = user_client.post(f"/api/interviews/{iv['id']}/transcribe", files={"audio": ("a.webm", b"x" * 10, "audio/webm")})
    assert tiny.json() == {"text": ""}  # silence: don't spend an API call


def test_list_all_interviews_across_analyses(user_client, other_client, analysis_id, no_ai):
    a = user_client.post(f"/api/analyses/{analysis_id}/interviews", json={"question_count": 10}).json()
    b = user_client.post(f"/api/analyses/{analysis_id}/interviews", json={"question_count": 11}).json()
    items = user_client.get("/api/interviews").json()
    assert [x["id"] for x in items] == [b["id"], a["id"]]  # newest first
    first = items[0]
    assert first["role"] == "Backend Engineer" and first["company"] == "Acme"
    assert first["resume_title"] == "cv" and isinstance(first["match_score"], int)
    assert other_client.get("/api/interviews").json() == []

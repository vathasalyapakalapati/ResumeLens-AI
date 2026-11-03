"""Run an analysis end to end through the API and read it back from history."""

from conftest import make_pdf

RESUME = [
    "Jane Doe",
    "Senior Software Engineer, Globex - Jan 2020 - Present",
    "- Built REST APIs in Python (FastAPI) on PostgreSQL",
    "B.S. in Computer Science, 2017",
]
JD = "Backend Engineer\nRequirements:\n- Python and FastAPI\n- PostgreSQL\n- Kafka\nNice to have:\n- Terraform"


def setup(client):
    rid = client.post("/api/resumes", files={"file": ("cv.pdf", make_pdf(RESUME), "application/pdf")}).json()["id"]
    jid = client.post("/api/jds", json={"text": JD, "company": "Acme"}).json()["id"]
    return rid, jid


def test_analysis_runs_and_appears_in_history(user_client):
    rid, jid = setup(user_client)
    started = user_client.post("/api/analyses", json={"resume_id": rid, "jd_id": jid})
    assert started.status_code == 202, started.text
    aid = started.json()["id"]

    # TestClient runs background tasks before returning, so it's finished already.
    a = user_client.get(f"/api/analyses/{aid}").json()
    assert a["status"] == "done", a
    assert 0 <= a["overall_score"] <= 100
    report = a["report"]
    assert report["engine"] == "built-in" and report["verdict"]
    statuses = {r["text"]: r["status"] for r in report["requirements"]}
    assert statuses["Python and FastAPI"] == "met" and statuses["Kafka"] == "missing"
    assert "Kafka" in report["keywords"]["missing"]
    # every cited line is snapshotted with its text
    cited = {e for r in report["requirements"] for e in r["evidence"]}
    assert cited and cited <= set(report["resume_lines"])

    history = user_client.get("/api/analyses").json()
    assert len(history) == 1
    assert history[0]["resume_title"] == "cv" and history[0]["jd_title"] == "Backend Engineer"
    assert history[0]["jd_company"] == "Acme" and history[0]["overall_score"] == a["overall_score"]


def test_history_survives_deleting_the_resume_and_jd(user_client):
    rid, jid = setup(user_client)
    aid = user_client.post("/api/analyses", json={"resume_id": rid, "jd_id": jid}).json()["id"]
    user_client.delete(f"/api/resumes/{rid}")
    user_client.delete(f"/api/jds/{jid}")

    a = user_client.get(f"/api/analyses/{aid}").json()
    assert a["resume_id"] is None and a["jd_id"] is None
    assert a["resume_title"] == "cv" and a["jd_title"] == "Backend Engineer"  # from the snapshot
    assert a["report"]["requirements"]


def test_jd_without_requirements_fails_with_a_clear_message(user_client):
    rid, _ = setup(user_client)
    jid = user_client.post("/api/jds", json={"text": "We are a friendly company.\nCome and join us today!"}).json()["id"]
    a = user_client.post("/api/analyses", json={"resume_id": rid, "jd_id": jid}).json()
    a = user_client.get(f"/api/analyses/{a['id']}").json()
    assert a["status"] == "failed" and "requirements" in a["error"]


def test_cannot_analyse_or_read_someone_elses_documents(user_client, other_client):
    rid, jid = setup(user_client)
    assert other_client.post("/api/analyses", json={"resume_id": rid, "jd_id": jid}).status_code == 404
    aid = user_client.post("/api/analyses", json={"resume_id": rid, "jd_id": jid}).json()["id"]
    assert other_client.get(f"/api/analyses/{aid}").status_code == 404
    assert other_client.delete(f"/api/analyses/{aid}").status_code == 404
    assert other_client.get("/api/analyses").json() == []


def test_delete_analysis(user_client):
    rid, jid = setup(user_client)
    aid = user_client.post("/api/analyses", json={"resume_id": rid, "jd_id": jid}).json()["id"]
    assert user_client.delete(f"/api/analyses/{aid}").status_code == 204
    assert user_client.get("/api/analyses").json() == []

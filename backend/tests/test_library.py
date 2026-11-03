"""Resume and job description upload, parsing, listing, download and deletion."""

import pytest
from conftest import make_docx, make_pdf
from fastapi.testclient import TestClient

from app.config import get_settings
from app.documents import DocumentError, clean_lines, parse_text
from app.main import app

RESUME_LINES = [
    "Ada Lovelace",
    "Senior Data Engineer",
    "- Built Spark pipelines processing 2 TB per day",
    "- Cut AWS costs by 30% with Airflow scheduling",
]
PDF = "application/pdf"
DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def upload(client, data: bytes, name: str, mime: str, **form):
    return client.post("/api/resumes", files={"file": (name, data, mime)}, data=form)


def test_pdf_resume_is_parsed_into_numbered_lines_and_file_is_kept(user_client, temp_storage):
    pdf = make_pdf(RESUME_LINES)
    res = upload(user_client, pdf, "Ada_Lovelace_CV.pdf", PDF)
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["title"] == "Ada Lovelace CV"
    assert body["format"] == "pdf" and body["pages"] == 1
    assert [line["id"] for line in body["lines"]] == ["L1", "L2", "L3", "L4"]
    assert [line["text"] for line in body["lines"]] == RESUME_LINES
    assert not any(temp_storage.rglob("*"))  # stored in Postgres, not on disk

    download = user_client.get(f"/api/resumes/{body['id']}/file")
    assert download.status_code == 200 and download.content == pdf
    assert download.headers["content-type"] == PDF
    assert "Ada_Lovelace_CV.pdf" in download.headers["content-disposition"]


def test_docx_resume_keeps_table_rows_in_order(user_client):
    data = make_docx(RESUME_LINES[:2], table=[["Skills", "Python, SQL, Spark"]])
    res = upload(user_client, data, "cv.docx", DOCX, title="My CV")
    assert res.status_code == 201, res.text
    texts = [line["text"] for line in res.json()["lines"]]
    assert texts == ["Ada Lovelace", "Senior Data Engineer", "Skills | Python, SQL, Spark"]
    assert res.json()["title"] == "My CV"


def test_list_get_and_delete_resume(user_client):
    rid = upload(user_client, make_pdf(RESUME_LINES), "cv.pdf", PDF).json()["id"]
    listed = user_client.get("/api/resumes").json()
    assert [(r["id"], r["line_count"]) for r in listed] == [(rid, 4)]
    assert "lines" not in listed[0]

    assert user_client.delete(f"/api/resumes/{rid}").status_code == 204
    assert user_client.get(f"/api/resumes/{rid}").status_code == 404
    assert user_client.get("/api/resumes").json() == []


def test_users_cannot_see_each_others_documents(user_client, other_client):
    rid = upload(user_client, make_pdf(RESUME_LINES), "cv.pdf", PDF).json()["id"]
    jid = user_client.post("/api/jds", json={"text": "Data Engineer\nMust know Spark and Airflow well."}).json()["id"]
    for url in (f"/api/resumes/{rid}", f"/api/resumes/{rid}/file", f"/api/jds/{jid}"):
        assert other_client.get(url).status_code == 404
    assert other_client.delete(f"/api/resumes/{rid}").status_code == 404
    assert other_client.delete(f"/api/jds/{jid}").status_code == 404
    assert other_client.get("/api/resumes").json() == []
    assert other_client.get("/api/jds").json() == []
    assert user_client.get(f"/api/resumes/{rid}").status_code == 200


def test_library_requires_login():
    anon = TestClient(app)
    assert anon.get("/api/resumes").status_code == 401
    assert anon.get("/api/jds").status_code == 401
    assert anon.post("/api/jds", json={"text": "x" * 50}).status_code == 401


@pytest.mark.parametrize(
    ("data", "name", "message"),
    [
        (b"just some words that are not a resume file", "cv.exe", "Unsupported file type"),
        (b"\xd0\xcf\x11\xe0legacy", "cv.doc", ".doc files aren't supported"),
        (b"PK\x03\x04not really a zip", "cv.docx", "isn't a Word document"),
        (make_pdf([]), "scan.pdf", "scanned image"),
        (b"%PDF-1.4 garbage", "broken.pdf", "damaged"),
        (b"Plain text resume " * 10, "cv.txt", "must be a PDF or DOCX"),
        (b"", "empty.pdf", "empty"),
    ],
)
def test_bad_resume_files_get_clear_errors(user_client, temp_storage, data, name, message):
    res = upload(user_client, data, name, "application/octet-stream")
    assert res.status_code == 422, res.text
    assert message in res.json()["detail"]
    assert not any(temp_storage.rglob("*.*"))  # nothing saved for a rejected file


def test_resume_over_size_limit_is_rejected(user_client, monkeypatch):
    monkeypatch.setattr(get_settings(), "max_upload_mb", 1)
    res = upload(user_client, b"%PDF-" + b"0" * (1024 * 1024), "big.pdf", PDF)
    assert res.status_code == 413


def test_paste_jd_uses_first_line_as_title(user_client):
    text = "Senior Data Engineer\n\n  Requirements:\n- 5+ years   Python\n- Spark, Airflow\n"
    res = user_client.post("/api/jds", json={"text": text, "company": " Acme  Corp "})
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["title"] == "Senior Data Engineer" and body["company"] == "Acme Corp"
    assert body["source"] == "paste"
    assert [line["text"] for line in body["lines"]] == [
        "Senior Data Engineer",
        "Requirements:",
        "- 5+ years Python",
        "- Spark, Airflow",
    ]
    assert user_client.get("/api/jds").json()[0]["line_count"] == 4


def test_upload_jd_accepts_txt_and_pdf(user_client):
    txt = user_client.post(
        "/api/jds/upload",
        files={"file": ("jd.txt", b"Backend Engineer\nFastAPI and PostgreSQL experience", "text/plain")},
        data={"title": "Backend role"},
    )
    assert txt.status_code == 201, txt.text
    assert txt.json()["title"] == "Backend role" and txt.json()["source"] == "upload"
    pdf = user_client.post("/api/jds/upload", files={"file": ("jd.pdf", make_pdf(RESUME_LINES), PDF)})
    assert pdf.status_code == 201, pdf.text
    assert user_client.delete(f"/api/jds/{pdf.json()['id']}").status_code == 204
    assert len(user_client.get("/api/jds").json()) == 1


def test_clean_lines_strips_control_chars_and_blank_lines():
    assert clean_lines(["  a\x00b  c  ", "", "   ", "ﬁne"]) == ["ab c", "fine"]


def test_too_short_paste_is_rejected():
    with pytest.raises(DocumentError, match="almost no text"):
        parse_text("hi")

import io
import uuid
from collections.abc import Iterator

import pytest
from docx import Document
from fastapi.testclient import TestClient
from sqlalchemy import delete

from app.config import get_settings
from app.db import SessionLocal
from app.main import app
from app.models import User


def _signed_in_client() -> Iterator[TestClient]:
    email = f"test-{uuid.uuid4().hex[:12]}@example.com"
    client = TestClient(app)
    assert client.post("/api/auth/signup", json={"email": email, "password": "password123"}).status_code == 201
    yield client
    with SessionLocal() as db:  # cascades to the user's resumes and JDs
        db.execute(delete(User).where(User.email == email))
        db.commit()


@pytest.fixture
def user_client() -> Iterator[TestClient]:
    yield from _signed_in_client()


@pytest.fixture
def other_client() -> Iterator[TestClient]:
    yield from _signed_in_client()


@pytest.fixture(autouse=True)
def temp_storage(tmp_path, monkeypatch):
    """Uploaded files go to a throwaway folder, never backend/storage."""
    monkeypatch.setattr(get_settings(), "storage_dir", tmp_path)
    return tmp_path


def make_pdf(lines: list[str]) -> bytes:
    """A minimal one-page PDF with real, selectable text."""
    ops = ["BT", "/F1 11 Tf", "14 TL", "72 740 Td"]
    for line in lines:
        safe = line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        ops += [f"({safe}) Tj", "T*"]
    ops.append("ET")
    stream = "\n".join(ops).encode("latin-1")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R "
        b"/Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = io.BytesIO()
    out.write(b"%PDF-1.4\n")
    offsets = []
    for i, body in enumerate(objects, start=1):
        offsets.append(out.tell())
        out.write(b"%d 0 obj\n" % i + body + b"\nendobj\n")
    xref = out.tell()
    out.write(b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1))
    for off in offsets:
        out.write(b"%010d 00000 n \n" % off)
    out.write(b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objects) + 1, xref))
    return out.getvalue()


def make_docx(paragraphs: list[str], table: list[list[str]] | None = None) -> bytes:
    doc = Document()
    for p in paragraphs:
        doc.add_paragraph(p)
    if table:
        t = doc.add_table(rows=len(table), cols=len(table[0]))
        for r, row in enumerate(table):
            for c, value in enumerate(row):
                t.cell(r, c).text = value
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()

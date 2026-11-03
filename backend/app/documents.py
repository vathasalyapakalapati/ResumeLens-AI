"""Turn an uploaded file (or pasted text) into clean lines with stable ids: L1, L2, ...

Every later finding cites one of these ids, so the numbering must never change for a stored
document. It is computed once here and saved in the `parsed` JSON column.
"""

import io
import re
import unicodedata
import zipfile
from dataclasses import dataclass, field

from docx import Document as load_docx
from docx.table import Table
from docx.text.paragraph import Paragraph
from pypdf import PdfReader
from pypdf.errors import PdfReadError

MAX_PDF_PAGES = 20
MAX_CHARS = 60_000
MIN_CHARS = 40  # less than this means nothing readable (e.g. a scanned image)


class DocumentError(ValueError):
    """The file can't be used. The message is safe to show to the user."""


@dataclass
class ParsedDocument:
    format: str  # pdf | docx | txt | paste
    lines: list[str]
    pages: int | None = None
    warnings: list[str] = field(default_factory=list)

    @property
    def text(self) -> str:
        return "\n".join(self.lines)

    def to_json(self) -> dict:
        return {
            "format": self.format,
            "pages": self.pages,
            "warnings": self.warnings,
            "lines": [{"id": f"L{i}", "text": t} for i, t in enumerate(self.lines, start=1)],
        }


# ---------- detection ----------


def detect_format(data: bytes, filename: str) -> str:
    """Decide by content, not just the extension (a renamed file shouldn't fool us)."""
    name = filename.lower()
    if data.startswith(b"%PDF-"):
        return "pdf"
    if data.startswith(b"PK\x03\x04"):
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as z:
                if "word/document.xml" in z.namelist():
                    return "docx"
        except zipfile.BadZipFile:
            pass
        raise DocumentError("This file isn't a Word document. Please upload a PDF or DOCX.")
    if data.startswith(b"\xd0\xcf\x11\xe0") or name.endswith(".doc"):
        raise DocumentError("Old .doc files aren't supported. Save it as .docx or PDF and try again.")
    if name.endswith((".txt", ".md")):
        return "txt"
    raise DocumentError("Unsupported file type. Please upload a PDF or DOCX.")


# ---------- extraction ----------


def _pdf_lines(data: bytes, warnings: list[str]) -> tuple[list[str], int]:
    try:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted and not reader.decrypt(""):
            raise DocumentError("This PDF is password-protected. Remove the password and upload it again.")
        pages = reader.pages
        if len(pages) > MAX_PDF_PAGES:
            raise DocumentError(f"This PDF has {len(pages)} pages. The limit is {MAX_PDF_PAGES}.")
        lines: list[str] = []
        empty_pages = 0
        for page in pages:
            text = page.extract_text() or ""
            if not text.strip():
                empty_pages += 1
            lines.extend(text.splitlines())
    except DocumentError:
        raise
    except (PdfReadError, ValueError, KeyError, TypeError) as exc:
        raise DocumentError("This PDF looks damaged and couldn't be read.") from exc
    if empty_pages and empty_pages < len(pages):
        warnings.append(
            f"{empty_pages} of {len(pages)} pages had no selectable text. "
            "Text inside images is invisible to most ATS software."
        )
    return lines, len(pages)


def _docx_lines(data: bytes) -> list[str]:
    try:
        doc = load_docx(io.BytesIO(data))
    except Exception as exc:  # python-docx raises a variety of zip/xml errors
        raise DocumentError("This Word document looks damaged and couldn't be read.") from exc
    lines: list[str] = []
    # Walk the body in order so tables stay where they appear in the document.
    for block in doc.iter_inner_content():
        if isinstance(block, Paragraph):
            lines.extend(block.text.splitlines())
        elif isinstance(block, Table):
            for row in block.rows:
                cells: list[str] = []
                for cell in row.cells:
                    t = " ".join(cell.text.split())
                    if t and t not in cells:  # merged cells repeat their text
                        cells.append(t)
                if cells:
                    lines.append(" | ".join(cells))
    return lines


def _txt_lines(data: bytes) -> list[str]:
    for encoding in ("utf-8-sig", "cp1252"):
        try:
            return data.decode(encoding).splitlines()
        except UnicodeDecodeError:
            continue
    raise DocumentError("Couldn't read this text file. Save it as UTF-8 and try again.")


# ---------- cleanup ----------

_SPACES = re.compile(r"[ \t  -​　]+")


def clean_lines(raw: list[str]) -> list[str]:
    out = []
    for line in raw:
        line = unicodedata.normalize("NFKC", line)
        # Drop control characters (Postgres rejects \x00) but keep everything printable.
        line = "".join(ch for ch in line if ch == "\t" or unicodedata.category(ch)[0] != "C")
        line = _SPACES.sub(" ", line).strip()
        if line:
            out.append(line)
    return out


def _finish(fmt: str, raw: list[str], pages: int | None, warnings: list[str]) -> ParsedDocument:
    lines = clean_lines(raw)
    chars = sum(len(line) for line in lines)
    if chars < MIN_CHARS:
        if fmt == "pdf":
            raise DocumentError(
                "We couldn't find any text in this PDF. It may be a scanned image; "
                "export it from Word or Google Docs as a text PDF instead."
            )
        raise DocumentError("There's almost no text here. Please check the file or paste the full text.")
    if chars > MAX_CHARS:
        raise DocumentError(f"This is too long ({chars:,} characters). The limit is {MAX_CHARS:,}.")
    return ParsedDocument(format=fmt, lines=lines, pages=pages, warnings=warnings)


def parse_file(data: bytes, filename: str) -> ParsedDocument:
    fmt = detect_format(data, filename)
    warnings: list[str] = []
    pages = None
    if fmt == "pdf":
        raw, pages = _pdf_lines(data, warnings)
    elif fmt == "docx":
        raw = _docx_lines(data)
    else:
        raw = _txt_lines(data)
    return _finish(fmt, raw, pages, warnings)


def parse_text(text: str) -> ParsedDocument:
    return _finish("paste", text.splitlines(), None, [])

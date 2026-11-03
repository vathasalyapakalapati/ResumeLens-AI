"""Reads and deletes resume files saved on local disk before migration 0004.

New uploads are stored in Postgres (resumes.file_data); this only serves older rows.
"""

from pathlib import Path

from .config import get_settings


def _root() -> Path:
    return get_settings().storage_dir.resolve()


def _resolve(blob_path: str) -> Path:
    path = (_root() / blob_path).resolve()
    if not path.is_relative_to(_root()):  # never follow a path out of the storage folder
        raise ValueError("bad blob path")
    return path


def open_path(blob_path: str) -> Path | None:
    path = _resolve(blob_path)
    return path if path.is_file() else None


def delete(blob_path: str | None) -> None:
    if blob_path:
        _resolve(blob_path).unlink(missing_ok=True)

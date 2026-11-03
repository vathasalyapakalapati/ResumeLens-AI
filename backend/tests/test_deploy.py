"""Production wiring: database URL formats and serving the built React app."""

import importlib

import pytest
from fastapi.testclient import TestClient

import app.main
from app.config import Settings, get_settings


@pytest.mark.parametrize(
    "url",
    [
        "postgres://u:p@host/db?sslmode=require",
        "postgresql://u:p@host/db?sslmode=require",
        "postgresql+psycopg://u:p@host/db?sslmode=require",
    ],
)
def test_hosted_database_urls_get_the_psycopg_driver(url):
    assert Settings(database_url=url).database_url == "postgresql+psycopg://u:p@host/db?sslmode=require"


@pytest.fixture
def prod_app(tmp_path, monkeypatch):
    """The app as it starts in production, with a fake React build next to it."""
    (tmp_path / "assets").mkdir()
    (tmp_path / "index.html").write_text("<div id=root>spa</div>")
    (tmp_path / "assets" / "app.js").write_text("console.log(1)")
    (tmp_path / "favicon.svg").write_text("<svg/>")
    monkeypatch.setenv("FRONTEND_DIST", str(tmp_path))
    get_settings.cache_clear()
    yield TestClient(importlib.reload(app.main).app)
    monkeypatch.delenv("FRONTEND_DIST")
    get_settings.cache_clear()
    importlib.reload(app.main)


def test_serves_react_app_and_keeps_api_routes(prod_app):
    assert prod_app.get("/").text == "<div id=root>spa</div>"
    assert prod_app.get("/history").text == "<div id=root>spa</div>"  # client-side route on refresh
    assert prod_app.get("/reports/123").text == "<div id=root>spa</div>"
    assert prod_app.get("/assets/app.js").text == "console.log(1)"
    assert prod_app.get("/favicon.svg").text == "<svg/>"
    assert prod_app.get("/api/health").json()["status"] == "ok"
    assert prod_app.get("/api/nope").status_code == 404  # unknown API paths are not swallowed by the SPA
    assert prod_app.get("/../backend/.env").text == "<div id=root>spa</div>"  # no path escape

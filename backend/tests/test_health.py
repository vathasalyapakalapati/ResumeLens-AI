"""Needs the Postgres from docker-compose.yml running, with migrations applied."""

from fastapi.testclient import TestClient
from sqlalchemy import inspect

from app.db import engine
from app.main import app

client = TestClient(app)


def test_health_reports_database_and_pgvector():
    res = client.get("/api/health")
    assert res.status_code == 200
    body = res.json()
    assert body["database"] == "ok"
    assert body["pgvector"]


def test_migration_created_all_six_tables():
    tables = set(inspect(engine).get_table_names())
    assert {"users", "refresh_tokens", "resumes", "job_descriptions", "analyses", "suggestions"} <= tables

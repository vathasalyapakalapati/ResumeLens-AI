"""FastAPI entry point. The React app calls everything under /api."""

from fastapi import Depends, FastAPI
from sqlalchemy import text
from sqlalchemy.orm import Session

from .db import get_db

app = FastAPI(title="ResumeLens AI", version="0.1.0", docs_url="/api/docs", openapi_url="/api/openapi.json")


@app.get("/api/health")
def health(db: Session = Depends(get_db)) -> dict:
    """Liveness plus a database round trip, so a broken DB shows up here."""
    db.execute(text("SELECT 1"))
    vector = db.execute(text("SELECT extversion FROM pg_extension WHERE extname = 'vector'")).scalar()
    return {"status": "ok", "database": "ok", "pgvector": vector}

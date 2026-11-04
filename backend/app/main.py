"""FastAPI entry point. The React app calls everything under /api."""

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from sqlalchemy.orm import Session

from .analyses import router as analyses_router
from .auth import router as auth_router
from .config import get_settings
from .db import get_db
from .interviews import router as interviews_router
from .library import router as library_router
from .prep import router as prep_router

app = FastAPI(title="ResumeLens AI", version="0.1.0", docs_url="/api/docs", openapi_url="/api/openapi.json")
app.include_router(auth_router)
app.include_router(library_router)
app.include_router(analyses_router)
app.include_router(interviews_router)
app.include_router(prep_router)


@app.get("/api/health")
def health(db: Session = Depends(get_db)) -> dict:
    """Liveness plus a database round trip, so a broken DB shows up here."""
    db.execute(text("SELECT 1"))
    vector = db.execute(text("SELECT extversion FROM pg_extension WHERE extname = 'vector'")).scalar()
    return {"status": "ok", "database": "ok", "pgvector": vector}


# ---------- the React app (production build only) ----------
# Registered last, so every /api route above wins. Unknown paths get index.html and React Router
# takes over (e.g. a refresh on /history).
DIST = get_settings().frontend_dist.resolve()
if (DIST / "index.html").is_file():
    app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str) -> FileResponse:
        if path.startswith("api/"):
            raise HTTPException(404, "Not found")
        file = (DIST / path).resolve()
        if path and file.is_file() and file.is_relative_to(DIST):
            return FileResponse(file)
        return FileResponse(DIST / "index.html")

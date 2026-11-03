"""App settings, read from environment variables or backend/.env."""

from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[1]

# Embedding size stored in the vector columns. Gemini embeddings are requested at this size,
# and the local fallback produces it too. Changing it needs a new migration.
EMBED_DIM = 768


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://resumelens:resumelens@localhost:5433/resumelens"
    jwt_secret: str = "change-me"
    access_token_minutes: int = 15
    refresh_token_days: int = 7
    # Send auth cookies over HTTPS only. Keep False for http://localhost; set True when hosted.
    cookie_secure: bool = False

    # Only for resumes uploaded before files moved into Postgres (migration 0004).
    storage_dir: Path = BACKEND_DIR / "storage"
    # The built React app. When present (production), FastAPI serves it, so one service runs everything.
    frontend_dist: Path = BACKEND_DIR.parent / "frontend" / "dist"
    max_upload_mb: int = 5

    # Which matcher scores resumes. mock = the built-in matcher (no key needed).
    # groq | gemini = an AI model, used when its key below is set; falls back to built-in on errors.
    llm_provider: str = "mock"
    groq_api_key: str = ""
    groq_model: str = "openai/gpt-oss-120b"
    google_api_key: str = ""
    gemini_model: str = "gemini-flash-latest"

    # local | gemini
    embedding_provider: str = "local"

    @field_validator("database_url")
    @classmethod
    def use_psycopg_driver(cls, url: str) -> str:
        # Hosts (Neon, Render) hand out postgres:// or postgresql:// URLs; SQLAlchemy needs the driver named.
        for prefix in ("postgres://", "postgresql://"):
            if url.startswith(prefix):
                return "postgresql+psycopg://" + url[len(prefix):]
        return url


@lru_cache
def get_settings() -> Settings:
    return Settings()

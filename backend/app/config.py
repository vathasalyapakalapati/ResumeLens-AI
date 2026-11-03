"""App settings, read from environment variables or backend/.env."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

# Embedding size stored in the vector columns. Gemini embeddings are requested at this size,
# and the local fallback produces it too. Changing it needs a new migration.
EMBED_DIM = 768


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://resumelens:resumelens@localhost:5433/resumelens"
    jwt_secret: str = "change-me"

    # mock | groq | gemini
    llm_provider: str = "mock"
    groq_api_key: str = ""
    groq_model: str = "openai/gpt-oss-120b"
    google_api_key: str = ""
    gemini_model: str = "gemini-flash-latest"

    # local | gemini
    embedding_provider: str = "local"


@lru_cache
def get_settings() -> Settings:
    return Settings()

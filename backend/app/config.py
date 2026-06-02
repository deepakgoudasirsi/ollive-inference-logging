from __future__ import annotations

from pydantic import BaseModel
import os


class Settings(BaseModel):
    db_url: str = os.getenv("OLLIVE_DB_URL", "sqlite:///./ollive.sqlite3")
    ingest_api_key: str = os.getenv("OLLIVE_INGEST_API_KEY", "dev-ingest-key")

    llm_provider: str = os.getenv("OLLIVE_LLM_PROVIDER", "mock")
    llm_model: str = os.getenv("OLLIVE_LLM_MODEL", "mock-mini")

    ingestion_url: str = os.getenv("OLLIVE_INGESTION_URL", "http://localhost:8000/api/ingest/inference")

    openai_api_key: str | None = os.getenv("OPENAI_API_KEY") or None
    anthropic_api_key: str | None = os.getenv("ANTHROPIC_API_KEY") or None
    gemini_api_key: str | None = os.getenv("GEMINI_API_KEY") or None


settings = Settings()


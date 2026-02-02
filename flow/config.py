"""Environment and settings (Pydantic Settings)."""

from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Flow application settings loaded from environment and .env."""

    model_config = SettingsConfigDict(
        env_prefix="FLOW_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Paths (local-first data)
    db_path: Path = Path("data/flow.db")
    chroma_path: Path = Path("data/knowledge_base")

    # LLM (optional for offline/core-only use)
    gemini_api_key: Optional[str] = None

    # Feature flags
    enable_ai: bool = True
    enable_sync: bool = True


def get_settings() -> Settings:
    """Return application settings (singleton-like)."""
    return Settings()

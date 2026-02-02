"""Environment and settings (Pydantic Settings)."""

from pathlib import Path
from typing import Literal, Optional

from pydantic_settings import BaseSettings, SettingsConfigDict

# Default data directory: ~/.flow/data/
_data_dir = Path.home() / ".flow" / "data"


class Settings(BaseSettings):
    """Flow application settings loaded from environment and .env.

    LLM settings are also loaded from ~/.flow/config.toml by the LLM module.
    Environment variables here provide fallback/override capability.
    """

    model_config = SettingsConfigDict(
        env_prefix="FLOW_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Paths (local-first data stored in ~/.flow/data/)
    db_path: Path = _data_dir / "flow.db"
    chroma_path: Path = _data_dir / "knowledge_base"

    # LLM Provider Settings
    # Primary config is in ~/.flow/config.toml, env vars provide override
    llm_provider: Literal["gemini", "openai", "ollama"] = "gemini"

    # Gemini settings (backward compatible with old gemini_api_key)
    gemini_api_key: Optional[str] = None
    gemini_model: str = "gemini-2.0-flash"

    # OpenAI settings
    openai_api_key: Optional[str] = None
    openai_model: str = "gpt-4o-mini"
    openai_base_url: Optional[str] = None

    # Ollama settings
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.2"

    # Feature flags
    enable_ai: bool = True
    enable_sync: bool = True

    # Logging
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    log_file: Path = _data_dir / "flow.log"


def get_settings() -> Settings:
    """Return application settings (singleton-like)."""
    return Settings()

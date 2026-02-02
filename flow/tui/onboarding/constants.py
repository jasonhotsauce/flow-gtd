"""Shared constants for onboarding wizard."""

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class ProviderMeta:
    """Metadata for an LLM provider."""

    id: str
    display_name: str
    api_key_url: Optional[str]


# Provider definitions used across onboarding screens
PROVIDERS: list[ProviderMeta] = [
    ProviderMeta("gemini", "Gemini (Google)", "https://aistudio.google.com/apikey"),
    ProviderMeta("openai", "OpenAI", "https://platform.openai.com/api-keys"),
    ProviderMeta("ollama", "Ollama (Local)", None),
]

# Quick lookup by provider ID
PROVIDER_MAP: dict[str, ProviderMeta] = {p.id: p for p in PROVIDERS}

# Provider hints for the selection screen
PROVIDER_HINTS: dict[str, str] = {
    "gemini": "Gemini: Free tier available, great for getting started",
    "openai": "OpenAI: Powerful models, requires paid API key",
    "ollama": "Ollama: Run models locally, no API key needed",
}

# Validation prompt for testing provider connectivity
VALIDATION_PROMPT = "Say 'ok' if you can read this."

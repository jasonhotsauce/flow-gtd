"""Multi-provider LLM module for Flow GTD.

Supports multiple LLM providers (Gemini, OpenAI, Ollama) via a unified
Strategy Pattern interface. Configuration is read from ~/.flow/config.toml.

Synchronous API:
    - complete(prompt, model, sanitize) -> Optional[str]
    - complete_stream(prompt, model, sanitize) -> Iterator[str]
    - complete_json(prompt, model, sanitize) -> Optional[dict]

Async API (for TUI - non-blocking):
    - complete_async(prompt, model, sanitize) -> Optional[str]
    - complete_json_async(prompt, model, sanitize) -> Optional[dict]

Utilities:
    - get_provider() -> Optional[LLMProvider]
    - reset_manager() -> None
    - load_config() -> LLMConfig

Configuration:
    Set FLOW_LLM_PROVIDER env var or configure in ~/.flow/config.toml:
    - "gemini" (default): Uses google-genai SDK
    - "openai": Uses openai SDK
    - "ollama": Uses httpx for local Ollama server

Example config.toml:
    [llm]
    provider = "gemini"

    [llm.gemini]
    api_key = "your-api-key"
    default_model = "gemini-2.0-flash"
    timeout = 30.0

    [llm.openai]
    api_key = "your-api-key"
    default_model = "gpt-4o-mini"
    timeout = 30.0

    [llm.ollama]
    base_url = "http://localhost:11434"
    default_model = "llama3.2"
    timeout = 120.0
"""

from .config import (
    GeminiConfig,
    LLMConfig,
    OllamaConfig,
    OpenAIConfig,
    load_config,
)
from .manager import (
    LLMManager,
    complete,
    complete_async,
    complete_json,
    complete_json_async,
    complete_stream,
    get_provider,
    reset_manager,
)
from .provider import LLMProvider

__all__ = [
    # Sync functions
    "complete",
    "complete_stream",
    "complete_json",
    # Async functions (for TUI)
    "complete_async",
    "complete_json_async",
    # Utilities
    "get_provider",
    "reset_manager",
    "load_config",
    # Classes
    "LLMManager",
    "LLMProvider",
    # Config classes
    "LLMConfig",
    "GeminiConfig",
    "OpenAIConfig",
    "OllamaConfig",
]

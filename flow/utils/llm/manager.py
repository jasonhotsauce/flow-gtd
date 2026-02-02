"""LLM Manager: Factory and unified API.

Provides a unified interface for LLM operations regardless of the
configured provider (Gemini, OpenAI, Ollama).
"""

import threading
from typing import Any, Iterator, Optional

from .config import LLMConfig, load_config
from .provider import LLMProvider


class LLMManager:
    """Manages LLM provider instantiation and provides unified API.

    Uses lazy initialization - provider is only created when first needed.
    """

    def __init__(self, config: Optional[LLMConfig] = None) -> None:
        """Initialize LLM manager.

        Args:
            config: Optional LLM config. If None, loads from config file.
        """
        self._config = config
        self._provider: Optional[LLMProvider] = None

    @property
    def config(self) -> LLMConfig:
        """Get configuration, loading from file if needed."""
        if self._config is None:
            self._config = load_config()
        return self._config

    def get_provider(self) -> Optional[LLMProvider]:
        """Get the configured LLM provider.

        Returns:
            LLMProvider instance, or None if configuration is invalid.
        """
        if self._provider is not None:
            return self._provider

        provider_type = self.config.provider

        try:
            if provider_type == "gemini":
                from .gemini import GeminiProvider

                if not self.config.gemini.api_key:
                    return None
                self._provider = GeminiProvider(
                    api_key=self.config.gemini.api_key,
                    default_model=self.config.gemini.default_model,
                    timeout=self.config.gemini.timeout,
                )

            elif provider_type == "openai":
                from .openai import OpenAIProvider

                if not self.config.openai.api_key:
                    return None
                self._provider = OpenAIProvider(
                    api_key=self.config.openai.api_key,
                    default_model=self.config.openai.default_model,
                    base_url=self.config.openai.base_url or None,
                    timeout=self.config.openai.timeout,
                )

            elif provider_type == "ollama":
                from .ollama import OllamaProvider

                self._provider = OllamaProvider(
                    base_url=self.config.ollama.base_url,
                    default_model=self.config.ollama.default_model,
                    timeout=self.config.ollama.timeout,
                )
        except ImportError:
            return None

        return self._provider


# Global manager instance (lazy initialization with thread safety)
_manager: Optional[LLMManager] = None
_manager_lock = threading.Lock()


def _get_manager() -> LLMManager:
    """Get the global LLM manager instance (thread-safe).

    Uses double-checked locking pattern for thread safety while
    minimizing lock contention after initialization.

    Returns:
        The singleton LLMManager instance.
    """
    global _manager
    if _manager is None:
        with _manager_lock:
            # Double-checked locking: re-check inside lock
            if _manager is None:
                _manager = LLMManager()
    return _manager


def reset_manager() -> None:
    """Reset the global manager (useful for testing or config reload).

    Thread-safe operation that clears the cached manager instance.
    """
    global _manager
    with _manager_lock:
        _manager = None


# =============================================================================
# Synchronous API
# =============================================================================


def complete(
    prompt: str,
    model: str | None = None,
    sanitize: bool = True,
) -> Optional[str]:
    """Generate text completion.

    Args:
        prompt: The input prompt.
        model: Model to use (defaults to provider's configured default).
        sanitize: If True, truncate prompt to max safe length.

    Returns:
        Generated text, or None on error.
    """
    provider = _get_manager().get_provider()
    if provider is None:
        return None
    return provider.generate_text(prompt, model=model, sanitize=sanitize)


def complete_stream(
    prompt: str,
    model: str | None = None,
    sanitize: bool = True,
) -> Iterator[str]:
    """Stream text completion chunks.

    Args:
        prompt: The input prompt.
        model: Model to use (defaults to provider's configured default).
        sanitize: If True, truncate prompt to max safe length.

    Yields:
        Text chunks as they are generated.
    """
    provider = _get_manager().get_provider()
    if provider is None:
        return iter([])
    return provider.generate_stream(prompt, model=model, sanitize=sanitize)


def complete_json(
    prompt: str,
    model: str | None = None,
    sanitize: bool = True,
) -> Optional[dict[str, Any]]:
    """Generate JSON completion with robust parsing.

    Args:
        prompt: The input prompt (should request JSON output).
        model: Model to use (defaults to provider's configured default).
        sanitize: If True, truncate prompt to max safe length.

    Returns:
        Parsed JSON dict, or None on error.
    """
    provider = _get_manager().get_provider()
    if provider is None:
        return None
    return provider.generate_json(prompt, model=model, sanitize=sanitize)


# =============================================================================
# Async API (for TUI usage - non-blocking)
# =============================================================================


async def complete_async(
    prompt: str,
    model: str | None = None,
    sanitize: bool = True,
) -> Optional[str]:
    """Async text completion for non-blocking TUI operations.

    Args:
        prompt: The input prompt.
        model: Model to use (defaults to provider's configured default).
        sanitize: If True, truncate prompt to max safe length.

    Returns:
        Generated text, or None on error.
    """
    provider = _get_manager().get_provider()
    if provider is None:
        return None
    return await provider.generate_text_async(prompt, model=model, sanitize=sanitize)


async def complete_json_async(
    prompt: str,
    model: str | None = None,
    sanitize: bool = True,
) -> Optional[dict[str, Any]]:
    """Async JSON completion for non-blocking TUI operations.

    Args:
        prompt: The input prompt (should request JSON output).
        model: Model to use (defaults to provider's configured default).
        sanitize: If True, truncate prompt to max safe length.

    Returns:
        Parsed JSON dict, or None on error.
    """
    provider = _get_manager().get_provider()
    if provider is None:
        return None
    return await provider.generate_json_async(prompt, model=model, sanitize=sanitize)


def get_provider() -> Optional[LLMProvider]:
    """Get the currently configured LLM provider.

    Returns:
        LLMProvider instance, or None if not configured.
    """
    return _get_manager().get_provider()

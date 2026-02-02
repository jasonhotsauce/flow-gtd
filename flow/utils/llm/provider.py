"""Abstract base class for LLM providers."""

import logging
from abc import ABC, abstractmethod
from typing import Any, Iterator, Optional

from .constants import MAX_PROMPT_LENGTH

logger = logging.getLogger(__name__)


class LLMProvider(ABC):
    """Abstract base class for LLM providers.

    All LLM providers must implement this interface to ensure consistent
    behavior across different backends (Gemini, OpenAI, Ollama, etc.).
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the provider name (e.g., 'gemini', 'openai', 'ollama')."""
        ...

    @property
    @abstractmethod
    def default_model(self) -> str:
        """Return the default model for this provider."""
        ...

    @abstractmethod
    def generate_text(
        self,
        prompt: str,
        model: str | None = None,
        sanitize: bool = True,
    ) -> Optional[str]:
        """Generate text completion.

        Args:
            prompt: The input prompt.
            model: Model to use (defaults to provider's default_model).
            sanitize: If True, truncate prompt to max safe length.

        Returns:
            Generated text, or None on error.
        """
        ...

    @abstractmethod
    def generate_json(
        self,
        prompt: str,
        model: str | None = None,
        sanitize: bool = True,
    ) -> Optional[dict[str, Any]]:
        """Generate JSON completion with robust parsing.

        Args:
            prompt: The input prompt (should request JSON output).
            model: Model to use (defaults to provider's default_model).
            sanitize: If True, truncate prompt to max safe length.

        Returns:
            Parsed JSON dict, or None on error/parse failure.
        """
        ...

    @abstractmethod
    def generate_stream(
        self,
        prompt: str,
        model: str | None = None,
        sanitize: bool = True,
    ) -> Iterator[str]:
        """Stream text completion chunks.

        Args:
            prompt: The input prompt.
            model: Model to use (defaults to provider's default_model).
            sanitize: If True, truncate prompt to max safe length.

        Yields:
            Text chunks as they are generated.
        """
        ...

    # =========================================================================
    # Async methods for TUI usage (non-blocking)
    # =========================================================================

    @abstractmethod
    async def generate_text_async(
        self,
        prompt: str,
        model: str | None = None,
        sanitize: bool = True,
    ) -> Optional[str]:
        """Async version of generate_text for non-blocking TUI operations.

        Args:
            prompt: The input prompt.
            model: Model to use (defaults to provider's default_model).
            sanitize: If True, truncate prompt to max safe length.

        Returns:
            Generated text, or None on error.
        """
        ...

    @abstractmethod
    async def generate_json_async(
        self,
        prompt: str,
        model: str | None = None,
        sanitize: bool = True,
    ) -> Optional[dict[str, Any]]:
        """Async version of generate_json for non-blocking TUI operations.

        Args:
            prompt: The input prompt (should request JSON output).
            model: Model to use (defaults to provider's default_model).
            sanitize: If True, truncate prompt to max safe length.

        Returns:
            Parsed JSON dict, or None on error/parse failure.
        """
        ...

    def _sanitize_prompt(self, prompt: str, max_length: int = MAX_PROMPT_LENGTH) -> str:
        """Truncate prompt to max safe length for LLM processing.

        Args:
            prompt: The input prompt.
            max_length: Maximum character length (default: MAX_PROMPT_LENGTH).

        Returns:
            Truncated prompt if it exceeds max_length, otherwise original.
        """
        return prompt[:max_length] if len(prompt) > max_length else prompt

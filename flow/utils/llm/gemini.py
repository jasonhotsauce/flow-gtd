"""Gemini LLM provider using google-genai SDK."""

import asyncio
import logging
from typing import Any, Iterator, Optional

from .json_parser import parse_json_response
from .provider import LLMProvider

logger = logging.getLogger(__name__)


class GeminiProvider(LLMProvider):
    """LLM provider for Google Gemini models.

    Uses the google-genai SDK for API access.
    """

    def __init__(
        self,
        api_key: str,
        default_model: str = "gemini-3-flash-preview",
        timeout: float = 30.0,
    ) -> None:
        """Initialize Gemini provider.

        Args:
            api_key: Google API key for Gemini.
            default_model: Default model to use.
            timeout: Request timeout in seconds.
        """
        self._api_key = api_key
        self._default_model = default_model
        self._timeout = timeout
        self._client: Any = None

    @property
    def name(self) -> str:
        """Return provider name."""
        return "gemini"

    @property
    def default_model(self) -> str:
        """Return default model."""
        return self._default_model

    def _get_client(self) -> Any:
        """Get or create the Gemini client."""
        if self._client is None:
            try:
                from google import genai

                self._client = genai.Client(api_key=self._api_key)
            except ImportError as exc:
                raise ImportError(
                    "google-genai package is required for Gemini provider. "
                    "Install with: pip install google-genai"
                ) from exc
        return self._client

    def generate_text(
        self,
        prompt: str,
        model: str | None = None,
        sanitize: bool = True,
    ) -> Optional[str]:
        """Generate text completion using Gemini.

        Args:
            prompt: The input prompt.
            model: Model to use (defaults to gemini-2.0-flash).
            sanitize: If True, truncate prompt to 8000 chars.

        Returns:
            Generated text, or None on error.
        """
        try:
            client = self._get_client()
        except ImportError as e:
            logger.warning("Gemini SDK not available: %s", e)
            return None

        text = self._sanitize_prompt(prompt) if sanitize else prompt
        model_name = model or self._default_model

        try:
            response = client.models.generate_content(
                model=model_name,
                contents=text,
            )
            if response and response.text:
                return response.text
        except Exception as e:
            logger.debug("Gemini generation failed: %s: %s", type(e).__name__, e)
            # Re-raise client/auth errors so callers can handle them properly
            error_msg = str(e).lower()
            if any(
                code in error_msg
                for code in (
                    "400",
                    "401",
                    "403",
                    "invalid",
                    "unauthorized",
                    "forbidden",
                    "api key",
                )
            ):
                raise

        return None

    def generate_json(
        self,
        prompt: str,
        model: str | None = None,
        sanitize: bool = True,
    ) -> Optional[dict[str, Any]]:
        """Generate JSON completion using Gemini.

        Args:
            prompt: The input prompt (should request JSON output).
            model: Model to use (defaults to gemini-2.0-flash).
            sanitize: If True, truncate prompt to 8000 chars.

        Returns:
            Parsed JSON dict, or None on error.
        """
        json_prompt = (
            f"{prompt}\n\nRespond with valid JSON only, no markdown or explanation."
        )
        response = self.generate_text(json_prompt, model=model, sanitize=sanitize)

        if response:
            return parse_json_response(response)
        return None

    def generate_stream(
        self,
        prompt: str,
        model: str | None = None,
        sanitize: bool = True,
    ) -> Iterator[str]:
        """Stream text completion using Gemini.

        Args:
            prompt: The input prompt.
            model: Model to use (defaults to gemini-2.0-flash).
            sanitize: If True, truncate prompt to 8000 chars.

        Yields:
            Text chunks as they are generated.
        """
        try:
            client = self._get_client()
        except ImportError as e:
            logger.warning("Gemini SDK not available: %s", e)
            return

        text = self._sanitize_prompt(prompt) if sanitize else prompt
        model_name = model or self._default_model

        try:
            for chunk in client.models.generate_content_stream(
                model=model_name,
                contents=text,
            ):
                if chunk.text:
                    yield chunk.text
        except Exception as e:
            logger.debug("Gemini streaming failed: %s: %s", type(e).__name__, e)

    # =========================================================================
    # Async methods for TUI usage
    # =========================================================================

    async def generate_text_async(
        self,
        prompt: str,
        model: str | None = None,
        sanitize: bool = True,
    ) -> Optional[str]:
        """Async version of generate_text for non-blocking TUI operations.

        Runs the synchronous call in a thread pool to avoid blocking.

        Args:
            prompt: The input prompt.
            model: Model to use (defaults to gemini-2.0-flash).
            sanitize: If True, truncate prompt to 8000 chars.

        Returns:
            Generated text, or None on error.
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, lambda: self.generate_text(prompt, model=model, sanitize=sanitize)
        )

    async def generate_json_async(
        self,
        prompt: str,
        model: str | None = None,
        sanitize: bool = True,
    ) -> Optional[dict[str, Any]]:
        """Async version of generate_json for non-blocking TUI operations.

        Args:
            prompt: The input prompt (should request JSON output).
            model: Model to use (defaults to gemini-2.0-flash).
            sanitize: If True, truncate prompt to 8000 chars.

        Returns:
            Parsed JSON dict, or None on error.
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, lambda: self.generate_json(prompt, model=model, sanitize=sanitize)
        )

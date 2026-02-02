"""OpenAI LLM provider using the openai SDK."""

import asyncio
import logging
from typing import Any, Iterator, Optional

from .json_parser import parse_json_response
from .provider import LLMProvider

logger = logging.getLogger(__name__)


class OpenAIProvider(LLMProvider):
    """LLM provider for OpenAI models (GPT-4, GPT-3.5, etc.).

    Uses the openai SDK for API access. Also supports Azure OpenAI
    and other OpenAI-compatible endpoints via base_url.
    """

    def __init__(
        self,
        api_key: str,
        default_model: str = "gpt-4o-mini",
        base_url: str | None = None,
        timeout: float = 30.0,
    ) -> None:
        """Initialize OpenAI provider.

        Args:
            api_key: OpenAI API key.
            default_model: Default model to use.
            base_url: Optional custom base URL (for Azure, etc.).
            timeout: Request timeout in seconds.
        """
        self._api_key = api_key
        self._default_model = default_model
        self._base_url = base_url
        self._timeout = timeout
        self._client: Any = None
        self._async_client: Any = None

    @property
    def name(self) -> str:
        """Return provider name."""
        return "openai"

    @property
    def default_model(self) -> str:
        """Return default model."""
        return self._default_model

    def _get_client(self) -> Any:
        """Get or create the OpenAI client."""
        if self._client is None:
            try:
                from openai import OpenAI

                kwargs: dict[str, Any] = {
                    "api_key": self._api_key,
                    "timeout": self._timeout,
                }
                if self._base_url:
                    kwargs["base_url"] = self._base_url
                self._client = OpenAI(**kwargs)
            except ImportError as exc:
                raise ImportError(
                    "openai package is required for OpenAI provider. "
                    "Install with: pip install openai"
                ) from exc
        return self._client

    def _get_async_client(self) -> Any:
        """Get or create the async OpenAI client."""
        if self._async_client is None:
            try:
                from openai import AsyncOpenAI

                kwargs: dict[str, Any] = {
                    "api_key": self._api_key,
                    "timeout": self._timeout,
                }
                if self._base_url:
                    kwargs["base_url"] = self._base_url
                self._async_client = AsyncOpenAI(**kwargs)
            except ImportError:
                raise ImportError(
                    "openai package is required for OpenAI provider. "
                    "Install with: pip install openai"
                )
        return self._async_client

    def generate_text(
        self,
        prompt: str,
        model: str | None = None,
        sanitize: bool = True,
    ) -> Optional[str]:
        """Generate text completion using OpenAI.

        Args:
            prompt: The input prompt.
            model: Model to use (defaults to gpt-4o-mini).
            sanitize: If True, truncate prompt to 8000 chars.

        Returns:
            Generated text, or None on error.
        """
        try:
            client = self._get_client()
        except ImportError as e:
            logger.warning("OpenAI SDK not available: %s", e)
            return None

        text = self._sanitize_prompt(prompt) if sanitize else prompt
        model_name = model or self._default_model

        try:
            response = client.chat.completions.create(
                model=model_name,
                messages=[{"role": "user", "content": text}],
            )
            if response.choices and response.choices[0].message.content:
                return response.choices[0].message.content
        except Exception as e:
            logger.debug("OpenAI generation failed: %s: %s", type(e).__name__, e)

        return None

    def generate_json(
        self,
        prompt: str,
        model: str | None = None,
        sanitize: bool = True,
    ) -> Optional[dict[str, Any]]:
        """Generate JSON completion using OpenAI.

        Uses OpenAI's native JSON mode when available.

        Args:
            prompt: The input prompt (should request JSON output).
            model: Model to use (defaults to gpt-4o-mini).
            sanitize: If True, truncate prompt to 8000 chars.

        Returns:
            Parsed JSON dict, or None on error.
        """
        try:
            client = self._get_client()
        except ImportError as e:
            logger.warning("OpenAI SDK not available: %s", e)
            return None

        text = self._sanitize_prompt(prompt) if sanitize else prompt
        model_name = model or self._default_model
        json_prompt = f"{text}\n\nRespond with valid JSON only."

        try:
            # Try with JSON mode first (supported by newer models)
            response = client.chat.completions.create(
                model=model_name,
                messages=[{"role": "user", "content": json_prompt}],
                response_format={"type": "json_object"},
            )
            if response.choices and response.choices[0].message.content:
                return parse_json_response(response.choices[0].message.content)
        except Exception as e:
            logger.debug("OpenAI JSON mode failed, trying without: %s", e)
            # Fall back to regular completion without JSON mode
            try:
                response = client.chat.completions.create(
                    model=model_name,
                    messages=[{"role": "user", "content": json_prompt}],
                )
                if response.choices and response.choices[0].message.content:
                    return parse_json_response(response.choices[0].message.content)
            except Exception as e2:
                logger.debug("OpenAI fallback generation failed: %s", e2)

        return None

    def generate_stream(
        self,
        prompt: str,
        model: str | None = None,
        sanitize: bool = True,
    ) -> Iterator[str]:
        """Stream text completion using OpenAI.

        Args:
            prompt: The input prompt.
            model: Model to use (defaults to gpt-4o-mini).
            sanitize: If True, truncate prompt to 8000 chars.

        Yields:
            Text chunks as they are generated.
        """
        try:
            client = self._get_client()
        except ImportError as e:
            logger.warning("OpenAI SDK not available: %s", e)
            return

        text = self._sanitize_prompt(prompt) if sanitize else prompt
        model_name = model or self._default_model

        try:
            stream = client.chat.completions.create(
                model=model_name,
                messages=[{"role": "user", "content": text}],
                stream=True,
            )
            for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
        except Exception as e:
            logger.debug("OpenAI streaming failed: %s: %s", type(e).__name__, e)

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

        Uses native async OpenAI client.

        Args:
            prompt: The input prompt.
            model: Model to use (defaults to gpt-4o-mini).
            sanitize: If True, truncate prompt to 8000 chars.

        Returns:
            Generated text, or None on error.
        """
        try:
            client = self._get_async_client()
        except ImportError as e:
            logger.warning("OpenAI SDK not available: %s", e)
            return None

        text = self._sanitize_prompt(prompt) if sanitize else prompt
        model_name = model or self._default_model

        try:
            response = await client.chat.completions.create(
                model=model_name,
                messages=[{"role": "user", "content": text}],
            )
            if response.choices and response.choices[0].message.content:
                return response.choices[0].message.content
        except Exception as e:
            logger.debug("OpenAI async generation failed: %s: %s", type(e).__name__, e)

        return None

    async def generate_json_async(
        self,
        prompt: str,
        model: str | None = None,
        sanitize: bool = True,
    ) -> Optional[dict[str, Any]]:
        """Async version of generate_json for non-blocking TUI operations.

        Args:
            prompt: The input prompt (should request JSON output).
            model: Model to use (defaults to gpt-4o-mini).
            sanitize: If True, truncate prompt to 8000 chars.

        Returns:
            Parsed JSON dict, or None on error.
        """
        try:
            client = self._get_async_client()
        except ImportError as e:
            logger.warning("OpenAI SDK not available: %s", e)
            return None

        text = self._sanitize_prompt(prompt) if sanitize else prompt
        model_name = model or self._default_model
        json_prompt = f"{text}\n\nRespond with valid JSON only."

        try:
            response = await client.chat.completions.create(
                model=model_name,
                messages=[{"role": "user", "content": json_prompt}],
                response_format={"type": "json_object"},
            )
            if response.choices and response.choices[0].message.content:
                return parse_json_response(response.choices[0].message.content)
        except Exception as e:
            logger.debug("OpenAI async JSON mode failed, trying without: %s", e)
            try:
                response = await client.chat.completions.create(
                    model=model_name,
                    messages=[{"role": "user", "content": json_prompt}],
                )
                if response.choices and response.choices[0].message.content:
                    return parse_json_response(response.choices[0].message.content)
            except Exception as e2:
                logger.debug("OpenAI async fallback generation failed: %s", e2)

        return None

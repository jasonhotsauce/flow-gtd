"""Ollama LLM provider using httpx for API calls."""

import asyncio
import json
import logging
from typing import Any, Iterator, Optional

from .constants import (
    DEFAULT_MODELS,
    HTTP_KEEPALIVE_TIMEOUT,
    HTTP_MAX_CONNECTIONS,
    OLLAMA_TIMEOUT,
)
from .json_parser import parse_json_response
from .provider import LLMProvider

logger = logging.getLogger(__name__)


class OllamaProvider(LLMProvider):
    """LLM provider for Ollama local models.

    Uses httpx for direct API calls to the Ollama server.
    No SDK dependency required.
    """

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        default_model: str = DEFAULT_MODELS["ollama"],
        timeout: float = OLLAMA_TIMEOUT,
    ) -> None:
        """Initialize Ollama provider.

        Args:
            base_url: Ollama server URL (default: http://localhost:11434).
            default_model: Default model to use (llama3.2 recommended).
            timeout: Request timeout in seconds (higher for local inference).
        """
        self._base_url = base_url.rstrip("/")
        self._default_model = default_model
        self._timeout = timeout
        # Reusable async client for connection pooling
        self._async_client: Any = None

    @property
    def name(self) -> str:
        """Return provider name."""
        return "ollama"

    @property
    def default_model(self) -> str:
        """Return default model."""
        return self._default_model

    def _get_httpx(self) -> Any:
        """Import and return httpx module.

        Returns:
            The httpx module.

        Raises:
            ImportError: If httpx is not installed.
        """
        try:
            import httpx

            return httpx
        except ImportError:
            raise ImportError(
                "httpx package is required for Ollama provider. "
                "Install with: pip install httpx"
            )

    async def _get_async_client(self) -> Any:
        """Get or create reusable async HTTP client for connection pooling.

        Returns:
            httpx.AsyncClient instance with configured timeout and limits.
        """
        if self._async_client is None:
            httpx = self._get_httpx()
            limits = httpx.Limits(
                max_connections=HTTP_MAX_CONNECTIONS,
                max_keepalive_connections=HTTP_MAX_CONNECTIONS,
                keepalive_expiry=HTTP_KEEPALIVE_TIMEOUT,
            )
            self._async_client = httpx.AsyncClient(
                timeout=self._timeout,
                limits=limits,
            )
        return self._async_client

    async def close(self) -> None:
        """Close the async HTTP client and release resources.

        Should be called when done with the provider to clean up connections.
        """
        if self._async_client is not None:
            await self._async_client.aclose()
            self._async_client = None

    def generate_text(
        self,
        prompt: str,
        model: str | None = None,
        sanitize: bool = True,
    ) -> Optional[str]:
        """Generate text completion using Ollama.

        Args:
            prompt: The input prompt.
            model: Model to use (defaults to llama3.2).
            sanitize: If True, truncate prompt to 8000 chars.

        Returns:
            Generated text, or None on error.
        """
        try:
            httpx = self._get_httpx()
        except ImportError as e:
            logger.warning("httpx not available: %s", e)
            return None

        text = self._sanitize_prompt(prompt) if sanitize else prompt
        model_name = model or self._default_model

        try:
            response = httpx.post(
                f"{self._base_url}/api/generate",
                json={
                    "model": model_name,
                    "prompt": text,
                    "stream": False,
                },
                timeout=self._timeout,
            )
            response.raise_for_status()
            data = response.json()
            if "response" in data:
                return data["response"]
        except Exception as e:
            logger.debug("Ollama generation failed: %s: %s", type(e).__name__, e)

        return None

    def generate_json(
        self,
        prompt: str,
        model: str | None = None,
        sanitize: bool = True,
    ) -> Optional[dict[str, Any]]:
        """Generate JSON completion using Ollama.

        Ollama supports native JSON mode via the format parameter.

        Args:
            prompt: The input prompt (should request JSON output).
            model: Model to use (defaults to llama3.2).
            sanitize: If True, truncate prompt to 8000 chars.

        Returns:
            Parsed JSON dict, or None on error.
        """
        try:
            httpx = self._get_httpx()
        except ImportError as e:
            logger.warning("httpx not available: %s", e)
            return None

        text = self._sanitize_prompt(prompt) if sanitize else prompt
        model_name = model or self._default_model
        json_prompt = f"{text}\n\nRespond with valid JSON only."

        try:
            # Try with JSON format mode
            response = httpx.post(
                f"{self._base_url}/api/generate",
                json={
                    "model": model_name,
                    "prompt": json_prompt,
                    "stream": False,
                    "format": "json",
                },
                timeout=self._timeout,
            )
            response.raise_for_status()
            data = response.json()
            if "response" in data:
                return parse_json_response(data["response"])
        except Exception as e:
            logger.debug("Ollama JSON mode failed, trying without: %s", e)
            # Fall back to regular generation without JSON mode
            try:
                response = httpx.post(
                    f"{self._base_url}/api/generate",
                    json={
                        "model": model_name,
                        "prompt": json_prompt,
                        "stream": False,
                    },
                    timeout=self._timeout,
                )
                response.raise_for_status()
                data = response.json()
                if "response" in data:
                    return parse_json_response(data["response"])
            except Exception as e2:
                logger.debug("Ollama fallback generation failed: %s", e2)

        return None

    def generate_stream(
        self,
        prompt: str,
        model: str | None = None,
        sanitize: bool = True,
    ) -> Iterator[str]:
        """Stream text completion using Ollama.

        Args:
            prompt: The input prompt.
            model: Model to use (defaults to llama3.2).
            sanitize: If True, truncate prompt to 8000 chars.

        Yields:
            Text chunks as they are generated.
        """
        try:
            httpx = self._get_httpx()
        except ImportError as e:
            logger.warning("httpx not available: %s", e)
            return

        text = self._sanitize_prompt(prompt) if sanitize else prompt
        model_name = model or self._default_model

        try:
            with httpx.stream(
                "POST",
                f"{self._base_url}/api/generate",
                json={
                    "model": model_name,
                    "prompt": text,
                    "stream": True,
                },
                timeout=self._timeout,
            ) as response:
                response.raise_for_status()
                for line in response.iter_lines():
                    if line:
                        try:
                            data = json.loads(line)
                            if "response" in data:
                                yield data["response"]
                        except json.JSONDecodeError:
                            pass
        except Exception as e:
            logger.debug("Ollama streaming failed: %s: %s", type(e).__name__, e)

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

        Uses a reusable httpx.AsyncClient for connection pooling and
        better performance on repeated requests.

        Args:
            prompt: The input prompt.
            model: Model to use (defaults to llama3.2).
            sanitize: If True, truncate prompt to max safe length.

        Returns:
            Generated text, or None on error.
        """
        try:
            client = await self._get_async_client()
        except ImportError as e:
            logger.warning("httpx not available: %s", e)
            return None

        text = self._sanitize_prompt(prompt) if sanitize else prompt
        model_name = model or self._default_model

        try:
            response = await client.post(
                f"{self._base_url}/api/generate",
                json={
                    "model": model_name,
                    "prompt": text,
                    "stream": False,
                },
            )
            response.raise_for_status()
            data = response.json()
            if "response" in data:
                return data["response"]
        except Exception as e:
            logger.debug("Ollama async generation failed: %s: %s", type(e).__name__, e)

        return None

    async def generate_json_async(
        self,
        prompt: str,
        model: str | None = None,
        sanitize: bool = True,
    ) -> Optional[dict[str, Any]]:
        """Async version of generate_json for non-blocking TUI operations.

        Uses a reusable httpx.AsyncClient for connection pooling.

        Args:
            prompt: The input prompt (should request JSON output).
            model: Model to use (defaults to llama3.2).
            sanitize: If True, truncate prompt to max safe length.

        Returns:
            Parsed JSON dict, or None on error.
        """
        try:
            client = await self._get_async_client()
        except ImportError as e:
            logger.warning("httpx not available: %s", e)
            return None

        text = self._sanitize_prompt(prompt) if sanitize else prompt
        model_name = model or self._default_model
        json_prompt = f"{text}\n\nRespond with valid JSON only."

        try:
            response = await client.post(
                f"{self._base_url}/api/generate",
                json={
                    "model": model_name,
                    "prompt": json_prompt,
                    "stream": False,
                    "format": "json",
                },
            )
            response.raise_for_status()
            data = response.json()
            if "response" in data:
                return parse_json_response(data["response"])
        except Exception as e:
            logger.debug("Ollama async JSON mode failed, trying without: %s", e)
            try:
                response = await client.post(
                    f"{self._base_url}/api/generate",
                    json={
                        "model": model_name,
                        "prompt": json_prompt,
                        "stream": False,
                    },
                )
                response.raise_for_status()
                data = response.json()
                if "response" in data:
                    return parse_json_response(data["response"])
            except Exception as e2:
                logger.debug("Ollama async fallback generation failed: %s", e2)

        return None

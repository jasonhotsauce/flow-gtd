"""Gemini GenAI SDK wrapper. Stream where possible; sanitize input; handle offline."""

import os
from typing import Iterator, Optional


def _get_client():
    try:
        from google import genai
        from flow.config import get_settings
        settings = get_settings()
        api_key = settings.gemini_api_key or os.environ.get("GOOGLE_API_KEY") or ""
        if not api_key:
            return None
        return genai.Client(api_key=api_key)
    except Exception:
        return None


def complete(
    prompt: str,
    model: str = "gemini-2.0-flash",
    sanitize: bool = True,
) -> Optional[str]:
    """
    Synchronous completion. Sends only prompt (sanitized: task title/description, no attachments).
    Returns None on error (offline or missing key).
    """
    client = _get_client()
    if not client:
        return None
    text = prompt[:8000] if sanitize else prompt
    try:
        response = client.models.generate_content(
            model=model,
            contents=text,
        )
        if response and response.text:
            return response.text
    except Exception:
        pass
    return None


def complete_stream(
    prompt: str,
    model: str = "gemini-2.0-flash",
    sanitize: bool = True,
) -> Iterator[str]:
    """
    Stream completion chunks. Yields text chunks; on error yields nothing.
    """
    client = _get_client()
    if not client:
        return
    text = prompt[:8000] if sanitize else prompt
    try:
        for chunk in client.models.generate_content_stream(
            model=model,
            contents=text,
        ):
            if chunk.text:
                yield chunk.text
    except Exception:
        pass

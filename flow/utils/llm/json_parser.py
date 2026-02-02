"""Robust JSON parsing utilities for LLM responses.

Different models output JSON differently:
- Some return clean JSON
- Some wrap in markdown code blocks (```json...```)
- Some add explanatory text before/after
- Some return malformed JSON

This module provides utilities to handle all these cases.
"""

import json
import re
from typing import Any, Optional


def parse_json_response(text: str) -> Optional[dict[str, Any]]:
    """Parse JSON from LLM response, handling various output formats.

    Args:
        text: Raw LLM response text.

    Returns:
        Parsed JSON dict, or None if parsing fails.
    """
    if not text or not text.strip():
        return None

    text = text.strip()

    # Strategy 1: Try direct JSON parse
    result = _try_direct_parse(text)
    if result is not None:
        return result

    # Strategy 2: Extract from markdown code block
    result = _try_markdown_block(text)
    if result is not None:
        return result

    # Strategy 3: Find JSON object boundaries
    result = _try_find_json_object(text)
    if result is not None:
        return result

    # Strategy 4: Find JSON array boundaries
    result = _try_find_json_array(text)
    if result is not None:
        return result

    return None


def _try_direct_parse(text: str) -> Optional[dict[str, Any]]:
    """Attempt direct JSON parsing."""
    try:
        result = json.loads(text)
        if isinstance(result, dict):
            return result
        # Wrap arrays in a dict for consistency
        if isinstance(result, list):
            return {"items": result}
    except json.JSONDecodeError:
        pass
    return None


def _try_markdown_block(text: str) -> Optional[dict[str, Any]]:
    """Extract JSON from markdown code blocks.

    Handles formats like:
    ```json
    {"key": "value"}
    ```

    or just:
    ```
    {"key": "value"}
    ```
    """
    # Pattern for ```json ... ``` or ``` ... ```
    patterns = [
        r"```json\s*\n?(.*?)\n?```",
        r"```\s*\n?(.*?)\n?```",
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
        if match:
            json_str = match.group(1).strip()
            result = _try_direct_parse(json_str)
            if result is not None:
                return result

    return None


def _try_find_json_object(text: str) -> Optional[dict[str, Any]]:
    """Find and extract JSON object from text.

    Looks for balanced { } braces.
    """
    # Find first { and try to find matching }
    start = text.find("{")
    if start == -1:
        return None

    # Find the matching closing brace
    depth = 0
    in_string = False
    escape_next = False

    for i, char in enumerate(text[start:], start):
        if escape_next:
            escape_next = False
            continue

        if char == "\\":
            escape_next = True
            continue

        if char == '"' and not escape_next:
            in_string = not in_string
            continue

        if in_string:
            continue

        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                json_str = text[start : i + 1]
                result = _try_direct_parse(json_str)
                if result is not None:
                    return result
                break

    return None


def _try_find_json_array(text: str) -> Optional[dict[str, Any]]:
    """Find and extract JSON array from text.

    Looks for balanced [ ] brackets.
    """
    # Find first [ and try to find matching ]
    start = text.find("[")
    if start == -1:
        return None

    # Find the matching closing bracket
    depth = 0
    in_string = False
    escape_next = False

    for i, char in enumerate(text[start:], start):
        if escape_next:
            escape_next = False
            continue

        if char == "\\":
            escape_next = True
            continue

        if char == '"' and not escape_next:
            in_string = not in_string
            continue

        if in_string:
            continue

        if char == "[":
            depth += 1
        elif char == "]":
            depth -= 1
            if depth == 0:
                json_str = text[start : i + 1]
                try:
                    result = json.loads(json_str)
                    if isinstance(result, list):
                        return {"items": result}
                except json.JSONDecodeError:
                    pass
                break

    return None


def extract_json_values(text: str, keys: list[str]) -> dict[str, Any]:
    """Extract specific key-value pairs from potentially malformed JSON.

    Useful for recovering partial data when full parsing fails.

    Args:
        text: Raw text that may contain JSON-like content.
        keys: List of keys to look for.

    Returns:
        Dict with found key-value pairs (may be empty).
    """
    result: dict[str, Any] = {}

    for key in keys:
        # Look for "key": value patterns
        pattern = (
            rf'"{key}"\s*:\s*("([^"\\]|\\.)*"|[\d.]+|true|false|null|\[.*?\]|\{{.*?\}})'
        )
        match = re.search(pattern, text, re.DOTALL)
        if match:
            value_str = match.group(1)
            try:
                result[key] = json.loads(value_str)
            except json.JSONDecodeError:
                # Store as string if can't parse
                result[key] = value_str.strip('"')

    return result

"""LLM-powered tag extraction for resources and tasks.

This module provides functions to extract relevant tags from content using
the configured LLM provider. Tags are matched against an existing vocabulary
when possible for consistency.
"""

import logging
import re
from typing import Optional

from flow.utils.llm import complete_json, complete_json_async

logger = logging.getLogger(__name__)

# Prompt template for tag extraction
_TAGGING_PROMPT = """Extract 2-5 relevant tags for this content.

Rules:
- Use lowercase, hyphenated tags (e.g., "code-review", "api-design")
- Prefer existing tags when semantically similar: {existing_tags}
- Include: topic, technology, action type if relevant
- Be specific but not overly narrow
- Do not include generic tags like "task", "todo", "work"

Content type: {content_type}
Content: {content_preview}

Return JSON: {{"tags": ["tag1", "tag2", ...]}}"""


def normalize_tag(tag: str) -> str:
    """Normalize a tag name to lowercase hyphenated format.

    Args:
        tag: Raw tag name.

    Returns:
        Normalized tag (lowercase, hyphenated, no special chars).

    Examples:
        >>> normalize_tag("Code Review")
        'code-review'
        >>> normalize_tag("API_Design")
        'api-design'
        >>> normalize_tag("  auth  ")
        'auth'
    """
    # Lowercase and strip whitespace
    tag = tag.lower().strip()
    # Replace underscores and spaces with hyphens
    tag = re.sub(r"[_\s]+", "-", tag)
    # Remove any characters that aren't alphanumeric or hyphens
    tag = re.sub(r"[^a-z0-9-]", "", tag)
    # Remove leading/trailing hyphens and collapse multiple hyphens
    tag = re.sub(r"-+", "-", tag).strip("-")
    return tag


def extract_tags(
    content: str,
    content_type: str = "text",
    existing_tags: Optional[list[str]] = None,
    max_content_length: int = 500,
) -> list[str]:
    """Extract tags from content using LLM.

    Args:
        content: The content to extract tags from (URL, filepath, or text).
        content_type: Type of content: 'url', 'file', or 'text'.
        existing_tags: List of existing tags to prefer for consistency.
        max_content_length: Maximum content length to send to LLM.

    Returns:
        List of normalized tag names (2-5 tags).
        Returns empty list if LLM fails or is unavailable.
    """
    # Truncate content for LLM
    preview = content[:max_content_length]
    if len(content) > max_content_length:
        preview += "..."

    # Format existing tags for prompt
    if existing_tags:
        tags_str = ", ".join(existing_tags[:30])  # Limit to avoid prompt bloat
    else:
        tags_str = "(none yet)"

    prompt = _TAGGING_PROMPT.format(
        existing_tags=tags_str,
        content_type=content_type,
        content_preview=preview,
    )

    try:
        result = complete_json(prompt)
        if result and "tags" in result:
            raw_tags = result["tags"]
            if isinstance(raw_tags, list):
                # Normalize and filter tags
                normalized = [normalize_tag(t) for t in raw_tags if isinstance(t, str)]
                # Filter empty tags and limit to 5
                return [t for t in normalized if t][:5]
    except (IOError, ValueError, RuntimeError, KeyError, TypeError) as e:
        logger.warning("Tag extraction failed: %s", e)

    return []


async def extract_tags_async(
    content: str,
    content_type: str = "text",
    existing_tags: Optional[list[str]] = None,
    max_content_length: int = 500,
) -> list[str]:
    """Extract tags from content using LLM (async version).

    Args:
        content: The content to extract tags from.
        content_type: Type of content: 'url', 'file', or 'text'.
        existing_tags: List of existing tags to prefer for consistency.
        max_content_length: Maximum content length to send to LLM.

    Returns:
        List of normalized tag names (2-5 tags).
        Returns empty list if LLM fails or is unavailable.
    """
    # Truncate content for LLM
    preview = content[:max_content_length]
    if len(content) > max_content_length:
        preview += "..."

    # Format existing tags for prompt
    if existing_tags:
        tags_str = ", ".join(existing_tags[:30])
    else:
        tags_str = "(none yet)"

    prompt = _TAGGING_PROMPT.format(
        existing_tags=tags_str,
        content_type=content_type,
        content_preview=preview,
    )

    try:
        result = await complete_json_async(prompt)
        if result and "tags" in result:
            raw_tags = result["tags"]
            if isinstance(raw_tags, list):
                normalized = [normalize_tag(t) for t in raw_tags if isinstance(t, str)]
                return [t for t in normalized if t][:5]
    except (IOError, ValueError, RuntimeError, KeyError, TypeError) as e:
        logger.warning("Async tag extraction failed: %s", e)

    return []


def extract_tags_from_url(
    url: str,
    title: Optional[str] = None,
    content_preview: Optional[str] = None,
    existing_tags: Optional[list[str]] = None,
) -> list[str]:
    """Extract tags from a URL resource.

    Combines URL, title, and content preview for better tag extraction.

    Args:
        url: The URL being saved.
        title: Page title if available.
        content_preview: First ~500 chars of page content if available.
        existing_tags: List of existing tags to prefer.

    Returns:
        List of normalized tag names.
    """
    # Build combined content for better context
    parts = [f"URL: {url}"]
    if title:
        parts.append(f"Title: {title}")
    if content_preview:
        parts.append(f"Content: {content_preview}")

    combined = "\n".join(parts)
    return extract_tags(combined, content_type="url", existing_tags=existing_tags)


def extract_tags_from_file(
    filepath: str,
    content_preview: Optional[str] = None,
    existing_tags: Optional[list[str]] = None,
) -> list[str]:
    """Extract tags from a file resource.

    Uses filepath and optional content preview for tag extraction.

    Args:
        filepath: Path to the file.
        content_preview: First ~500 chars of file content if available.
        existing_tags: List of existing tags to prefer.

    Returns:
        List of normalized tag names.
    """
    parts = [f"File: {filepath}"]
    if content_preview:
        parts.append(f"Content: {content_preview}")

    combined = "\n".join(parts)
    return extract_tags(combined, content_type="file", existing_tags=existing_tags)


def suggest_tags_from_vocabulary(
    content: str,
    existing_tags: list[str],
    max_suggestions: int = 10,
) -> list[str]:
    """Suggest tags from existing vocabulary without using LLM.

    Simple keyword matching for privacy mode when user doesn't want
    content sent to LLM.

    Args:
        content: Content to match against.
        existing_tags: Available tags to suggest from.
        max_suggestions: Maximum number of suggestions.

    Returns:
        List of matching tag names from the vocabulary.
    """
    content_lower = content.lower()
    suggestions = []

    for tag in existing_tags:
        # Check if tag or its parts appear in content
        tag_parts = tag.split("-")
        if tag in content_lower or any(part in content_lower for part in tag_parts):
            suggestions.append(tag)
            if len(suggestions) >= max_suggestions:
                break

    return suggestions


def parse_user_tags(user_input: str, existing_tags: list[str]) -> list[str]:
    """Parse user tag input from interactive mode.

    Handles:
    - Comma-separated tag names or numbers
    - NEW:tag-name syntax for creating new tags
    - Numbers referencing positions in existing_tags list

    Args:
        user_input: Raw user input string.
        existing_tags: List of existing tags (for number references).

    Returns:
        List of normalized tag names.

    Examples:
        >>> parse_user_tags("auth, backend", ["auth", "backend", "frontend"])
        ['auth', 'backend']
        >>> parse_user_tags("1, 2, NEW:my-tag", ["auth", "backend"])
        ['auth', 'backend', 'my-tag']
    """
    if not user_input.strip():
        return []

    parts = [p.strip() for p in user_input.split(",")]
    result = []

    for part in parts:
        if not part:
            continue

        # Handle NEW:tag-name syntax
        if part.upper().startswith("NEW:"):
            new_tag = normalize_tag(part[4:])
            if new_tag:
                result.append(new_tag)
            continue

        # Handle numeric references
        if part.isdigit():
            idx = int(part) - 1  # Convert to 0-based index
            if 0 <= idx < len(existing_tags):
                result.append(existing_tags[idx])
            continue

        # Handle direct tag name
        normalized = normalize_tag(part)
        if normalized:
            result.append(normalized)

    return list(dict.fromkeys(result))  # Remove duplicates, preserve order

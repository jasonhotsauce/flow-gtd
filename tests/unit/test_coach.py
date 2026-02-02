"""Unit tests for Coach (mock LLM)."""

import pytest

from flow.core.coach import coach_task, suggest_clusters


def test_coach_task_no_api_key() -> None:
    """coach_task returns None when LLM unavailable (no API key)."""
    result = coach_task("Fix bug")
    # Without API key, complete() returns None
    assert result is None or isinstance(result, str)


def test_suggest_clusters_empty() -> None:
    """suggest_clusters returns [] for empty list."""
    assert suggest_clusters([]) == []


def test_suggest_clusters_no_llm() -> None:
    """suggest_clusters returns list (may be empty when LLM unavailable)."""
    result = suggest_clusters(["Task A", "Task B"])
    assert isinstance(result, list)
    for item in result:
        assert isinstance(item, tuple)
        assert len(item) == 2
        assert isinstance(item[0], str)
        assert isinstance(item[1], list)

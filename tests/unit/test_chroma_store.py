"""Tests for Chroma vector-store compatibility helpers."""

from __future__ import annotations

from types import SimpleNamespace

from flow.database.chroma_store import ChromaVectorStore


def test_needs_posthog_capture_compat_for_new_signature() -> None:
    """New posthog signature should be marked as requiring a compat shim."""

    def _capture(event: str, **kwargs: object) -> str:
        return event

    assert ChromaVectorStore._needs_posthog_capture_compat(_capture) is True


def test_needs_posthog_capture_compat_for_legacy_signature() -> None:
    """Legacy positional signature should not require adaptation."""

    def _capture(distinct_id: str, event: str, properties: dict | None = None) -> str:
        return event

    assert ChromaVectorStore._needs_posthog_capture_compat(_capture) is False


def test_make_posthog_capture_compat_adapts_legacy_chroma_call() -> None:
    """Compat wrapper should map legacy positional args into modern kwargs."""
    calls: list[tuple[str, dict]] = []

    def _capture(event: str, **kwargs: object) -> str:
        calls.append((event, kwargs))
        return "ok"

    posthog_module = SimpleNamespace(disabled=False, project_api_key="phc_123")
    wrapper = ChromaVectorStore._make_posthog_capture_compat(
        _capture, posthog_module=posthog_module
    )

    result = wrapper("user-123", "ClientStartEvent", {"source": "chroma"})

    assert result == "ok"
    assert calls == [
        (
            "ClientStartEvent",
            {
                "distinct_id": "user-123",
                "properties": {"source": "chroma"},
                "api_key": "phc_123",
            },
        )
    ]


def test_make_posthog_capture_compat_noop_when_disabled() -> None:
    """Compat wrapper should short-circuit if telemetry is disabled."""
    calls: list[tuple[str, dict]] = []

    def _capture(event: str, **kwargs: object) -> str:
        calls.append((event, kwargs))
        return "ok"

    posthog_module = SimpleNamespace(disabled=True, project_api_key="phc_123")
    wrapper = ChromaVectorStore._make_posthog_capture_compat(
        _capture, posthog_module=posthog_module
    )

    result = wrapper("user-123", "ClientStartEvent", {"source": "chroma"})

    assert result is None
    assert calls == []

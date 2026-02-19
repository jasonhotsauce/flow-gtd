"""Unit tests for onboarding first capture screen behavior."""

from __future__ import annotations

from flow.tui.onboarding.screens.first_capture import FirstCaptureScreen


def test_first_capture_submit_returns_structured_result() -> None:
    """Submitting should return a structured first-capture payload."""
    screen = FirstCaptureScreen()
    dismissed: list[object] = []
    screen.dismiss = lambda result=None: dismissed.append(result)  # type: ignore[method-assign]
    screen._get_capture_text = lambda: "Draft roadmap"
    screen.action_submit()

    assert dismissed == [{"action": "submit", "text": "Draft roadmap"}]


def test_first_capture_skip_returns_structured_result() -> None:
    """Skipping should return an explicit structured skip payload."""
    screen = FirstCaptureScreen()
    dismissed: list[object] = []
    screen.dismiss = lambda result=None: dismissed.append(result)  # type: ignore[method-assign]
    screen.action_skip()

    assert dismissed == [{"action": "skip", "text": ""}]

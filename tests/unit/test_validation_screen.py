"""Unit tests for onboarding validation screen behavior."""

from __future__ import annotations

from textual._context import active_app

from flow.tui.onboarding.screens.validation import ValidationScreen


class _FakeValidationApp:
    def __init__(self) -> None:
        self.push_calls: list[object] = []
        self.exit_calls: list[object] = []
        self.first_capture_outcome: dict[str, object] | None = None

    def push_screen(self, screen: object, callback: object | None = None) -> None:
        self.push_calls.append((screen, callback))

    def exit(self, result: object | None = None) -> None:
        self.exit_calls.append(result)


def test_validation_start_flow_pushes_first_capture_screen() -> None:
    """Successful validation should route to FirstCaptureScreen before exiting."""
    screen = ValidationScreen()
    screen._validation_success = True
    fake_app = _FakeValidationApp()
    token = active_app.set(fake_app)  # type: ignore[arg-type]
    try:
        screen.action_start_flow()
    finally:
        active_app.reset(token)

    assert len(fake_app.push_calls) == 1
    pushed_screen, callback = fake_app.push_calls[0]
    assert pushed_screen.__class__.__name__ == "FirstCaptureScreen"
    assert callback is not None
    assert fake_app.exit_calls == []


def test_validation_start_flow_ignored_until_success() -> None:
    """Enter/start_flow should be ignored until validation succeeds."""
    screen = ValidationScreen()
    fake_app = _FakeValidationApp()
    token = active_app.set(fake_app)  # type: ignore[arg-type]
    try:
        screen.action_start_flow()
    finally:
        active_app.reset(token)

    assert fake_app.push_calls == []


def test_validation_handles_first_capture_result_and_exits() -> None:
    """Validation should store first-capture outcome and exit onboarding."""
    screen = ValidationScreen()
    fake_app = _FakeValidationApp()
    token = active_app.set(fake_app)  # type: ignore[arg-type]
    try:
        result = {"action": "skip", "text": ""}
        screen._on_first_capture_complete(result)
    finally:
        active_app.reset(token)

    assert fake_app.first_capture_outcome == result
    assert fake_app.exit_calls == [True]

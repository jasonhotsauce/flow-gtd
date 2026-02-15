"""Unit tests for CLI default entry behavior."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest
import typer

from flow.cli import _launch_tui, main


def test_main_without_subcommand_launches_default_tui(monkeypatch: Any) -> None:
    """Bare `flow` should open TUI default screen (Inbox)."""
    calls: list[object] = []

    def fake_launch_tui(initial_screen: object = None) -> None:
        calls.append(initial_screen)

    monkeypatch.setattr("flow.cli._launch_tui", fake_launch_tui)

    main(ctx=SimpleNamespace(invoked_subcommand=None), version=False)

    assert calls == [None]


def test_launch_tui_hands_off_onboarding_first_capture(monkeypatch: Any) -> None:
    """First capture submit should create item and seed Inbox startup context."""
    app_inits: list[dict[str, object]] = []
    captured_texts: list[str] = []

    class _FakeOnboardingApp:
        def run(self) -> bool:
            return True

        def get_onboarding_result(self) -> dict[str, object]:
            return {
                "completed": True,
                "first_capture": {"action": "submit", "text": "  Draft roadmap  "},
            }

    class _FakeFlowApp:
        def __init__(self, **kwargs: object) -> None:
            app_inits.append(dict(kwargs))

        def run(self) -> None:
            return

    class _FakeEngine:
        def capture(self, text: str) -> object:
            captured_texts.append(text)
            return SimpleNamespace(id="inbox-123")

    monkeypatch.setattr("flow.utils.llm.config.is_onboarding_completed", lambda: False)
    monkeypatch.setattr("flow.tui.onboarding.app.OnboardingApp", _FakeOnboardingApp)
    monkeypatch.setattr("flow.cli.FlowApp", _FakeFlowApp)
    monkeypatch.setattr("flow.cli.Engine", _FakeEngine)

    _launch_tui()

    assert captured_texts == ["Draft roadmap"]
    assert app_inits == [
        {
            "initial_screen": None,
            "startup_context": {
                "highlighted_item_id": "inbox-123",
                "show_first_value_hint": True,
            },
        }
    ]


def test_launch_tui_keeps_default_behavior_when_no_first_capture(
    monkeypatch: Any,
) -> None:
    """Skip/no text should not create captures or startup context."""
    app_inits: list[dict[str, object]] = []
    engine_calls: list[str] = []

    class _FakeOnboardingApp:
        def run(self) -> bool:
            return True

        def get_onboarding_result(self) -> dict[str, object]:
            return {
                "completed": True,
                "first_capture": {"action": "skip", "text": ""},
            }

    class _FakeFlowApp:
        def __init__(self, **kwargs: object) -> None:
            app_inits.append(dict(kwargs))

        def run(self) -> None:
            return

    class _FakeEngine:
        def capture(self, text: str) -> object:
            engine_calls.append(text)
            return SimpleNamespace(id="unused")

    monkeypatch.setattr("flow.utils.llm.config.is_onboarding_completed", lambda: False)
    monkeypatch.setattr("flow.tui.onboarding.app.OnboardingApp", _FakeOnboardingApp)
    monkeypatch.setattr("flow.cli.FlowApp", _FakeFlowApp)
    monkeypatch.setattr("flow.cli.Engine", _FakeEngine)

    _launch_tui()

    assert engine_calls == []
    assert app_inits == [{"initial_screen": None, "startup_context": None}]


def test_launch_tui_continues_when_first_capture_fails(monkeypatch: Any) -> None:
    """Capture failures in optional first-capture handoff should not block app launch."""
    app_inits: list[dict[str, object]] = []

    class _FakeOnboardingApp:
        def run(self) -> bool:
            return True

        def get_onboarding_result(self) -> dict[str, object]:
            return {
                "completed": True,
                "first_capture": {"action": "submit", "text": "draft plan"},
            }

    class _FakeFlowApp:
        def __init__(self, **kwargs: object) -> None:
            app_inits.append(dict(kwargs))

        def run(self) -> None:
            return

    class _FakeEngine:
        def capture(self, _text: str) -> object:
            raise RuntimeError("db locked")

    monkeypatch.setattr("flow.utils.llm.config.is_onboarding_completed", lambda: False)
    monkeypatch.setattr("flow.tui.onboarding.app.OnboardingApp", _FakeOnboardingApp)
    monkeypatch.setattr("flow.cli.FlowApp", _FakeFlowApp)
    monkeypatch.setattr("flow.cli.Engine", _FakeEngine)

    _launch_tui()

    assert app_inits == [{"initial_screen": None, "startup_context": None}]


def test_launch_tui_exits_when_onboarding_not_completed(monkeypatch: Any) -> None:
    """If onboarding is abandoned, CLI should exit without launching FlowApp."""
    run_calls: list[bool] = []

    class _FakeOnboardingApp:
        def run(self) -> bool:
            return False

    class _FakeFlowApp:
        def __init__(self, **_kwargs: object) -> None:
            return

        def run(self) -> None:
            run_calls.append(True)

    monkeypatch.setattr("flow.utils.llm.config.is_onboarding_completed", lambda: False)
    monkeypatch.setattr("flow.tui.onboarding.app.OnboardingApp", _FakeOnboardingApp)
    monkeypatch.setattr("flow.cli.FlowApp", _FakeFlowApp)

    with pytest.raises(typer.Exit):
        _launch_tui()

    assert run_calls == []

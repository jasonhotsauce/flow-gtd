"""Unit tests for Process screen key bindings."""

from __future__ import annotations

import pytest

from flow.tui.screens.process.process import ProcessScreen


def test_process_screen_has_delete_key_binding_for_two_minute_drill() -> None:
    """Process screen should expose `x` as a single-keystroke delete in Stage 3."""
    assert any(
        (binding[0] == "x" if isinstance(binding, tuple) else binding.key == "x")
        for binding in ProcessScreen.BINDINGS
    )


def test_process_screen_has_enter_binding_for_primary_cta() -> None:
    """Process screen should expose Enter as a primary action accelerator."""
    assert any(
        (binding[0] == "enter" if isinstance(binding, tuple) else binding.key == "enter")
        for binding in ProcessScreen.BINDINGS
    )


def test_process_screen_primary_cta_copy_for_two_minute_stage() -> None:
    """Stage 3 copy should make the explicit throughput CTA obvious."""
    screen = ProcessScreen()

    assert screen._primary_cta_text(3) == "Primary: Enter to Do Now"
    assert screen._next_step_hint(3) == "Next: Press 4 for Coach when this item is handled."


class _FakeStatic:
    def __init__(self) -> None:
        self.value: object = ""

    def update(self, value: object) -> None:
        self.value = value


class _FakeContainer:
    def __init__(self) -> None:
        self.display = False


class _FakeOptionList:
    def __init__(self) -> None:
        self.display = True
        self.options: list[object] = []

    def clear_options(self) -> None:
        self.options.clear()

    def add_option(self, option: object) -> None:
        self.options.append(option)


@pytest.mark.asyncio
async def test_process_screen_hides_cluster_list_when_no_suggestions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Cluster empty-state should not show an extra empty list box."""
    screen = ProcessScreen()
    screen._stage = 2

    widgets = {
        "#process-help-text": _FakeStatic(),
        "#process-cta-text": _FakeStatic(),
        "#cluster-list": _FakeOptionList(),
        "#complete-state": _FakeContainer(),
        "#complete-text": _FakeStatic(),
    }

    monkeypatch.setattr(
        screen,
        "query_one",
        lambda selector, *_args, **_kwargs: widgets[selector],
    )
    monkeypatch.setattr(ProcessScreen, "is_mounted", property(lambda self: True))
    monkeypatch.setattr(screen._engine, "get_cluster_suggestions", lambda: [])

    await screen._render_cluster_async()

    assert widgets["#complete-state"].display is True
    assert widgets["#cluster-list"].display is False


def test_process_screen_stage4_complete_uses_focus_bridge_copy_when_pending(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Stage 4 completion should promote Focus mode during first-run handoff."""
    screen = ProcessScreen()
    screen._first_run_focus_bridge_pending = True
    monkeypatch.setattr(screen._engine, "get_coach_current", lambda: None)

    widgets = {
        "#complete-state": _FakeContainer(),
        "#complete-icon": _FakeStatic(),
        "#complete-text": _FakeStatic(),
        "#process-help-text": _FakeStatic(),
        "#process-cta-text": _FakeStatic(),
    }

    monkeypatch.setattr(
        screen,
        "query_one",
        lambda selector, *_args, **_kwargs: widgets[selector],
    )

    screen._render_coach()

    assert widgets["#complete-state"].display is True
    assert widgets["#complete-icon"].value == "🎯"
    assert "Focus mode" in str(widgets["#complete-text"].value)
    assert widgets["#process-cta-text"].value == "Primary: Enter to Start Focus"


@pytest.mark.asyncio
async def test_process_screen_stage4_primary_routes_to_focus_for_first_run_bridge(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Stage 4 Enter should launch Focus and mark first-run completion once."""
    screen = ProcessScreen()
    screen._first_run_focus_bridge_pending = True
    monkeypatch.setattr(screen._engine, "get_coach_current", lambda: None)

    marked: list[bool] = []
    launched: list[bool] = []
    monkeypatch.setattr(
        "flow.tui.screens.process.process.mark_first_value_completed",
        lambda: marked.append(True),
    )
    monkeypatch.setattr(screen, "action_start_focus", lambda: launched.append(True))

    await screen._primary_stage4_async()

    assert marked == [True]
    assert launched == [True]
    assert screen._first_run_focus_bridge_pending is False

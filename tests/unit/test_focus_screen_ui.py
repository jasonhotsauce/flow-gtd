"""Unit tests for Focus screen task metadata and resources panel UI."""

from __future__ import annotations

from typing import Any

import pytest

from flow.models import Item
from flow.tui.screens.focus.focus import FocusScreen


class _FakeStatic:
    def __init__(self) -> None:
        self.value: object = ""

    def update(self, value: object) -> None:
        self.value = value


class _FakeContainer:
    def __init__(self) -> None:
        self.display = False


class _FakeResourcesPanel:
    def __init__(self) -> None:
        self.display = True
        self.value: object = ""
        self.cleared = False

    def update(self, value: object) -> None:
        self.value = value

    def clear_resources(self) -> None:
        self.cleared = True


def _query_widget_map() -> dict[str, Any]:
    return {
        "#focus-icon": _FakeStatic(),
        "#focus-mode-badge": _FakeStatic(),
        "#focus-time-text": _FakeStatic(),
        "#focus-task-title": _FakeStatic(),
        "#focus-duration-badge": _FakeStatic(),
        "#focus-tags": _FakeStatic(),
        "#focus-main": _FakeContainer(),
        "#focus-empty": _FakeContainer(),
        "#focus-empty-icon": _FakeStatic(),
        "#focus-resources": _FakeResourcesPanel(),
    }


def test_focus_screen_prefixes_tags_with_hash_and_sets_resources_loading_copy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Focus task tags should render with hashtag prefixes and no blank resource panel."""
    screen = FocusScreen()
    screen._current_task = Item(
        id="item-1",
        type="action",
        title="Build landing page",
        status="active",
        context_tags=["flow-gtd", "web-development"],
        estimated_duration=30,
    )

    widgets = _query_widget_map()
    monkeypatch.setattr(FocusScreen, "is_mounted", property(lambda self: True))
    monkeypatch.setattr(
        screen, "query_one", lambda selector, *_args, **_kwargs: widgets[selector]
    )

    screen._update_ui("Standard", "3h free")

    assert "#flow-gtd" in str(widgets["#focus-tags"].value)
    assert "#web-development" in str(widgets["#focus-tags"].value)
    assert "Related Resources" in str(widgets["#focus-resources"].value)


def test_focus_screen_hides_resources_panel_when_no_task(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Focus resources panel should be hidden in empty state."""
    screen = FocusScreen()
    screen._current_task = None

    widgets = _query_widget_map()
    monkeypatch.setattr(FocusScreen, "is_mounted", property(lambda self: True))
    monkeypatch.setattr(
        screen, "query_one", lambda selector, *_args, **_kwargs: widgets[selector]
    )

    screen._update_ui("Standard", "No window")

    assert widgets["#focus-resources"].display is False
    assert widgets["#focus-resources"].cleared is True

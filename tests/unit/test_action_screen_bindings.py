"""Unit tests for Action screen key bindings."""

from __future__ import annotations

from typing import Any

from flow.tui.screens.action.action import ActionScreen


def _has_binding(screen: type[ActionScreen], key: str, action: str | None = None) -> bool:
    for binding in screen.BINDINGS:
        if isinstance(binding, tuple):
            if binding[0] != key:
                continue
            if action is None or binding[1] == action:
                return True
            continue
        if binding.key != key:
            continue
        if action is None or binding.action == action:
            return True
    return False


def test_action_screen_has_defer_key_binding() -> None:
    """Action screen should expose `f` for defer workflow."""
    assert _has_binding(ActionScreen, "f")


def test_action_screen_has_panel_shortcuts() -> None:
    """Action screen should expose number/name panel shortcuts."""
    assert _has_binding(ActionScreen, "1", "focus_tasks_panel")
    assert _has_binding(ActionScreen, "2", "focus_resources_panel")
    assert _has_binding(ActionScreen, "t", "focus_tasks_panel")
    assert _has_binding(ActionScreen, "r", "focus_resources_panel")


def test_action_screen_focus_task_panel_routes_to_task_list(monkeypatch: Any) -> None:
    """Task panel focus action should focus the list widget."""
    screen = ActionScreen()
    focused = {"called": False}

    class Dummy:
        def focus(self) -> None:
            focused["called"] = True

    def fake_query_one(selector: str, _widget_type: type[Any]) -> Dummy:
        assert selector == "#action-list"
        return Dummy()

    monkeypatch.setattr(screen, "query_one", fake_query_one)
    screen.action_focus_tasks_panel()
    assert focused["called"] is True


def test_action_screen_focus_resource_panel_routes_to_sidecar(
    monkeypatch: Any,
) -> None:
    """Resource panel focus action should focus the sidecar widget."""
    screen = ActionScreen()
    focused = {"called": False}

    class Dummy:
        def focus(self) -> None:
            focused["called"] = True

    def fake_query_one(selector: str, _widget_type: type[Any]) -> Dummy:
        assert selector == "#sidecar"
        return Dummy()

    monkeypatch.setattr(screen, "query_one", fake_query_one)
    screen.action_focus_resources_panel()
    assert focused["called"] is True

"""Unit tests for Projects screen panel bindings."""

from __future__ import annotations

from typing import Any

from flow.tui.screens.projects.projects import ProjectsScreen


def _has_binding(
    screen: type[ProjectsScreen], key: str, action: str | None = None
) -> bool:
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


def test_projects_screen_has_panel_shortcuts() -> None:
    """Projects screen should expose number/name panel shortcuts."""
    assert _has_binding(ProjectsScreen, "1", "focus_list_panel")
    assert _has_binding(ProjectsScreen, "2", "focus_detail_panel")
    assert _has_binding(ProjectsScreen, "l", "focus_list_panel")
    assert _has_binding(ProjectsScreen, "d", "focus_detail_panel")


def test_projects_screen_focus_list_panel_routes_to_list(monkeypatch: Any) -> None:
    """List panel focus action should focus projects list."""
    screen = ProjectsScreen()
    focused = {"called": False}

    class Dummy:
        def focus(self) -> None:
            focused["called"] = True

    def fake_query_one(selector: str, _widget_type: type[Any]) -> Dummy:
        assert selector == "#projects-list"
        return Dummy()

    monkeypatch.setattr(screen, "query_one", fake_query_one)
    screen.action_focus_list_panel()
    assert focused["called"] is True


def test_projects_screen_focus_detail_panel_routes_to_detail(monkeypatch: Any) -> None:
    """Detail panel focus action should focus detail scroll area."""
    screen = ProjectsScreen()
    focused = {"called": False}

    class Dummy:
        def focus(self) -> None:
            focused["called"] = True

    def fake_query_one(selector: str, _widget_type: type[Any]) -> Dummy:
        assert selector == "#projects-detail-next-scroll"
        return Dummy()

    monkeypatch.setattr(screen, "query_one", fake_query_one)
    screen.action_focus_detail_panel()
    assert focused["called"] is True

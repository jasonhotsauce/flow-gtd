"""Unit tests for Inbox screen key bindings."""

from __future__ import annotations

from typing import Any

from flow.tui.screens.inbox.inbox import InboxScreen


def _has_binding(screen: type[InboxScreen], key: str, action: str | None = None) -> bool:
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


def test_inbox_screen_has_projects_key_binding() -> None:
    """Inbox should expose a direct projects shortcut."""
    assert _has_binding(InboxScreen, "g")


def test_inbox_screen_has_defer_key_binding() -> None:
    """Inbox should expose `f` for defer workflow."""
    assert _has_binding(InboxScreen, "f")


def test_inbox_screen_enter_binding_is_process_menu() -> None:
    """Inbox Enter should open process menu."""
    assert _has_binding(InboxScreen, "enter", "open_process_menu")


def test_inbox_screen_has_panel_shortcuts() -> None:
    """Inbox should expose number/name panel shortcuts."""
    assert _has_binding(InboxScreen, "1", "focus_list_panel")
    assert _has_binding(InboxScreen, "2", "focus_detail_panel")
    assert _has_binding(InboxScreen, "l", "focus_list_panel")
    assert _has_binding(InboxScreen, "e", "focus_detail_panel")


def test_inbox_screen_focus_list_panel_routes_to_list(monkeypatch: Any) -> None:
    """List panel focus action should focus inbox list."""
    screen = InboxScreen()
    focused = {"called": False}

    class Dummy:
        def focus(self) -> None:
            focused["called"] = True

    def fake_query_one(selector: str, _widget_type: type[Any]) -> Dummy:
        assert selector == "#inbox-list"
        return Dummy()

    monkeypatch.setattr(screen, "query_one", fake_query_one)
    screen.action_focus_list_panel()
    assert focused["called"] is True


def test_inbox_screen_focus_detail_panel_routes_to_detail(monkeypatch: Any) -> None:
    """Detail panel focus action should focus detail scroll area."""
    screen = InboxScreen()
    focused = {"called": False}

    class Dummy:
        def focus(self) -> None:
            focused["called"] = True

    def fake_query_one(selector: str, _widget_type: type[Any]) -> Dummy:
        assert selector == "#inbox-detail-scroll"
        return Dummy()

    monkeypatch.setattr(screen, "query_one", fake_query_one)
    screen.action_focus_detail_panel()
    assert focused["called"] is True

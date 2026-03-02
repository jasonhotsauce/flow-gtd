"""Unit tests for Focus screen key bindings."""

from __future__ import annotations

from typing import Any

from flow.tui.common.base_screen import FlowScreen
from flow.tui.screens.focus.focus import FocusScreen


def _has_binding(screen: type[FocusScreen], key: str, action: str | None = None) -> bool:
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


def test_focus_screen_inherits_flow_screen() -> None:
    """Focus screen should inherit shared FlowScreen contract."""
    assert issubclass(FocusScreen, FlowScreen)


def test_focus_screen_has_shared_help_binding() -> None:
    """Focus screen should expose shared help binding."""
    assert _has_binding(FocusScreen, "?")


def test_focus_screen_has_new_inbox_task_binding() -> None:
    """Focus should expose a direct shortcut to create a new inbox task."""
    assert _has_binding(FocusScreen, "n", "go_to_inbox_new_task")


def test_focus_screen_new_inbox_task_action_pushes_inbox_with_startup_context(
    monkeypatch: Any,
) -> None:
    """Focus CTA should navigate to Inbox and trigger startup quick-create."""
    screen = FocusScreen()
    pushed: list[object] = []

    class _FakeApp:
        def push_screen(self, new_screen: object) -> None:
            pushed.append(new_screen)

    fake_app = _FakeApp()
    monkeypatch.setattr(FocusScreen, "app", property(lambda self: fake_app))

    screen.action_go_to_inbox_new_task()

    assert len(pushed) == 1
    target = pushed[0]
    assert type(target).__name__ == "InboxScreen"
    assert getattr(target, "_startup_context", None) == {"start_new_task": True}

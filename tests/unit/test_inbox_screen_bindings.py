"""Unit tests for Inbox screen key bindings."""

from __future__ import annotations

from flow.tui.screens.inbox.inbox import InboxScreen


def test_inbox_screen_has_projects_key_binding() -> None:
    """Inbox should expose a direct projects shortcut."""
    assert any(
        (binding[0] == "g" if isinstance(binding, tuple) else binding.key == "g")
        for binding in InboxScreen.BINDINGS
    )


def test_inbox_screen_has_defer_key_binding() -> None:
    """Inbox should expose `f` for defer workflow."""
    assert any(
        (binding[0] == "f" if isinstance(binding, tuple) else binding.key == "f")
        for binding in InboxScreen.BINDINGS
    )

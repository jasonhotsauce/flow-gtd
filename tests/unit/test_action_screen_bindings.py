"""Unit tests for Action screen key bindings."""

from __future__ import annotations

from flow.tui.screens.action.action import ActionScreen


def test_action_screen_has_defer_key_binding() -> None:
    """Action screen should expose `f` for defer workflow."""
    assert any(
        (binding[0] == "f" if isinstance(binding, tuple) else binding.key == "f")
        for binding in ActionScreen.BINDINGS
    )

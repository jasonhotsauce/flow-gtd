"""Unit tests for Focus screen key bindings."""

from __future__ import annotations

from flow.tui.common.base_screen import FlowScreen
from flow.tui.screens.focus.focus import FocusScreen


def test_focus_screen_inherits_flow_screen() -> None:
    """Focus screen should inherit shared FlowScreen contract."""
    assert issubclass(FocusScreen, FlowScreen)


def test_focus_screen_has_shared_help_binding() -> None:
    """Focus screen should expose shared help binding."""
    assert any(
        (binding[0] == "?" if isinstance(binding, tuple) else binding.key == "?")
        for binding in FocusScreen.BINDINGS
    )

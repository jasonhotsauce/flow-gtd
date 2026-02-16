"""Contract tests for shared TUI base screen classes."""

from flow.tui.common.base_screen import FlowModalScreen, FlowScreen
from flow.tui.common.keybindings import HELP_BINDING, QUIT_Q_BINDING


def test_flow_screen_includes_global_bindings() -> None:
    """FlowScreen should expose shared global keybindings."""
    assert QUIT_Q_BINDING in FlowScreen.BINDINGS
    assert HELP_BINDING in FlowScreen.BINDINGS


def test_flow_modal_screen_includes_escape_cancel() -> None:
    """FlowModalScreen should expose modal cancel keybinding."""
    assert any(binding[0] == "escape" for binding in FlowModalScreen.BINDINGS)

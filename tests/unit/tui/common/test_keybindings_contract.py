"""Contract tests for shared TUI keybindings."""

from flow.tui.common import keybindings


def test_global_keybinding_contract_exports_expected_bindings() -> None:
    """Shared keybinding module should export stable global bindings."""
    assert keybindings.QUIT_Q_BINDING == ("q", "quit", "Quit")
    assert keybindings.BACK_ESCAPE_BINDING == ("escape", "go_back", "Back")
    assert keybindings.HELP_BINDING == ("?", "show_help", "Help")
    assert keybindings.NAV_DOWN_BINDING == ("j", "cursor_down", "Down")
    assert keybindings.NAV_UP_BINDING == ("k", "cursor_up", "Up")


def test_with_global_bindings_prefixes_global_contract() -> None:
    """Composed global bindings should include defaults and custom bindings."""
    custom = ("x", "delete", "Delete")
    composed = keybindings.with_global_bindings(custom)
    assert composed[0] == keybindings.QUIT_Q_BINDING
    assert keybindings.HELP_BINDING in composed
    assert custom in composed

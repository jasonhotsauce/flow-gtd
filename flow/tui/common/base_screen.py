"""Shared base screen classes for Flow TUI."""

from __future__ import annotations

from typing import Generic, TypeVar

from textual.screen import ModalScreen, Screen

from flow.tui.common.keybindings import with_global_bindings, with_modal_bindings

_T = TypeVar("_T")


class FlowScreen(Screen):
    """Base class for Flow screens with unified global bindings."""

    BINDINGS = with_global_bindings()

    def action_quit(self) -> None:
        """Quit the app from any screen."""
        self.app.exit()

    def action_go_back(self) -> None:
        """Default back behavior for screens."""
        if len(self.app.screen_stack) <= 2:
            self.app.exit()
        else:
            self.app.pop_screen()

    def action_show_help(self) -> None:
        """Fallback help action when a screen does not override it."""
        self.notify("No additional help for this screen.", timeout=2)

    def action_cursor_down(self) -> None:
        """Default no-op cursor movement hook."""
        return

    def action_cursor_up(self) -> None:
        """Default no-op cursor movement hook."""
        return


class FlowModalScreen(ModalScreen[_T], Generic[_T]):
    """Base class for Flow modal screens with unified modal bindings."""

    BINDINGS = with_modal_bindings()

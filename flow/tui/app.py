"""Main TUI app and lifecycle."""

from typing import Optional, Type

from textual.app import App
from textual.screen import Screen

from flow.tui.screens.inbox.inbox import InboxScreen


class FlowApp(App):
    """Flow GTD TUI. Default screen: Inbox.

    A modern, focused GTD interface with Vim-native navigation
    and a beautiful dark theme.
    """

    CSS_PATH = "common/theme.tcss"
    TITLE = "Flow GTD"
    SUB_TITLE = "Get Things Done"

    BINDINGS = []

    def __init__(
        self, initial_screen: Optional[Type[Screen]] = None, **kwargs
    ):  # type: ignore[no-untyped-def]
        super().__init__(**kwargs)
        self._initial_screen = initial_screen

    def on_mount(self) -> None:
        """Push initial screen on mount."""
        if self._initial_screen is not None:
            self.push_screen(self._initial_screen())
        else:
            self.push_screen(InboxScreen())

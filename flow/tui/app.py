"""Main TUI app and lifecycle."""

import threading
from typing import Optional, Type

from textual.app import App
from textual.screen import Screen

from flow.core.engine import Engine
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
        self,
        initial_screen: Optional[Type[Screen]] = None,
        startup_context: dict[str, object] | None = None,
        **kwargs,
    ):  # type: ignore[no-untyped-def]
        super().__init__(**kwargs)
        self._initial_screen = initial_screen
        self._startup_context = startup_context

    def on_mount(self) -> None:
        """Push initial screen on mount."""
        self._start_index_worker()
        if self._initial_screen is not None:
            self.push_screen(self._initial_screen())
        else:
            self.push_screen(InboxScreen(startup_context=self._startup_context))

    @staticmethod
    def _start_index_worker() -> None:
        """Best-effort queue processing for semantic index jobs."""
        def _run() -> None:
            try:
                Engine().process_index_jobs(limit=20)
            except Exception:
                return

        threading.Thread(target=_run, daemon=True).start()

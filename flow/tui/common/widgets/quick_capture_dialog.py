"""Reusable quick-capture modal for creating inbox tasks."""

from __future__ import annotations

from typing import TypedDict

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Input, Static

from flow.tui.common.base_screen import FlowModalScreen
from flow.tui.common.keybindings import with_modal_bindings


class QuickCaptureResult(TypedDict):
    """Result payload for quick-capture modal."""

    action: str
    text: str


class QuickCaptureDialog(FlowModalScreen[QuickCaptureResult | None]):
    """Modal for entering a single inbox capture."""

    BINDINGS = with_modal_bindings(
        ("enter", "submit", "Create"),
    )

    DEFAULT_CSS = """
    QuickCaptureDialog {
        align: center middle;
    }

    #quick-capture-dialog {
        width: 76;
        height: auto;
        border: round #3f5a73;
        background: #121922;
        padding: 1 2;
    }

    #quick-capture-title {
        content-align: center middle;
        margin-bottom: 1;
        text-style: bold;
        color: #7ad0de;
    }

    #quick-capture-hint {
        margin-top: 1;
        color: #b8c6d8;
    }
    """

    def compose(self) -> ComposeResult:
        """Build quick-capture dialog layout."""
        with Vertical(id="quick-capture-dialog"):
            yield Static("Create new inbox task", id="quick-capture-title")
            yield Input(
                placeholder="Describe the next concrete action...",
                id="quick-capture-input",
            )
            yield Static("Press Enter to create or Esc to cancel.", id="quick-capture-hint")

    def on_mount(self) -> None:
        """Focus text input on open."""
        self.query_one("#quick-capture-input", Input).focus()

    def action_cancel(self) -> None:
        """Close modal with no result."""
        self.dismiss(None)

    def action_submit(self) -> None:
        """Submit quick-capture text."""
        text = self.query_one("#quick-capture-input", Input).value.strip()
        self.dismiss({"action": "submit", "text": text})

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Submit text when input is confirmed."""
        if event.input.id != "quick-capture-input":
            return
        self.action_submit()

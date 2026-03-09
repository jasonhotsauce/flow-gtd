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
        background: #0d111799;
    }

    #quick-capture-dialog {
        width: 82;
        height: auto;
        border: round #3f5a73;
        background: #121922;
        padding: 1 2 2 2;
    }

    #quick-capture-title {
        margin-bottom: 1;
        text-style: bold;
        color: #7ad0de;
    }

    #quick-capture-status {
        color: #8ea2b7;
        margin-bottom: 1;
    }

    #quick-capture-input {
        margin-top: 1;
        margin-bottom: 1;
        border: tall #253241;
        background: #18222d;
    }

    #quick-capture-input:focus {
        border: tall #3f5a73;
    }

    #quick-capture-hint {
        margin-top: 1;
        color: #b8c6d8;
    }
    """

    def __init__(self, origin_label: str = "Flow") -> None:
        super().__init__()
        self._origin_label = origin_label

    def compose(self) -> ComposeResult:
        """Build quick-capture dialog layout."""
        with Vertical(id="quick-capture-dialog"):
            yield Static("Quick Capture", id="quick-capture-title")
            yield Static(
                f"{self._origin_label}  |  Capture a concrete next step without leaving the current flow.",
                id="quick-capture-status",
            )
            yield Input(
                placeholder="Describe the next concrete step...",
                id="quick-capture-input",
            )
            yield Static("Enter creates the task. Esc cancels and returns to your current workspace.", id="quick-capture-hint")

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

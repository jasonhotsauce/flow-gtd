"""Screen 4: Optional first capture during onboarding."""

from __future__ import annotations

from typing import Literal, TypedDict

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Input, Static


class FirstCaptureResult(TypedDict):
    """Structured result emitted from first-capture onboarding step."""

    action: Literal["submit", "skip"]
    text: str


class FirstCaptureScreen(Screen):
    """Collect an optional first capture before entering the main app."""

    BINDINGS = [
        ("enter", "submit", "Submit"),
        ("escape", "skip", "Skip"),
    ]

    def compose(self) -> ComposeResult:
        """Build first-capture UI."""
        yield Header()
        with Container(id="first-capture-container"):
            with Vertical(id="first-capture-content"):
                yield Static("Capture your first thought", id="first-capture-title")
                yield Static(
                    "Optional: add something to your inbox now.", id="first-capture-subtitle"
                )
                yield Input(
                    placeholder="Example: Draft Q2 hiring plan",
                    id="first-capture-input",
                )
                with Horizontal(id="first-capture-actions"):
                    yield Button("Skip", id="skip-btn")
                    yield Button("Submit", id="submit-btn", variant="primary")
        yield Footer()

    def on_mount(self) -> None:
        """Focus the input immediately for keyboard-first flow."""
        self.query_one("#first-capture-input", Input).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle submit/skip button presses."""
        if event.button.id == "submit-btn":
            self.action_submit()
        elif event.button.id == "skip-btn":
            self.action_skip()

    def _get_capture_text(self) -> str:
        """Get trimmed capture text from input."""
        return self.query_one("#first-capture-input", Input).value.strip()

    def action_submit(self) -> None:
        """Close with structured submit payload."""
        capture_text = self._get_capture_text()
        self.dismiss(FirstCaptureResult(action="submit", text=capture_text))

    def action_skip(self) -> None:
        """Close with structured skip payload."""
        self.dismiss(FirstCaptureResult(action="skip", text=""))

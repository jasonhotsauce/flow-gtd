"""Screen 4: Optional first capture during onboarding."""

from __future__ import annotations

from typing import Literal, TypedDict

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Button, Footer, Header, Input, Static

from flow.tui.common.base_screen import FlowScreen
from flow.tui.common.keybindings import (
    HELP_BINDING,
    NAV_DOWN_BINDING,
    NAV_UP_BINDING,
    QUIT_Q_BINDING,
    compose_bindings,
)


class FirstCaptureResult(TypedDict):
    """Structured result emitted from first-capture onboarding step."""

    action: Literal["submit", "skip"]
    text: str


class FirstCaptureScreen(FlowScreen):
    """Collect an optional first capture before entering the main app."""

    CSS_PATH = ["../../common/ops_tokens.tcss", "first_capture.tcss"]

    BINDINGS = compose_bindings(
        QUIT_Q_BINDING,
        NAV_DOWN_BINDING,
        NAV_UP_BINDING,
        HELP_BINDING,
        ("enter", "submit", "Submit"),
        ("escape", "skip", "Skip"),
    )

    def compose(self) -> ComposeResult:
        """Build first-capture UI."""
        yield Header()
        with Container(id="onboarding-shell"):
            yield Static("Step 5/5  |  First Capture", id="onboarding-progress")
            with Horizontal(id="onboarding-layout"):
                with Vertical(id="onboarding-main-pane"):
                    yield Static("Capture First Thought", id="onboarding-title")
                    yield Static(
                        "Optional: add one item to your inbox now.",
                        id="first-capture-subtitle",
                    )
                    with Vertical(id="first-capture-content", classes="onboarding-panel"):
                        yield Static("Quick capture", id="first-capture-title", classes="section-title")
                        yield Input(
                            placeholder="Example: Draft Q2 hiring plan",
                            id="first-capture-input",
                        )
                        with Horizontal(id="first-capture-actions"):
                            yield Button("Skip", id="skip-btn")
                            yield Button("Submit", id="submit-btn", variant="primary")
                with Vertical(id="onboarding-ops-pane"):
                    with Vertical(classes="onboarding-side-panel"):
                        yield Static("WHY THIS STEP", classes="section-title")
                        yield Static(
                            "Starting with one capture confirms your setup and seeds your workflow.",
                            id="first-capture-tip",
                        )
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

"""Reusable defer chooser modal for GTD defer flows."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Input, OptionList, Static
from textual.widgets.option_list import Option

from flow.core.defer_utils import parse_defer_until
from flow.tui.common.base_screen import FlowModalScreen
from flow.tui.common.keybindings import with_modal_bindings


class DeferDialog(FlowModalScreen[dict[str, str] | None]):
    """Modal for choosing defer mode and optional defer-until input."""

    BINDINGS = with_modal_bindings()

    DEFAULT_CSS = """
    DeferDialog {
        align: center middle;
    }

    #defer-dialog {
        width: 72;
        height: auto;
        border: round $primary;
        background: $surface;
        padding: 1 2;
    }

    #defer-title {
        content-align: center middle;
        margin-bottom: 1;
        text-style: bold;
    }

    #defer-hint {
        margin: 1 0 0 0;
        color: $text-muted;
    }

    #defer-until-input {
        margin-top: 1;
    }
    """

    def compose(self) -> ComposeResult:
        with Vertical(id="defer-dialog"):
            yield Static("Choose defer type", id="defer-title")
            yield OptionList(
                Option("Waiting For", id="waiting"),
                Option("Defer Until", id="until"),
                Option("Someday/Maybe", id="someday"),
                Option("Cancel", id="cancel"),
                id="defer-options",
            )
            yield Input(
                placeholder="tomorrow | next week | YYYY-MM-DD | YYYY-MM-DD HH:MM",
                id="defer-until-input",
            )
            yield Static(
                "Defer Until accepts tomorrow, next week, YYYY-MM-DD, YYYY-MM-DD HH:MM.",
                id="defer-hint",
            )

    def on_mount(self) -> None:
        """Initialize modal state."""
        self.query_one("#defer-until-input", Input).display = False
        self.query_one("#defer-options", OptionList).focus()

    def action_cancel(self) -> None:
        """Close modal with no result."""
        self.dismiss(None)

    def action_cursor_down(self) -> None:
        """Move option cursor down."""
        self.query_one("#defer-options", OptionList).action_cursor_down()

    def action_cursor_up(self) -> None:
        """Move option cursor up."""
        self.query_one("#defer-options", OptionList).action_cursor_up()

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        """Handle defer mode selection."""
        mode = event.option.id
        if mode == "waiting":
            self.dismiss({"mode": "waiting"})
            return
        if mode == "someday":
            self.dismiss({"mode": "someday"})
            return
        if mode == "cancel":
            self.dismiss(None)
            return
        if mode == "until":
            input_widget = self.query_one("#defer-until-input", Input)
            input_widget.display = True
            input_widget.focus()
            input_widget.value = ""

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Submit raw defer-until input."""
        if event.input.id != "defer-until-input":
            return
        raw = event.value.strip()
        if not raw:
            self.notify(
                "Enter a date/time for Defer Until", severity="warning", timeout=2
            )
            return
        parsed = parse_defer_until(raw)
        if parsed is None:
            self.notify(
                "Invalid date/time. Use tomorrow, next week, YYYY-MM-DD, or YYYY-MM-DD HH:MM",
                severity="error",
                timeout=4,
            )
            return
        self.dismiss({"mode": "until", "defer_until": parsed.isoformat()})

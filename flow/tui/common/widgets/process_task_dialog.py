"""Reusable process-action chooser for inbox tasks."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import OptionList, Static
from textual.widgets.option_list import Option


class ProcessTaskDialog(ModalScreen[dict[str, str] | None]):
    """Modal for choosing how to process an inbox task."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
        Binding("j", "cursor_down", "Down", show=False),
        Binding("k", "cursor_up", "Up", show=False),
    ]

    DEFAULT_CSS = """
    ProcessTaskDialog {
        align: center middle;
    }

    #process-task-dialog {
        width: 56;
        height: auto;
        border: round $primary;
        background: $surface;
        padding: 1 2;
    }

    #process-task-title {
        content-align: center middle;
        margin-bottom: 1;
        text-style: bold;
    }
    """

    def compose(self) -> ComposeResult:
        with Vertical(id="process-task-dialog"):
            yield Static("Process task", id="process-task-title")
            yield OptionList(
                Option("Do now", id="do_now"),
                Option("Defer", id="defer"),
                Option("Add to project", id="add_to_project"),
                Option("Delete", id="delete"),
                Option("Cancel", id="cancel"),
                id="process-task-options",
            )

    def on_mount(self) -> None:
        """Focus the option list on open."""
        self.query_one("#process-task-options", OptionList).focus()

    def action_cancel(self) -> None:
        """Close modal with no result."""
        self.dismiss(None)

    def action_cursor_down(self) -> None:
        """Move option cursor down."""
        self.query_one("#process-task-options", OptionList).action_cursor_down()

    def action_cursor_up(self) -> None:
        """Move option cursor up."""
        self.query_one("#process-task-options", OptionList).action_cursor_up()

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        """Return selected process action."""
        action = event.option.id
        if action in {"do_now", "defer", "add_to_project", "delete"}:
            self.dismiss({"action": action})
            return
        self.dismiss(None)

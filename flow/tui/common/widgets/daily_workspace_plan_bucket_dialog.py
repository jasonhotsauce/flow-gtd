"""Keyboard-first chooser for adding an unplanned task back into today's plan."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import OptionList, Static
from textual.widgets.option_list import Option

from flow.models import Item
from flow.tui.common.base_screen import FlowModalScreen
from flow.tui.common.keybindings import with_modal_bindings


class DailyWorkspacePlanBucketDialog(FlowModalScreen[dict[str, str] | None]):
    """Ask whether an unplanned task should go to Top 3 or Bonus."""

    BINDINGS = with_modal_bindings()

    DEFAULT_CSS = """
    DailyWorkspacePlanBucketDialog {
        align: center middle;
    }

    #daily-workspace-plan-bucket-dialog {
        width: 60;
        height: auto;
        border: round #3f5a73;
        background: #121922;
        padding: 1 2;
    }

    #daily-workspace-plan-bucket-title {
        content-align: center middle;
        margin-bottom: 1;
        text-style: bold;
        color: #7ad0de;
    }

    #daily-workspace-plan-bucket-status {
        margin-bottom: 1;
        color: #b8c6d8;
    }
    """

    def __init__(self, item: Item) -> None:
        super().__init__()
        self._item = item

    def compose(self) -> ComposeResult:
        with Vertical(id="daily-workspace-plan-bucket-dialog"):
            yield Static(
                "Add task back to today's plan",
                id="daily-workspace-plan-bucket-title",
            )
            yield Static(
                self._item.title,
                id="daily-workspace-plan-bucket-status",
            )
            yield OptionList(
                Option("Top 3", id="top"),
                Option("Bonus", id="bonus"),
                Option("Cancel", id="cancel"),
                id="daily-workspace-plan-bucket-options",
            )

    def on_mount(self) -> None:
        """Focus the option list on open."""
        self.query_one(
            "#daily-workspace-plan-bucket-options", OptionList
        ).focus()

    def action_cancel(self) -> None:
        """Close modal with no result."""
        self.dismiss(None)

    def action_cursor_down(self) -> None:
        """Move chooser cursor down."""
        self.query_one(
            "#daily-workspace-plan-bucket-options", OptionList
        ).action_cursor_down()

    def action_cursor_up(self) -> None:
        """Move chooser cursor up."""
        self.query_one(
            "#daily-workspace-plan-bucket-options", OptionList
        ).action_cursor_up()

    def on_option_list_option_selected(
        self, event: OptionList.OptionSelected
    ) -> None:
        """Return the selected target bucket."""
        bucket = event.option.id
        if bucket in {"top", "bonus"}:
            self.dismiss({"bucket": str(bucket)})
            return
        self.dismiss(None)

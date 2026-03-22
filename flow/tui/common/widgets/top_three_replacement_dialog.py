"""Keyboard-first chooser for replacing a full Top 3 slot."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import OptionList, Static
from textual.widgets.option_list import Option

from flow.models import Item
from flow.tui.common.base_screen import FlowModalScreen
from flow.tui.common.keybindings import with_modal_bindings


class TopThreeReplacementDialog(FlowModalScreen[dict[str, str] | None]):
    """Prompt the user to choose which Top 3 item should be demoted."""

    BINDINGS = with_modal_bindings()

    DEFAULT_CSS = """
    TopThreeReplacementDialog {
        align: center middle;
    }

    #top-three-replacement-dialog {
        width: 64;
        height: auto;
        border: round #3f5a73;
        background: #121922;
        padding: 1 2;
    }

    #top-three-replacement-title {
        content-align: center middle;
        margin-bottom: 1;
        text-style: bold;
        color: #7ad0de;
    }

    #top-three-replacement-status {
        margin-bottom: 1;
        color: #b8c6d8;
    }
    """

    def __init__(self, top_items: list[Item], incoming_item: Item) -> None:
        super().__init__()
        self._top_items = top_items
        self._incoming_item = incoming_item

    def compose(self) -> ComposeResult:
        with Vertical(id="top-three-replacement-dialog"):
            yield Static("Choose Top 3 item to demote", id="top-three-replacement-title")
            yield Static(
                f"Make room for: {self._incoming_item.title}",
                id="top-three-replacement-status",
            )
            yield OptionList(id="top-three-replacement-options")

    def on_mount(self) -> None:
        """Render the current Top 3 and focus the chooser."""
        options = self.query_one("#top-three-replacement-options", OptionList)
        for index, item in enumerate(self._top_items, start=1):
            options.add_option(Option(f"Top {index}: {item.title}", id=item.id))
        options.focus()

    def action_cancel(self) -> None:
        """Close the chooser without applying a replacement."""
        self.dismiss(None)

    def action_cursor_down(self) -> None:
        """Move chooser cursor down."""
        self.query_one("#top-three-replacement-options", OptionList).action_cursor_down()

    def action_cursor_up(self) -> None:
        """Move chooser cursor up."""
        self.query_one("#top-three-replacement-options", OptionList).action_cursor_up()

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        """Return the chosen Top 3 item id."""
        demote_item_id = event.option.id
        if not demote_item_id:
            self.dismiss(None)
            return
        self.dismiss({"demote_item_id": demote_item_id})

"""Inbox screen: capture triage and list."""

from textual.app import ComposeResult
from textual.containers import Container, Vertical
from textual.screen import Screen
from textual.widgets import Footer, Header, OptionList, Static
from textual.widgets.option_list import Option

from flow.core.engine import Engine


class InboxScreen(Screen):
    """Screen showing inbox items. Default landing for TUI."""

    CSS_PATH = "inbox.tcss"

    BINDINGS = [
        ("q", "app.quit", "Quit"),
        ("j", "cursor_down", "Down"),
        ("k", "cursor_up", "Up"),
        ("enter", "process_item", "Process"),
        ("d", "delete_item", "Delete"),
        ("p", "go_process", "Process All"),
        ("a", "go_action", "Actions"),
        ("r", "go_review", "Review"),
        ("?", "show_help", "Help"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._engine = Engine()
        self._items: list = []

    def compose(self) -> ComposeResult:
        yield Header()
        with Container(id="inbox-header"):
            yield Static("📥 Inbox", id="inbox-title")
            yield Static("", id="inbox-count")
        with Container(id="inbox-stats"):
            yield Static("", id="inbox-stats-content")
        with Container(id="inbox-list-container"):
            yield OptionList(id="inbox-list")
        with Vertical(id="inbox-empty"):
            yield Static("📭", id="inbox-empty-icon")
            yield Static("Your inbox is empty!", id="inbox-empty-text")
            yield Static(
                "Use 'flow c <text>' to capture new items", id="inbox-empty-hint"
            )
        with Container(id="inbox-help"):
            yield Static(
                "j/k: Navigate │ Enter: Process │ d: Delete │ p: Process All │ a: Actions │ r: Review",
                id="inbox-help-text",
            )
        yield Footer()

    def on_mount(self) -> None:
        """Load inbox items on mount."""
        self._refresh_list()

    def _refresh_list(self) -> None:
        """Refresh the inbox list from database."""
        self._items = self._engine.list_inbox()
        opt_list = self.query_one("#inbox-list", OptionList)
        opt_list.clear_options()

        empty_container = self.query_one("#inbox-empty", Vertical)
        list_container = self.query_one("#inbox-list-container", Container)
        count_widget = self.query_one("#inbox-count", Static)
        stats_widget = self.query_one("#inbox-stats-content", Static)

        if not self._items:
            empty_container.display = True
            list_container.display = False
            count_widget.update("")
            stats_widget.update("")
        else:
            empty_container.display = False
            list_container.display = True
            count_widget.update(f"({len(self._items)} items)")

            # Calculate stats
            today_count = sum(1 for it in self._items if self._is_today(it))
            stats_widget.update(
                f"📊 Total: {len(self._items)} │ 🆕 Today: {today_count}"
            )

            for i, item in enumerate(self._items):
                # Truncate and format title
                title = item.title[:65] + "..." if len(item.title) > 65 else item.title
                # Add visual indicator for new items
                bullet = "●" if self._is_today(item) else "○"
                opt_list.add_option(Option(f" {bullet}  {title}", id=str(i)))

    def _is_today(self, item) -> bool:
        """Check if item was created today."""
        from datetime import date

        if hasattr(item, "created_at") and item.created_at:
            try:
                return item.created_at.date() == date.today()
            except (AttributeError, TypeError):
                pass
        return False

    def action_cursor_down(self) -> None:
        """Move cursor down in list."""
        opt_list = self.query_one("#inbox-list", OptionList)
        opt_list.action_cursor_down()

    def action_cursor_up(self) -> None:
        """Move cursor up in list."""
        opt_list = self.query_one("#inbox-list", OptionList)
        opt_list.action_cursor_up()

    def action_process_item(self) -> None:
        """Process the selected item."""
        if not self._items:
            return
        opt_list = self.query_one("#inbox-list", OptionList)
        idx = opt_list.highlighted
        if idx is not None and 0 <= idx < len(self._items):
            self.notify(f"Processing: {self._items[idx].title[:40]}...", timeout=2)

    def action_delete_item(self) -> None:
        """Delete the selected item."""
        if not self._items:
            return
        opt_list = self.query_one("#inbox-list", OptionList)
        idx = opt_list.highlighted
        if idx is not None and 0 <= idx < len(self._items):
            item = self._items[idx]
            self._engine.archive_item(item.id)
            self.notify(
                f"🗑️ Archived: {item.title[:30]}...", severity="warning", timeout=2
            )
            self._refresh_list()

    def action_go_process(self) -> None:
        """Navigate to process screen."""
        from flow.tui.screens.process.process import ProcessScreen

        self.app.push_screen(ProcessScreen())

    def action_go_action(self) -> None:
        """Navigate to action screen."""
        from flow.tui.screens.action.action import ActionScreen

        self.app.push_screen(ActionScreen())

    def action_go_review(self) -> None:
        """Navigate to review screen."""
        from flow.tui.screens.review.review import ReviewScreen

        self.app.push_screen(ReviewScreen())

    def action_show_help(self) -> None:
        """Show help toast."""
        self.notify(
            "📖 Keyboard shortcuts:\n"
            "j/k: Navigate │ Enter: Process item\n"
            "d: Delete │ p: Process All\n"
            "a: Actions │ r: Review │ q: Quit",
            title="Help",
            timeout=5,
        )

"""Inbox screen: capture triage and list."""

from rich.text import Text

from textual.binding import Binding
from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical, ScrollableContainer
from textual.screen import Screen
from textual.widgets import Footer, Header, OptionList, Static
from textual.widgets.option_list import Option

from flow.core.engine import Engine
from flow.models import Item


class InboxScreen(Screen):
    """Screen showing inbox items. Default landing for TUI."""

    CSS_PATH = "inbox.tcss"

    BINDINGS = [
        ("q", "app.quit", "Quit"),
        ("j", "cursor_down", "Down"),
        ("k", "cursor_up", "Up"),
        ("enter", "process_item", "Process"),
        ("d", "delete_item", "Delete"),
        ("p", "go_process", "Process"),
        Binding("a", "go_action", "Actions", show=False),
        Binding("r", "go_review", "Review", show=False),
        Binding("P", "go_projects", "Projects", show=False),
        ("?", "show_help", "Help"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._engine = Engine()
        self._items: list[Item] = []

    def compose(self) -> ComposeResult:
        yield Header()
        with Container(id="inbox-header"):
            yield Static("📥 Inbox", id="inbox-title")
            yield Static("", id="inbox-count")
        with Container(id="inbox-stats"):
            yield Static("", id="inbox-stats-content")
        with Horizontal(id="inbox-content"):
            with Vertical(id="inbox-left"):
                with Container(id="inbox-list-container"):
                    yield OptionList(id="inbox-list")
            with Vertical(id="inbox-right"):
                yield Static("📄 Task", id="inbox-detail-title")
                with ScrollableContainer(id="inbox-detail-scroll"):
                    yield Static("", id="inbox-detail-body")
                yield Static("", id="inbox-detail-tags")
        with Vertical(id="inbox-empty"):
            yield Static("📭", id="inbox-empty-icon")
            yield Static("Your inbox is empty!", id="inbox-empty-text")
            yield Static(
                "Use 'flow c <text>' to capture new items", id="inbox-empty-hint"
            )
        with Container(id="inbox-help"):
            yield Static(
                "j/k: Navigate │ Enter: Process │ d: Delete │ p: Process │ ?: Help",
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
        content_container = self.query_one("#inbox-content", Horizontal)
        count_widget = self.query_one("#inbox-count", Static)
        stats_widget = self.query_one("#inbox-stats-content", Static)

        if not self._items:
            empty_container.display = True
            content_container.display = False
            count_widget.update("")
            stats_widget.update("")
            self._update_detail_panel(None)
        else:
            empty_container.display = False
            content_container.display = True
            count_widget.update(f"({len(self._items)} items)")

            # Calculate stats
            today_count = sum(1 for it in self._items if self._is_today(it))
            stats_widget.update(
                f"📊 Total: {len(self._items)} │ 🆕 Today: {today_count}"
            )

            # List: short one-line preview; full text in detail panel
            for i, item in enumerate(self._items):
                preview = item.title.split("\n")[0].strip()
                if len(preview) > 48:
                    preview = preview[:48] + "…"
                bullet = "●" if self._is_today(item) else "○"
                opt_list.add_option(Option(f" {bullet}  {preview}", id=str(i)))

            # Show first item's full text and tags in detail panel
            try:
                opt_list.action_first()
                idx = opt_list.highlighted
                if idx is not None and 0 <= idx < len(self._items):
                    self._update_detail_panel(self._items[idx])
            except Exception:
                self._update_detail_panel(self._items[0] if self._items else None)
            try:
                opt_list.focus()
            except (ValueError, KeyError):
                pass

    def _is_today(self, item: Item) -> bool:
        """Check if item was created today."""
        from datetime import date

        if hasattr(item, "created_at") and item.created_at:
            try:
                return item.created_at.date() == date.today()
            except (AttributeError, TypeError):
                pass
        return False

    def _update_detail_panel(self, item: Item | None) -> None:
        """Update the right-hand detail panel with full task text and tags."""
        body = self.query_one("#inbox-detail-body", Static)
        tags_widget = self.query_one("#inbox-detail-tags", Static)
        if item is None:
            body.update("Select a task to view full text and tags.")
            tags_widget.update("")
        else:
            body.update(item.title)
            if item.context_tags:
                tag_text = Text()
                tag_text.append("Tags: ", style="dim")
                tag_text.append(", ".join(item.context_tags), style="bold #a78bfa")
                tags_widget.update(tag_text)
            else:
                tags_widget.update("")

    def on_option_list_option_highlighted(
        self, event: OptionList.OptionHighlighted
    ) -> None:
        """Update detail panel when selection changes."""
        try:
            idx = int(event.option.id)
        except (ValueError, TypeError):
            idx = -1
        if 0 <= idx < len(self._items):
            self._update_detail_panel(self._items[idx])

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

    def action_go_projects(self) -> None:
        """Navigate to projects screen."""
        from flow.tui.screens.projects.projects import ProjectsScreen

        self.app.push_screen(ProjectsScreen())

    def action_show_help(self) -> None:
        """Show help toast."""
        self.notify(
            "j/k: Navigate │ Enter: Process │ d: Delete │ p: Process\n"
            "a: Actions │ r: Review │ P: Projects │ q: Quit",
            title="Help",
            timeout=5,
        )

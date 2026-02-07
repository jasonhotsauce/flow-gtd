"""Review screen: stale items, someday suggestions, weekly report."""

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Footer, Header, OptionList, Static
from textual.widgets.option_list import Option

from flow.core.engine import Engine


class ReviewScreen(Screen):
    """Weekly review: Stale (archive), Someday (resurface), Report."""

    CSS_PATH = "review.tcss"

    BINDINGS = [
        ("q", "app.quit", "Quit"),
        ("escape", "app.pop_screen", "Back"),
        ("j", "cursor_down", "Down"),
        ("k", "cursor_up", "Up"),
        ("a", "archive", "Archive"),
        ("r", "resurface", "Resurface"),
        ("1", "show_stale", "Stale"),
        ("2", "show_someday", "Someday"),
        ("3", "show_report", "Report"),
        ("tab", "next_section", "Next"),
        ("i", "go_inbox", "Inbox"),
        ("?", "show_help", "Help"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._engine = Engine()
        self._mode = "stale"  # stale | someday | report
        self._stale: list = []
        self._someday: list = []

    def compose(self) -> ComposeResult:
        yield Header()
        with Container(id="review-header"):
            yield Static("📅 Weekly Review", id="review-main-title")
        with Horizontal(id="review-tabs"):
            yield Static("1️⃣ Stale", id="tab-stale", classes="mode-tab -active")
            yield Static("2️⃣ Someday", id="tab-someday", classes="mode-tab")
            yield Static("3️⃣ Report", id="tab-report", classes="mode-tab")
        with Container(id="review-section"):
            yield Static("", id="review-title")
            yield Static("", id="review-subtitle")
        with Container(id="review-content"):
            yield OptionList(id="review-list")
            yield Static("", id="review-detail")
        yield Footer()

    def on_mount(self) -> None:
        """Initialize review screen."""
        self._show_stale()

    def _update_tabs(self) -> None:
        """Update tab visual states."""
        tab_stale = self.query_one("#tab-stale", Static)
        tab_someday = self.query_one("#tab-someday", Static)
        tab_report = self.query_one("#tab-report", Static)

        # Reset all tabs
        tab_stale.remove_class("-active")
        tab_someday.remove_class("-active")
        tab_report.remove_class("-active")

        # Activate current tab
        if self._mode == "stale":
            tab_stale.add_class("-active")
        elif self._mode == "someday":
            tab_someday.add_class("-active")
        else:
            tab_report.add_class("-active")

    def _show_stale(self) -> None:
        """Show stale items view."""
        self._mode = "stale"
        self._update_tabs()
        self._stale = self._engine.get_stale(days=14)

        title = self.query_one("#review-title", Static)
        subtitle = self.query_one("#review-subtitle", Static)
        title.update(f"⚠️  Stale Items ({len(self._stale)})")
        subtitle.update("Items untouched for 14+ days. Archive or refresh them.")

        opt_list = self.query_one("#review-list", OptionList)
        detail = self.query_one("#review-detail", Static)
        opt_list.display = True
        detail.display = False

        opt_list.clear_options()
        if not self._stale:
            opt_list.add_option(
                Option("  ✨  No stale items! Great job staying current.", id="-1")
            )
        else:
            for i, item in enumerate(self._stale):
                title_text = (
                    item.title[:55] + "..." if len(item.title) > 55 else item.title
                )
                days = self._get_days_old(item)
                opt_list.add_option(
                    Option(f"  🕐  {title_text} ({days}d)", id=f"stale-{i}")
                )

    def _show_someday(self) -> None:
        """Show someday suggestions view."""
        self._mode = "someday"
        self._update_tabs()
        self._someday = self._engine.get_someday_suggestions()

        title = self.query_one("#review-title", Static)
        subtitle = self.query_one("#review-subtitle", Static)
        title.update(f"💭  Someday/Maybe ({len(self._someday)})")
        subtitle.update("Items parked for later. Resurface ones that are now relevant.")

        opt_list = self.query_one("#review-list", OptionList)
        detail = self.query_one("#review-detail", Static)
        opt_list.display = True
        detail.display = False

        opt_list.clear_options()
        if not self._someday:
            opt_list.add_option(Option("  📭  No someday items.", id="-1"))
        else:
            for i, item in enumerate(self._someday):
                title_text = (
                    item.title[:55] + "..." if len(item.title) > 55 else item.title
                )
                opt_list.add_option(Option(f"  💤  {title_text}", id=f"someday-{i}"))

    def _show_report(self) -> None:
        """Show weekly report view."""
        self._mode = "report"
        self._update_tabs()
        report = self._engine.weekly_report()

        title = self.query_one("#review-title", Static)
        subtitle = self.query_one("#review-subtitle", Static)
        title.update("📊  Weekly Report")
        subtitle.update("Completed this week.")

        opt_list = self.query_one("#review-list", OptionList)
        detail = self.query_one("#review-detail", Static)
        opt_list.display = False
        detail.display = True

        # Format report with visual elements
        formatted_report = self._format_report(report)
        detail.update(formatted_report)

    def _format_report(self, report: str) -> str:
        """Format the report with visual elements."""
        if not report:
            return (
                "📊 Weekly Summary\n"
                "═══════════════════════════════════════\n\n"
                "  No data available for this week.\n\n"
                "  Start capturing tasks to see your stats!\n"
            )

        # Add visual header
        lines = [
            "📊 Weekly Summary",
            "═══════════════════════════════════════",
            "",
        ]
        lines.append(report)
        lines.extend(
            [
                "",
                "───────────────────────────────────────",
                "💡 Tip: Review weekly to stay on track!",
            ]
        )
        return "\n".join(lines)

    def _get_days_old(self, item) -> int:
        """Calculate days since item was last updated."""
        from datetime import date, datetime

        if hasattr(item, "updated_at") and item.updated_at:
            try:
                if isinstance(item.updated_at, datetime):
                    delta = date.today() - item.updated_at.date()
                    return delta.days
            except (AttributeError, TypeError):
                pass
        return 14  # Default to threshold

    def action_cursor_down(self) -> None:
        """Move cursor down."""
        if self._mode != "report":
            opt_list = self.query_one("#review-list", OptionList)
            opt_list.action_cursor_down()

    def action_cursor_up(self) -> None:
        """Move cursor up."""
        if self._mode != "report":
            opt_list = self.query_one("#review-list", OptionList)
            opt_list.action_cursor_up()

    def action_archive(self) -> None:
        """Archive the selected stale item."""
        if self._mode != "stale" or not self._stale:
            return
        opt_list = self.query_one("#review-list", OptionList)
        try:
            idx = opt_list.highlighted
            if idx is not None and 0 <= idx < len(self._stale):
                item = self._stale[idx]
                self._engine.archive_item(item.id)
                self.notify(
                    f"🗑️ Archived: {item.title[:30]}...",
                    severity="warning",
                    timeout=2,
                )
                self._show_stale()
        except (ValueError, TypeError, IndexError):
            pass

    def action_resurface(self) -> None:
        """Resurface the selected someday item."""
        if self._mode != "someday" or not self._someday:
            return
        opt_list = self.query_one("#review-list", OptionList)
        try:
            idx = opt_list.highlighted
            if idx is not None and 0 <= idx < len(self._someday):
                item = self._someday[idx]
                self._engine.resurface_item(item.id)
                self.notify(
                    f"🔄 Resurfaced: {item.title[:30]}...",
                    severity="information",
                    timeout=2,
                )
                self._show_someday()
        except (ValueError, TypeError, IndexError):
            pass

    def action_next_section(self) -> None:
        """Cycle to next section."""
        if self._mode == "stale":
            self._show_someday()
        elif self._mode == "someday":
            self._show_report()
        else:
            self._show_stale()

    def action_show_stale(self) -> None:
        """Show stale items."""
        self._show_stale()

    def action_show_someday(self) -> None:
        """Show someday items."""
        self._show_someday()

    def action_show_report(self) -> None:
        """Show weekly report."""
        self._show_report()

    def action_go_inbox(self) -> None:
        """Navigate to inbox."""
        from flow.tui.screens.inbox.inbox import InboxScreen

        self.app.push_screen(InboxScreen())

    def action_show_help(self) -> None:
        """Show help toast."""
        self.notify(
            "📖 Keyboard shortcuts:\n"
            "1/2/3: Switch sections │ Tab: Cycle\n"
            "a: Archive │ r: Resurface\n"
            "j/k: Navigate │ Esc: Back │ q: Quit",
            title="Help",
            timeout=5,
        )

"""Projects screen: list active projects with next-action preview (GTD review)."""

import asyncio
from typing import Optional

from rich.text import Text

from textual.binding import Binding
from textual.app import ComposeResult
from textual.containers import Container, Horizontal, ScrollableContainer, Vertical
from textual.widgets import Footer, Header, OptionList, Static
from textual.widgets.option_list import Option

from flow.core.engine import Engine
from flow.models import Item
from flow.tui.common.base_screen import FlowScreen
from flow.tui.common.keybindings import with_global_bindings


class ProjectsScreen(FlowScreen):
    """Screen showing active projects and next-action preview. Enter opens project detail."""

    CSS_PATH = ["../../common/ops_tokens.tcss", "projects.tcss"]

    BINDINGS = with_global_bindings(
        ("enter", "open_project", "Open"),
        ("1", "focus_list_panel", "List"),
        ("2", "focus_detail_panel", "Detail"),
        ("l", "focus_list_panel", "List"),
        ("d", "focus_detail_panel", "Detail"),
        Binding("a", "go_action", "Actions", show=False),
        Binding("i", "go_inbox", "Inbox", show=False),
        Binding("r", "go_review", "Review", show=False),
    )

    def __init__(self) -> None:
        super().__init__()
        self._engine = Engine()
        self._projects: list[Item] = []
        self._project_actions: list[list[Item]] = []

    def compose(self) -> ComposeResult:
        yield Header()
        with Container(id="ops-status-strip"):
            yield Static("PROJECTS  |  Active outcomes and next actions", id="ops-status-text")
        with Container(id="projects-header"):
            yield Static("Projects", id="projects-title")
            yield Static("", id="projects-count")
        with Horizontal(id="projects-content"):
            with Vertical(id="projects-left"):
                yield Static("[1] Project List (l)", id="projects-list-title")
                with Container(id="projects-list-container"):
                    yield OptionList(id="projects-list")
            with Vertical(id="projects-right"):
                yield Static("[2] Project Detail (d)", id="projects-detail-section-project")
                yield Static("", id="projects-detail-project-name")
                yield Static("Suggested next action", id="projects-detail-section-next")
                with ScrollableContainer(id="projects-detail-next-scroll"):
                    yield Static("", id="projects-detail-next-body")
                yield Static("", id="projects-detail-tags")
                yield Static("Tasks", id="projects-detail-section-tasks")
                with ScrollableContainer(id="projects-detail-tasks-scroll"):
                    yield Static("", id="projects-detail-tasks-list")
        with Vertical(id="projects-empty"):
            yield Static(
                "No projects. Use Process (Stage 2) to cluster tasks into projects.",
                id="projects-empty-text",
            )
        with Container(id="projects-help"):
            yield Static(
                "j/k: Navigate │ 1/2 or l/d: Panels │ Enter: Open project │ Esc: Back │ ?: Help",
                id="projects-help-text",
            )
        yield Footer()

    def on_mount(self) -> None:
        """Load projects on mount."""
        asyncio.create_task(self._refresh_list_async())

    def on_screen_resume(self) -> None:
        """Refresh project list when returning from child screens."""
        asyncio.create_task(self._refresh_list_async())

    async def _refresh_list_async(self) -> None:
        """Load project list and actions per project in background (no main-thread DB)."""
        try:
            rows = await asyncio.to_thread(
                self._engine.list_projects_with_actions
            )
            if not self.is_mounted:
                return
            self._projects = [proj for proj, _ in rows]
            self._project_actions = [actions for _, actions in rows]
            self._apply_list()
        except Exception:
            if self.is_mounted:
                self._projects = []
                self._project_actions = []
                self._apply_list()
                self.notify("Failed to load projects", severity="error", timeout=3)

    def _apply_list(self) -> None:
        """Render project list from in-memory data (no DB calls)."""
        opt_list = self.query_one("#projects-list", OptionList)
        opt_list.clear_options()

        empty = self.query_one("#projects-empty", Vertical)
        content = self.query_one("#projects-content", Horizontal)
        count_widget = self.query_one("#projects-count", Static)

        if not self._projects:
            empty.display = True
            content.display = False
            count_widget.update("")
        else:
            empty.display = False
            content.display = True
            count_widget.update(f"({len(self._projects)} projects)")

            for i, proj in enumerate(self._projects):
                actions = self._project_actions[i] if i < len(self._project_actions) else []
                next_action = actions[0] if actions else None
                if next_action:
                    preview = next_action.title.split("\n")[0].strip()
                    if len(preview) > 40:
                        preview = preview[:40] + "…"
                    line = f"  📁  {proj.title}  →  next: {preview}"
                else:
                    line = f"  📁  {proj.title}  →  No next action"
                opt_list.add_option(Option(line, id=str(i)))

            try:
                opt_list.action_first()
                self._update_detail_panel(0)
                opt_list.focus()
            except (ValueError, KeyError):
                self._update_detail_panel(0 if self._projects else None)

    def _update_detail_panel(self, idx: Optional[int]) -> None:
        """Update right panel: project name, suggested next action (full text), and task list."""
        name_widget = self.query_one("#projects-detail-project-name", Static)
        next_body = self.query_one("#projects-detail-next-body", Static)
        tags_widget = self.query_one("#projects-detail-tags", Static)
        tasks_list_widget = self.query_one("#projects-detail-tasks-list", Static)

        if idx is None or idx < 0 or idx >= len(self._projects):
            name_widget.update("—")
            next_body.update("Select a project to view details and next action.")
            tags_widget.update("")
            tasks_list_widget.update("")
            return

        proj = self._projects[idx]
        actions = self._project_actions[idx] if idx < len(self._project_actions) else []
        next_action = actions[0] if actions else None

        name_widget.update(proj.title)

        if next_action:
            next_body.update(next_action.title)
            if next_action.context_tags:
                tag_text = Text()
                tag_text.append("Tags: ", style="dim")
                tag_text.append(", ".join(next_action.context_tags), style="bold #a78bfa")
                tags_widget.update(tag_text)
            else:
                tags_widget.update("")
        else:
            next_body.update("No next action defined.")
            tags_widget.update("")

        # Task list: numbered, first one marked as suggested next action
        if not actions:
            tasks_list_widget.update("No tasks.")
        else:
            lines: list[str] = []
            for j, task in enumerate(actions):
                first_line = task.title.split("\n")[0].strip()
                if len(first_line) > 60:
                    first_line = first_line[:60] + "…"
                if j == 0:
                    lines.append(f"  → {j + 1}. {first_line}  [next]")
                else:
                    lines.append(f"    {j + 1}. {first_line}")
            tasks_list_widget.update("\n".join(lines))

    def on_option_list_option_highlighted(
        self, event: OptionList.OptionHighlighted
    ) -> None:
        """Update detail panel when selection changes."""
        try:
            idx = int(event.option.id)
        except (ValueError, TypeError):
            idx = -1
        if 0 <= idx < len(self._projects):
            self._update_detail_panel(idx)

    def action_cursor_down(self) -> None:
        """Move cursor down."""
        self.query_one("#projects-list", OptionList).action_cursor_down()

    def action_cursor_up(self) -> None:
        """Move cursor up."""
        self.query_one("#projects-list", OptionList).action_cursor_up()

    def action_focus_list_panel(self) -> None:
        """Focus the project list panel."""
        self.query_one("#projects-list", OptionList).focus()

    def action_focus_detail_panel(self) -> None:
        """Focus the project detail panel."""
        self.query_one("#projects-detail-next-scroll", ScrollableContainer).focus()

    def action_open_project(self) -> None:
        """Open selected project (push project detail screen)."""
        if not self._projects:
            return
        opt_list = self.query_one("#projects-list", OptionList)
        idx = opt_list.highlighted
        if idx is not None and 0 <= idx < len(self._projects):
            from flow.tui.screens.projects.project_detail import ProjectDetailScreen

            self.app.push_screen(ProjectDetailScreen(self._projects[idx]))

    def action_go_action(self) -> None:
        """Navigate to Actions."""
        from flow.tui.screens.action.action import ActionScreen

        self.app.push_screen(ActionScreen())

    def action_go_inbox(self) -> None:
        """Navigate to Inbox."""
        from flow.tui.screens.inbox.inbox import InboxScreen

        self.app.push_screen(InboxScreen())

    def action_go_review(self) -> None:
        """Navigate to Review."""
        from flow.tui.screens.review.review import ReviewScreen

        self.app.push_screen(ReviewScreen())

    def action_show_help(self) -> None:
        """Show help toast."""
        self.notify(
            "j/k: Navigate │ Enter: Open project\n"
            "a: Actions │ i: Inbox │ r: Review │ Esc: Back │ q: Quit",
            title="Help",
            timeout=5,
        )

    def action_go_back(self) -> None:
        """Map global back action to existing pop-screen behavior."""
        self.action_pop_screen()

    def action_pop_screen(self) -> None:
        """Pop screen or quit if only screen."""
        if len(self.app.screen_stack) <= 2:
            self.app.exit()
        else:
            self.app.pop_screen()

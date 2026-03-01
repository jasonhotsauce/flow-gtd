"""Focus screen: context-aware tunnel vision for deep work."""

import asyncio
from typing import Optional

from textual.app import ComposeResult
from textual.containers import Container, Vertical
from textual.events import Resize
from textual.widgets import Footer, Header, Static

from flow.core.focus import FocusDispatcher
from flow.models import Item
from flow.tui.common.base_screen import FlowScreen
from flow.tui.common.keybindings import with_global_bindings
from flow.tui.common.widgets.empty_state import EmptyStateRenderer
from flow.tui.common.widgets.sidecar import ResourceContextPanel


class FocusScreen(FlowScreen):
    """Focus Mode: AI selects best task based on available time window.

    Layout:
    - Header: Focus Mode indicator + time window info
    - Center: Current task title (large, centered)
    - Metadata: Duration badge + tags
    - Footer: Actions (Complete, Skip, Exit)
    """

    CSS_PATH = ["../../common/ops_tokens.tcss", "focus.tcss"]

    BINDINGS = with_global_bindings(
        ("space", "complete_task", "Complete"),
        ("s", "skip_task", "Skip"),
        ("r", "refresh", "Refresh"),
        ("n", "go_to_inbox_new_task", "New Inbox Task"),
    )

    def __init__(self) -> None:
        super().__init__()
        self._dispatcher = FocusDispatcher()
        self._current_task: Optional[Item] = None
        self._loading: bool = False
        self._empty_state_renderer = EmptyStateRenderer()

    def compose(self) -> ComposeResult:
        yield Header()
        with Container(id="ops-status-strip"):
            yield Static("FOCUS  |  Select one best task for current time window", id="ops-status-text")

        # Focus header with mode indicator
        with Container(id="focus-header"):
            yield Static("", id="focus-icon")
            yield Static("Focus Mode", id="focus-title")
            yield Static("", id="focus-mode-badge")

        # Time window info
        with Container(id="focus-time-info"):
            yield Static("", id="focus-time-text")

        # Main task display area
        with Vertical(id="focus-main"):
            with Container(id="focus-task-container"):
                yield Static("", id="focus-task-title")

            with Container(id="focus-task-meta"):
                yield Static("", id="focus-duration-badge")
                yield Static("", id="focus-tags")

            yield ResourceContextPanel(id="focus-resources")

        # Empty state
        with Vertical(id="focus-empty"):
            yield Static("", id="focus-empty-content")

        with Container(id="ops-keyhint"):
            yield Static(
                "Space: Complete  |  s: Skip  |  r: Refresh  |  n: New Inbox Task  |  Esc: Back  |  ?: Help",
                id="ops-keyhint-text",
            )

        yield Footer()

    def on_mount(self) -> None:
        """Initialize focus mode on mount."""
        asyncio.create_task(self._refresh_task_async())

    def on_resize(self, _event: Resize) -> None:
        """Re-render empty state to maintain centered layout."""
        if self.is_mounted and self._current_task is None:
            self._render_empty_state()

    def _empty_state_viewport(self) -> tuple[int, int]:
        """Return available viewport for centered empty-state layout."""
        container = self.query_one("#focus-empty", Vertical)
        container_size = getattr(container, "size", None)
        container_width = getattr(container_size, "width", 0) if container_size else 0
        container_height = (
            getattr(container_size, "height", 0) if container_size else 0
        )
        screen_width = max(getattr(self.size, "width", 0), 0)
        screen_height = max(getattr(self.size, "height", 0), 0)
        raw_width = (container_width or screen_width or 80) - 2
        raw_height = (container_height or screen_height or 24) - 2
        width = min(max(raw_width, 24), 240)
        height = min(max(raw_height, 8), 80)
        return width, height

    def _render_empty_state(self) -> None:
        """Render Focus empty state with dynamic center padding."""
        content = self.query_one("#focus-empty-content", Static)
        view_width, view_height = self._empty_state_viewport()
        content.update(
            self._empty_state_renderer.render(
                view_width=view_width,
                view_height=view_height,
                status_header="No Active Tasks",
                cta_key="N",
                cta_action="Create New Inbox Task",
            )
        )

    async def _refresh_task_async(self) -> None:
        """Refresh the current task and UI asynchronously.

        Runs calendar queries in a background thread to avoid blocking TUI.
        """
        if self._loading:
            return
        self._loading = True

        try:
            # Run dispatcher operations in background thread (EventKit can be slow)
            self._current_task = await asyncio.to_thread(self._dispatcher.select_task)
            mode = await asyncio.to_thread(self._dispatcher.get_mode_indicator)
            time_info = await asyncio.to_thread(self._dispatcher.get_window_description)

            # Update UI on main thread
            self._update_ui(mode, time_info)

            # Load resources for current task off main thread
            if self._current_task is not None and self.is_mounted:
                try:
                    hits = await asyncio.to_thread(
                        self._dispatcher.get_semantic_resources_for_task,
                        self._current_task,
                        3,
                    )
                    if self.is_mounted:
                        sidecar = self.query_one("#focus-resources", ResourceContextPanel)
                        if hits:
                            sidecar.show_semantic_hits(
                                hits, task_tags=self._current_task.context_tags
                            )
                        else:
                            resources = await asyncio.to_thread(
                                self._dispatcher.get_resources_for_task, self._current_task
                            )
                            sidecar.show_resources(
                                resources, task_tags=self._current_task.context_tags
                            )
                except (IOError, ValueError, RuntimeError):
                    if self.is_mounted:
                        self.query_one(
                            "#focus-resources", ResourceContextPanel
                        ).show_error("Failed to load resources")

        except Exception as e:
            # Handle EventKit or other failures gracefully
            self.notify(
                f"Error loading focus mode: {str(e)[:50]}",
                severity="error",
                timeout=3,
            )
            self._current_task = None
            self._update_ui("Standard", "Calendar unavailable")

        finally:
            self._loading = False

    def _update_ui(self, mode: str, time_info: str) -> None:
        """Update all UI elements with current state.

        Args:
            mode: Current focus mode indicator.
            time_info: Time window description.
        """
        # Guard against updates after screen unmount
        if not self.is_mounted:
            return

        # Update UI elements
        icon_widget = self.query_one("#focus-icon", Static)
        mode_badge = self.query_one("#focus-mode-badge", Static)
        time_text = self.query_one("#focus-time-text", Static)
        task_title = self.query_one("#focus-task-title", Static)
        duration_badge = self.query_one("#focus-duration-badge", Static)
        tags_widget = self.query_one("#focus-tags", Static)
        resources_panel = self.query_one("#focus-resources", ResourceContextPanel)

        main_container = self.query_one("#focus-main", Vertical)
        empty_container = self.query_one("#focus-empty", Vertical)

        # Update header info based on mode
        if "Quick" in mode:
            icon_widget.update("[bold yellow]>>>[/]")
            mode_badge.update("[yellow]Quick Wins[/]")
        elif "Deep" in mode:
            icon_widget.update("[bold blue]|||[/]")
            mode_badge.update("[blue]Deep Work[/]")
        else:
            icon_widget.update("[bold green]>>>[/]")
            mode_badge.update("[green]Standard[/]")

        time_text.update(time_info)

        if self._current_task is None:
            # Show empty state
            main_container.display = False
            empty_container.display = True
            self._render_empty_state()
            resources_panel.display = False
            resources_panel.clear_resources()
            return

        # Show task
        main_container.display = True
        empty_container.display = False
        resources_panel.display = True
        resources_panel.update(
            "🔗 Related Resources\n"
            "────────────────────────────\n\n"
            "Loading resources for this task…"
        )

        # Update task title
        title = self._current_task.title
        task_title.update(f"[bold]{title}[/]")

        # Update duration badge
        duration = self._current_task.estimated_duration
        if duration is not None:
            if duration <= 15:
                duration_badge.update(f"[green]{duration}m[/]")
            elif duration <= 30:
                duration_badge.update(f"[yellow]{duration}m[/]")
            else:
                duration_badge.update(f"[blue]{duration}m[/]")
        else:
            duration_badge.update("[dim]~[/]")

        # Update tags
        tags = self._current_task.context_tags
        if tags:
            tags_str = " ".join(f"[cyan]#{tag}[/]" for tag in tags)
            tags_widget.update(tags_str)
        else:
            tags_widget.update("")

    def action_complete_task(self) -> None:
        """Complete the current task and advance to next."""
        if self._current_task is None:
            self.notify("No task to complete", severity="warning", timeout=2)
            return

        # Capture task info before async operation
        task_id = self._current_task.id
        task_title = self._current_task.title[:30]
        asyncio.create_task(self._complete_task_async(task_id, task_title))

    async def _complete_task_async(self, task_id: str, task_title: str) -> None:
        """Complete task asynchronously to avoid blocking TUI."""
        try:
            # Run DB operation in background thread
            await asyncio.to_thread(self._dispatcher.complete_task, task_id)
            self.notify(
                f"Completed: {task_title}...",
                severity="information",
                timeout=2,
            )
        except Exception as e:
            self.notify(f"Error completing task: {e}", severity="error", timeout=3)
            return
        await self._refresh_task_async()

    def action_skip_task(self) -> None:
        """Skip the current task and move to next."""
        if self._current_task is None:
            self.notify("No task to skip", severity="warning", timeout=2)
            return

        try:
            task_title = self._current_task.title[:30]
            self._dispatcher.skip_task(self._current_task.id)
            self.notify(
                f"Skipped: {task_title}...",
                severity="warning",
                timeout=2,
            )
            asyncio.create_task(self._refresh_task_async())
        except Exception as e:
            self.notify(f"Error skipping task: {e}", severity="error", timeout=3)

    def action_refresh(self) -> None:
        """Refresh task selection (useful after time passes)."""
        self._dispatcher.reset_skipped()
        asyncio.create_task(self._refresh_task_async())
        self.notify("Refreshed task selection", timeout=2)

    def action_go_to_inbox_new_task(self) -> None:
        """Navigate to Inbox and trigger startup quick-create."""
        from flow.tui.screens.inbox.inbox import InboxScreen

        self.app.push_screen(InboxScreen(startup_context={"start_new_task": True}))

    def action_go_back(self) -> None:
        """Return to previous screen."""
        self.app.pop_screen()

    def action_show_help(self) -> None:
        """Show help toast."""
        self.notify(
            "Focus Mode Help:\n"
            "[Space] Complete current task\n"
            "[S] Skip task (won't show again this session)\n"
            "[R] Refresh selection\n"
            "[N] Create new inbox task\n"
            "[Esc] Exit focus mode",
            title="Help",
            timeout=5,
        )

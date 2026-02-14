"""Reusable project picker dialog for assigning tasks."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Input, OptionList, Static
from textual.widgets.option_list import Option

from flow.models import Item


class ProjectPickerDialog(ModalScreen[dict[str, str] | None]):
    """Modal for picking an active project."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
        Binding("j", "cursor_down", "Down", show=False),
        Binding("k", "cursor_up", "Up", show=False),
    ]

    DEFAULT_CSS = """
    ProjectPickerDialog {
        align: center middle;
    }

    #project-picker-dialog {
        width: 72;
        height: auto;
        max-height: 24;
        border: round $primary;
        background: $surface;
        padding: 1 2;
    }

    #project-picker-title {
        content-align: center middle;
        margin-bottom: 1;
        text-style: bold;
    }

    #project-picker-search {
        margin-bottom: 1;
    }
    """

    def __init__(self, projects: list[Item]) -> None:
        super().__init__()
        self._projects = projects
        self._visible = projects

    def compose(self) -> ComposeResult:
        with Vertical(id="project-picker-dialog"):
            yield Static("Add to existing project", id="project-picker-title")
            yield Input(placeholder="Search projects...", id="project-picker-search")
            yield OptionList(id="project-picker-options")

    def on_mount(self) -> None:
        """Populate options and focus search box."""
        self._render_options()
        self.query_one("#project-picker-search", Input).focus()

    def _render_options(self) -> None:
        """Render currently visible project options."""
        options = self.query_one("#project-picker-options", OptionList)
        options.clear_options()
        for project in self._visible:
            options.add_option(Option(project.title, id=project.id))

    def action_cancel(self) -> None:
        """Close picker with no result."""
        self.dismiss(None)

    def action_cursor_down(self) -> None:
        """Move option cursor down."""
        self.query_one("#project-picker-options", OptionList).action_cursor_down()

    def action_cursor_up(self) -> None:
        """Move option cursor up."""
        self.query_one("#project-picker-options", OptionList).action_cursor_up()

    def on_input_changed(self, event: Input.Changed) -> None:
        """Filter projects by title as the query changes."""
        if event.input.id != "project-picker-search":
            return
        query = event.value.strip().lower()
        if not query:
            self._visible = self._projects
        else:
            self._visible = [
                project for project in self._projects if query in project.title.lower()
            ]
        self._render_options()

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        """Return selected project id."""
        project_id = event.option.id
        if not project_id:
            self.dismiss(None)
            return
        self.dismiss({"project_id": project_id})

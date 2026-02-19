"""Contract tests for shared modal dialog bindings."""

from __future__ import annotations

from flow.tui.common.base_screen import FlowModalScreen
from flow.tui.common.widgets.defer_dialog import DeferDialog
from flow.tui.common.widgets.process_task_dialog import ProcessTaskDialog
from flow.tui.common.widgets.project_picker_dialog import ProjectPickerDialog


def test_defer_dialog_inherits_flow_modal_screen() -> None:
    """Defer dialog should inherit shared modal keybinding base."""
    assert issubclass(DeferDialog, FlowModalScreen)


def test_process_task_dialog_has_jk_navigation() -> None:
    """Process-task dialog should retain j/k navigation."""
    keys = {
        binding[0] if isinstance(binding, tuple) else binding.key
        for binding in ProcessTaskDialog.BINDINGS
    }
    assert {"j", "k"}.issubset(keys)


def test_project_picker_dialog_inherits_flow_modal_screen() -> None:
    """Project picker should inherit shared modal keybinding base."""
    assert issubclass(ProjectPickerDialog, FlowModalScreen)


def test_project_picker_dialog_keeps_escape_cancel_binding() -> None:
    """Project picker should keep escape-to-cancel behavior."""
    keys = {
        binding[0] if isinstance(binding, tuple) else binding.key
        for binding in ProjectPickerDialog.BINDINGS
    }
    assert "escape" in keys

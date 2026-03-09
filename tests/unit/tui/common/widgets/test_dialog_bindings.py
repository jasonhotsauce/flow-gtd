"""Contract tests for shared modal dialog bindings."""

from __future__ import annotations

from textual.app import App, ComposeResult
from textual.widgets import Input, Static

from flow.tui.common.base_screen import FlowModalScreen
from flow.tui.common.widgets.defer_dialog import DeferDialog
from flow.tui.common.widgets.process_task_dialog import ProcessTaskDialog
from flow.tui.common.widgets.project_picker_dialog import ProjectPickerDialog
from flow.tui.common.widgets.quick_capture_dialog import QuickCaptureDialog


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


def test_quick_capture_dialog_inherits_flow_modal_screen() -> None:
    """Quick capture dialog should inherit shared modal keybinding base."""
    assert issubclass(QuickCaptureDialog, FlowModalScreen)


async def test_quick_capture_dialog_uses_ops_style_copy() -> None:
    """Quick capture dialog should match the refreshed ops/material language."""

    dialog = QuickCaptureDialog(origin_label="Daily workspace")

    class DialogApp(App[None]):
        def compose(self) -> ComposeResult:
            if False:
                yield

    app = DialogApp()
    async with app.run_test() as pilot:
        app.push_screen(dialog)
        await pilot.pause()

        title = str(dialog.query_one("#quick-capture-title", Static).renderable)
        status = str(dialog.query_one("#quick-capture-status", Static).renderable)
        placeholder = dialog.query_one("#quick-capture-input", Input).placeholder

    assert "Quick Capture" in title
    assert "Daily workspace" in status
    assert placeholder is not None and "next concrete step" in placeholder

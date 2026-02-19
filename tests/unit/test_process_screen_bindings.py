"""Unit tests for Process screen key bindings."""

from __future__ import annotations

from flow.tui.screens.process.process import ProcessScreen


def test_process_screen_has_delete_key_binding_for_two_minute_drill() -> None:
    """Process screen should expose `x` as a single-keystroke delete in Stage 3."""
    assert any(
        (binding[0] == "x" if isinstance(binding, tuple) else binding.key == "x")
        for binding in ProcessScreen.BINDINGS
    )

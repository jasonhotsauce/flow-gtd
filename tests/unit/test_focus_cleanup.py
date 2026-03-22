"""Regression tests for removing obsolete standalone focus artifacts."""

from pathlib import Path


def test_standalone_focus_screen_artifact_is_removed() -> None:
    """Daily Workspace should be the only execution surface."""
    assert not Path("flow/tui/screens/focus/focus.py").exists()

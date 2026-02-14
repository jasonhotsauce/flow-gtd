"""Unit tests for CLI default entry behavior."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from flow.cli import main


def test_main_without_subcommand_launches_default_tui(monkeypatch: Any) -> None:
    """Bare `flow` should open TUI default screen (Inbox)."""
    calls: list[object] = []

    def fake_launch_tui(initial_screen: object = None) -> None:
        calls.append(initial_screen)

    monkeypatch.setattr("flow.cli._launch_tui", fake_launch_tui)

    main(ctx=SimpleNamespace(invoked_subcommand=None), version=False)

    assert calls == [None]

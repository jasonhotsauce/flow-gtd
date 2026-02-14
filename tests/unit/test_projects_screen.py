"""Unit tests for Projects screen refresh behavior."""

from __future__ import annotations

from collections.abc import Coroutine
from types import SimpleNamespace
from typing import Any

from flow.tui.screens.projects.projects import ProjectsScreen


def test_projects_screen_refreshes_on_resume(monkeypatch: Any) -> None:
    """Returning to Projects screen should trigger a refresh."""
    screen = ProjectsScreen()

    async def fake_refresh() -> None:
        return None

    monkeypatch.setattr(screen, "_refresh_list_async", fake_refresh)
    calls: list[Coroutine[Any, Any, Any]] = []

    def fake_create_task(coro: Coroutine[Any, Any, Any]) -> SimpleNamespace:
        calls.append(coro)
        coro.close()
        return SimpleNamespace()

    monkeypatch.setattr(
        "flow.tui.screens.projects.projects.asyncio.create_task", fake_create_task
    )

    screen.on_screen_resume()

    assert len(calls) == 1

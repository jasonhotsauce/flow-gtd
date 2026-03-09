"""Unit tests for CLI default entry behavior."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest
import typer

import flow.cli as cli
from flow.cli import _launch_tui, main, save
from flow.tui.screens.daily_workspace.daily_workspace import DailyWorkspaceScreen


def test_main_without_subcommand_launches_default_tui(monkeypatch: Any) -> None:
    """Bare `flow` should open the daily workspace screen."""
    calls: list[object] = []

    def fake_launch_tui(initial_screen: object = None) -> None:
        calls.append(initial_screen)

    monkeypatch.setattr("flow.cli._launch_tui", fake_launch_tui)

    main(ctx=SimpleNamespace(invoked_subcommand=None), version=False)

    assert calls == [DailyWorkspaceScreen]


def test_launch_tui_hands_off_onboarding_first_capture(monkeypatch: Any) -> None:
    """First capture submit should create item and seed Inbox startup context."""
    app_inits: list[dict[str, object]] = []
    captured_texts: list[str] = []

    class _FakeOnboardingApp:
        def run(self) -> bool:
            return True

        def get_onboarding_result(self) -> dict[str, object]:
            return {
                "completed": True,
                "first_capture": {"action": "submit", "text": "  Draft roadmap  "},
            }

    class _FakeFlowApp:
        def __init__(self, **kwargs: object) -> None:
            app_inits.append(dict(kwargs))

        def run(self) -> None:
            return

    class _FakeEngine:
        def capture(self, text: str) -> object:
            captured_texts.append(text)
            return SimpleNamespace(id="inbox-123")

    monkeypatch.setattr("flow.utils.llm.config.is_onboarding_completed", lambda: False)
    monkeypatch.setattr("flow.tui.onboarding.app.OnboardingApp", _FakeOnboardingApp)
    monkeypatch.setattr("flow.cli.FlowApp", _FakeFlowApp)
    monkeypatch.setattr("flow.cli.Engine", _FakeEngine)

    _launch_tui()

    assert captured_texts == ["Draft roadmap"]
    assert app_inits == [
        {
            "initial_screen": None,
            "startup_context": {
                "highlighted_item_id": "inbox-123",
                "show_first_value_hint": True,
            },
        }
    ]


def test_launch_tui_keeps_default_behavior_when_no_first_capture(
    monkeypatch: Any,
) -> None:
    """Skip/no text should not create captures or startup context."""
    app_inits: list[dict[str, object]] = []
    engine_calls: list[str] = []

    class _FakeOnboardingApp:
        def run(self) -> bool:
            return True

        def get_onboarding_result(self) -> dict[str, object]:
            return {
                "completed": True,
                "first_capture": {"action": "skip", "text": ""},
            }

    class _FakeFlowApp:
        def __init__(self, **kwargs: object) -> None:
            app_inits.append(dict(kwargs))

        def run(self) -> None:
            return

    class _FakeEngine:
        def capture(self, text: str) -> object:
            engine_calls.append(text)
            return SimpleNamespace(id="unused")

    monkeypatch.setattr("flow.utils.llm.config.is_onboarding_completed", lambda: False)
    monkeypatch.setattr("flow.tui.onboarding.app.OnboardingApp", _FakeOnboardingApp)
    monkeypatch.setattr("flow.cli.FlowApp", _FakeFlowApp)
    monkeypatch.setattr("flow.cli.Engine", _FakeEngine)

    _launch_tui()

    assert engine_calls == []
    assert app_inits == [{"initial_screen": None, "startup_context": None}]


def test_launch_tui_continues_when_first_capture_fails(monkeypatch: Any) -> None:
    """Capture failures in optional first-capture handoff should not block app launch."""
    app_inits: list[dict[str, object]] = []

    class _FakeOnboardingApp:
        def run(self) -> bool:
            return True

        def get_onboarding_result(self) -> dict[str, object]:
            return {
                "completed": True,
                "first_capture": {"action": "submit", "text": "draft plan"},
            }

    class _FakeFlowApp:
        def __init__(self, **kwargs: object) -> None:
            app_inits.append(dict(kwargs))

        def run(self) -> None:
            return

    class _FakeEngine:
        def capture(self, _text: str) -> object:
            raise RuntimeError("db locked")

    monkeypatch.setattr("flow.utils.llm.config.is_onboarding_completed", lambda: False)
    monkeypatch.setattr("flow.tui.onboarding.app.OnboardingApp", _FakeOnboardingApp)
    monkeypatch.setattr("flow.cli.FlowApp", _FakeFlowApp)
    monkeypatch.setattr("flow.cli.Engine", _FakeEngine)

    _launch_tui()

    assert app_inits == [{"initial_screen": None, "startup_context": None}]


def test_launch_tui_exits_when_onboarding_not_completed(monkeypatch: Any) -> None:
    """If onboarding is abandoned, CLI should exit without launching FlowApp."""
    run_calls: list[bool] = []

    class _FakeOnboardingApp:
        def run(self) -> bool:
            return False

    class _FakeFlowApp:
        def __init__(self, **_kwargs: object) -> None:
            return

        def run(self) -> None:
            run_calls.append(True)

    monkeypatch.setattr("flow.utils.llm.config.is_onboarding_completed", lambda: False)
    monkeypatch.setattr("flow.tui.onboarding.app.OnboardingApp", _FakeOnboardingApp)
    monkeypatch.setattr("flow.cli.FlowApp", _FakeFlowApp)

    with pytest.raises(typer.Exit):
        _launch_tui()

    assert run_calls == []


def test_save_spawns_index_worker_process(monkeypatch: Any, tmp_path: Any) -> None:
    """Save should enqueue indexing and start detached process worker."""
    db_path = tmp_path / "flow.db"
    enqueue_calls: list[dict[str, object]] = []
    process_inits: list[dict[str, object]] = []
    process_starts: list[bool] = []

    class _FakeStore:
        def list_resources(self, *, limit: int = 100, content_type: str | None = None) -> list[object]:
            _ = (limit, content_type)
            return []

        def list_tags(self) -> list[str]:
            return []

        def save_resource(self, resource: object) -> object:
            return resource

    class _FakeEngine:
        def __init__(self, db_path: object = None) -> None:
            self._db_path = db_path

        def enqueue_resource_index(self, **kwargs: object) -> str:
            enqueue_calls.append(kwargs)
            return "job-1"

    class _FakeProcess:
        def __init__(
            self,
            *,
            target: object,
            args: tuple[object, ...],
            daemon: bool,
        ) -> None:
            process_inits.append({"target": target, "args": args, "daemon": daemon})

        def start(self) -> None:
            process_starts.append(True)

    monkeypatch.setattr("flow.cli.get_settings", lambda: SimpleNamespace(db_path=db_path))
    monkeypatch.setattr(
        "flow.cli.create_resource_store", lambda provider, **_kwargs: _FakeStore()
    )
    monkeypatch.setattr("flow.cli.Engine", _FakeEngine)
    monkeypatch.setattr("flow.cli.multiprocessing.Process", _FakeProcess)

    save(content="A plain text note", tags="reference")

    assert len(enqueue_calls) == 1
    assert process_inits == [
        {
            "target": cli._kickoff_index_worker,
            "args": (db_path,),
            "daemon": False,
        }
    ]
    assert process_starts == [True]


def test_save_uses_selected_resource_store(monkeypatch: Any, tmp_path: Any) -> None:
    db_path = tmp_path / "flow.db"
    calls: list[str] = []

    class _FakeStore:
        def list_resources(self, *, limit: int = 100, content_type: str | None = None) -> list[object]:
            _ = (limit, content_type)
            return []

        def save_resource(self, resource: object) -> object:
            calls.append("save_resource")
            return resource

        def list_tags(self) -> list[str]:
            calls.append("list_tags")
            return []

    monkeypatch.setattr("flow.cli.get_settings", lambda: SimpleNamespace(db_path=db_path))
    monkeypatch.setattr(
        "flow.cli.load_config",
        lambda: SimpleNamespace(
            resource_storage="flow-library",
            obsidian_vault_path="",
            obsidian_notes_dir="flow/resources",
        ),
    )
    monkeypatch.setattr(
        "flow.cli.create_resource_store", lambda provider, **_kwargs: _FakeStore()
    )

    save(content="A plain text note", tags="reference")

    assert "save_resource" in calls


def test_launch_tui_prompts_existing_user_for_storage_selection(
    monkeypatch: Any,
) -> None:
    updates: list[dict[str, object]] = []
    app_inits: list[dict[str, object]] = []

    class _FakeFlowApp:
        def __init__(self, **kwargs: object) -> None:
            app_inits.append(dict(kwargs))

        def run(self) -> None:
            return

    monkeypatch.setattr("flow.cli.is_onboarding_completed", lambda: True)
    monkeypatch.setattr("flow.cli.has_resource_storage_config", lambda: False)
    monkeypatch.setattr("flow.cli.typer.prompt", lambda *_args, **_kwargs: "1")
    monkeypatch.setattr(
        "flow.cli.set_resource_storage_config",
        lambda **kwargs: updates.append(dict(kwargs)),
    )
    monkeypatch.setattr("flow.cli.FlowApp", _FakeFlowApp)

    _launch_tui()

    assert updates == [{"storage_provider": "flow-library"}]
    assert app_inits == [{"initial_screen": None, "startup_context": None}]


def test_resources_command_reads_from_resource_store(monkeypatch: Any, tmp_path: Any) -> None:
    db_path = tmp_path / "flow.db"
    outputs: list[str] = []

    class _FakeResource:
        def __init__(self, source: str, title: str, tags: list[str]) -> None:
            self.source = source
            self.title = title
            self.tags = tags
            self.content_type = "url"

    class _FakeStore:
        def list_resources(self, *, limit: int = 20, content_type: str | None = None) -> list[object]:
            _ = content_type
            return [_FakeResource("https://x", "X", ["docs"])][:limit]

        def search_by_tags(self, tags: list[str], *, limit: int = 100) -> list[object]:
            _ = tags
            return [_FakeResource("https://x", "X", ["docs"])][:limit]

    monkeypatch.setattr("flow.cli.get_settings", lambda: SimpleNamespace(db_path=db_path))
    monkeypatch.setattr(
        "flow.cli.load_config",
        lambda: SimpleNamespace(
            resource_storage="flow-library",
            obsidian_vault_path="",
            obsidian_notes_dir="flow/resources",
        ),
    )
    monkeypatch.setattr(
        "flow.cli.create_resource_store", lambda provider, **_kwargs: _FakeStore()
    )
    monkeypatch.setattr("flow.cli.typer.echo", lambda msg="": outputs.append(str(msg)))

    cli.resources(limit=5)

    assert any("Resources" in line for line in outputs)

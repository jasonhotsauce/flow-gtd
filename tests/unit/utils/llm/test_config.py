from __future__ import annotations

import tomllib
from datetime import datetime
from pathlib import Path

from flow.utils.llm.config import (
    mark_first_value_completed,
    read_first_run_state,
    save_config,
)


def test_save_config_writes_first_value_pending_flag(tmp_path: Path) -> None:
    config_path = tmp_path / "config.toml"

    save_config(
        "gemini",
        {"api_key": "k"},
        config_path=config_path,
        onboarding_completed=True,
    )

    parsed = tomllib.loads(config_path.read_text())
    assert parsed["first_value_pending"] is True
    assert parsed["first_value_completed_at"] == ""


def test_mark_first_value_completed_updates_flags(tmp_path: Path) -> None:
    config_path = tmp_path / "config.toml"

    save_config(
        "gemini",
        {"api_key": "k"},
        config_path=config_path,
        onboarding_completed=True,
    )

    mark_first_value_completed(config_path=config_path)
    state = read_first_run_state(config_path=config_path)
    parsed = tomllib.loads(config_path.read_text())

    assert state.first_value_pending is False
    assert state.first_value_completed_at is not None
    assert parsed["first_value_pending"] is False
    assert parsed["first_value_completed_at"] == state.first_value_completed_at
    datetime.fromisoformat(parsed["first_value_completed_at"])


def test_read_first_run_state_returns_saved_values(tmp_path: Path) -> None:
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        "\n".join(
            [
                "onboarding_completed = true",
                "first_value_pending = false",
                'first_value_completed_at = "2026-02-15T10:00:00+00:00"',
                "",
                "[llm]",
                'provider = "gemini"',
            ]
        )
    )

    state = read_first_run_state(config_path=config_path)

    assert state.first_value_pending is False
    assert state.first_value_completed_at == "2026-02-15T10:00:00+00:00"


def test_mark_first_value_completed_preserves_custom_llm_fields(tmp_path: Path) -> None:
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        "\n".join(
            [
                "onboarding_completed = true",
                "first_value_pending = true",
                'first_value_completed_at = ""',
                "",
                "[llm]",
                'provider = "openai"',
                "",
                "[llm.openai]",
                'api_key = "openai-secret"',
                'default_model = "gpt-4.1-mini"',
                'base_url = "https://example.local/openai"',
                "timeout = 42.5",
            ]
        )
    )

    mark_first_value_completed(config_path=config_path)
    parsed = tomllib.loads(config_path.read_text())

    assert parsed["llm"]["openai"]["default_model"] == "gpt-4.1-mini"
    assert parsed["llm"]["openai"]["base_url"] == "https://example.local/openai"
    assert parsed["llm"]["openai"]["timeout"] == 42.5
    assert parsed["first_value_pending"] is False
    assert parsed["first_value_completed_at"] != ""


def test_mark_first_value_completed_preserves_unrelated_top_level_sections(
    tmp_path: Path,
) -> None:
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        "\n".join(
            [
                "onboarding_completed = true",
                "first_value_pending = true",
                'first_value_completed_at = ""',
                "",
                "[llm]",
                'provider = "gemini"',
                "",
                "[llm.gemini]",
                'api_key = "gem-key"',
                "",
                "[sync]",
                "enabled = true",
            ]
        )
    )

    mark_first_value_completed(config_path=config_path)
    parsed = tomllib.loads(config_path.read_text())

    assert parsed["sync"]["enabled"] is True
    assert parsed["onboarding_completed"] is True
    assert parsed["first_value_pending"] is False
    assert parsed["first_value_completed_at"] != ""

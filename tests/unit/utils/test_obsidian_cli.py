"""Tests for Obsidian CLI wrapper."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from flow.utils.obsidian_cli import ObsidianCLI, ObsidianCLIError


@patch("flow.utils.obsidian_cli.subprocess.run")
def test_obsidian_cli_builds_expected_command(mock_run: MagicMock) -> None:
    mock_run.return_value = MagicMock(returncode=0, stdout="ok", stderr="")

    cli = ObsidianCLI(binary="obsidian")
    result = cli.create_note(vault_path="/vault", note_path="flow/note.md", content="body")

    called_args = mock_run.call_args[0][0]
    assert called_args == [
        "obsidian",
        "note",
        "create",
        "--vault",
        "/vault",
        "--file",
        "flow/note.md",
        "--content",
        "body",
    ]
    assert result.ok is True


@patch("flow.utils.obsidian_cli.shutil.which")
def test_obsidian_cli_health_check_when_binary_missing(mock_which: MagicMock) -> None:
    mock_which.return_value = None

    cli = ObsidianCLI(binary="obsidian")
    result = cli.health_check()

    assert result.ok is False
    assert result.message == "obsidian CLI not found"


@patch("flow.utils.obsidian_cli.subprocess.run")
def test_obsidian_cli_raises_on_failure(mock_run: MagicMock) -> None:
    mock_run.side_effect = RuntimeError("boom")

    cli = ObsidianCLI(binary="obsidian")

    with pytest.raises(ObsidianCLIError, match="boom"):
        cli.create_note(vault_path="/vault", note_path="flow/note.md", content="body")

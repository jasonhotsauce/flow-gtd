"""Tests for Obsidian vault resource store provider."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from flow.core.resources.models import ResourceRecord
from flow.core.resources.providers.obsidian_vault import ObsidianVaultResourceStore
from flow.utils.obsidian_cli import ObsidianCLIResult


class _FakeObsidianCLI:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, str]] = []
        self._health = ObsidianCLIResult(ok=True)

    def create_note(self, vault_path: str, note_path: str, content: str) -> ObsidianCLIResult:
        self.calls.append((vault_path, note_path, content))
        return ObsidianCLIResult(ok=True)

    def health_check(self) -> ObsidianCLIResult:
        return self._health



def test_obsidian_provider_save_writes_note_with_frontmatter(tmp_path: Path) -> None:
    cli = _FakeObsidianCLI()
    store = ObsidianVaultResourceStore(vault_path=tmp_path, cli=cli)
    resource = ResourceRecord(
        id="obs-1",
        content_type="url",
        source="https://example.com",
        title="Example",
        summary="A summary",
        tags=["docs", "api"],
        created_at=datetime(2026, 2, 28, tzinfo=timezone.utc),
        raw_content="full content",
    )

    saved = store.save_resource(resource)

    assert saved.id == "obs-1"
    assert cli.calls
    _, note_path, content = cli.calls[0]
    assert note_path == "flow/resources/obs-1.md"
    assert "tags:" in content
    assert "- docs" in content
    assert "source: https://example.com" in content
    assert "full content" in content


def test_obsidian_provider_health_check_fails_when_cli_missing() -> None:
    cli = _FakeObsidianCLI()
    cli._health = ObsidianCLIResult(ok=False, message="obsidian CLI not found")
    store = ObsidianVaultResourceStore(vault_path="/vault", cli=cli)

    result = store.health_check()

    assert result.ok is False
    assert result.message == "obsidian CLI not found"


def test_obsidian_provider_persists_index_and_supports_semantic_search(
    tmp_path: Path,
) -> None:
    cli = _FakeObsidianCLI()
    store = ObsidianVaultResourceStore(vault_path=tmp_path, cli=cli)
    resource = ResourceRecord(
        id="obs-2",
        content_type="text",
        source="https://example.com/auth-guide",
        title="OAuth guide",
        summary="PKCE for mobile clients",
        tags=["security", "auth"],
        raw_content="Use PKCE and short-lived tokens",
    )
    store.save_resource(resource)

    reloaded = ObsidianVaultResourceStore(vault_path=tmp_path, cli=cli)
    hits = reloaded.semantic_search("pkce oauth auth", top_k=3)

    assert reloaded.get_resource("obs-2") is not None
    assert hits
    assert hits[0].resource_id == "obs-2"

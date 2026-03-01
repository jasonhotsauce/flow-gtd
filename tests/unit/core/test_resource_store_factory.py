"""Tests for resource store factory."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from flow.core.resources.factory import create_resource_store
from flow.core.resources.providers.flow_library import FlowLibraryResourceStore
from flow.core.resources.providers.obsidian_vault import ObsidianVaultResourceStore
from flow.database.resources import ResourceDB


class _NoopCLI:
    def create_note(self, vault_path: str, note_path: str, content: str):  # pragma: no cover
        raise NotImplementedError

    def health_check(self):  # pragma: no cover
        raise NotImplementedError



def test_factory_builds_flow_library_store() -> None:
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as handle:
        db_path = Path(handle.name)

    db = ResourceDB(db_path)
    db.init_db()

    store = create_resource_store(provider="flow-library", resource_db=db)

    assert isinstance(store, FlowLibraryResourceStore)


def test_factory_builds_obsidian_store_when_provider_is_obsidian() -> None:
    store = create_resource_store(
        provider="obsidian-vault",
        vault_path="/vault",
        obsidian_cli=_NoopCLI(),
    )

    assert isinstance(store, ObsidianVaultResourceStore)


def test_factory_raises_for_unknown_provider() -> None:
    with pytest.raises(ValueError, match="Unsupported resource store provider"):
        create_resource_store(provider="unknown")

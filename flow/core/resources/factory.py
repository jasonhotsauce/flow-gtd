"""Factory for creating resource store providers."""

from __future__ import annotations

from pathlib import Path

from flow.core.resources.providers.flow_library import FlowLibraryResourceStore
from flow.core.resources.providers.obsidian_vault import ObsidianVaultResourceStore
from flow.core.resources.store import ResourceStore
from flow.database.resources import ResourceDB
from flow.utils.obsidian_cli import ObsidianCLI


def create_resource_store(
    provider: str,
    *,
    resource_db: ResourceDB | None = None,
    vault_path: str | Path | None = None,
    notes_dir: str = "flow/resources",
    obsidian_cli: ObsidianCLI | None = None,
) -> ResourceStore:
    """Create a provider-specific resource store instance."""

    if provider == "flow-library":
        if resource_db is None:
            raise ValueError("resource_db is required for flow-library provider")
        return FlowLibraryResourceStore(resource_db)

    if provider == "obsidian-vault":
        if vault_path is None:
            raise ValueError("vault_path is required for obsidian-vault provider")
        return ObsidianVaultResourceStore(
            vault_path=vault_path,
            notes_dir=notes_dir,
            cli=obsidian_cli,
        )

    raise ValueError(f"Unsupported resource store provider: {provider}")

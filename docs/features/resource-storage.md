# Resource Storage

Flow supports pluggable resource storage providers.

## User Choices in Setup

- **Flow Library**: built-in local storage managed by Flow.
- **Obsidian Vault**: resources saved as notes in an Obsidian vault using Obsidian CLI.

## Commands

- `flow save <url|file|text>`: saves to the selected provider.
- `flow resources`: lists resources from the selected provider.
- `flow tags`: lists resource tags from the selected provider.

## Obsidian Notes

When using Obsidian Vault, Flow writes notes under a configurable folder
(default `flow/resources`) and keeps a local index file under the vault at:

- `.flow/resources_index.json`

This index powers listing, tag search, and semantic matching.

## Configuration

Resource storage is configured in `~/.flow/config.toml`:

```toml
[resources]
storage = "flow-library" # or "obsidian-vault"
obsidian_vault_path = ""
obsidian_notes_dir = "flow/resources"
```

# Resource Storage Abstraction Design

## Context

Flow currently persists resources through SQLite (`ResourceDB`) plus Chroma vector indexing.
The goal is to make storage provider-based so users can choose a storage experience,
starting with Obsidian now and leaving clear extension points for Apple Notes and others.

User-approved constraints:

- New users choose storage during setup with plain-language options.
- Existing users are prompted on next startup to choose storage.
- No migration of old resources; new saves follow the selected store.
- Obsidian should support semantic search.
- UX should hide backend implementation details.

## Goals

- Decouple CLI/Engine/TUI from concrete SQLite resource APIs.
- Add a first-class Obsidian resource store.
- Preserve resource workflows (`save`, `resources`, `tags`, sidecar matching, semantic retrieval).
- Keep provider architecture clean so Apple Notes can be added by implementing one contract.

## Non-Goals

- Migrating existing resources between backends.
- Implementing Apple Notes backend in this task.
- Redesigning task/item storage outside resource layer.

## User-Facing Experience

During setup, users choose:

- `Flow Library` (stores resources in Flow-managed local storage)
- `Obsidian Vault` (stores resources in an Obsidian vault)

If `Obsidian Vault` is selected:

- Setup validates `obsidian` CLI availability and vault path.
- Setup saves storage choice and Obsidian settings.

For existing users, next startup adds a one-time storage choice step with the same labels.

## Architecture

### 1. Resource Store Contract

Add a core contract (protocol or abstract class) that owns resource behavior:

- save resource
- get/list resources
- tag-based search
- semantic search
- list tags
- health check

Core callers (CLI/Engine/TUI) only depend on this contract.

### 2. Provider Implementations

- `FlowLibraryResourceStore`: wraps current local behavior (SQLite + current semantic path).
- `ObsidianResourceStore`: stores resource notes in vault and implements tag + semantic retrieval.

### 3. Factory/Registry

Add a `ResourceStoreFactory` that builds a provider from config.

- Fail fast with actionable messages when config is invalid.
- Keep provider IDs internal; onboarding presents human-readable labels.

### 4. Semantic Capability

Semantic behavior is part of the `ResourceStore` contract so each backend can own implementation details.
Core requests semantic results through one interface, regardless of backend internals.

## Data Model Direction

Introduce backend-agnostic models for store results (or evolve existing models safely):

- `ResourceRecord` (id, source, title, summary, tags, created_at, content_type, backend metadata)
- `TagRecord` (name, usage or relevance metadata)
- `SemanticHit` (resource id, score, snippet/title/source)

The contract should avoid leaking backend-specific structures into callers.

## Flow Changes

### Save

`flow save` delegates to selected store:

- detect content type
- gather metadata and tags
- call `store.save_resource(...)`
- call store semantic indexing method when needed

### Resource Listing and Tag Listing

- `flow resources` and `flow tags` call store methods only.

### Action/Focus Sidecar

- Engine delegates to store for tag and semantic search.
- UI stays unchanged except for using store-backed return types.

## Error Handling

- `health_check()` runs during setup and at key entry points.
- Obsidian setup/runtime errors are explicit and actionable (CLI missing, vault path invalid, command failure).
- No silent fallback to another backend.

## Testing Strategy

- Contract tests for shared `ResourceStore` behavior.
- Provider tests:
  - Flow library provider parity with current behavior.
  - Obsidian provider behavior: write/read, tags, semantic search, error paths.
- CLI/Engine/TUI tests updated to mock `ResourceStore` instead of `ResourceDB` directly.
- Onboarding tests for storage choice and persistence.

## Risks and Mitigations

- Risk: Obsidian CLI availability and runtime assumptions.
  - Mitigation: strict setup validation + clear runtime errors.
- Risk: broad refactor touches many call sites.
  - Mitigation: contract first, then phased call-site migration with parity tests.
- Risk: semantic behavior mismatch between providers.
  - Mitigation: define semantic result contract and test invariants at contract level.

## Rollout

1. Introduce abstraction and flow-library provider (parity baseline).
2. Add Obsidian provider and setup integration.
3. Switch callers to factory-resolved store.
4. Verify parity and Obsidian path through targeted tests.
5. Update README/docs for storage setup and prerequisites.

# Native App Hard Cutover Design

## Goal

Remove the legacy terminal product surface and align the repository around Flow as a native macOS app only.

## Decision

Adopt a hard cutover now.

- Delete the Textual TUI package instead of deprecating it in place.
- Remove user-facing CLI/TUI positioning from product docs and packaging metadata.
- Keep only native app build/test tooling and any non-UI code still needed by the native app or repository internals.

## Scope

### In Scope

- Delete `flow/tui/`.
- Remove or rewrite user-facing CLI/TUI references in `README.md`, `AGENTS.md`, feature docs, plans, and packaging metadata where they describe the current supported product.
- Remove tests that only validate the retired CLI/TUI surface.
- Keep native SwiftUI sources, native smoke tests, and native build/test scripts as the supported app surface.
- Update task tracking with explicit verification results for the cutover.

### Out of Scope

- Re-architecting the native app core.
- Replacing every historical mention of the old TUI in archival design docs unless those docs are positioned as current product documentation.
- Removing backend or storage code that is still useful to the native app or its migration path.

## Approach Options

### Option A: Hard Cutover Now

- Delete the TUI package and rewrite current docs in the same change.
- Remove packaging/test surface that exists only to support the terminal app.

Pros:
- Repository matches product reality immediately.
- Avoids split messaging and stale entrypoints.

Cons:
- Requires a broader cleanup pass across tests, metadata, and docs.

### Option B: Soft Deprecation

- Keep TUI/CLI code in-tree but mark it unsupported.

Pros:
- Lower short-term breakage risk.

Cons:
- Leaves dead user-facing surface and contradictory docs.
- Keeps maintenance burden for code that should be retired.

### Option C: Docs-Only First

- Rewrite docs now and delete old code later.

Pros:
- Small initial change.

Cons:
- Creates an immediate mismatch between the repo and the documented product.

## Recommended Design

Choose Option A.

The native SwiftUI app is already the intended product. The repository should stop advertising terminal-first usage, remove the retired TUI implementation, and narrow verification to the native app path.

## Change Areas

### Code

- Delete `flow/tui/`.
- Audit `flow/cli.py`, `flow/main.py`, and Python package metadata for references that make the CLI a supported product entrypoint.
- Remove tests that only exist for the retired CLI/TUI behavior.

### Documentation

- Rewrite `README.md` so installation, usage, architecture, and verification all center on the native macOS app.
- Update `AGENTS.md` product framing and architecture guardrails that still describe Flow as a CLI/TUI product.
- Update feature docs that currently instruct users to launch TUI screens or CLI commands as the product workflow.

### Packaging

- Update `pyproject.toml` description and dependencies if `textual` and `typer` are no longer needed for supported product behavior.
- Keep Python dependencies that are still needed by shared core/storage/sync code.

## Risks

- Hidden imports or tests may still assume `flow/tui/` exists.
- Some docs may mix historical migration notes with current product guidance; those need selective edits rather than blind deletion.
- Removing `typer` or CLI code entirely may be premature if repository tooling still imports it indirectly.

## Verification

- Search for stale user-facing references: `TUI`, `Textual`, `flow tui`, `flow process`, `flow review`, `Typer`, and `CLI`.
- Run native verification:
  - `./scripts/test_native_app.sh`
  - `./scripts/build_native_app.sh`
- If Python packaging or import wiring changes materially, run targeted Python tests only for code that remains in scope.

## Success Criteria

- No supported product documentation describes Flow as a CLI or TUI.
- `flow/tui/` is removed from the repository.
- Native build and smoke verification pass after the cleanup.

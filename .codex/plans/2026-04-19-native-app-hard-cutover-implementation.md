# Native App Hard Cutover Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Remove the retired TUI product surface and rewrite the repository’s current product/documentation story so Flow is a native macOS app only.

**Architecture:** The change removes the Textual presentation layer, narrows current product documentation to the SwiftUI app, and trims packaging/tests that only exist for the terminal surface. Shared Python core code stays only where it still supports the native app or repository internals.

**Tech Stack:** SwiftUI, Swift, Python 3.11, Poetry, pytest, shell scripts, ripgrep

---

### Task 1: Re-baseline task tracking for the hard cutover

**Files:**
- Modify: `tasks/todo.md`

**Step 1: Replace the stale migration checklist**

- Rewrite `tasks/todo.md` so it tracks the native-app-only cutover instead of the already-completed migration work.

**Step 2: Add verification targets**

- Include search-based stale-reference checks plus native smoke/build verification.

**Step 3: Leave a review/results section**

- Reserve space for final outcomes and any follow-up risks discovered during execution.

### Task 2: Remove the retired TUI code and related tests

**Files:**
- Delete: `flow/tui/`
- Modify/Delete: CLI/TUI-only test files under `tests/unit/` as discovered by search

**Step 1: Find imports and tests coupled to `flow/tui/`**

Run: `rg -n "flow/tui|flow\\.tui|Textual|TUI|typer" flow tests`

**Step 2: Delete the TUI package**

- Remove the entire `flow/tui/` tree.

**Step 3: Remove or rewrite tests that only validate retired behavior**

- Delete tests whose purpose is the terminal UI surface.
- Keep tests only if they still validate shared code that remains supported.

### Task 3: Update packaging and product metadata

**Files:**
- Modify: `pyproject.toml`
- Modify: `AGENTS.md`
- Modify: Python entrypoint/module files if they still advertise CLI product behavior

**Step 1: Rewrite package description**

- Change product wording from CLI/TUI to native macOS app.

**Step 2: Trim unsupported dependencies cautiously**

- Remove `textual` and `typer` only if no remaining supported code path needs them.

**Step 3: Update architecture guidance**

- Rewrite `AGENTS.md` sections that still describe Flow as CLI/TUI-first.

### Task 4: Rewrite current product docs

**Files:**
- Modify: `README.md`
- Modify: current feature docs under `docs/features/` that still describe TUI/CLI workflows

**Step 1: Rewrite README around the native app**

- Installation, build, smoke test, architecture, and usage should all center on the macOS app.

**Step 2: Remove terminal workflow instructions**

- Delete command tables and TUI navigation sections that are no longer part of the supported product.

**Step 3: Update feature docs selectively**

- Rewrite only docs that present current product behavior; leave historical migration docs intact unless they claim to describe the current experience.

### Task 5: Verify the cutover and record results

**Files:**
- Modify: `tasks/todo.md`

**Step 1: Run stale-reference searches**

Run:
- `rg -n "flow tui|daily workspace TUI|Textual|TUI Panel|Launch TUI|Typer CLI|GTD CLI" README.md AGENTS.md docs flow tests pyproject.toml`

Expected:
- No current-product references remain outside archival or migration-history documents that are clearly historical.

**Step 2: Run native verification**

Run:
- `./scripts/test_native_app.sh`
- `./scripts/build_native_app.sh`

Expected:
- Both commands pass.

**Step 3: Record review/results**

- Update `tasks/todo.md` with what changed, what was verified, and any remaining cleanup that is intentionally deferred.

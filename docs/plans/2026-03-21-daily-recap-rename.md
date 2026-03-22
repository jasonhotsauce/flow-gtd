# Daily Recap Rename Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace the user-facing and code-level `wrap` feature terminology with `daily recap` so the feature is easier to understand.

**Architecture:** Keep the existing Daily Workspace behavior and recap-gating flow intact while renaming the TUI labels, action/method identifiers, tests, and docs to `daily recap`. Preserve persistence behavior and avoid unrelated changes; if a storage identifier would create migration risk, keep the storage behavior stable and rename only the surrounding APIs/copy.

**Tech Stack:** Python 3.11, Textual, Typer, pytest, Markdown docs

---

### Task 1: Track the rename work

**Files:**
- Modify: `tasks/todo.md`

**Step 1: Add the rename task checklist**
- Record checklist items for code, docs, verification, and review.

**Step 2: Update results after verification**
- Add a short review/results section with what changed and what was verified.

### Task 2: Rename the Daily Workspace feature surface

**Files:**
- Modify: `flow/tui/screens/daily_workspace/daily_workspace.py`
- Test: `tests/unit/test_daily_workspace_screen.py`
- Test: `tests/unit/test_cli_main.py`

**Step 1: Update tests for recap terminology**
- Rename screen/CLI test names and expectations from `wrap` to `recap`.
- Keep selectors and runtime behavior aligned with the current UI structure.

**Step 2: Run targeted tests to confirm failures or stale references**

```bash
source .venv/bin/activate && pytest tests/unit/test_daily_workspace_screen.py tests/unit/test_cli_main.py -q
```

**Step 3: Rename the screen bindings, methods, copy, and status text**
- Replace `Wrap`/`Daily Wrap` with `Recap`/`Daily Recap`.
- Rename screen action/method identifiers such as `show_daily_wrap` and `generate_wrap_insight`.
- Keep the focus-state behavior unchanged.

**Step 4: Re-run the targeted UI tests**

```bash
source .venv/bin/activate && pytest tests/unit/test_daily_workspace_screen.py tests/unit/test_cli_main.py -q
```

### Task 3: Rename engine/service terminology and update docs

**Files:**
- Modify: `flow/core/engine.py`
- Modify: `flow/core/services/daily_plan.py`
- Modify: `README.md`
- Modify: `docs/PRD.md`
- Test: `tests/unit/test_daily_workspace.py`

**Step 1: Update service/engine tests and docs references**
- Rename relevant daily-plan test names and doc copy to `daily recap`.

**Step 2: Rename service/engine APIs where safe**
- Replace `wrap` terminology in method names, comments, and local variables with `recap`.
- Keep persistence semantics stable.

**Step 3: Re-run targeted daily-plan tests**

```bash
source .venv/bin/activate && pytest tests/unit/test_daily_workspace.py -q
```

### Task 4: Verify and review

**Files:**
- Modify: `tasks/todo.md`

**Step 1: Run combined targeted verification**

```bash
source .venv/bin/activate && pytest tests/unit/test_daily_workspace.py tests/unit/test_daily_workspace_screen.py tests/unit/test_cli_main.py -q
```

**Step 2: Run the Flow review checklist on touched `flow/` and `tests/` files**
- Review for architecture direction, typing, async safety, and tests.

**Step 3: Record results in `tasks/todo.md`**
- Note the rename scope, verification commands, and review outcome.

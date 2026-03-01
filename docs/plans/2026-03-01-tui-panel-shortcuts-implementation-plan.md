# TUI Panel Shortcuts Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add panel switching by number and name abbreviation across split-panel TUI screens and show explicit panel headers.

**Architecture:** Extend per-screen keybinding maps and local action handlers without introducing shared abstraction yet, to keep scope minimal and avoid broad refactors. Keep focus routing within each screen by widget ID.

**Tech Stack:** Python 3.11+, Textual screens/bindings, pytest unit tests.

---

### Task 1: Add failing tests for new panel shortcuts and focus routing

**Files:**
- Modify: `tests/unit/test_action_screen_bindings.py`
- Modify: `tests/unit/test_inbox_screen_bindings.py`
- Create: `tests/unit/test_projects_screen_bindings.py`

**Step 1: Write failing tests**
- Add tests that assert new bindings exist for each screen (`1/2` and name abbreviation keys).
- Add tests that assert focus actions call `.focus()` on expected widget IDs via monkeypatch stubs.

**Step 2: Run tests to verify RED**
Run: `pytest tests/unit/test_action_screen_bindings.py tests/unit/test_inbox_screen_bindings.py tests/unit/test_projects_screen_bindings.py -v`
Expected: FAIL because new bindings/actions are not implemented yet.

### Task 2: Implement Action screen shortcuts + headers

**Files:**
- Modify: `flow/tui/screens/action/action.py`

**Step 1: Add bindings and actions**
- Add `1/2/t/r` bindings mapped to focused panel actions.
- Keep `tab` mapped for backward compatibility.
- Implement `action_focus_tasks_panel` and `action_focus_resources_panel`.
- Route `action_focus_sidecar` to resources panel action.

**Step 2: Update panel headers/help text**
- Header labels: `[1] Tasks (t)`, `[2] Resources (r)`.
- Help text includes `1/2` and `t/r` hints.

### Task 3: Implement Inbox screen shortcuts + headers

**Files:**
- Modify: `flow/tui/screens/inbox/inbox.py`

**Step 1: Add bindings and actions**
- Add `1/2/l/e` bindings.
- Implement focus actions for list/detail panels.

**Step 2: Update panel headers/help text**
- Add visible left-panel header.
- Update right-panel header and help copy with shortcut hints.

### Task 4: Implement Projects screen shortcuts + headers

**Files:**
- Modify: `flow/tui/screens/projects/projects.py`

**Step 1: Add bindings and actions**
- Add `1/2/l/d` bindings.
- Implement focus actions for list/detail panels.

**Step 2: Update panel headers/help text**
- Update panel section labels to include numeric/name hints.
- Update help text with shortcut hints.

### Task 5: Verify and review

**Files:**
- Modify: `tasks/todo.md`

**Step 1: Run targeted tests**
Run: `pytest tests/unit/test_action_screen_bindings.py tests/unit/test_inbox_screen_bindings.py tests/unit/test_projects_screen_bindings.py -v`
Expected: PASS.

**Step 2: Run broader suite for TUI units**
Run: `pytest tests/unit -v`
Expected: all pass or report precise failures.

**Step 3: Review checklist**
- Run mandatory `code-review-flow` checklist against changed files.
- Confirm no async blocking, architecture drift, or missing typing in modified APIs.

**Step 4: Document results**
- Update `tasks/todo.md` checkboxes and review/results section with test evidence.

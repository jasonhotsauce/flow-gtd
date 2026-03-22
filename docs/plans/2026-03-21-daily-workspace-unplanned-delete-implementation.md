# Daily Workspace Unplanned Delete Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Let Daily Workspace archive selected unplanned work with the same semantics as the Process screen.

**Architecture:** Keep the existing `d` binding and make `DailyWorkspaceScreen.action_remove_selected_draft_item()` context-sensitive in confirmed mode. When pane `3` is focused, call the existing `Engine.two_min_delete()` path, remove the item from the local unplanned groups, and refresh the supporting panes and detail copy.

**Tech Stack:** Python 3.11, Textual, Flow `Engine`, pytest

---

### Task 1: Add the regression test

**Files:**
- Modify: `tests/unit/test_daily_workspace_screen.py`

**Step 1: Write the failing test**

Add a confirmed-mode screen test that focuses the unplanned pane, selects an unplanned item, presses `d`, and asserts:
- `Engine.two_min_delete()` is called with that item id
- the item disappears from `#unplanned-list`
- focus stays on the unplanned pane

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && pytest tests/unit/test_daily_workspace_screen.py -k confirmed_unplanned_delete_archives_selected_item -v`

Expected: FAIL because Daily Workspace currently ignores `d` when confirmed-mode wrap/unplanned pane is active.

### Task 2: Implement the minimal delete path

**Files:**
- Modify: `flow/tui/screens/daily_workspace/daily_workspace.py`

**Step 3: Write minimal implementation**

Update confirmed-mode delete handling so:
- `Today` focus keeps the current remove-to-unplanned behavior
- `Unplanned Work` focus archives the selected item through `Engine.two_min_delete()`
- the local unplanned groups/lookup are updated and panes refreshed
- the unplanned detail hint mentions `d` as delete/archive

**Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && pytest tests/unit/test_daily_workspace_screen.py -k confirmed_unplanned_delete_archives_selected_item -v`

Expected: PASS

### Task 3: Verify and review

**Files:**
- Modify: `tasks/todo.md`

**Step 5: Run targeted verification**

Run: `source .venv/bin/activate && pytest tests/unit/test_daily_workspace_screen.py -k "confirmed_unplanned_delete_archives_selected_item or confirmed_state_adds_and_removes_items_without_reentering_planning or confirmed_remove_returns_item_to_original_unplanned_list_without_switching_focus" -v`

Expected: PASS

**Step 6: Run Flow review checklist**

Check architecture, typing, async safety, and targeted coverage for touched files. Record the result in `tasks/todo.md`.

# Inbox Add-To-Existing-Project Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a keyboard-first Inbox flow where `Enter` opens a process menu and users can assign the selected Inbox task to an existing active project.

**Architecture:** Keep assignment business logic in `flow/core/engine.py` via a new `assign_item_to_project` API, and keep UI orchestration in Inbox + new reusable dialogs under `flow/tui/common/widgets/`. The Inbox screen will delegate `Enter` to a process menu, then branch to defer/delete/assign actions with user-visible toasts and refresh behavior.

**Tech Stack:** Python 3.11+, Textual (`Screen`, modal dialogs, `OptionList`, key bindings), Pydantic models, sqlite3 via existing `SqliteDB` access in `Engine`, pytest unit tests.

---

### Task 1: Add failing engine tests for assignment behavior

**Files:**
- Modify: `tests/unit/test_engine.py`

**Step 1: Write the failing test**

```python
def test_assign_item_to_project_sets_parent_and_action_type(engine: Engine) -> None:
    item = engine.capture("Draft migration note")
    project = engine.create_project("Infra cleanup", [])

    updated = engine.assign_item_to_project(item.id, project.id)

    assert updated.parent_id == project.id
    assert updated.type == "action"
```

Add a second test for invalid target:

```python
def test_assign_item_to_project_rejects_non_project_target(engine: Engine) -> None:
    item = engine.capture("Call accountant")
    not_project = engine.capture("Just a task")

    with pytest.raises(ValueError):
        engine.assign_item_to_project(item.id, not_project.id)
```

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && pytest tests/unit/test_engine.py::test_assign_item_to_project_sets_parent_and_action_type tests/unit/test_engine.py::test_assign_item_to_project_rejects_non_project_target -v`

Expected: FAIL because `Engine.assign_item_to_project` does not exist yet.

**Step 3: Commit checkpoint (tests-only)**

```bash
git add tests/unit/test_engine.py
git commit -m "test: add failing coverage for inbox-to-project assignment"
```

### Task 2: Implement engine assignment API

**Files:**
- Modify: `flow/core/engine.py`
- Test: `tests/unit/test_engine.py`

**Step 1: Write minimal implementation**

Add API:

```python
def assign_item_to_project(self, item_id: str, project_id: str) -> Item:
    item = self._db.get_item(item_id)
    if not item or item.status in {"done", "archived"}:
        raise ValueError("Item is not assignable")

    project = self._db.get_item(project_id)
    if not project or project.type != "project" or project.status != "active":
        raise ValueError("Project is not assignable")

    if item.id == project.id:
        raise ValueError("Item cannot be its own project")

    updated = item.model_copy(update={"parent_id": project.id, "type": "action"})
    self._db.update_item(updated)
    self._process_inbox = self.list_inbox()
    return updated
```

**Step 2: Run tests**

Run: `source .venv/bin/activate && pytest tests/unit/test_engine.py::test_assign_item_to_project_sets_parent_and_action_type tests/unit/test_engine.py::test_assign_item_to_project_rejects_non_project_target -v`

Expected: PASS.

**Step 3: Run nearby regression tests**

Run: `source .venv/bin/activate && pytest tests/unit/test_engine.py::test_list_inbox_excludes_deferred_and_project_items -v`

Expected: PASS; assigned items remain hidden from Inbox.

**Step 4: Commit**

```bash
git add flow/core/engine.py tests/unit/test_engine.py
git commit -m "feat: add engine API to assign inbox task to active project"
```

### Task 3: Add failing Inbox binding and enter-flow tests

**Files:**
- Modify: `tests/unit/test_inbox_screen_bindings.py`
- Create: `tests/unit/test_inbox_screen_process_menu.py`

**Step 1: Write failing binding test**

In `tests/unit/test_inbox_screen_bindings.py`, add:

```python
def test_inbox_screen_enter_binding_is_process_menu() -> None:
    assert any(
        (binding[0] == "enter" and binding[1] == "open_process_menu")
        if isinstance(binding, tuple)
        else (binding.key == "enter" and binding.action == "open_process_menu")
        for binding in InboxScreen.BINDINGS
    )
```

**Step 2: Write failing screen behavior test**

In `tests/unit/test_inbox_screen_process_menu.py`, add focused unit test that monkeypatches `push_screen` and asserts:

- `action_open_process_menu()` opens process dialog when an item is highlighted.
- Callback branch `"add_to_project"` opens project picker dialog.

**Step 3: Run tests to verify failure**

Run: `source .venv/bin/activate && pytest tests/unit/test_inbox_screen_bindings.py tests/unit/test_inbox_screen_process_menu.py -v`

Expected: FAIL due to missing action/dialog wiring.

**Step 4: Commit checkpoint (tests-only)**

```bash
git add tests/unit/test_inbox_screen_bindings.py tests/unit/test_inbox_screen_process_menu.py
git commit -m "test: cover inbox enter process-menu workflow"
```

### Task 4: Add process menu and project picker dialogs

**Files:**
- Create: `flow/tui/common/widgets/process_task_dialog.py`
- Create: `flow/tui/common/widgets/project_picker_dialog.py`
- Modify: `flow/tui/common/widgets/__init__.py`
- Test: `tests/unit/test_inbox_screen_process_menu.py`

**Step 1: Implement `ProcessTaskDialog`**

Implement a small modal returning one of:

```python
{"action": "do_now" | "defer" | "add_to_project" | "delete"}
```

**Step 2: Implement `ProjectPickerDialog`**

Dialog API:

```python
ProjectPickerDialog(projects: list[Item])
```

Result payload:

```python
{"project_id": "<id>"}
```

Behavior:
- Local filter by typed query.
- Only active projects are passed in by caller.
- `Esc` cancels with `None`.

**Step 3: Export widgets**

Update `flow/tui/common/widgets/__init__.py` with new dialog imports.

**Step 4: Run dialog-related tests**

Run: `source .venv/bin/activate && pytest tests/unit/test_inbox_screen_process_menu.py -v`

Expected: PASS for dialog opening and callback routing.

**Step 5: Commit**

```bash
git add flow/tui/common/widgets/process_task_dialog.py flow/tui/common/widgets/project_picker_dialog.py flow/tui/common/widgets/__init__.py tests/unit/test_inbox_screen_process_menu.py
git commit -m "feat: add inbox process and project-picker dialogs"
```

### Task 5: Wire Inbox `Enter` to process menu and assignment path

**Files:**
- Modify: `flow/tui/screens/inbox/inbox.py`
- Test: `tests/unit/test_inbox_screen_process_menu.py`

**Step 1: Replace enter binding action**

In `InboxScreen.BINDINGS`:

- Change `("enter", "process_item", "Process")`
- To `("enter", "open_process_menu", "Process")`

**Step 2: Implement menu/picker callbacks**

Add methods:

```python
def action_open_process_menu(self) -> None: ...
def _apply_process_result(self, item_id: str, result: dict[str, str] | None) -> None: ...
def _open_project_picker(self, item_id: str) -> None: ...
def _apply_project_assignment(self, item_id: str, result: dict[str, str] | None) -> None: ...
```

Route actions:
- `do_now` -> current processing behavior (or no-op toast placeholder)
- `defer` -> reuse existing defer dialog
- `delete` -> reuse archive behavior
- `add_to_project` -> open project picker and call engine assignment

**Step 3: Keep help text accurate**

Update inline help strings to mention `Enter: Process Menu`.

**Step 4: Run focused tests**

Run: `source .venv/bin/activate && pytest tests/unit/test_inbox_screen_bindings.py tests/unit/test_inbox_screen_process_menu.py -v`

Expected: PASS.

**Step 5: Commit**

```bash
git add flow/tui/screens/inbox/inbox.py tests/unit/test_inbox_screen_bindings.py tests/unit/test_inbox_screen_process_menu.py
git commit -m "feat: wire inbox enter key to process menu and project assignment"
```

### Task 6: Add no-project and invalid-state handling tests

**Files:**
- Modify: `tests/unit/test_inbox_screen_process_menu.py`

**Step 1: Add failing edge-case tests**

Add tests to assert:
- Empty active project list shows warning toast and does not crash.
- Missing item/project from race condition shows warning/error and refresh.
- Failed assignment (`ValueError`) surfaces user-visible error toast.

**Step 2: Run tests and confirm failure**

Run: `source .venv/bin/activate && pytest tests/unit/test_inbox_screen_process_menu.py -v`

Expected: FAIL before handler polish.

**Step 3: Implement minimal fixes in Inbox screen**

Handle edge cases in `_open_project_picker` / `_apply_project_assignment` without blocking UI.

**Step 4: Re-run tests**

Run: `source .venv/bin/activate && pytest tests/unit/test_inbox_screen_process_menu.py -v`

Expected: PASS.

**Step 5: Commit**

```bash
git add tests/unit/test_inbox_screen_process_menu.py flow/tui/screens/inbox/inbox.py
git commit -m "fix: harden inbox project-assignment error handling"
```

### Task 7: Documentation updates

**Files:**
- Modify: `docs/features/projects.md`
- Modify: `docs/PRD.md`

**Step 1: Update feature docs**

Document new Inbox path:
- `Enter` opens process menu.
- `Add to project` assigns task to existing active project.

**Step 2: Update PRD execution loop text**

Add one sentence under Inbox/Process flow to mention direct assignment to existing projects from Inbox triage.

**Step 3: Commit**

```bash
git add docs/features/projects.md docs/PRD.md
git commit -m "docs: describe inbox add-to-existing-project workflow"
```

### Task 8: Verification and code review gate

**Files:**
- Modify (if needed): any file touched above based on failures/review feedback

**Step 1: Run mandatory targeted tests**

Run:

```bash
source .venv/bin/activate
pytest tests/unit/test_engine.py -v
pytest tests/unit/test_inbox_screen_bindings.py -v
pytest tests/unit/test_inbox_screen_process_menu.py -v
pytest tests/unit -v
```

Expected: PASS.

**Step 2: Run Flow code review checklist skill**

- Invoke `code-review-flow` skill and resolve findings for:
  - architecture boundaries
  - type hints
  - async/Textual safety
  - error handling
  - test adequacy

**Step 3: Final commit (only if additional fixes were required)**

```bash
git add <updated-files>
git commit -m "chore: address review findings for inbox project assignment"
```

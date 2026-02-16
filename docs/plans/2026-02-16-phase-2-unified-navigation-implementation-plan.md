# Phase 2 Unified Navigation Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Unify keybindings across all TUI screens and dialogs using shared base classes and a centralized contract without changing screen-specific behavior.

**Architecture:** Add a shared keybinding contract module and two base classes (`FlowScreen`, `FlowModalScreen`) in `flow/tui/common/`. Migrate existing screens/dialogs to inherit and compose shared bindings while preserving local actions. Validate with binding contract tests and per-screen regression tests.

**Tech Stack:** Python 3.11+, Textual (`Screen`, `ModalScreen`, bindings), pytest.

---

### Task 1: Add Shared Keybinding Contract Module

**Files:**
- Create: `flow/tui/common/keybindings.py`
- Test: `tests/unit/tui/common/test_keybindings_contract.py`

**Step 1: Write the failing test**

```python
from flow.tui.common import keybindings


def test_global_keybinding_contract_exports_expected_bindings() -> None:
    assert keybindings.QUIT_Q_BINDING == ("q", "quit_app", "Quit")
    assert keybindings.BACK_ESCAPE_BINDING == ("escape", "go_back", "Back")
    assert keybindings.HELP_BINDING == ("?", "show_help", "Help")
    assert keybindings.NAV_DOWN_BINDING == ("j", "cursor_down", "Down")
    assert keybindings.NAV_UP_BINDING == ("k", "cursor_up", "Up")


def test_with_global_bindings_prefixes_global_contract() -> None:
    custom = ("x", "delete", "Delete")
    composed = keybindings.with_global_bindings(custom)
    assert composed[0] == keybindings.QUIT_Q_BINDING
    assert keybindings.HELP_BINDING in composed
    assert custom in composed
```

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && pytest tests/unit/tui/common/test_keybindings_contract.py -v`
Expected: FAIL because `flow.tui.common.keybindings` does not exist yet.

**Step 3: Write minimal implementation**

```python
Binding = tuple[str, str, str]

QUIT_Q_BINDING: Binding = ("q", "quit_app", "Quit")
BACK_ESCAPE_BINDING: Binding = ("escape", "go_back", "Back")
HELP_BINDING: Binding = ("?", "show_help", "Help")
NAV_DOWN_BINDING: Binding = ("j", "cursor_down", "Down")
NAV_UP_BINDING: Binding = ("k", "cursor_up", "Up")


def compose_bindings(*bindings: Binding) -> list[Binding]:
    return list(bindings)


def with_global_bindings(*bindings: Binding) -> list[Binding]:
    return compose_bindings(
        QUIT_Q_BINDING,
        BACK_ESCAPE_BINDING,
        NAV_DOWN_BINDING,
        NAV_UP_BINDING,
        HELP_BINDING,
        *bindings,
    )
```

**Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && pytest tests/unit/tui/common/test_keybindings_contract.py -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add flow/tui/common/keybindings.py tests/unit/tui/common/test_keybindings_contract.py
git commit -m "refactor: add shared tui keybinding contract module"
```

### Task 2: Add Shared Base Screen and Modal Base

**Files:**
- Create: `flow/tui/common/base_screen.py`
- Test: `tests/unit/tui/common/test_base_screen_bindings.py`

**Step 1: Write the failing test**

```python
from flow.tui.common.base_screen import FlowModalScreen, FlowScreen
from flow.tui.common.keybindings import HELP_BINDING, QUIT_Q_BINDING


def test_flow_screen_includes_global_bindings() -> None:
    assert QUIT_Q_BINDING in FlowScreen.BINDINGS
    assert HELP_BINDING in FlowScreen.BINDINGS


def test_flow_modal_screen_includes_escape_cancel() -> None:
    assert any(binding[0] == "escape" for binding in FlowModalScreen.BINDINGS)
```

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && pytest tests/unit/tui/common/test_base_screen_bindings.py -v`
Expected: FAIL because `base_screen.py` does not exist.

**Step 3: Write minimal implementation**

```python
class FlowScreen(Screen):
    BINDINGS = with_global_bindings()

    def action_quit_app(self) -> None:
        self.app.exit()

    def action_go_back(self) -> None:
        if len(self.app.screen_stack) <= 2:
            self.app.exit()
        else:
            self.app.pop_screen()

    def action_show_help(self) -> None:
        self.notify("Help not available on this screen yet.", timeout=2)

    def action_cursor_down(self) -> None:
        return

    def action_cursor_up(self) -> None:
        return


class FlowModalScreen(ModalScreen[T]):
    BINDINGS = with_modal_bindings()
```

**Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && pytest tests/unit/tui/common/test_base_screen_bindings.py -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add flow/tui/common/base_screen.py tests/unit/tui/common/test_base_screen_bindings.py
git commit -m "refactor: add base screen classes for unified keybindings"
```

### Task 3: Migrate Core App Screens to `FlowScreen`

**Files:**
- Modify: `flow/tui/screens/inbox/inbox.py`
- Modify: `flow/tui/screens/process/process.py`
- Modify: `flow/tui/screens/action/action.py`
- Modify: `flow/tui/screens/projects/projects.py`
- Modify: `flow/tui/screens/projects/project_detail.py`
- Modify: `flow/tui/screens/review/review.py`
- Modify: `flow/tui/screens/focus/focus.py`
- Test: `tests/unit/test_inbox_screen_bindings.py`
- Test: `tests/unit/test_action_screen_bindings.py`
- Test: `tests/unit/test_process_screen_bindings.py`
- Test: `tests/unit/test_project_detail_screen.py`
- Test: `tests/unit/test_projects_screen.py`
- Create: `tests/unit/test_review_screen_bindings.py`
- Create: `tests/unit/test_focus_screen_bindings.py`

**Step 1: Write failing/updated tests**

```python
def test_review_screen_inherits_global_quit_binding() -> None:
    from flow.tui.screens.review.review import ReviewScreen
    assert any((b[0] == "q" if isinstance(b, tuple) else b.key == "q") for b in ReviewScreen.BINDINGS)


def test_focus_screen_has_shared_help_binding() -> None:
    from flow.tui.screens.focus.focus import FocusScreen
    assert any((b[0] == "?" if isinstance(b, tuple) else b.key == "?") for b in FocusScreen.BINDINGS)
```

**Step 2: Run tests to verify failures**

Run: `source .venv/bin/activate && pytest tests/unit/test_inbox_screen_bindings.py tests/unit/test_action_screen_bindings.py tests/unit/test_process_screen_bindings.py tests/unit/test_review_screen_bindings.py tests/unit/test_focus_screen_bindings.py -v`
Expected: FAIL for new tests before migration.

**Step 3: Write minimal implementation**

Implementation details:
- Replace `Screen` inheritance with `FlowScreen`.
- Replace duplicated global binding tuples with `with_global_bindings(...)` or equivalent composition.
- Keep existing screen-specific actions and local bindings unchanged.
- Ensure any explicit `action_pop_screen` semantics (for example in Action screen) remain as screen overrides.

**Step 4: Run tests to verify passes**

Run: `source .venv/bin/activate && pytest tests/unit/test_inbox_screen_bindings.py tests/unit/test_action_screen_bindings.py tests/unit/test_process_screen_bindings.py tests/unit/test_review_screen_bindings.py tests/unit/test_focus_screen_bindings.py tests/unit/test_projects_screen.py tests/unit/test_project_detail_screen.py -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add flow/tui/screens/inbox/inbox.py flow/tui/screens/process/process.py flow/tui/screens/action/action.py flow/tui/screens/projects/projects.py flow/tui/screens/projects/project_detail.py flow/tui/screens/review/review.py flow/tui/screens/focus/focus.py tests/unit/test_inbox_screen_bindings.py tests/unit/test_action_screen_bindings.py tests/unit/test_process_screen_bindings.py tests/unit/test_projects_screen.py tests/unit/test_project_detail_screen.py tests/unit/test_review_screen_bindings.py tests/unit/test_focus_screen_bindings.py
git commit -m "refactor: migrate core tui screens to shared navigation base"
```

### Task 4: Migrate Onboarding Screens to Shared Contract

**Files:**
- Modify: `flow/tui/onboarding/screens/provider.py`
- Modify: `flow/tui/onboarding/screens/credentials.py`
- Modify: `flow/tui/onboarding/screens/validation.py`
- Modify: `flow/tui/onboarding/screens/first_capture.py`
- Modify: `tests/unit/test_onboarding_keybindings_contract.py`

**Step 1: Write failing/updated tests**

```python
def test_first_capture_includes_shared_help_or_global_quit_when_expected() -> None:
    from flow.tui.onboarding.screens.first_capture import FirstCaptureScreen
    assert any((b[0] == "escape" if isinstance(b, tuple) else b.key == "escape") for b in FirstCaptureScreen.BINDINGS)
```

**Step 2: Run tests to verify failures**

Run: `source .venv/bin/activate && pytest tests/unit/test_onboarding_keybindings_contract.py -v`
Expected: FAIL until onboarding screens adopt new composition.

**Step 3: Write minimal implementation**

Implementation details:
- Use shared contract helpers for global keys and onboarding-specific action bindings.
- Preserve behavior from Phase 1 (provider/credentials/validation flow semantics).
- Keep `first_capture` submit/skip behavior unchanged while aligning base keys.

**Step 4: Run tests to verify passes**

Run: `source .venv/bin/activate && pytest tests/unit/test_onboarding_keybindings_contract.py tests/unit/test_first_capture_screen.py tests/unit/test_validation_screen.py -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add flow/tui/onboarding/screens/provider.py flow/tui/onboarding/screens/credentials.py flow/tui/onboarding/screens/validation.py flow/tui/onboarding/screens/first_capture.py tests/unit/test_onboarding_keybindings_contract.py
git commit -m "refactor: align onboarding screens with unified navigation base"
```

### Task 5: Migrate Dialogs/Modals to `FlowModalScreen`

**Files:**
- Modify: `flow/tui/common/widgets/defer_dialog.py`
- Modify: `flow/tui/common/widgets/process_task_dialog.py`
- Modify: `flow/tui/common/widgets/project_picker_dialog.py`
- Create: `tests/unit/tui/common/widgets/test_dialog_bindings.py`

**Step 1: Write failing tests**

```python
from flow.tui.common.widgets.defer_dialog import DeferDialog
from flow.tui.common.widgets.process_task_dialog import ProcessTaskDialog
from flow.tui.common.widgets.project_picker_dialog import ProjectPickerDialog


def test_defer_dialog_has_escape_cancel_binding() -> None:
    assert any((b.key == "escape") if not isinstance(b, tuple) else b[0] == "escape" for b in DeferDialog.BINDINGS)


def test_process_task_dialog_has_jk_navigation() -> None:
    keys = {b.key if not isinstance(b, tuple) else b[0] for b in ProcessTaskDialog.BINDINGS}
    assert {"j", "k"}.issubset(keys)
```

**Step 2: Run tests to verify failures**

Run: `source .venv/bin/activate && pytest tests/unit/tui/common/widgets/test_dialog_bindings.py -v`
Expected: FAIL before modal base migration.

**Step 3: Write minimal implementation**

Implementation details:
- Change dialogs to inherit from `FlowModalScreen[...]`.
- Compose dialog-specific bindings with shared modal defaults.
- Preserve dialog dismissal/results behavior exactly.

**Step 4: Run tests to verify passes**

Run: `source .venv/bin/activate && pytest tests/unit/tui/common/widgets/test_dialog_bindings.py -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add flow/tui/common/widgets/defer_dialog.py flow/tui/common/widgets/process_task_dialog.py flow/tui/common/widgets/project_picker_dialog.py tests/unit/tui/common/widgets/test_dialog_bindings.py
git commit -m "refactor: unify modal dialog bindings with shared base"
```

### Task 6: Full Verification + Docs Update

**Files:**
- Modify: `docs/plans/2026-02-15-first-run-ux-design.md` (Phase 2 row status/test evidence)

**Step 1: Run targeted binding suite**

Run: `source .venv/bin/activate && pytest tests/unit -v -k "bindings or keybinding"`
Expected: PASS.

**Step 2: Run broader touched-screen regression suite**

Run: `source .venv/bin/activate && pytest tests/unit/test_inbox_startup_context.py tests/unit/test_inbox_screen_process_menu.py tests/unit/test_projects_screen.py tests/unit/test_project_detail_screen.py tests/unit/test_first_capture_screen.py tests/unit/test_validation_screen.py -v`
Expected: PASS.

**Step 3: Update phase tracker**

In `docs/plans/2026-02-15-first-run-ux-design.md`:
- Set Phase 2 status to `completed`.
- Fill approval with approver and date.
- Record test command(s) and summary.

**Step 4: Commit**

```bash
git add docs/plans/2026-02-15-first-run-ux-design.md
git commit -m "docs: mark phase 2 unified navigation rollout complete"
```


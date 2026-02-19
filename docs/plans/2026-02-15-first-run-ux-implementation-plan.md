# First-Run UX Phase 1 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Deliver a first-run flow where users complete onboarding, capture their first task, and land in Inbox with explicit next-step guidance.

**Architecture:** Extend local onboarding config state and onboarding screen flow with a first-capture handoff. Keep business logic in existing core/engine paths; presentation layer orchestrates transitions and non-blocking UI work. Add a small keybinding contract hook to support future global navigation unification.

**Tech Stack:** Python 3.11+, Textual screens/workers, Typer launch flow, local TOML config in `flow/utils/llm/config.py`, pytest unit tests.

---

### Task 1: Add First-Run Config State Helpers

**Files:**
- Modify: `flow/utils/llm/config.py`
- Test: `tests/unit/utils/llm/test_config.py`

**Step 1: Write failing tests for first-run state fields**

```python
def test_save_config_writes_first_value_pending_flag(tmp_path: Path) -> None:
    config_path = tmp_path / "config.toml"
    save_config("gemini", {"api_key": "k"}, config_path=config_path, onboarding_completed=True)
    content = config_path.read_text()
    assert "first_value_pending = true" in content


def test_mark_first_value_completed_updates_flags(tmp_path: Path) -> None:
    config_path = tmp_path / "config.toml"
    save_config("gemini", {"api_key": "k"}, config_path=config_path, onboarding_completed=True)
    mark_first_value_completed(config_path=config_path)
    cfg = read_first_run_state(config_path=config_path)
    assert cfg.first_value_pending is False
    assert cfg.first_value_completed_at is not None
```

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && pytest tests/unit/utils/llm/test_config.py -k first_value -v`  
Expected: FAIL with missing fields/functions.

**Step 3: Write minimal implementation**

```python
@dataclass
class FirstRunState:
    first_value_pending: bool
    first_value_completed_at: Optional[str]


def read_first_run_state(config_path: Optional[Path] = None) -> FirstRunState:
    ...


def mark_first_value_completed(config_path: Optional[Path] = None) -> None:
    ...
```

Also update `save_config(...)` TOML output to include:
- `first_value_pending = true`
- `first_value_completed_at = ""`

**Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && pytest tests/unit/utils/llm/test_config.py -k first_value -v`  
Expected: PASS.

**Step 5: Commit**

```bash
git add flow/utils/llm/config.py tests/unit/utils/llm/test_config.py
git commit -m "feat: add first-run config state for first value handoff"
```

### Task 2: Add Onboarding First-Capture Screen and Flow

**Files:**
- Create: `flow/tui/onboarding/screens/first_capture.py`
- Modify: `flow/tui/onboarding/screens/validation.py`
- Modify: `flow/tui/onboarding/app.py`
- Test: `tests/unit/tui/onboarding/test_validation_screen.py`
- Test: `tests/unit/tui/onboarding/test_first_capture_screen.py`

**Step 1: Write failing tests for success transition**

```python
def test_validation_success_routes_to_first_capture(...) -> None:
    # After successful validation, app should push FirstCaptureScreen.
    ...
```

```python
def test_first_capture_submits_and_returns_result(...) -> None:
    # Enter submits non-empty text and emits structured result.
    ...
```

**Step 2: Run tests to verify they fail**

Run: `source .venv/bin/activate && pytest tests/unit/tui/onboarding/test_validation_screen.py tests/unit/tui/onboarding/test_first_capture_screen.py -v`  
Expected: FAIL due to missing screen/transition.

**Step 3: Implement new first-capture screen and route**

```python
class FirstCaptureScreen(Screen):
    BINDINGS = [
        ("escape", "skip_to_inbox", "Skip"),
        ("enter", "submit_capture", "Capture"),
    ]
```

Validation success path should:
1. Save config with onboarding complete + first_value_pending.
2. Push `FirstCaptureScreen`.
3. Defer actual capture execution to callback in onboarding app.

**Step 4: Run tests to verify they pass**

Run: `source .venv/bin/activate && pytest tests/unit/tui/onboarding/test_validation_screen.py tests/unit/tui/onboarding/test_first_capture_screen.py -v`  
Expected: PASS.

**Step 5: Commit**

```bash
git add flow/tui/onboarding/app.py flow/tui/onboarding/screens/validation.py flow/tui/onboarding/screens/first_capture.py tests/unit/tui/onboarding/test_validation_screen.py tests/unit/tui/onboarding/test_first_capture_screen.py
git commit -m "feat: add onboarding first capture handoff screen"
```

### Task 3: Wire First-Capture Result into Main App Launch

**Files:**
- Modify: `flow/cli.py`
- Modify: `flow/tui/app.py`
- Modify: `flow/tui/screens/inbox/inbox.py`
- Test: `tests/unit/test_cli.py`
- Test: `tests/unit/tui/screens/inbox/test_inbox_screen.py`

**Step 1: Write failing tests for launch handoff**

```python
def test_launch_tui_accepts_first_capture_payload(...) -> None:
    # CLI receives onboarding result and forwards startup context.
    ...
```

```python
def test_inbox_screen_highlights_captured_item_and_shows_hint(...) -> None:
    ...
```

**Step 2: Run tests to verify they fail**

Run: `source .venv/bin/activate && pytest tests/unit/test_cli.py tests/unit/tui/screens/inbox/test_inbox_screen.py -v`  
Expected: FAIL due to missing startup context support.

**Step 3: Implement launch/startup context plumbing**

```python
class FlowApp(App):
    def __init__(..., startup_context: Optional[dict[str, str]] = None, **kwargs):
        self._startup_context = startup_context or {}
```

`InboxScreen` accepts optional:
- `highlight_item_id`
- `show_first_value_hint`

and applies after async refresh completes.

**Step 4: Run tests to verify they pass**

Run: `source .venv/bin/activate && pytest tests/unit/test_cli.py tests/unit/tui/screens/inbox/test_inbox_screen.py -v`  
Expected: PASS.

**Step 5: Commit**

```bash
git add flow/cli.py flow/tui/app.py flow/tui/screens/inbox/inbox.py tests/unit/test_cli.py tests/unit/tui/screens/inbox/test_inbox_screen.py
git commit -m "feat: hand off first capture to inbox startup context"
```

### Task 4: Add Onboarding Keybinding Contract Hook

**Files:**
- Create: `flow/tui/onboarding/keybindings.py`
- Modify: `flow/tui/onboarding/screens/provider.py`
- Modify: `flow/tui/onboarding/screens/credentials.py`
- Modify: `flow/tui/onboarding/screens/validation.py`
- Test: `tests/unit/tui/onboarding/test_keybindings_contract.py`

**Step 1: Write failing tests for contract usage**

```python
def test_provider_bindings_follow_contract() -> None:
    assert "j" in PROVIDER_NAV_KEYS
    assert "k" in PROVIDER_NAV_KEYS
```

```python
def test_validation_bindings_include_retry_and_edit_hooks() -> None:
    ...
```

**Step 2: Run tests to verify they fail**

Run: `source .venv/bin/activate && pytest tests/unit/tui/onboarding/test_keybindings_contract.py -v`  
Expected: FAIL with missing module/constants.

**Step 3: Implement keybinding contract module and adopt in screens**

```python
PROVIDER_NAV_KEYS = ("j", "k", "enter", "c")
CREDENTIALS_KEYS = ("tab", "shift+tab", "enter", "ctrl+enter", "escape")
VALIDATION_KEYS = ("r", "escape")
```

Use constants when declaring `BINDINGS` to make future phase migration straightforward.

**Step 4: Run tests to verify they pass**

Run: `source .venv/bin/activate && pytest tests/unit/tui/onboarding/test_keybindings_contract.py -v`  
Expected: PASS.

**Step 5: Commit**

```bash
git add flow/tui/onboarding/keybindings.py flow/tui/onboarding/screens/provider.py flow/tui/onboarding/screens/credentials.py flow/tui/onboarding/screens/validation.py tests/unit/tui/onboarding/test_keybindings_contract.py
git commit -m "refactor: add onboarding keybinding contract hooks"
```

### Task 5: Phase Tracking, Verification, and Documentation Updates

**Files:**
- Modify: `docs/plans/2026-02-15-first-run-ux-design.md`
- Modify: `docs/plans/2026-02-15-first-run-ux-implementation-plan.md`

**Step 1: Write failing verification checklist item**

Add checklist placeholders that must be replaced with real test output summaries before completion:
- `[ ] Onboarding transition tests`
- `[ ] First capture handoff tests`
- `[ ] Keybinding contract tests`

**Step 2: Run full targeted suite for touched behavior**

Run: `source .venv/bin/activate && pytest tests/unit/tui/onboarding tests/unit/tui/screens/inbox tests/unit/utils/llm/test_config.py tests/unit/test_cli.py -v`  
Expected: PASS.

**Step 3: Update phase status rows**

Set:
- Phase 1A -> completed
- Phase 1B -> completed
- Phase 1C -> completed

with:
- approval date
- approver note
- command evidence summary

**Step 4: Run lint/format/tests as required by repo standards**

Run: `source .venv/bin/activate && pytest tests/unit -v`  
Expected: PASS for touched scope (or document known unrelated failures).

**Step 5: Commit**

```bash
git add docs/plans/2026-02-15-first-run-ux-design.md docs/plans/2026-02-15-first-run-ux-implementation-plan.md
git commit -m "docs: track first-run ux phase completion evidence"
```

## Execution Record (2026-02-15)

- [x] Onboarding transition tests
  - `source .venv/bin/activate && pytest tests/unit/test_validation_screen.py tests/unit/test_first_capture_screen.py -v`
  - Result: 4 passed
- [x] First capture handoff tests
  - `source .venv/bin/activate && pytest tests/unit/test_cli_main.py tests/unit/test_inbox_startup_context.py -v`
  - Result: 7 passed
- [x] Keybinding contract tests
  - `source .venv/bin/activate && pytest tests/unit/test_onboarding_keybindings_contract.py -v`
  - Result: 4 passed
- [x] First-run config state tests
  - `source .venv/bin/activate && pytest tests/unit/utils/llm/test_config.py -v`
  - Result: 5 passed
- [x] Combined touched-area verification
  - `source .venv/bin/activate && pytest tests/unit/test_validation_screen.py tests/unit/test_first_capture_screen.py tests/unit/test_onboarding_keybindings_contract.py tests/unit/test_inbox_startup_context.py tests/unit/test_cli_main.py tests/unit/utils/llm/test_config.py -v`
  - Result: 20 passed
- [x] Full unit suite
  - `source .venv/bin/activate && pytest tests/unit -v`
  - Result: 133 passed

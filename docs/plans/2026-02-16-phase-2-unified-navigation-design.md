# Phase 2 Unified Navigation Design

## Context

Phase 1 established a keybinding contract hook inside onboarding. Phase 2 extends this to all TUI surfaces so navigation behavior is consistent regardless of screen or modal context.

This design aligns with:
- `docs/plans/2026-02-15-first-run-ux-design.md` (Phase tracker and carry-over)
- `docs/strategy_audit_context.md` (keyboard-first, responsive CLI/TUI experience)

## Goal

Unify keybinding behavior for all screens and dialogs by introducing shared base classes and a centralized binding contract, while preserving existing screen-specific behaviors.

## Decision

Selected approach: **Option 2 (Base screen/mixin style)**.

Rationale:
- Creates durable consistency through inheritance instead of duplicated tuples.
- Reduces long-term drift risk across rapidly evolving screens.
- Keeps behavior stable by treating screen-specific actions as additive.

## Design

### 1. Base Binding Contract

Introduce shared global key semantics:
- `q`: quit
- `escape`: back/cancel
- `?`: help
- `j/k`: move up/down
- cross-screen navigation actions exposed consistently where relevant

Keep feature-specific keys local to each screen/dialog (for example `c`, `f`, `d`, `x`, stage keys).

### 2. Shared Base Layers

Create:
- `flow/tui/common/keybindings.py`
- `flow/tui/common/base_screen.py`

`base_screen.py` provides:
- `FlowScreen(Screen)` for normal screens
- `FlowModalScreen(ModalScreen[T])` for dialogs/modals

Both provide default global bindings and shared fallback actions. Screens remain free to override or extend.

### 3. Migration Scope (All Current Binding Surfaces)

All `Screen` classes:
- `flow/tui/screens/inbox/inbox.py`
- `flow/tui/screens/process/process.py`
- `flow/tui/screens/action/action.py`
- `flow/tui/screens/projects/projects.py`
- `flow/tui/screens/projects/project_detail.py`
- `flow/tui/screens/review/review.py`
- `flow/tui/screens/focus/focus.py`
- `flow/tui/onboarding/screens/provider.py`
- `flow/tui/onboarding/screens/credentials.py`
- `flow/tui/onboarding/screens/validation.py`
- `flow/tui/onboarding/screens/first_capture.py`

All modal/dialog classes:
- `flow/tui/common/widgets/defer_dialog.py`
- `flow/tui/common/widgets/process_task_dialog.py`
- `flow/tui/common/widgets/project_picker_dialog.py`

App-level classes (`flow/tui/app.py`, `flow/tui/onboarding/app.py`) remain bootstrap-focused.

### 4. Non-Goals

- No behavioral redesign of process/review/action flows.
- No new navigation routes beyond consistency normalization.
- No changes to engine/domain logic.

## Error Handling and UX Safety

- Base actions should fail gracefully when no back stack exists.
- Help action should remain non-blocking and user-visible.
- Any fallback path should preserve current async/non-blocking behavior.

## Testing and Verification

Add contract coverage for:
- shared keybinding constants/composition
- base screen/modal defaults
- per-screen binding conformance
- modal/dialog binding conformance

Verification commands:
- `source .venv/bin/activate && pytest tests/unit -v -k "bindings or keybinding"`
- `source .venv/bin/activate && pytest tests/unit/test_inbox_screen_bindings.py tests/unit/test_action_screen_bindings.py tests/unit/test_process_screen_bindings.py tests/unit/test_projects_screen.py tests/unit/test_project_detail_screen.py -v`

## Approval

Approved in chat on **2026-02-16**:
- Use Option 2 (base-screen approach)
- Apply to all screens
- Proceed with this rollout and test strategy

# First-Run UX Redesign (Phase 1) Design

## Context

Flow's onboarding and first-run experience currently validates provider setup, but it does not reliably carry users into an immediate "first value" moment. This design targets reduced onboarding friction and improved early retention by guiding new users from setup to first capture and into Inbox in one sequence.

Primary target for this iteration:
- First-run success

Future-ready hooks (not fully implemented in this phase):
- Unified global navigation (Phase 2)
- Faster process throughput affordances (Phase 3)
- Focus mode habit loop entry points (Phase 4)

## Goals

- New users complete onboarding and reach first captured task in under 5 minutes.
- Users see explicit "what to do next" instructions at each step.
- Errors are recoverable in place without losing typed state.
- Keyboard-first interactions remain consistent with Textual and current Flow usage.

## Non-Goals (Phase 1)

- Full keybinding migration across all TUI screens.
- Full process funnel redesign.
- Full focus-mode onboarding journey.

## User Experience Design

### 1. Onboarding Completion UX (Phase 1A)

Provider screen:
- Keep `j/k` navigation.
- Add `Enter` as a first-class continue path.
- Keep provider hints and add clearer default recommendation copy.

Credentials screen:
- Keep `Enter` for continue and `Esc`/`Ctrl+b` for back.
- Add pre-submit field validation hints.
- Preserve typed input when returning from validation errors.

Validation screen:
- Keep current loading/success/error states.
- On success, make CTA explicit for first value:
  - Primary path: capture first task
  - Secondary path: skip to Inbox (escape hatch)

### 2. First-Value Handoff (Phase 1B)

After successful validation:
- Show a lightweight first-capture step.
- Save capture via existing engine path.
- Route to Inbox and highlight captured item.
- Show one-time hint:
  - "Press Enter to process, ? for help"

### 3. Interaction Concept Source (v0 MCP Subagent)

A dedicated v0-backed design pass produced three alternatives:
- Progressive Credential Wizard
- Task-First Handshake
- Contextual Pipeline Flow

Chosen direction for Phase 1:
- Progressive Credential Wizard

Reason:
- Lowest implementation risk against current screen architecture.
- Preserves current user mental model.
- Adds explicit first-value transition with minimal additional complexity.

## Navigation Contract Hook (Phase 1C)

Create a shared contract module for onboarding/first-run surfaces and future expansion:
- Global contract (reserved for app-wide adoption):
  - `q` quit
  - `escape` back
  - `?` help
  - `j/k` move
- Reserved future globals:
  - `i` inbox
  - `a` actions
  - `p` process
  - `g` projects
  - `f` focus

Phase 1 applies the contract to onboarding + first-value handoff only.

## Data Flow

Config state extensions in `~/.flow/config.toml`:
- `onboarding_completed = true`
- `first_value_pending = true` after successful provider validation
- `first_value_completed_at = "<ISO8601>"` after first capture is completed

Optional local analytics hooks for future iterations:
- `first_run_variant = "<variant_name>"`
- `onboarding_duration_ms = <int>`

All state remains local-first.

## Error Handling

- Credential validation failures remain in place with clear actions: retry/back/edit.
- Preserve typed credential and first-capture draft across recoverable failures.
- If capture fails after successful onboarding:
  - show inline error and retry option
  - provide skip-to-inbox fallback
  - keep `first_value_pending = true`

## Architecture and Safety

- Preserve dependency direction:
  - Presentation -> Core -> Database/Models
- Keep blocking work off the UI thread (`run_worker` / `asyncio.to_thread`).
- Keep existing security behavior (`chmod 600` for config writes).
- Avoid moving TUI screen styles into global theme files.

## Testing Strategy

Targeted tests:
- Config state transitions for first-run flags.
- Onboarding success -> first-capture route.
- Capture success/failure transitions and flag behavior.
- State persistence in retry/back/edit flows.
- Keybinding contract consistency for onboarding screens.

## Iteration Phase Tracker

This file is the source of truth for implementation stages.

| Phase | Goal | Status | Approval | Test Evidence |
|---|---|---|---|---|
| 1A | Onboarding completion UX polish | completed | Approved by user on 2026-02-15 | `pytest tests/unit/test_validation_screen.py tests/unit/test_first_capture_screen.py tests/unit/test_onboarding_keybindings_contract.py -v` (10 passed) |
| 1B | First-value handoff (capture -> inbox) | completed | Approved by user on 2026-02-15 | `pytest tests/unit/test_cli_main.py tests/unit/test_inbox_startup_context.py tests/unit/utils/llm/test_config.py -v` (12 passed) |
| 1C | Navigation contract hooks for later phases | completed | Approved by user on 2026-02-15 | `pytest tests/unit/test_onboarding_keybindings_contract.py -v` (4 passed) |
| 2 | Unified cross-screen navigation rollout | completed | Approved by user on 2026-02-16 | `pytest tests/unit -v -k "bindings or keybinding"` (22 passed) and `pytest tests/unit/test_inbox_startup_context.py tests/unit/test_inbox_screen_process_menu.py tests/unit/test_projects_screen.py tests/unit/test_project_detail_screen.py tests/unit/test_first_capture_screen.py tests/unit/test_validation_screen.py -v` (16 passed) |
| 3 | Process throughput simplification | in_progress | pending | `source .venv/bin/activate && pytest tests/unit/test_process_screen_bindings.py -v` (3 passed) |
| 4 | Focus stickiness entry loop | completed | Pending user approval (2026-02-19) | `source .venv/bin/activate && pytest tests/unit/test_process_screen_bindings.py -v` (6 passed) |

## Carry-Over for Next Iterations

- Phase 3 should reduce process funnel interaction cost by reusing first-run guidance patterns (single explicit CTA, one-step-next hints).
- Phase 4 delivered a first-run focus bridge from Process completion (`Enter` starts Focus and marks first-run loop complete).

## Completion Protocol

When each phase is done:
1. Run targeted tests.
2. Update phase row:
   - status -> `completed`
   - approval -> approver + date
   - test evidence -> command + short result summary
3. Record carry-over work for the next phase.

# Daily Workspace Enter Confirm Regression

- [x] Reproduce the no-response Enter bug on the focused daily list
- [x] Add failing runtime test for Enter-driven confirmation
- [x] Route OptionList selection to the daily workspace primary action
- [x] Run targeted verification and update lessons learned

## Review / Results
- Mandatory Flow review checklist run for security/privacy/architecture/typing/async safety/tests: no material issues found.
- Verification evidence:
  - `source .venv/bin/activate && pytest tests/unit/test_daily_workspace_screen.py tests/unit/test_daily_workspace.py -q` => 17 passed, 0 failed.
- Root cause:
  - The focused `OptionList` consumed `Enter`, but the daily workspace did not handle `OptionList.OptionSelected`.
  - The daily list also initialized with `highlighted=None`, so pressing `Enter` had nothing to select.
- Implemented behavior:
  - Daily workspace now initializes the first plan/focus row as selected after list population.
  - Daily workspace no longer depends on `Enter` for plan confirmation.
  - Plan confirmation uses `x`, which avoids `OptionList` key conflicts and matches the on-screen help/status guidance.

# Daily Workspace UI Brainstorm

- [x] Explore project context (current daily workspace UI, docs, recent commits)
- [x] Ask clarifying questions (one at a time)
- [x] Propose 2-3 approaches with trade-offs and recommendation
- [x] Present design and get approval
- [x] Write design doc in `docs/plans/`
- [x] Transition to implementation planning (`writing-plans`)

## Review / Results
- Approved design saved to `docs/plans/2026-03-09-daily-workspace-ui-refresh-design.md`.
- Implementation plan saved to `docs/plans/2026-03-09-daily-workspace-ui-refresh-implementation-plan.md`.
- Ready for execution in a separate `executing-plans` session.

# Daily Workspace Confirmed-Plan Guidance

- [x] Explore current daily workspace status-strip behavior and existing tests
- [x] Add failing test for persistent post-confirmation guidance
- [x] Implement persistent status-strip guidance after plan confirmation
- [x] Update relevant docs for the confirmed-plan guidance
- [x] Run targeted verification and Flow review checklist

## Review / Results
- Mandatory Flow review checklist run for security/privacy/architecture/typing/async safety/tests: no material issues found.
- Verification evidence:
  - `source .venv/bin/activate && pytest tests/unit/test_daily_workspace_screen.py tests/unit/test_daily_workspace.py -q` => 15 passed, 0 failed.
- Implemented behavior:
  - Daily workspace planning mode now keeps a persistent status strip that tells the user to confirm the plan with `x`.
  - After plan approval, the status strip switches to persistent next-step guidance for `[1]` planned work, `c` completion, and `w` Daily Wrap.

# Inbox vs Focus Brainstorm

- [x] Explore project context (Inbox/Focus behavior, docs, recent commits)
- [x] Ask clarifying questions (one at a time)
- [x] Propose 2-3 approaches with trade-offs and recommendation
- [x] Present design and get approval
- [x] Write design doc in Obsidian vault
- [x] Transition to implementation planning (`writing-plans`)
- [x] Add failing tests for daily-plan persistence and engine APIs
- [x] Implement daily-plan storage and engine/service layer
- [x] Add failing tests for default `flow` routing and daily workspace screen
- [x] Implement daily workspace TUI and default routing
- [x] Update docs for `flow` daily workspace behavior
- [x] Run targeted verification, full unit suite, and review checklist

## Review / Results
- Obsidian docs saved:
  - `Personal/Projects/flow-gtd/01-designs/2026/2026-03-08-flow-daily-workspace-redesign-design.md`
  - `Personal/Projects/flow-gtd/02-implementation-plans/2026/2026-03-08-flow-daily-workspace-redesign-implementation-plan.md`
- Mandatory code review checklist run for security/privacy/architecture/typing/async safety/tests: no material issues found.
- Verification evidence:
  - `source .venv/bin/activate && pytest tests/unit/test_sqlite.py tests/unit/test_daily_workspace.py tests/unit/test_daily_workspace_screen.py tests/unit/test_cli_main.py -v` => 32 passed, 0 failed.
  - `source .venv/bin/activate && pytest tests/unit -v` => 222 passed, 0 failed.
- Implemented behavior:
  - Plain `flow` and `flow tui` now open a new daily workspace screen instead of defaulting to Inbox.
  - Added first-class daily-plan persistence for `Top 3` and `Bonus` entries.
  - Added engine APIs for daily workspace candidate grouping, plan persistence, wrap summary, and optional AI wrap insight.
  - Added a new daily workspace screen with planning, focus-list, and wrap summary states, while keeping Inbox/Projects/Review reachable.

---

# Resource Storage Migration Todo

- [x] Explore project context (resource save/search, onboarding/setup, config)
- [x] Ask clarifying questions (one at a time)
- [x] Propose 2-3 approaches with trade-offs and recommendation
- [x] Present design and get approval
- [x] Write design doc in docs/plans/
- [x] Transition to implementation planning (writing-plans)
- [x] Implement resource storage abstraction + provider factory
- [x] Add Obsidian provider with persisted vault index + semantic search
- [x] Migrate CLI and engine resource paths to abstraction
- [x] Add onboarding storage selection and existing-user storage prompt
- [x] Update docs for new storage behavior
- [x] Verify with full unit test suite

## Review / Results
- Mandatory code review checklist run for security/privacy/architecture/typing/async safety/tests: no material issues found.
- Verification evidence:
  - `pytest tests/unit -v` => 186 passed, 0 failed.
- User-approved behavior implemented:
  - Plain-language storage selection in setup.
  - Obsidian storage option with setup-time validation.
  - No migration of old resources; storage applies to new saves.

---

# TUI Panel Focus Shortcuts + Headers

- [x] Explore project context (panel layouts, current focus keys, help text)
- [x] Ask clarifying questions (one at a time)
- [x] Propose 2-3 approaches with trade-offs and recommendation
- [x] Present design and get approval
- [x] Write design doc in `docs/plans/`
- [x] Transition to implementation planning (`writing-plans`)
- [x] Add failing tests for panel shortcut/focus behavior
- [x] Implement number/name-based panel switching and panel headers
- [x] Update help text/docs to reflect new shortcuts
- [x] Run targeted tests and relevant unit suite

## Review / Results
- Mandatory code review checklist run for security/privacy/architecture/typing/async safety/tests: no material issues found.
- Verification evidence:
  - `pytest tests/unit/test_action_screen_bindings.py tests/unit/test_inbox_screen_bindings.py tests/unit/test_projects_screen_bindings.py -v` => 13 passed, 0 failed.
  - `pytest tests/unit -v` => 195 passed, 0 failed.
- Implemented behavior:
  - Added panel focus shortcuts by number and panel abbreviation across `Inbox`, `Projects`, and `Action`.
  - Added explicit panel headers showing shortcut hints.
  - Preserved `Tab` focus behavior on the Action screen.

---

# Professional Ops Full UI Overhaul

- [x] Explore project context (current onboarding screens, styles, and recent changes)
- [x] Ask clarifying questions (one at a time)
- [x] Propose 2-3 approaches with trade-offs and recommendation
- [x] Present design and get approval
- [x] Write design doc in `docs/plans/`
- [x] Transition to implementation planning (`writing-plans`)
- [x] Implement approved redesign in onboarding screens/styles
- [x] Add or update tests for any behavior changes
- [x] Run targeted verification tests

## Review / Results
- Mandatory code review checklist run for security/privacy/architecture/typing/async safety/tests: no material issues found.
- Verification evidence:
  - `python -m compileall flow/tui` => success.
  - `pytest tests/unit/tui/common/test_keybindings_contract.py tests/unit/tui/common/test_base_screen_bindings.py tests/unit/tui/common/widgets/test_dialog_bindings.py tests/unit/test_action_screen_bindings.py tests/unit/test_inbox_screen_bindings.py tests/unit/test_projects_screen_bindings.py -v` => 21 passed, 0 failed.
  - `pytest tests/unit -v` => 195 passed, 0 failed.
- Implemented behavior:
  - Replaced global visual system with professional-ops token palette and shared shell primitives.
  - Moved shared TCSS tokens to `flow/tui/common/ops_tokens.tcss` and loaded it from app/screen `CSS_PATH` lists.
  - Reworked onboarding screens to two-pane operational layout with progress and details pane.
  - Applied consistent ops shell/status/keyhint framing to core TUI screens and modal dialogs.
  - Stabilized `test_engine_resources` by forcing `flow-library` storage backend in-module so tests do not depend on local user config.

---

# Focus Empty State UI Upgrade

- [x] Explore project context (focus screen layout, current empty state, related tests)
- [x] Ask clarifying questions (one at a time)
- [x] Propose 2-3 approaches with trade-offs and recommendation
- [x] Present design and get approval
- [x] Write design doc in Obsidian vault (`Personal/Projects/flow-gtd/01-designs/2026/`)
- [x] Transition to implementation planning (`writing-plans`)
- [x] Add failing tests for approved empty-state behavior
- [x] Implement approved focus empty-state UI and guidance actions
- [x] Run targeted verification tests

## Review / Results
- Obsidian docs saved:
  - `Personal/Projects/flow-gtd/01-designs/2026/2026-03-01-focus-empty-state-inbox-cta-design.md`
  - `Personal/Projects/flow-gtd/02-implementation-plans/2026/2026-03-01-focus-empty-state-inbox-cta-implementation-plan.md`
- Verification evidence:
  - `source .venv/bin/activate && pytest tests/unit/test_focus_screen_bindings.py tests/unit/test_focus_screen_ui.py tests/unit/test_inbox_startup_context.py tests/unit/tui/common/widgets/test_dialog_bindings.py -v` => 17 passed, 0 failed.
  - `source .venv/bin/activate && pytest tests/unit/test_inbox_screen_bindings.py tests/unit/test_focus_screen_bindings.py tests/unit/test_focus_screen_ui.py tests/unit/test_inbox_startup_context.py tests/unit/tui/common/widgets/test_dialog_bindings.py -v` => 23 passed, 0 failed.

---

# Empty State Component for Focus/Inbox

- [x] Explore project context (Focus/Inbox screen structure and existing empty-state tests)
- [x] Add failing tests for empty-state renderer and updated screen behavior
- [x] Implement reusable empty-state renderer with dynamic center padding and randomized tips provider
- [x] Integrate renderer into Focus and Inbox empty states
- [x] Add Inbox `n` shortcut to open quick capture from empty state
- [x] Run targeted verification tests

## Review / Results
- Mandatory code review checklist run for security/privacy/architecture/typing/async safety/tests: no material issues found.
- Verification evidence:
  - `source .venv/bin/activate && pytest tests/unit/tui/common/widgets/test_empty_state.py tests/unit/test_focus_screen_ui.py tests/unit/test_inbox_screen_bindings.py tests/unit/test_inbox_startup_context.py tests/unit/test_inbox_screen_process_menu.py -q` => 24 passed, 0 failed.
- Implemented behavior:
  - Focus and Inbox now show a centered, low-noise empty-state block with ASCII anchor, status header, high-contrast `[Key] Action`, and one randomized productivity tip.
  - Empty-state layout re-centers on terminal resize using dynamic padding.
  - Inbox now supports `n` as a direct quick-capture action.

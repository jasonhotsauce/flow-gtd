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

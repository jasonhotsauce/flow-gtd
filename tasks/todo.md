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

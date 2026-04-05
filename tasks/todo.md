# Worktree Environment Bootstrap

- [x] Write design and implementation plan docs for worktree environment bootstrap
- [x] Add failing regression tests for repo-managed worktree environment setup
- [x] Implement versioned bootstrap script and `make worktree-setup`
- [x] Add parent-root convenience wrapper script for the worktree root
- [x] Update README with the worktree bootstrap workflow
- [x] Run targeted verification for tests and real setup commands

## Review / Results
- Implemented behavior:
  - Added `scripts/setup_worktree_env.sh` and `make worktree-setup WORKTREE=<name>` so a checkout can create its own `.venv`, install `poetry`, install dependencies from `main`, and then install the target checkout in editable mode.
  - Added a parent-root convenience wrapper at `/Users/wenbinzhang/Documents/flow-gtd/worktree-setup` so the setup command can be launched directly from the shared directory that contains `main/` and sibling worktrees.
  - Updated `README.md` with the supported parent-root bootstrap workflow.
  - Synced `Makefile`, `README.md`, and `scripts/setup_worktree_env.sh` into the sibling `../main` checkout so `make -C main worktree-setup ...` works immediately in the current local layout.
- TDD evidence:
  - `source .venv/bin/activate && pytest tests/unit/test_worktree_env_setup.py -v` initially failed because `scripts/setup_worktree_env.sh` did not exist.
  - The same command passed after the implementation: `3 passed in 2.14s`.
- Verification evidence:
  - From `/Users/wenbinzhang/Documents/flow-gtd`: `./worktree-setup main` completed successfully and created `/Users/wenbinzhang/Documents/flow-gtd/main/.venv`.
  - From `/Users/wenbinzhang/Documents/flow-gtd`: `./worktree-setup project-tasks-as-candidate` completed successfully and reused `/Users/wenbinzhang/Documents/flow-gtd/project-tasks-as-candidate/.venv` while reinstalling from `main`.
  - `source .venv/bin/activate && python -c 'import flow,sys; print(sys.executable); print(flow.__file__)'` in `/Users/wenbinzhang/Documents/flow-gtd/main` resolved to `main/.venv/bin/python` and `main/flow/__init__.py`.
  - `source .venv/bin/activate && python -c 'import flow,sys; print(sys.executable); print(flow.__file__)'` in `/Users/wenbinzhang/Documents/flow-gtd/project-tasks-as-candidate` resolved to `project-tasks-as-candidate/.venv/bin/python` and `project-tasks-as-candidate/flow/__init__.py`.
  - `source .venv/bin/activate && poetry --version` reported `Poetry (version 2.3.3)` in both checkouts.
- Mandatory Flow review checklist:
  - Security/privacy: no secrets, unsafe SQL, or sensitive logging added; the new shell entrypoints only operate on explicit local checkout paths.
  - Architecture: changes stay in repo tooling, docs, and tests; no Flow package dependency-direction rules were affected.
  - Typing: the new Python test module uses explicit `Path` and `CompletedProcess[str]`-compatible typing.
  - Async safety: no Textual runtime paths changed.
  - Tests: added focused regression coverage for sibling-target setup, `main` setup, and missing-target failure.
  - Review findings: no material issues found.

# Daily Recap Rename

- [x] Record implementation plan and rename scope
- [x] Rename Daily Workspace feature labels and actions from `wrap` to `daily recap`
- [x] Rename relevant engine/service/test identifiers to `recap` where safe
- [x] Update README and PRD terminology
- [x] Run targeted verification
- [x] Run Flow review checklist on touched files

## Review / Results
- Implemented behavior:
  - Renamed the Daily Workspace feature surface from `wrap` to `Daily Recap` in the TUI, CLI startup path, engine/service APIs, tests, and docs.
  - Kept persistence behavior unchanged; the SQLite table remains `daily_wrap_status` for backward compatibility, but the Python API around it now uses recap terminology.
- Verification evidence:
  - `source .venv/bin/activate && pytest tests/unit/test_daily_workspace.py tests/unit/test_daily_workspace_screen.py tests/unit/test_cli_main.py -q` => `70 passed in 2.11s`.
- Mandatory Flow review checklist:
  - Security/privacy: no new secrets, logging, unsafe SQL, or user-input path handling added.
  - Architecture: rename stays within presentation/core/database boundaries; no dependency-direction violations introduced.
  - Typing: changed public APIs remain explicitly typed across screen, engine, service, and sqlite layers.
  - Async safety: Daily Workspace still uses `asyncio.to_thread` for blocking engine calls; no new blocking TUI work added.
  - Tests: targeted unit coverage updated for renamed UI actions, startup recap gating, and recap summary APIs.
  - Review findings: no material issues found.

# Daily Recap Gate Acknowledgement

- [x] Confirm the startup daily recap acknowledgement path and capture the root cause
- [x] Add a failing regression test for acknowledging a prior-day recap gate routing into today's workspace
- [x] Implement the minimal daily recap acknowledgement transition into today's workspace
- [x] Run targeted verification
- [x] Run Flow review checklist on touched files

## Review / Results
- Root cause:
  - In the startup recap gate, `w` called `action_show_daily_recap()`, which marked the prior day recapped but only re-rendered the same recap pane for the same `plan_date`.
  - `x` remained bound to `action_confirm_plan()`, which returned immediately outside planning mode, so it did nothing in the recap gate.
- Implemented behavior:
  - When the screen is launched in the prior-day startup recap gate, both `w` and `x` now acknowledge that recap, clear the gate flags, switch `plan_date` to today, and asynchronously load today's normal workspace in-place.
  - Normal non-gated recap behavior is unchanged: `w` still opens the current plan's explicit recap summary.
- TDD evidence:
  - `source .venv/bin/activate && pytest tests/unit/test_daily_workspace_screen.py -k startup_recap_gate_acknowledgement_routes_into_today -v` initially failed:
    - `w`: prior recap was marked but `screen._plan_date` stayed on `2026-03-08`
    - `x`: no recap acknowledgement was recorded at all
  - The same command passed after the fix, covering both `w` and `x` with real Textual key presses.
- Verification evidence:
  - `source .venv/bin/activate && pytest tests/unit/test_daily_workspace_screen.py -v` => `46 passed in 2.36s`.
- Mandatory Flow review checklist:
  - Security/privacy: no secrets, unsafe SQL, or sensitive logging added.
  - Architecture: change stays inside the Daily Workspace TUI screen and its unit tests; no dependency-direction violations introduced.
  - Typing: changed helper and test doubles remain explicitly typed.
  - Async safety: transition still uses `asyncio.create_task(self._refresh_async())`; no new blocking TUI work added.
  - Tests: added runtime regression coverage for both `w` and `x` acknowledgement paths, and reran the full screen module.
  - Review findings: no material issues found.

# Reminders Sync Active-Only

- [x] Review existing Reminders sync path and identify why completed reminders still appear in Flow
- [x] Add a failing regression test for previously imported reminders that are now completed in Apple Reminders
- [x] Implement minimal sync reconciliation so only active reminders remain active in Flow
- [x] Run targeted verification
- [x] Run Flow review checklist on touched files

## Review / Results
- Root cause:
  - `flow sync` already skipped reminders where `rem.isCompleted()` is true, but it only applied that filter to the current import pass.
  - When a reminder had been imported earlier and was later completed in Apple Reminders, the matching Flow item identified by `original_ek_id` was left active in SQLite, so it kept showing up in Flow after subsequent syncs.
- Implemented behavior:
  - During Reminders sync, completed source reminders now archive any matching non-terminal Flow item with the same `original_ek_id`.
  - Active reminders keep the existing import/update path, so sync still refreshes active reminder titles and counts only incomplete reminders as imported.
- TDD evidence:
  - `source .venv/bin/activate && pytest tests/unit/test_reminders_sync.py -k source_reminder_is_completed -v` => failed first with `AssertionError: assert 'active' == 'archived'`, then passed after archiving previously imported items whose source reminder is now completed.
- Verification evidence:
  - `source .venv/bin/activate && pytest tests/unit/test_reminders_sync.py -v` => `1 passed in 0.07s`.
- Mandatory Flow review checklist:
  - Security/privacy: no secrets, logging, or unsafe path/SQL changes.
  - Architecture: EventKit sync behavior remains isolated to `flow/sync/reminders.py`; no dependency-direction violations introduced.
  - Typing: new test doubles and changed sync path keep explicit types compatible with current modules.
  - Async safety: unchanged; sync remains CLI-side synchronous EventKit work.
  - Tests: targeted regression coverage now exists for the stale completed-reminder path.
  - Review findings: no material issues found.

# Reminders Sync Skip Recently Deleted

- [x] Confirm the Reminder sync path currently imports incomplete reminders from the macOS `Recently Deleted` system list
- [x] Add a failing regression test for an incomplete reminder whose calendar title is `Recently Deleted`
- [x] Implement minimal filtering so `flow sync` ignores reminders from `Recently Deleted`
- [x] Run targeted verification
- [x] Run Flow review checklist on touched files

## Review / Results
- Root cause:
  - `sync_reminders_to_flow()` iterated every fetched reminder and only filtered on completion state and missing EventKit ids.
  - EventKit reminders from the macOS `Recently Deleted` system list still look incomplete, so they were counted and imported like normal tasks.
- Implemented behavior:
  - Reminders whose `calendar().title()` normalizes to `recently deleted` are skipped before Flow applies active/completed reconciliation.
  - Normal lists keep the existing sync behavior, including archiving previously imported reminders that later become completed.
- TDD evidence:
  - `source .venv/bin/activate && pytest tests/unit/test_reminders_sync.py -k recently_deleted -v` => failed first with `AssertionError: assert 1 == 0`, then passed after filtering the `Recently Deleted` calendar.
- Verification evidence:
  - `source .venv/bin/activate && pytest tests/unit/test_reminders_sync.py -v` => `2 passed in 0.10s`.
- Mandatory Flow review checklist:
  - Security/privacy: no secrets, unsafe SQL, or sensitive logging added.
  - Architecture: change stays inside `flow/sync/reminders.py` and its unit test; dependency direction is unchanged.
  - Typing: new helper stays internal and typed compatibly with current module conventions.
  - Async safety: unchanged; no new blocking behavior added to Textual paths.
  - Tests: regression coverage now includes the `Recently Deleted` import path.
  - Review findings: no material issues found.

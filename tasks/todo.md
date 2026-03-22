# Wrap Gate Review Fixes

- [x] Reproduce the completed-plan wrap gate regression and the inconsistent startup wrap-gate labeling
- [x] Add failing regression tests for preserved wrap state and coherent startup wrap-gate copy
- [x] Implement the minimal wrap-state and startup-label fix
- [x] Run targeted verification for Daily Workspace wrap behavior and CLI routing
- [x] Run Flow review checklist on touched `flow/` and `tests/` files

## Review / Results
- Root cause:
  - `DailyPlanService.get_plan_items()` intentionally filters out completed planned items, but `Engine.get_daily_workspace_state()` was using the filtered active-item lists to decide `needs_plan`. That collapsed completed-but-unwrapped plans back into planning mode even though a saved plan and wrap summary still existed.
  - The startup wrap-gate branch relabeled pane `1` to `Wrap Summary` while still rendering the normal carry-forward plan list there, so the pane labels and content disagreed.
- Implemented behavior:
  - Daily Workspace now treats “saved plan exists” separately from “active planned items remain,” so an unwrapped prior plan still opens as confirmed-mode wrap flow even when every planned item is already done.
  - Startup wrap-gate copy now labels pane `1` as `Carry Forward` and keeps pane `2` as normal task detail, matching the list content that is actually rendered while pane `3` continues to hold the wrap summary.
- TDD evidence:
  - `source .venv/bin/activate && pytest tests/unit/test_daily_workspace.py -k "completed_saved_plan_still_blocks_wrap_gate_until_wrapped" -v` => failed first with `assert True is False`, then passed after separating saved-plan existence from active-item presence.
  - `source .venv/bin/activate && pytest tests/unit/test_daily_workspace_screen.py -k "start_in_wrap_renders_as_prior_day_wrap_gate" -v` => failed first because pane `1` still showed `[1] Wrap Summary`, then passed after making the startup wrap-gate labels match the carry-forward list.
- Verification evidence:
  - `source .venv/bin/activate && pytest tests/unit/test_daily_workspace.py tests/unit/test_daily_workspace_screen.py tests/unit/test_cli_main.py -v` => `69 passed in 1.86s`.
- Mandatory Flow review checklist:
  - No material issues found in security/privacy, architecture direction, typing, async safety, or targeted test coverage for the touched files.

# Execute Daily Workspace Calendar Reuse Implementation Plan

- [x] Review approved implementation plan, relevant skills, existing lessons, and current worktree overlap
- [x] Task 1 RED: add failing focus recommendation tests for calendar-aware confirmed-mode ranking and explanation metadata
- [x] Task 1 GREEN: implement calendar-aware confirmed recommendation inputs, explanation text, and deterministic fallback ordering
- [x] Task 2 RED: add failing engine tests for compact calendar availability summary and unavailable fallback
- [x] Task 2 GREEN: expose calendar availability through Engine with a narrow EventKit-backed service and exception-safe fallback
- [x] Task 3 RED: add failing Daily Workspace screen tests for confirmed-mode `f` using calendar-aware recommendation output and explanation status
- [x] Task 3 GREEN: fetch calendar availability off the main loop, highlight the recommended planned item, and surface explanation text in the detail status area
- [x] Update README.md and docs/PRD.md for implementation-accurate Daily Workspace recommendation behavior
- [x] Run targeted verification from the approved plan
- [x] Run broader `daily_workspace` / `focus` regression coverage from the approved plan
- [x] Run Flow review checklist on touched `flow/` and `tests/` files
- [x] Record verification evidence and final review notes in this file

## Review / Results
- Execution notes:
  - Work stayed in the existing worktree `/Users/wenbinzhang/Documents/worktree/confirmed-state-redesign` as requested.
  - The worktree already had overlapping uncommitted Daily Workspace and docs changes; I preserved them and applied the calendar-reuse changes incrementally on top.
  - Existing reusable calendar-availability code was not present in the current tree, but prior branch history included an old EventKit calendar reader in commit `a542159`; this task reused that approach in a smaller engine/service seam instead of reviving the removed Focus screen.
- Implemented behavior:
  - `flow/core/focus.py` now accepts a compact `CalendarAvailability` input, ranks only active confirmed `Top 3` / `Bonus` items, and returns a short explanation string with the recommendation.
  - Calendar fit is advisory only: if both calendar window data and duration metadata exist, `f` prefers the first fitting active `Top 3` item, then fitting `Bonus`; otherwise it falls back deterministically to saved confirmed-plan order.
  - `Engine.get_calendar_availability()` now returns a compact summary with safe `unavailable` fallback, backed by a narrow EventKit reader in `flow/core/services/calendar_availability.py`.
  - `DailyWorkspaceScreen.action_recommend_focus_item()` now fetches calendar availability through `asyncio.to_thread(...)`, highlights the returned planned item, and shows the explanation in `#detail-pane-status` without adding any calendar pane or scheduling UI.
  - The screen preserves the recommendation explanation across the highlight event triggered by programmatic selection, then clears that override on later navigation changes.
  - README / PRD now describe confirmed-mode `f` as a calendar-aware heuristic only, with no auto-scheduling or calendar UI.
- TDD evidence:
  - `source .venv/bin/activate && pytest tests/unit/test_focus.py -v` => first failed with `ImportError: cannot import name 'CalendarAvailability' from 'flow.core.focus'`, then passed after implementing the new recommendation contract.
  - `source .venv/bin/activate && pytest tests/unit/test_daily_workspace.py -k calendar -v` => first failed because `Engine` had no `_calendar_availability_service`, then passed after adding the engine/service seam and fallback behavior.
  - `source .venv/bin/activate && pytest tests/unit/test_daily_workspace_screen.py -k recommend_focus_item -v` => first selected `0` tests because names did not match the plan command, then failed with `assert 0 == 1` because `f` still highlighted the first Top item, then passed after wiring calendar-aware recommendation through an async-safe path.
- Verification evidence:
  - `source .venv/bin/activate && pytest tests/unit/test_focus.py tests/unit/test_daily_workspace.py tests/unit/test_daily_workspace_screen.py -v` => `59 passed in 1.79s`.
  - `source .venv/bin/activate && pytest tests/unit -k "daily_workspace or focus" -v` => `69 passed, 198 deselected in 1.87s`.
- Mandatory Flow review checklist:
  - Security/privacy: no secrets added, no SQL changes, no unsafe path handling, and no sensitive task/calendar content is newly logged.
  - Architecture: Daily Workspace remains the only planned-work execution surface; TUI code stays in `flow/tui`, recommendation logic stays in `flow/core/focus.py`, and EventKit handling stays below the TUI layer in a narrow core service.
  - Typing: new/changed APIs use explicit types, including the calendar summary and recommendation models.
  - Async safety: calendar reads now run through `asyncio.to_thread(...)` from the Daily Workspace path, avoiding main-loop blocking.
  - Fallback behavior: calendar failures and unavailable metadata fall back to deterministic saved-plan order instead of raising or changing execution scope.
  - Tests: focused unit coverage was added for recommendation ranking, engine fallback behavior, and confirmed-mode `f` screen behavior.
  - Review findings: no material issues remain after fixing the recommendation-status highlight event ordering in the Daily Workspace screen.

# Execute Daily Workspace and Focus Dedup Plan

- [x] Review approved implementation plan, relevant skills, and existing lessons
- [x] Inspect current worktree state and identify pre-existing unrelated dirty files
- [x] Confirm current repo still exposes standalone `flow focus` and process-to-focus bridge
- [x] Task 1 RED: add CLI regression test proving `focus` is no longer a valid subcommand
- [x] Task 1 GREEN: remove standalone CLI `focus` surface and align README / PRD command docs
- [x] Task 2 RED: add process-screen regression test proving completion no longer routes to standalone Focus
- [x] Task 2 GREEN: remove standalone process navigation/help references and point users back to Daily Workspace
- [x] Task 3 RED: add pure unit tests for confirmed-plan-only recommendation ranking
- [x] Task 3 GREEN: refactor focus recommendation helper to rank only active confirmed-plan items
- [x] Task 4 RED: add Daily Workspace tests for confirmed-mode recommendation action behavior
- [x] Task 4 GREEN: wire confirmed Daily Workspace recommendation action to the confirmed-plan helper
- [x] Task 5 RED/GREEN: remove obsolete focus artifacts and stale references/tests
- [x] Run targeted verification from the approved plan
- [x] Run full `pytest tests/unit -v`
- [x] Run Flow review checklist on touched `flow/` and `tests/` files
- [x] Record verification evidence and final review notes in this file

## Review / Results
- Execution notes:
  - Current repository work is already in the dedicated worktree `/Users/wenbinzhang/Documents/worktree/confirmed-state-redesign` on branch `codex/confirmed-state-redesign`.
  - Pre-existing dirty files include `README.md`, `docs/PRD.md`, `flow/tui/screens/daily_workspace/daily_workspace.py`, `flow/tui/screens/daily_workspace/daily_workspace.tcss`, `tests/unit/test_daily_workspace_screen.py`, `tasks/todo.md`, `tasks/lessons.md`, and `flow/tui/common/widgets/`.
  - Dirty changes inspected so far appear to be compatible with the approved focus-dedup plan, but they overlap Daily Workspace implementation files and will be preserved while I apply the plan incrementally.
- Implemented behavior:
  - Removed standalone `flow focus` from the CLI and updated README / PRD language so Daily Workspace is the only planned-work execution surface.
  - Removed the Process screen first-run bridge into standalone Focus and redirected completion copy/primary action back to Daily Workspace.
  - Narrowed `flow/core/focus.py` to confirmed-plan recommendation helpers only, keeping recommendations constrained to active confirmed `Top 3` / `Bonus` items with deterministic saved-plan ordering.
  - Added confirmed-mode `f` recommendation behavior in Daily Workspace so the screen can highlight the next planned item without ever recommending unplanned work.
  - Deleted obsolete standalone Focus screen artifacts, calendar-based focus selector code, and the old Focus screen UI tests.
- Verification evidence:
  - `source .venv/bin/activate && pytest tests/unit/test_cli_main.py -k focus -v` => failed first with `AssertionError: assert 'focus' not in {...}`, then passed after removing the command.
  - `source .venv/bin/activate && pytest tests/unit/test_process_screen_bindings.py -k stage4 -v` => failed first because completion copy still said `Start Focus mode` and `_primary_stage4_async()` still called `action_start_focus()`, then passed after redirecting back to Daily Workspace.
  - `source .venv/bin/activate && pytest tests/unit/test_focus.py -v` => failed first with `ImportError: cannot import name 'recommend_confirmed_focus_item'`, then passed after adding the confirmed-plan helper.
  - `source .venv/bin/activate && pytest tests/unit/test_daily_workspace_screen.py -k "recommend_focus_item or exposes_plan_focus_and_wrap_bindings" -v` => failed first because the `f` binding/action was missing, then passed after wiring the confirmed-mode recommendation action.
  - `source .venv/bin/activate && pytest tests/unit -k focus -v` => `32 passed, 237 deselected in 1.64s`.
  - `source .venv/bin/activate && pytest tests/unit/test_cli_main.py -v` => `11 passed in 0.47s`.
  - `source .venv/bin/activate && pytest tests/unit/test_daily_workspace_screen.py -v` => `42 passed in 2.12s`.
  - `source .venv/bin/activate && pytest tests/unit/test_focus.py tests/unit/test_focus_recommendation.py -v` => `8 passed in 0.07s`.
  - `source .venv/bin/activate && pytest tests/unit/test_process_screen_bindings.py -v` => `6 passed in 0.20s`.
  - `source .venv/bin/activate && pytest tests/unit -v` => `269 passed in 10.22s`.
- Mandatory Flow review checklist:
  - Security/privacy: no secrets added, no unsafe path handling introduced, no SQL query construction changed, and no sensitive task/resource content is newly logged.
  - Architecture: command removal stayed in `flow/cli.py`; recommendation logic now stays as a pure helper in `flow/core/focus.py`; Daily Workspace owns the confirmed-mode UX; no dependency-direction violations were introduced.
  - Typing: new/changed helper and screen methods keep explicit type hints.
  - Async safety: Daily Workspace and Process screen changes avoid new blocking work on the Textual event loop; engine calls remain on existing async/threaded paths.
  - Tests: targeted TDD coverage was added/updated for CLI removal, process completion handoff, confirmed-plan recommendation logic, Daily Workspace recommendation behavior, and focus-artifact cleanup.

# Daily Workspace and Focus Dedup

- [x] Explore current CLI and TUI execution surfaces for overlap
- [x] Clarify product rule for focus selection within confirmed daily plan
- [x] Propose consolidation approaches and approve a single-surface design
- [x] Write design doc in the Obsidian design archive
- [x] Create implementation plan for removing standalone Focus

## Review / Results
- Approved product decision:
  - `Daily Workspace` is the only planning and execution surface.
  - Standalone `Focus` command and screen should be removed immediately.
  - Smart recommendation remains as an in-workspace action during confirmed mode only.
  - Recommendation is constrained to active confirmed-plan items only, prioritizing `Top 3` before `Bonus`.
- Planned change areas:
  - CLI command surface and docs
  - Daily workspace confirmed-state interaction model
  - Focus-selection logic migration from standalone screen/service path into daily-workspace-owned behavior
  - Targeted tests for command removal and confirmed-plan-only recommendation behavior

# Product Research: GTD Adoption and Productivity Assessment

- [x] Review project lessons and existing task tracking context
- [x] Inspect README, PRD, strategy audit, and feature docs
- [x] Examine shipped CLI, core services, and TUI workflows for GTD support
- [x] Synthesize how Flow supports GTD adoption, time management, and productivity
- [x] Produce prioritized improvement recommendations

## Review / Results
- Scope:
  - Evaluated product positioning, documented workflow intent, and implementation-accurate user flows across capture, process, projects, review, daily workspace, focus mode, and resource sidecar behavior.
- Evidence reviewed:
  - `README.md`
  - `docs/PRD.md`
  - `docs/strategy_audit_context.md`
  - `docs/features/projects.md`
  - `flow/cli.py`
  - `flow/core/engine.py`
  - `flow/core/services/process.py`
  - `flow/core/services/daily_plan.py`
  - `flow/core/services/review.py`
  - `flow/core/focus.py`
  - `flow/database/sqlite.py`
  - `flow/tui/screens/inbox/inbox.py`
  - `flow/tui/screens/process/process.py`
  - `flow/tui/screens/projects/projects.py`
  - `flow/tui/screens/action/action.py`
  - `flow/tui/screens/focus/focus.py`
  - `flow/tui/screens/daily_workspace/daily_workspace.py`
- Outcome:
  - Flow already supports the core GTD loop unusually well for a CLI/TUI product: low-friction capture, structured clarification, project/next-action organization, weekly review, and daily execution with contextual resources.
  - The biggest product gaps are not basic GTD coverage; they are adoption gaps for new or inconsistent users: limited explicit habit scaffolding, weak system-health visibility, fragmented entry points for some GTD behaviors, and a relatively high mental-model load around when to use each screen.

# Daily Workspace Focus Persistence

- [x] Reproduce focus-mode add/edit persistence gap and isolate the save path
- [x] Add a failing regression test for persisting focus-mode Top 3 / Bonus edits
- [x] Implement the minimal confirmed-plan persistence fix
- [x] Run targeted verification and Flow review checklist

## Review / Results
- Root cause:
  - Daily workspace focus mode allowed live edits to the confirmed Top 3 and Bonus lists, but those actions only mutated `_top_items` and `_bonus_items` in memory.
  - Persistence only happened in planning mode via `action_confirm_plan()`, so re-entering Flow reloaded the previous saved plan and discarded focus-mode additions.
- Implemented behavior:
  - Confirmed-plan edits now save immediately through a shared persistence helper after focus-mode add, remove, promote, demote, reorder, and Top 3 replacement actions.
  - Newly added Top 3 and Bonus tasks now survive exit and re-entry because the current confirmed plan is written back as soon as it changes.
- Verification evidence:
  - `source .venv/bin/activate && pytest tests/unit/test_daily_workspace_screen.py -k confirmed_add_to_bonus_persists_updated_plan -v` => failed first with no `save_daily_plan` call, then passed after the fix.
  - `source .venv/bin/activate && pytest tests/unit/test_daily_workspace_screen.py -k "confirmed_add_to_bonus_persists_updated_plan or confirmed_state_preserves_reorder_promote_demote_and_complete or confirmed_remove_switches_to_unplanned_and_list_navigation_recovers or top_three_replacement_chooser_demotes_selected_item_into_bonus" -v` => `4 passed`.
  - `source .venv/bin/activate && pytest tests/unit/test_daily_workspace_screen.py tests/unit/test_daily_workspace.py -v` => `47 passed in 1.57s`.
- Mandatory Flow review checklist:
  - No material issues found in security/privacy, architecture direction, typing, async safety, or targeted test coverage.

# Daily Workspace UI Refresh Execution

# Daily Workspace Candidate Focus After Draft Add

- [x] Inspect planning-mode add-to-draft focus behavior and current tests
- [x] Add a failing regression test for keeping Candidates focused after `t`/`b`
- [x] Implement the minimal daily workspace focus-policy change
- [x] Run targeted verification and Flow review checklist

## Review / Results
- Root cause:
  - Planning-mode `action_add_to_top()` and `action_add_to_bonus()` switched `_draft_focus` to `top` or `bonus` immediately after adding a candidate.
  - That focus handoff forced users back to pane `1` before they could keep triaging Candidates.
- Implemented behavior:
  - Planning-mode adds now update Top 3 / Bonus content without stealing focus from Candidates.
  - The candidate list keeps its highlight after `t` or `b`, so users can continue adding items without an extra pane-switch keystroke.
- Verification evidence:
  - `source .venv/bin/activate && pytest tests/unit/test_daily_workspace_screen.py -k planning_add_to_draft_keeps_candidates_focused -v` => failed first with `_draft_focus == "top"` instead of `"candidates"`, then passed after the fix.
  - `source .venv/bin/activate && pytest tests/unit/test_daily_workspace_screen.py -v` => `35 passed in 1.50s`.
- Mandatory Flow review checklist:
  - No material issues found in security/privacy, architecture direction, typing, async safety, or targeted test coverage.

# Daily Wrap Duplicate Summary

- [x] Reproduce the duplicate daily wrap content and trace the render path
- [x] Add a failing regression test for duplicate wrap summary rendering
- [x] Implement the minimal daily workspace fix for the duplicate summary
- [x] Run targeted verification and Flow review checklist

## Review / Results
- Root cause:
  - The wrap pane still had two text render targets, `#wrap-content` and `#daily-wrap`.
  - In explicit wrap mode and startup wrap-gate mode, the screen wrote the same formatted summary into both widgets, so the pane rendered the summary twice.
- Implemented behavior:
  - `#wrap-content` is now the single active daily-wrap summary surface.
  - The legacy `#daily-wrap` widget is cleared in all wrap-summary refresh paths, eliminating the duplicate block shown in the screenshot.
- Verification evidence:
  - `source .venv/bin/activate && pytest tests/unit/test_daily_workspace_screen.py -k "show_daily_wrap_explicitly_replaces_unplanned_pane_content or start_in_wrap_renders_as_prior_day_wrap_gate" -v` => failed first, then passed after the fix.
  - `source .venv/bin/activate && pytest tests/unit/test_daily_workspace_screen.py -v` => `34 passed`.
- Mandatory Flow review checklist:
  - No material issues found in security/privacy, architecture direction, typing, async safety, or targeted test coverage.

# Daily Workspace UI Refresh Execution

# Daily Workspace Unplanned Grouping

- [x] Review the confirmed-state pane-3 implementation and current tests
- [x] Add a failing test for grouped unplanned rows inside the pane-3 widget
- [x] Implement grouped unplanned headers in the selectable pane-3 list and remove the duplicate lower summary
- [x] Run targeted verification and Flow review checklist

## Review / Results
- Implemented behavior:
  - Confirmed-state pane `3` now renders one grouped `OptionList` with disabled headers for `Inbox`, `Next Actions`, and `Project Tasks`, including item counts.
  - The duplicate lower `wrap-content` text summary is now empty in confirmed mode, so unplanned work only appears once.
  - Wrap-panel keyboard navigation now skips header rows and lands only on actionable task rows.
- Verification evidence:
  - `source .venv/bin/activate && pytest tests/unit/test_daily_workspace_screen.py -k "confirmed_state_renders_today_detail_and_grouped_unplanned_work or confirmed_wrap_focus_keeps_list_navigation_active or confirmed_state_detail_follows_planned_and_unplanned_selection or confirmed_state_adds_and_removes_items_without_reentering_planning or confirmed_remove_returns_item_to_original_unplanned_list_without_switching_focus or confirmed_add_to_top_opens_replacement_chooser_when_top_three_is_full or top_three_replacement_chooser_demotes_selected_item_into_bonus" -v` => `7 passed`
  - `source .venv/bin/activate && pytest tests/unit/test_daily_workspace_screen.py -v` => `34 passed`
- Mandatory Flow review checklist:
  - No material issues found in security/privacy, architecture direction, typing, async safety, or test coverage.

# Final PR Review

- [x] Review current branch against `origin/main` for final PR blockers
- [x] Run targeted verification for touched Daily Workspace / CLI / focus tests

## Review / Results
- Findings:
  - Blocker: prior-day wrap gating breaks for fully completed but unwrapped plans because `get_latest_unwrapped_plan_date()` still returns the date, while `get_daily_workspace_state()` derives `needs_plan=True` from active-only planned items and drops into planning mode instead of wrap mode.
  - Important: startup wrap-gate labeling is inconsistent with rendered content. Pane `1` is retitled `Wrap Summary`, but `_refresh_confirmed_list()` still fills `#daily-list` with Top 3 / Bonus items, so the UI claims to show the wrap summary while actually showing today’s plan list.
- Verification evidence:
  - `source .venv/bin/activate && pytest tests/unit/test_daily_workspace.py tests/unit/test_daily_workspace_screen.py tests/unit/test_cli_main.py tests/unit/test_process_screen_bindings.py -q` => `74 passed in 1.79s`
  - `source .venv/bin/activate && pytest tests/unit/test_focus.py -q` => `4 passed in 0.09s`
  - `source .venv/bin/activate && python - <<'PY' ...` => reproduced `latest_unwrapped 2026-03-08` together with `needs_plan True` for a completed-but-unwrapped prior day, confirming the wrap-gate regression.

# Confirmed-State Remove Focus Regression

- [x] Inspect confirmed-state daily workspace remove/focus code paths and existing tests
- [x] Add a failing screen regression test for remove-to-unplanned plus focus/list navigation recovery
- [x] Update confirmed-state list refresh and add/remove focus transitions
- [x] Run targeted verification and Flow review checklist

## Review / Results
- Root cause:
  - Confirmed-mode remove left `_draft_focus` on `today`, so the shared `#daily-list` rebuilt with Today items immediately after `d` instead of switching to Unplanned.
  - Confirmed-mode add/remove flows used inconsistent pane transitions, and list refresh always reset highlight to the first row.
- Implemented behavior:
  - Removing a confirmed planned item now switches the shared list into Unplanned mode immediately.
  - Adding an unplanned item back into Top 3 or Bonus switches the shared list back to Today.
  - Confirmed-list refresh now preserves the current highlighted option when that item still exists after a rebuild.
- Verification evidence:
  - `source .venv/bin/activate && pytest tests/unit/test_daily_workspace_screen.py -k "confirmed_remove_switches_to_unplanned_and_list_navigation_recovers" -v` => failed first with `_draft_focus == "today"` instead of `"wrap"`.
  - `source .venv/bin/activate && pytest tests/unit/test_daily_workspace_screen.py -k "confirmed_state_adds_and_removes_items_without_reentering_planning or confirmed_remove_switches_to_unplanned_and_list_navigation_recovers or confirmed_state_detail_follows_planned_and_unplanned_selection or confirmed_state_preserves_reorder_promote_demote_and_complete" -v` => `4 passed`.
  - `source .venv/bin/activate && pytest tests/unit/test_daily_workspace_screen.py -v` => `31 passed`.
  - `source .venv/bin/activate && pytest tests/unit/test_daily_workspace_screen.py tests/unit/test_daily_workspace.py -v` => `42 passed`.
- Mandatory Flow review checklist:
  - No material issues found in security/privacy, architecture direction, typing, async safety, or test coverage.

# Release Daily Workspace to Main

- [x] Inspect branch status, release targets, and existing version/tags
- [x] Run fresh targeted verification for touched daily-workspace paths
- [x] Run fresh full unit-suite verification on the current working tree
- [ ] Bump version for the release and commit remaining branch changes
- [ ] Merge `feat/daily-workspace` into `main` and verify the merged result
- [ ] Run the Make-based release workflow and capture exact output / blockers

## Review / Results
- Release verification evidence:
  - `source .venv/bin/activate && poetry run pytest tests/unit/test_daily_workspace_screen.py tests/unit/test_daily_workspace.py tests/unit/tui/common/widgets/test_dialog_bindings.py -v` => `36 passed in 0.92s`
  - `source .venv/bin/activate && poetry run pytest tests/unit -v` => `242 passed in 1.72s`

# Daily Workspace Calendar Reuse Design

- [x] Review current daily workspace recommendation flow and existing calendar references
- [x] Approve product direction for lightweight calendar reuse inside Daily Workspace
- [x] Write design doc for calendar-aware confirmed-plan recommendation behavior
- [x] Write implementation plan with TDD and verification steps

## Review / Results
- Approved product direction:
  - Reuse calendar as an advisory ranking signal for Daily Workspace recommendation in confirmed mode.
  - Keep Daily Workspace task-first; do not add a calendar pane or scheduling UI.
  - Preserve deterministic `Top 3`/`Bonus` fallback behavior when calendar data or duration metadata is unavailable.
- Planned change areas:
  - Calendar availability read model exposed through the engine/service layer
  - Calendar-aware confirmed-plan recommendation helper in `flow/core/focus.py`
  - Daily Workspace recommendation UX and explanation messaging
  - Unit and screen regression coverage for recommendation ranking and no-calendar fallback
- Mandatory Flow review checklist:
  - No material issues found in security/privacy, architecture direction, typing, async safety, or test coverage.

- [x] Review approved design, implementation plan, and required skills
- [x] Verify clean branch baseline for daily workspace tests
- [x] Record execution deviation: user requested implementation in current branch without a git worktree
- [x] Task 1: Add failing screen tests for draft feedback, draft editing, and confirm transition
- [x] Task 2: Implement multi-pane daily workspace layout, editing actions, and terminal-native Material styling
- [x] Task 3: Add failing service tests and implement richer deterministic wrap feedback
- [x] Task 4: Add failing screen tests and integrate richer wrap-pane rendering
- [x] Task 5: Update docs, run verification commands, run Flow review, and capture evidence

## Review / Results
- Execution note:
  - User explicitly requested development in the current branch instead of using a git worktree.
- Baseline verification evidence:
  - `source .venv/bin/activate && pytest tests/unit/test_daily_workspace_screen.py tests/unit/test_daily_workspace.py -q` => `17 passed in 0.51s`
- Implemented behavior:
  - Daily workspace planning now shows persistent `Candidates`, `Top 3 Draft`, `Bonus Draft`, `Detail`, and live `Wrap` surfaces with the existing professional-ops palette and a more terminal-native material hierarchy.
  - Planning supports same-screen draft editing for remove, promote, demote, and Top 3 reordering, then transitions in place to a merged `Today` execution view after confirmation.
  - Daily wrap now derives deterministic accomplishments, carry-forward items, verdicts, and coaching feedback from persisted daily-plan entries without relying on AI.
- Verification evidence:
  - `source .venv/bin/activate && pytest tests/unit/test_daily_workspace_screen.py -v` => `17 passed in 0.49s`
  - `source .venv/bin/activate && pytest tests/unit/test_daily_workspace.py -v` => `9 passed in 0.08s`
  - `source .venv/bin/activate && pytest tests/unit/test_daily_workspace_screen.py tests/unit/test_daily_workspace.py -v` => `28 passed in 0.77s`
  - `source .venv/bin/activate && pytest tests/unit/test_daily_workspace_screen.py tests/unit/test_daily_workspace.py tests/unit/test_cli_main.py -v` => `37 passed in 1.20s`
  - `source .venv/bin/activate && pytest tests/unit -v` => `239 passed in 1.98s`
- Mandatory Flow review checklist:
  - Security/privacy: no secrets added; no SQL changes; no new sensitive logging.
  - Architecture: daily-wrap rules stay in `flow/core/services/daily_plan.py`; TUI remains in `flow/tui/screens/daily_workspace/`; no dependency-direction violations introduced.
  - Typing: changed service and screen APIs keep explicit type hints.
  - Async safety: screen refresh and AI insight generation still run engine work via `asyncio.to_thread`; no new blocking work added to Textual handlers.
  - Tests: targeted screen and service TDD coverage added, plus targeted CLI verification and full unit-suite verification passed.

### Follow-up: Daily Workspace Inline Quick Capture

- [x] Add persistent `n` daily-workspace action for quick capture
- [x] Show new-task guidance when planning candidates are empty
- [x] Restyle shared quick-capture dialog to match updated ops/material shell
- [x] Run targeted verification for daily workspace and shared quick-capture paths

## Review / Results
- Follow-up behavior:
  - Daily workspace now exposes `n` as a persistent action in planning mode, not just an empty-state fallback.
  - When no candidates exist, the candidates pane and detail pane both direct the user to create a new task with `n`.
  - The shared quick-capture dialog now uses the same refreshed surface grammar and copy style as the updated daily workspace.
- Follow-up verification evidence:
  - `source .venv/bin/activate && pytest tests/unit/test_daily_workspace_screen.py tests/unit/tui/common/widgets/test_dialog_bindings.py -v` => `27 passed in 0.81s`
  - `source .venv/bin/activate && pytest tests/unit/test_daily_workspace_screen.py tests/unit/tui/common/widgets/test_dialog_bindings.py tests/unit/test_inbox_screen_process_menu.py -v` => `33 passed in 0.79s`
- Follow-up Flow review checklist:
  - No material issues found in security/privacy, architecture, typing, async safety, or test coverage.

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

# Today's Plan Confirmed-State Redesign Brainstorm

- [x] Explore project context (daily workspace screen, docs, tests, recent commits)
- [x] Ask clarifying questions (one at a time)
- [x] Propose 2-3 approaches with trade-offs and recommendation
- [x] Present design and get approval
- [x] Write design doc in Obsidian vault
- [x] Transition to implementation planning (`writing-plans`)

## Review / Results
- Context gathered:
  - Current confirmed-plan view reuses planning/wrap panes and still renders live wrap copy before the day is actually done.
  - Existing actions for add/remove/promote/demote/reorder already exist, but they are gated to planning mode only.
  - Engine already exposes daily-plan state and wrap summary; resource retrieval APIs exist via `flow.core.focus.FocusService`.
- Approved behavior:
  - Confirmed plan remains editable all day.
  - Adding from unplanned work requires explicit placement into Top 3 or Bonus.
  - If Top 3 is full, adding into Top 3 opens a chooser so the user can select which current Top 3 task to demote.
  - Removing a planned task returns it to its original open grouping, not always Inbox.
  - Right side shows all open unplanned actionable work across inbox, next actions, and project tasks, with a small-screen grouped fallback.
  - No live wrap pane during execution; wrap appears only when explicitly opened.
  - If the prior day was never wrapped, the next day must surface that wrap before today's planning flow.
- Artifacts:
  - Design: `/Users/wenbinzhang/Library/Mobile Documents/iCloud~md~obsidian/Documents/Personal/10 Projects/flow-gtd/01-designs/2026/2026-03-13-todays-plan-confirmed-state-redesign-design.md`
  - Implementation plan: `/Users/wenbinzhang/Library/Mobile Documents/iCloud~md~obsidian/Documents/Personal/10 Projects/flow-gtd/02-implementation-plans/2026/2026-03-13-todays-plan-confirmed-state-redesign-implementation-plan.md`

# Today's Plan Confirmed-State Redesign Execution

- [x] Load required skills and review the approved implementation plan
- [x] Create sibling git worktree at `../worktree/confirmed-state-redesign`
- [x] Inspect `.gitignore` and inventory only task-relevant ignored local assets
- [x] Verify copied `.venv` usability and recreate it in the worktree when reuse fails
- [x] Run clean baseline verification in the worktree before coding
- [x] Task 1: Add failing engine tests for confirmed-state workspace data
- [x] Task 2: Add failing screen tests for confirmed-state layout and editing
- [x] Task 3: Add failing tests for confirmed-state add/remove/promote/demote flows
- [x] Task 4: Add failing tests for Top 3 full replacement chooser
- [x] Task 5: Add failing tests for task detail resources
- [x] Task 6: Add failing tests for explicit wrap and prior-day wrap gate
- [x] Task 7: Update docs, run review, and capture final verification evidence

## Review / Results
- Worktree setup:
  - Worktree path: `/Users/wenbinzhang/Documents/worktree/confirmed-state-redesign`
  - `.gitignore` inspected for development/test relevance: `.venv/`, `data/`, `.pytest_cache/`, `.mypy_cache/`, `.ruff_cache/`, `.textual/`, `.cache/`, `models/`, `logs/`, `tmp/`, `temp/`, `.codex/.env_setup_done`
  - Copied into worktree:
    - `.venv/`: copied first because it is the only ignored asset required to quickly validate the Python/Poetry/test toolchain for this task
  - Skipped from copy:
    - `data/`: present locally, but not required for these unit tests or the planned code paths
    - `.pytest_cache/`, `.mypy_cache/`, `.ruff_cache/`, `.textual/`, `.cache/`, `models/`, `logs/`, `tmp/`, `temp/`, `.codex/.env_setup_done`: absent locally or not needed to develop and run the targeted tests
  - `.venv` outcome:
    - Copied `.venv` was not reusable because activating it still resolved `python` to `/Users/wenbinzhang/Documents/flow-gtd/.venv/bin/python`
    - Preserved the copied directory as `.venv.copied-from-main`
    - Recreated `.venv` in the worktree with `python3.11 -m venv .venv`, then installed Poetry and project dependencies there
- Baseline verification:
  - `source .venv/bin/activate && python -V && which python && poetry --version && pytest tests/unit/test_daily_workspace.py tests/unit/test_daily_workspace_screen.py tests/unit/test_cli_main.py -q` => `Python 3.11.15`, worktree-local interpreter path, `Poetry 2.3.2`, `39 passed in 2.75s`
- Task 1 TDD evidence:
  - RED: `source .venv/bin/activate && pytest tests/unit/test_daily_workspace.py -v` => `2 failed, 9 passed`; failures were missing `unplanned_work` data and missing `mark_daily_plan_wrapped`
  - GREEN: `source .venv/bin/activate && pytest tests/unit/test_daily_workspace.py -v` => `11 passed in 0.09s`
- Task 2 TDD evidence:
  - RED: `source .venv/bin/activate && pytest tests/unit/test_daily_workspace_screen.py -v` => `2 failed, 20 passed`; failures were stale confirmed-state pane titles and missing unplanned-selection detail behavior
  - GREEN: `source .venv/bin/activate && pytest tests/unit/test_daily_workspace_screen.py -v` => `22 passed in 0.71s`
- Task 3 TDD evidence:
  - RED: `source .venv/bin/activate && pytest tests/unit/test_daily_workspace_screen.py -v` => `2 failed, 22 passed`; failures were confirmed-state action guards still blocking add/remove/reorder flows
  - GREEN: `source .venv/bin/activate && pytest tests/unit/test_daily_workspace_screen.py -v` => `24 passed in 0.74s`
- Task 4 TDD evidence:
  - RED: `source .venv/bin/activate && pytest tests/unit/test_daily_workspace_screen.py -v` => collection failed with `ModuleNotFoundError` for `top_three_replacement_dialog`, confirming the chooser path did not exist yet
  - GREEN: `source .venv/bin/activate && pytest tests/unit/test_daily_workspace_screen.py -v` => `26 passed in 0.79s`
- Task 5 TDD evidence:
  - RED: `source .venv/bin/activate && pytest tests/unit/test_daily_workspace_screen.py -v` => `2 failed, 26 passed`; failures were missing detail metadata/resources and missing concise resource rendering for unplanned items
  - GREEN: `source .venv/bin/activate && pytest tests/unit/test_daily_workspace_screen.py -v` => `28 passed in 0.76s`
- Task 6 TDD evidence:
  - RED: `source .venv/bin/activate && pytest tests/unit/test_daily_workspace_screen.py tests/unit/test_cli_main.py -v` => `2 failed, 37 passed`; failures were missing explicit wrap visibility state and missing prior-day wrap startup routing
  - GREEN: `source .venv/bin/activate && pytest tests/unit/test_daily_workspace_screen.py tests/unit/test_cli_main.py -v` => `39 passed in 0.82s`
- Task 7 doc checklist:
  - [x] Confirmed plan remains editable after confirmation
  - [x] Unplanned work is grouped on the right
  - [x] Wrap is explicit, not live by default
  - [x] Prior-day unwrapped plan gates startup before today
- Task 7 verification:
  - `source .venv/bin/activate && pytest tests/unit/test_daily_workspace.py tests/unit/test_daily_workspace_screen.py tests/unit/test_cli_main.py -v` => `50 passed in 0.93s`
  - `source .venv/bin/activate && pytest tests/unit/test_daily_workspace_screen.py tests/unit/test_cli_main.py -v` => `39 passed in 0.82s`
  - `source .venv/bin/activate && pytest tests/unit -v` => `253 passed in 8.52s`
- Flow code review checklist:
  - Security/privacy: no secrets added; no unsafe SQL or new sensitive logging introduced.
  - Architecture: presentation changes stayed in `flow/tui/` and `flow/cli.py`; persistence stayed in `flow/core/` plus `flow/database/sqlite.py`; no dependency-direction violations introduced.
  - Typing: new and changed helpers keep explicit type hints across engine, CLI, and TUI code.
  - Async safety: detail-resource loading stays off the UI thread via `asyncio.to_thread`; wrap and list refresh flows remain non-blocking in normal app execution.
  - Tests: targeted daily-workspace/CLI verification and the full unit suite both passed.
  - Result: no material issues found.
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

---

# Daily Workspace Wrap Focus Navigation Fix

- [x] Reproduce the confirmed-state `[3]` wrap/unplanned focus bug with focused runtime/label regression tests
- [x] Fix focus/highlight ownership for the shared confirmed-state list when switching to unplanned work
- [x] Run targeted verification for the touched daily-workspace screen/tests

## Review / Results
- Root cause:
  - The previous fix treated confirmed state as one shared `OptionList` whose meaning flipped between Today and Unplanned. That contradicted the implementation plan and made pane `3` visually wrong in the live UI.
  - Confirmed-state `d` also forced focus into wrap mode, which was not the intended design; removal should restore the task to its original unplanned group while Today remains editable.
  - Confirmed-state add flow used direct `t/b` mutation instead of a chooser, so the UI skipped the required `Top 3` vs `Bonus` decision.
- Implemented behavior:
  - Confirmed state now renders two real lists: Today stays in `#daily-list`, and Unplanned Work uses a dedicated `#unplanned-list` in pane `3`.
  - Pressing `3` focuses the unplanned pane list, and `j/k` moves the cursor there.
  - Removing from Today with `d` restores the task to its original unplanned group without switching away from Today.
  - Adding an unplanned task now opens a `Top 3` vs `Bonus` chooser before mutating the plan; Top 3 replacement still uses the existing replacement chooser when full.
- Verification evidence:
  - `source .venv/bin/activate && pytest tests/unit/test_daily_workspace_screen.py -k "confirmed_wrap_focus_keeps_list_navigation_active or confirmed_state_renders_today_detail_and_grouped_unplanned_work or confirmed_wrap_focus_targets_unplanned_list or confirmed_state_adds_and_removes_items_without_reentering_planning or confirmed_remove_returns_item_to_original_unplanned_list_without_switching_focus or confirmed_remove_switches_to_unplanned_and_list_navigation_recovers or confirmed_add_to_top_opens_replacement_chooser_when_top_three_is_full or top_three_replacement_chooser_demotes_selected_item_into_bonus" -v` => failed first across the old shared-list behavior, then passed after the redesign.
  - `source .venv/bin/activate && pytest tests/unit/test_daily_workspace_screen.py tests/unit/test_daily_workspace.py -v` => `45 passed`.
- Mandatory Flow review checklist:
  - No material issues found in security/privacy, architecture direction, typing, async safety, or targeted test coverage.

---

# Daily Workspace Focus Dedup Implementation Execution

- [x] Review approved implementation plan, relevant skills, and current lessons
- [x] Inspect current worktree state and identify pre-existing dirty changes in affected files
- [ ] Task 1: Add failing CLI test for removing standalone `flow focus`, then remove CLI/docs references
- [ ] Task 2: Add failing process-screen test for removing Focus bridge/navigation, then update process copy/flow
- [ ] Task 3: Add failing recommendation tests, then constrain focus recommendation to active confirmed-plan items only
- [ ] Task 4: Add failing Daily Workspace confirmed-mode tests, then wire the in-workspace focus recommendation action
- [ ] Task 5: Remove obsolete standalone focus artifacts and stale tests/imports
- [ ] Task 6: Run targeted verification, full unit verification, Flow review checklist, and record evidence

## Review / Results
- Execution note:
  - Work started from an already-dirty feature worktree. Existing uncommitted Daily Workspace changes in `flow/tui/screens/daily_workspace/daily_workspace.py`, `tests/unit/test_daily_workspace_screen.py`, and related docs/widgets were treated as baseline and preserved.

---

# Daily Plan Duplicate Entry Crash

- [x] Capture traceback evidence and inspect current daily-plan persistence constraints
- [x] Trace the duplicate item path through daily workspace planning actions
- [x] Add failing tests for duplicate planned-item handling in the screen flow and save path
- [x] Implement the minimal duplicate-prevention / normalization fix
- [x] Run targeted verification and record Flow review checklist results

## Review / Results
- Root cause hypothesis:
  - Planning-mode add actions only reject duplicates already present in the target bucket.
  - The same candidate can therefore be added to `Top 3` and then to `Bonus`, producing duplicate `item_id` values in the in-memory draft.
  - Confirming the plan passes both lists directly into persistence, where `daily_plan_entries` enforces `PRIMARY KEY (plan_date, item_id)` and raises `IntegrityError`.
- Execution note:
  - The worktree already contains unrelated in-progress changes; this bugfix will stay scoped to the daily plan/daily workspace path and avoid reverting any baseline edits.
- Implemented fix:
  - Daily workspace draft-add actions now guard by `item.id` across both planned buckets instead of relying on whole-object equality.
  - Daily plan persistence now normalizes duplicate ids before writing, preserving first occurrence order in `Top 3` and then `Bonus`.
- Verification evidence:
  - `source .venv/bin/activate && pytest tests/unit/test_daily_workspace.py tests/unit/test_daily_workspace_screen.py -k "deduplicates_item_ids_before_persisting or planning_add_to_draft_keeps_candidates_focused or planning_add_to_bonus_rejects_item_already_in_top_by_id" -v` => `3 passed, 54 deselected`.
  - `source .venv/bin/activate && pytest tests/unit/test_daily_workspace.py tests/unit/test_daily_workspace_screen.py -v` => `57 passed in 1.59s`.
- Mandatory Flow review checklist:
  - Security/privacy: no secrets, unsafe logging, or SQL changes introduced.
  - Architecture: fix stayed within daily-workspace presentation and daily-plan service boundaries; no dependency-direction violations introduced.
  - Typing: new helpers and changed logic retain explicit type hints.
  - Async safety: no new blocking work added to Textual handlers; existing async patterns remain unchanged.
  - Tests: added regression coverage for duplicate-id draft/save behavior and re-ran the touched daily workspace suites.
  - Result: no material issues found.

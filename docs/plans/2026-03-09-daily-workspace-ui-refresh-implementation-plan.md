# Daily Workspace UI Refresh Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Redesign the daily workspace so planning has visible draft feedback and edit actions, confirmation transitions smoothly into execution, and daily wrap shows meaningful accomplishments and coaching feedback.

**Architecture:** Keep the existing daily workspace entry point, persistence model, and engine APIs as the base. Expand the screen into a structured multi-pane layout, add screen-local draft-plan editing state/actions, and move deterministic wrap-feedback logic into the daily-plan service or engine layer so business rules stay out of the TUI. Preserve async safety by continuing to load/refresh workspace state through `asyncio.to_thread`.

**Tech Stack:** Python 3.11+, Textual screens/TCSS, Flow engine and daily-plan service, pytest unit tests.

---

### Task 1: Lock the new planning and focus behavior with failing screen tests

**Files:**
- Modify: `tests/unit/test_daily_workspace_screen.py`

**Step 1: Write failing tests for visible draft-plan feedback**
- Add a test that applies planning state, seeds `screen._top_items` / `screen._bonus_items`, and asserts the draft panes render `Top 3` and `Bonus` entries rather than only count text.
- Add a test that the detail pane shows the focused item's planning status, for example `Not planned`, `Top 3 #1`, or `Bonus`.

**Step 2: Write failing tests for direct plan editing actions**
- Add tests for:
  - removing an item from `Top 3`
  - removing an item from `Bonus`
  - promoting a `Bonus` item into `Top 3`
  - demoting a `Top 3` item into `Bonus`
  - reordering `Top 3`
- Use screen-level state assertions (`screen._top_items`, `screen._bonus_items`) plus widget update assertions for visible draft panes.

**Step 3: Write failing tests for smooth post-confirmation transition**
- Add a test that after confirmation the screen updates pane titles and status text in place instead of switching to an unrelated layout.
- Assert that the confirmed view produces one ordered `Today` list with `Top 3` rows first and `Bonus` rows second.
- Assert that the detail pane shows transition copy such as `Plan confirmed` or equivalent explicit execution-state guidance.

**Step 4: Run the targeted screen tests to verify RED**
Run:
```bash
source .venv/bin/activate && pytest tests/unit/test_daily_workspace_screen.py -v
```
Expected: FAIL on the new planning/editing/transition expectations.

**Step 5: Commit the red tests**
Run:
```bash
git add tests/unit/test_daily_workspace_screen.py
git commit -m "test: cover daily workspace draft editing and transition"
```

### Task 2: Implement the multi-pane daily workspace layout and draft-plan editing

**Files:**
- Modify: `flow/tui/screens/daily_workspace/daily_workspace.py`
- Modify: `flow/tui/screens/daily_workspace/daily_workspace.tcss`

**Step 1: Restructure the screen composition**
- Replace the current one-list/two-text-pane composition with a stable three-surface layout.
- Planning mode layout target:
  - left: `Candidates`
  - center: `Top 3 Draft`
  - right: `Bonus Draft` plus lower `Detail`
- Focus mode layout target:
  - left or center primary pane: `Today`
  - stable `Detail` pane
  - stable `Wrap` pane
- Keep pane shells persistent so mode changes update content/title/state in place rather than swapping the whole mental model.

**Step 2: Add explicit draft widgets and rendering helpers**
- Introduce dedicated widget IDs for:
  - candidates list
  - top draft list
  - bonus draft list
  - today list
  - detail content
  - wrap content
- Add helpers that render:
  - grouped candidate rows
  - fixed-slot `Top 3` rows with open-slot placeholders
  - bonus rows
  - merged `Today` rows with `Top 3` and `Bonus` sections
  - focused-item detail text including current bucket/status

**Step 3: Add direct plan-editing actions**
- Add bindings/actions for:
  - remove selected draft item
  - promote selected bonus item
  - demote selected top item
  - reorder top item up/down
- Keep existing `t`, `b`, `x`, `c`, `w`, `I` behavior where still valid.
- Route actions by focused pane instead of relying on a single `OptionList`.
- Preserve current non-blocking refresh behavior.

**Step 4: Implement consistent pane shell styling**
- Update `daily_workspace.tcss` so every major pane has:
  - border
  - title row
  - consistent padding
  - focus/active treatment
  - compact status or helper text area
- Keep the current professional-ops palette from shared tokens; do not introduce a new palette.
- Use a terminal-native Material interpretation: consistent surfaces, clear hierarchy, restrained accents.

**Step 5: Run the targeted screen tests to verify GREEN**
Run:
```bash
source .venv/bin/activate && pytest tests/unit/test_daily_workspace_screen.py -v
```
Expected: PASS.

**Step 6: Commit the layout/editing implementation**
Run:
```bash
git add flow/tui/screens/daily_workspace/daily_workspace.py flow/tui/screens/daily_workspace/daily_workspace.tcss tests/unit/test_daily_workspace_screen.py
git commit -m "feat: add editable multi-pane daily workspace planner"
```

### Task 3: Add deterministic wrap feedback and richer daily wrap data

**Files:**
- Modify: `tests/unit/test_daily_workspace.py`
- Modify: `flow/core/services/daily_plan.py`
- Modify: `flow/core/engine.py`

**Step 1: Write failing service/engine tests for richer wrap output**
- Add a test that `engine.get_daily_wrap_summary()` returns:
  - completion counts
  - completed top item titles/ids
  - completed bonus item titles/ids
  - open planned item titles/ids
  - a deterministic verdict/headline
  - deterministic coaching feedback text
- Add at least two rule-path tests, for example:
  - all `Top 3` complete -> positive verdict
  - overloaded/unfinished `Top 3` with many bonuses -> improvement verdict

**Step 2: Run the targeted service/engine tests to verify RED**
Run:
```bash
source .venv/bin/activate && pytest tests/unit/test_daily_workspace.py -v
```
Expected: FAIL because the current wrap summary returns counts only.

**Step 3: Implement richer wrap summary logic**
- Extend the daily-plan service to derive planned-item collections from the persisted plan and current item statuses.
- Add deterministic wrap-evaluation logic in the service layer, not the screen:
  - verdict/headline
  - short coaching feedback
  - accomplishments list
  - carry-forward list
- Keep AI insight generation separate and optional.
- Update engine return types accordingly.

**Step 4: Run the targeted service/engine tests to verify GREEN**
Run:
```bash
source .venv/bin/activate && pytest tests/unit/test_daily_workspace.py -v
```
Expected: PASS.

**Step 5: Commit the wrap-summary expansion**
Run:
```bash
git add flow/core/services/daily_plan.py flow/core/engine.py tests/unit/test_daily_workspace.py
git commit -m "feat: enrich daily wrap summary feedback"
```

### Task 4: Connect the richer wrap data and confirmed-state messaging to the screen

**Files:**
- Modify: `tests/unit/test_daily_workspace_screen.py`
- Modify: `flow/tui/screens/daily_workspace/daily_workspace.py`

**Step 1: Add failing screen tests for wrap presentation**
- Add a test that the wrap pane shows:
  - verdict/headline
  - accomplishments section
  - unfinished planned items
  - coaching feedback
- Add a test that completion updates the wrap pane on refresh without requiring the AI insight path.

**Step 2: Run the targeted screen tests to verify RED**
Run:
```bash
source .venv/bin/activate && pytest tests/unit/test_daily_workspace_screen.py -v
```
Expected: FAIL on richer wrap-pane expectations.

**Step 3: Implement wrap-pane rendering and transition messaging**
- Update screen rendering helpers so the wrap pane is always informative, not blank until wrap mode.
- Make `show_daily_wrap` expand or emphasize the same pane instead of navigating elsewhere.
- Render the richer wrap summary structure from engine data.
- Ensure the confirmed-state detail pane explicitly tells the user the plan is active and the `Today` list is now the execution surface.

**Step 4: Run both daily-workspace test modules**
Run:
```bash
source .venv/bin/activate && pytest tests/unit/test_daily_workspace_screen.py tests/unit/test_daily_workspace.py -v
```
Expected: PASS.

**Step 5: Commit the integrated screen behavior**
Run:
```bash
git add flow/tui/screens/daily_workspace/daily_workspace.py tests/unit/test_daily_workspace_screen.py tests/unit/test_daily_workspace.py
git commit -m "feat: surface wrap feedback in daily workspace"
```

### Task 5: Update docs, verify broadly, and record results

**Files:**
- Modify: `README.md`
- Modify: `docs/PRD.md` (only if implementation meaningfully changes stated workspace behavior)
- Modify: `tasks/todo.md`

**Step 1: Update user-facing docs**
- In `README.md`, update the `Daily Workspace` section so it reflects:
  - visible `Top 3` / `Bonus` draft panes during planning
  - same-screen plan editing
  - merged `Today` list after confirmation
  - richer daily wrap feedback
- Update `docs/PRD.md` only if implementation adds durable product behavior not already captured by the approved concept.

**Step 2: Run targeted verification for the changed behavior**
Run:
```bash
source .venv/bin/activate && pytest tests/unit/test_daily_workspace_screen.py tests/unit/test_daily_workspace.py tests/unit/test_cli_main.py -v
```
Expected: PASS.

**Step 3: Run the broader unit suite**
Run:
```bash
source .venv/bin/activate && pytest tests/unit -v
```
Expected: PASS, or document exact unrelated failures with evidence.

**Step 4: Run the mandatory Flow review**
- Open and follow `.codex/skills/code-review-flow/SKILL.md`.
- Check security/privacy, architecture direction, typing, async safety, and tests.
- Confirm the screen still avoids blocking work on the UI thread.

**Step 5: Update task tracking**
- Mark all `Daily Workspace UI Brainstorm` follow-through items complete in `tasks/todo.md`.
- Add a `Review / Results` section with:
  - files changed
  - verification commands
  - pass/fail evidence
  - brief notes on any deviations from the plan

**Step 6: Commit docs and task tracking**
Run:
```bash
git add README.md docs/PRD.md tasks/todo.md docs/plans/2026-03-09-daily-workspace-ui-refresh-design.md docs/plans/2026-03-09-daily-workspace-ui-refresh-implementation-plan.md
git commit -m "docs: record daily workspace ui refresh plan"
```

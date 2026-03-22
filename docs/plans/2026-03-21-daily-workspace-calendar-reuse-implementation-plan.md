# Daily Workspace Calendar Reuse Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Reuse calendar availability inside Daily Workspace confirmed mode so `f` recommends the best active planned item without turning the workspace into a calendar UI.

**Architecture:** Add a compact calendar-availability read model below the TUI layer, extend confirmed-plan recommendation logic to use that advisory signal, and keep the screen responsible only for invoking the recommendation and rendering the explanation string. Preserve deterministic `Top 3`-then-`Bonus` fallback when calendar data or duration metadata is unavailable.

**Tech Stack:** Python 3.11, Typer/Textual, existing `Engine` service boundary, unit tests with `pytest`, optional EventKit-backed availability provider.

---

### Task 1: Define The Recommendation Inputs

**Files:**
- Modify: `flow/core/focus.py`
- Test: `tests/unit/test_focus.py`

**Step 1: Write the failing test**

Add unit tests that describe the new recommendation contract:
- a calendar-aware recommendation returns the fitting active `Top 3` item when one fits the next free window
- a `Bonus` item can win only when no active `Top 3` item fits and the `Bonus` item does
- sparse metadata falls back to saved plan order
- the result includes a short explanation string for UI use

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && pytest tests/unit/test_focus.py -v`

Expected: FAIL because `recommend_confirmed_focus()` does not yet accept calendar context or return explanation metadata.

**Step 3: Write minimal implementation**

In `flow/core/focus.py`:
- add a small typed calendar-availability input model for recommendation
- extend `ConfirmedFocusRecommendation` to include a short explanation string
- implement ranking that:
  - filters to active confirmed items only
  - uses next-free-window fit when both window size and task duration metadata are available
  - prefers `Top 3` over `Bonus` when fit is tied
  - preserves existing saved order as the final tie-breaker
  - falls back cleanly to deterministic plan order with fallback explanation text

**Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && pytest tests/unit/test_focus.py -v`

Expected: PASS

**Step 5: Commit**

```bash
git add flow/core/focus.py tests/unit/test_focus.py
git commit -m "feat: add calendar-aware confirmed focus ranking"
```

### Task 2: Expose Calendar Availability Through Engine

**Files:**
- Modify: `flow/core/engine.py`
- Create or modify: `flow/core/services/<calendar availability module if needed>`
- Test: `tests/unit/test_daily_workspace.py`

**Step 1: Write the failing test**

Add unit coverage proving the engine can provide a compact calendar-availability summary for Daily Workspace recommendation, and proving failures degrade to a stable `unavailable` result instead of raising.

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && pytest tests/unit/test_daily_workspace.py -k calendar -v`

Expected: FAIL because the engine does not yet expose a calendar availability read model.

**Step 3: Write minimal implementation**

Implement a narrow engine/service method that returns only the summary needed by recommendation:
- available/unavailable
- next free window minutes, if known
- minutes until next event, if known

Implementation notes:
- if existing calendar code already exists elsewhere in the codebase or branch history, adapt it instead of rebuilding a larger abstraction
- keep EventKit/PyObjC handling below the TUI layer
- catch exceptions and return an unavailable summary
- if the provider is expensive, keep usage compatible with `asyncio.to_thread(...)` from the screen path

**Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && pytest tests/unit/test_daily_workspace.py -k calendar -v`

Expected: PASS

**Step 5: Commit**

```bash
git add flow/core/engine.py flow/core/services tests/unit/test_daily_workspace.py
git commit -m "feat: expose calendar availability for workspace recommendations"
```

### Task 3: Wire Recommendation Explanation Into Daily Workspace

**Files:**
- Modify: `flow/tui/screens/daily_workspace/daily_workspace.py`
- Test: `tests/unit/test_daily_workspace_screen.py`

**Step 1: Write the failing test**

Add screen tests covering confirmed-mode `f` behavior:
- highlights the item returned by the calendar-aware recommendation
- surfaces the recommendation explanation in an existing detail/status area
- still shows the existing no-active-items notification path when nothing is eligible

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && pytest tests/unit/test_daily_workspace_screen.py -k recommend_focus_item -v`

Expected: FAIL because the screen currently ignores explanation metadata and only highlights by bucket/id.

**Step 3: Write minimal implementation**

Update `DailyWorkspaceScreen.action_recommend_focus_item()` so it:
- fetches calendar availability through the engine on a safe path
- passes that summary into `recommend_confirmed_focus()`
- highlights the chosen item as before
- writes the explanation string into the existing detail/status surface without adding a new pane
- preserves current behavior when no recommendation is available

Keep the TUI non-blocking. Any calendar read must not block the main loop.

**Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && pytest tests/unit/test_daily_workspace_screen.py -k recommend_focus_item -v`

Expected: PASS

**Step 5: Commit**

```bash
git add flow/tui/screens/daily_workspace/daily_workspace.py tests/unit/test_daily_workspace_screen.py
git commit -m "feat: show calendar-aware recommendations in daily workspace"
```

### Task 4: Update User-Facing Documentation

**Files:**
- Modify: `README.md`
- Modify: `docs/PRD.md`

**Step 1: Write the failing doc expectation**

Record the missing implementation-accurate behavior:
- Daily Workspace reuses calendar context for advisory recommendation only
- Flow does not auto-schedule or create a calendar pane

**Step 2: Verify docs are currently incomplete**

Inspect:
- `README.md`
- `docs/PRD.md`

Expected: current docs do not describe Daily Workspace calendar reuse accurately.

**Step 3: Write minimal documentation updates**

Update docs so they describe:
- confirmed-mode `f` uses calendar availability heuristically
- recommendation remains limited to confirmed planned work
- no rigid calendar blocking is introduced

**Step 4: Verify docs read consistently**

Re-open the edited sections and confirm README/PRD language matches shipped behavior.

**Step 5: Commit**

```bash
git add README.md docs/PRD.md
git commit -m "docs: describe calendar-aware daily workspace recommendation"
```

### Task 5: Run Verification And Review

**Files:**
- Review: `flow/core/focus.py`
- Review: `flow/core/engine.py`
- Review: `flow/tui/screens/daily_workspace/daily_workspace.py`
- Review: `tests/unit/test_focus.py`
- Review: `tests/unit/test_daily_workspace.py`
- Review: `tests/unit/test_daily_workspace_screen.py`

**Step 1: Run targeted tests**

Run:

```bash
source .venv/bin/activate && pytest tests/unit/test_focus.py tests/unit/test_daily_workspace.py tests/unit/test_daily_workspace_screen.py -v
```

Expected: PASS

**Step 2: Run broader daily-workspace regression coverage**

Run:

```bash
source .venv/bin/activate && pytest tests/unit -k "daily_workspace or focus" -v
```

Expected: PASS

**Step 3: Run Flow review checklist**

Review for:
- architecture direction
- async safety in TUI code
- graceful fallback on calendar errors
- type hints on new APIs
- test coverage for recommendation changes

Expected: no material issues

**Step 4: Record results**

Update `tasks/todo.md` with:
- verification commands run
- pass/fail outcomes
- review notes

**Step 5: Commit**

```bash
git add tasks/todo.md
git commit -m "chore: record calendar recommendation verification"
```

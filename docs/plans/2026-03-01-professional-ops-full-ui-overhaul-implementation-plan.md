# Professional Ops Full UI Overhaul Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace Flow GTD's current purple card-style UI with a consistent professional operations-console visual system across onboarding, core screens, and dialogs while preserving behavior.

**Architecture:** Centralize design tokens and baseline widget styling in `flow/tui/common/theme.tcss`, then migrate onboarding and primary screen TCSS/Python layouts to a shared panel grammar (top status, framed content, contextual details, keyhint/status strip). Keep navigation and business logic stable; refactor only presentation structure and text hierarchy needed for the new shell.

**Tech Stack:** Python 3.11, Textual (`Screen`, `Container`, `Static`, `OptionList`, `Input`, dialogs), TCSS styles, pytest unit tests.

---

### Task 1: Baseline Test Safety Net

**Files:**
- Test: `tests/unit/tui/common/test_keybindings_contract.py`
- Test: `tests/unit/tui/common/test_base_screen_bindings.py`
- Test: `tests/unit/tui/common/widgets/test_dialog_bindings.py`

**Step 1: Run existing binding/contract tests before UI changes**

Run: `source .venv/bin/activate && pytest tests/unit/tui/common/test_keybindings_contract.py tests/unit/tui/common/test_base_screen_bindings.py tests/unit/tui/common/widgets/test_dialog_bindings.py -v`
Expected: PASS. Capture this as baseline evidence.

**Step 2: Commit baseline checkpoint**

```bash
git add tests/unit/tui/common/test_keybindings_contract.py tests/unit/tui/common/test_base_screen_bindings.py tests/unit/tui/common/widgets/test_dialog_bindings.py
git commit -m "test: record pre-overhaul tui binding baseline"
```

### Task 2: Implement Global Ops Theme Tokens

**Files:**
- Modify: `flow/tui/common/theme.tcss`

**Step 1: Write/adjust a focused style contract test if feasible**
- If there is no snapshot/style contract framework, document this and keep behavior tests as guardrails.

**Step 2: Replace token palette and baseline component styles**
- Add professional-ops token groups for surface, border, text, semantic status.
- Update Header/Footer, Input, Button, OptionList/ListView, Markdown, Toast to use new tokens.
- Add reusable utility classes/ids for panel grammar (`panel`, `section-title`, `value-row`, `status-chip`, `keyhint-line`).

**Step 3: Run impacted TUI common tests**

Run: `source .venv/bin/activate && pytest tests/unit/tui/common -v`
Expected: PASS.

**Step 4: Commit**

```bash
git add flow/tui/common/theme.tcss tests/unit/tui/common
git commit -m "feat(tui): add professional ops global theme and panel primitives"
```

### Task 3: Overhaul Onboarding Screen Layouts

**Files:**
- Modify: `flow/tui/onboarding/screens/provider.py`
- Modify: `flow/tui/onboarding/screens/provider.tcss`
- Modify: `flow/tui/onboarding/screens/credentials.py`
- Modify: `flow/tui/onboarding/screens/credentials.tcss`
- Modify: `flow/tui/onboarding/screens/validation.py`
- Modify: `flow/tui/onboarding/screens/validation.tcss`
- Modify: `flow/tui/onboarding/screens/resource_storage.py`
- Modify: `flow/tui/onboarding/screens/first_capture.py`

**Step 1: Add failing test(s) for onboarding flow behavior if layout edits touch control IDs/events**
- Ensure selection/submit/back behavior remains identical.

**Step 2: Refactor compose trees for split dashboard layout**
- Introduce left field pane + right detail/help pane.
- Add progress/context row and standardized section title lines.
- Keep existing keybindings and submission logic unchanged.

**Step 3: Refactor onboarding TCSS to remove local duplicate token declarations**
- Use global tokens from `theme.tcss`.
- Implement ops panel framing and dense row rhythm.

**Step 4: Run onboarding tests**

Run: `source .venv/bin/activate && pytest tests/unit -k onboarding -v`
Expected: PASS for onboarding-related tests.

**Step 5: Commit**

```bash
git add flow/tui/onboarding/screens tests/unit
git commit -m "feat(onboarding): migrate setup flow to professional ops dashboard layout"
```

### Task 4: Overhaul Main Screen Visual Shells

**Files:**
- Modify: `flow/tui/screens/inbox/inbox.py`
- Modify: `flow/tui/screens/inbox/inbox.tcss`
- Modify: `flow/tui/screens/projects/projects.py`
- Modify: `flow/tui/screens/projects/projects.tcss`
- Modify: `flow/tui/screens/action/action.py`
- Modify: `flow/tui/screens/action/action.tcss`
- Modify: `flow/tui/screens/review/review.py`
- Modify: `flow/tui/screens/review/review.tcss`
- Modify: `flow/tui/screens/process/process.py`
- Modify: `flow/tui/screens/process/process.tcss`
- Modify: `flow/tui/screens/focus/focus.py`
- Modify: `flow/tui/screens/focus/focus.tcss`

**Step 1: Add/adjust failing tests where screen composition changes could affect focus/key interactions**
- Keep existing panel shortcut and focus contracts intact.

**Step 2: Apply shared panel grammar per screen**
- Standardize top status/context strip.
- Standardize content panel structure and section titles.
- Expose key runtime status cues in consistent positions.

**Step 3: Run screen-specific tests**

Run: `source .venv/bin/activate && pytest tests/unit/test_action_screen_bindings.py tests/unit/test_inbox_screen_bindings.py tests/unit/test_projects_screen_bindings.py -v`
Expected: PASS.

**Step 4: Commit**

```bash
git add flow/tui/screens tests/unit/test_action_screen_bindings.py tests/unit/test_inbox_screen_bindings.py tests/unit/test_projects_screen_bindings.py
git commit -m "feat(tui): apply professional ops shell to core flow screens"
```

### Task 5: Update Dialogs and Shared Widgets

**Files:**
- Modify: `flow/tui/common/widgets/defer_dialog.py`
- Modify: `flow/tui/common/widgets/process_task_dialog.py`
- Modify: `flow/tui/common/widgets/project_picker_dialog.py`
- Modify: `flow/tui/common/widgets/card.py`
- Modify: `flow/tui/common/widgets/sidecar.py`

**Step 1: Ensure dialog/widget binding tests exist for impacted modal flows**
- Add tests only if behavior contracts are missing.

**Step 2: Align dialog/widget composition and classes with ops primitives**
- Update panel/chrome spacing and semantic status display.

**Step 3: Run dialog/common tests**

Run: `source .venv/bin/activate && pytest tests/unit/tui/common/widgets -v`
Expected: PASS.

**Step 4: Commit**

```bash
git add flow/tui/common/widgets tests/unit/tui/common/widgets
git commit -m "feat(tui): restyle dialogs and shared widgets to ops system"
```

### Task 6: Documentation Sync

**Files:**
- Modify: `README.md` (if setup/TUI visuals are user-visible and described)
- Modify: `docs/patterns-and-lessons.md` (if visual-system principles are documented)

**Step 1: Update user-facing text to match new setup/UI language**
- Remove outdated references to previous visual style.

**Step 2: Commit docs updates**

```bash
git add README.md docs/patterns-and-lessons.md
git commit -m "docs: sync onboarding and tui visual system language"
```

### Task 7: Final Verification + Mandatory Review

**Files:**
- Modify: `tasks/todo.md`

**Step 1: Run mandatory code review checklist skill**
- Use `.codex/skills/code-review-flow/SKILL.md` and apply checklist to touched `flow/` and `tests/` files.

**Step 2: Run full unit suite**

Run: `source .venv/bin/activate && pytest tests/unit -v`
Expected: PASS.

**Step 3: Manual verification pass**
- Launch TUI and onboarding; validate desktop+narrow terminal readability.
- Validate focus traversal, key hints, and error states.

**Step 4: Record results in todo file**
- Update review/results section with evidence and residual risks.

**Step 5: Final commit**

```bash
git add tasks/todo.md
git commit -m "chore: record verification results for professional ops overhaul"
```

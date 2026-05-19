# SPLIT-ASSISTANT-CHATGPT-UI

## Source Input

- Planner artifact: `artifacts/agent-results/planner/PLAN-ASSISTANT-CHATGPT-UI.md`
- Project root: `/Users/wenbinzhang/Documents/flow-gtd/feature-agent-runtime-sdk-native`
- Scope constraint: preserve Flow outer workspace; change only internal Assistant layout.
- Splitter constraint: this artifact is task decomposition only; no production code changes were made by splitter.

## Live Boundary Summary

- Primary UI boundary: `Sources/FlowMacApp/UI/Assistant/AssistantView.swift`
- Primary smoke boundary: `tests/NativeSmoke/AssistantWorkflowSmokeTests.swift`
- Store/action boundary: `Sources/FlowMacCore/State/WorkspaceStore.swift`
- Current UI still includes Assistant-internal `WorkspaceHeader`, `SurfaceCard` chat wrappers, `StatusPill`-heavy rows, duplicate feedback surfaces, proposal/audit chrome, and pending rail subtitle copy `Thinking... session switching is locked.`
- Existing store APIs already provide the required session/message lane and pending guards: `assistantSessions`, `selectedAssistantSessionID`, `assistantMessages`, `assistantComposerText`, `assistantSendPending`, `createAssistantSession`, `selectAssistantSession`, `sendAssistantMessage`, `confirmSelectedAssistantProposal`, `dismissSelectedAssistantProposal`, and `undoLastAssistantMutation`.

## Execution Principles

- Use TDD where feasible: update the rendered-state/native smoke contract first, confirm it fails against the current UI, then implement.
- Do not change data models, repositories, schema, migrations, provider/runtime behavior, `WorkspaceShell`, global Flow sidebar, or non-Assistant workspaces.
- Keep `WorkspaceShell(store:)` as the outer wrapper.
- Preserve proposal confirm/dismiss and undo behavior, but present proposal UI as inline message content rather than dominant dashboard/inspector chrome.
- While `assistantSendPending == true`, the visible text in the composer/message interaction slot must be exactly `Thinking...`.
- Disable send, new chat, and session switching while pending.
- Avoid brittle pixel-position assertions; assert stable structure, state flags, and user-facing strings.

## Tasks

### ASSISTANT-UI-001 - Update Rendered-State Smoke Contract

**Goal:** Convert the existing Assistant rendered-state smoke test from the current Flow-card surface contract to the target ChatGPT-style internal layout contract.

**Owner:** `executor`

**Required inputs:**

- `artifacts/agent-results/planner/PLAN-ASSISTANT-CHATGPT-UI.md`
- `tests/NativeSmoke/AssistantWorkflowSmokeTests.swift`
- `Sources/FlowMacApp/UI/Assistant/AssistantView.swift`

**Expected code outputs:**

- Update `AssistantRenderedSurfaceState` and `AssistantView.renderedSurfaceState(store:)` shape only as needed to expose stable layout intent fields.
- Update `smokeTestAssistantViewUsesRenderedChatFirstSurface` assertions to require the target structure.

**Required contract fields or equivalent stable assertions:**

- `usesChatGPTStyleLayout == true`
- `keepsOuterWorkspaceShell == true`
- `hasConversationRail == true`
- `hasMainTranscript == true`
- `hasBottomComposer == true`
- `thinkingText == "Thinking..."` while pending
- `showsLegacyTurnDrivenSurface == false`
- `showsFlowDashboardHeader == false`
- `showsRailPendingCopy == false`
- Existing session/message behavior remains covered: rail titles, selected session, message roles, proposal visibility, disclosure availability, new chat, undo, pending disablement, switching restoration.

**TDD expectation:**

- First edit the smoke contract and rendered-state fields so `./scripts/test_native_app.sh` fails before the UI refactor because the current implementation still reports/renders old dashboard chrome and rail pending copy.
- Do not weaken existing persistence, reload, proposal, sidecar, or turn-fail-open tests.

**Completion criteria:**

- Smoke test expectations describe the target layout instead of old Flow `WorkspaceHeader`/`SurfaceCard` internals.
- Failing state before implementation is captured in the executor result summary.
- No production data-layer behavior is changed.

**Verification commands:**

- `./scripts/test_native_app.sh` must be run after the test-contract change and before implementation; expected result for this task alone is failure for the intended Assistant layout contract.
- `git diff --check`

**Tester routing after implementation group:** `functional_tester`

### ASSISTANT-UI-002 - Refactor Assistant Internals Into Chat Shell

**Goal:** Replace the Assistant-internal dashboard/card layout with a ChatGPT-style chat shell while preserving Flow's outer workspace shell.

**Owner:** `executor`

**Dependencies:** `ASSISTANT-UI-001`

**Required inputs:**

- Updated rendered-state contract from `ASSISTANT-UI-001`
- `Sources/FlowMacApp/UI/Assistant/AssistantView.swift`
- Store actions in `Sources/FlowMacCore/State/WorkspaceStore.swift`

**Expected code outputs:**

- Keep `WorkspaceShell(store:)` as the Assistant entry wrapper.
- Remove Assistant-internal use of `WorkspaceHeader` for this experience.
- Remove the two dominant `SurfaceCard` wrappers for rail and conversation pane, replacing them with a dedicated internal chat shell.
- Introduce or reshape small private views such as `AssistantChatShell`, `AssistantConversationRail`, `AssistantTranscript`, `AssistantComposer`, and a pending/thinking presentation if helpful.
- Layout must have a left conversation rail, central transcript, and fixed bottom composer anchored to the transcript pane.
- Support responsive behavior equivalent to current `ViewThatFits` intent without making the global Flow workspace change.

**Functional requirements:**

- Rail lists `store.assistantSessions` with title and lightweight preview metadata.
- Rail supports new chat via `store.createAssistantSession()`.
- Rail session rows switch via `store.selectAssistantSession(id:)`.
- Transcript renders `store.assistantMessages` oldest-to-newest.
- User messages align visually as user messages; assistant messages align visually as assistant responses.
- Empty state is a lightweight chat surface with prompt suggestions, not a Flow card stack.
- Composer binds to `store.assistantComposerText` and sends through `store.sendAssistantMessage()`.
- Proposal confirm/dismiss remains available for pending assistant proposal messages via existing store actions.
- Undo remains available where currently surfaced, but should not dominate the chat surface.

**Visual requirements:**

- Use existing Flow dark theme tokens where practical.
- Rail rows should feel compact and conversational, not dashboard tiles.
- Message content should be primary; metadata and audit/provenance should be secondary disclosure inside assistant messages.
- Composer should read as a rounded bottom input bar/card.
- Avoid excessive labels such as `Session Rail`, `Composer`, or metric-style dashboard copy in the main user path.

**Completion criteria:**

- Updated smoke contract from `ASSISTANT-UI-001` passes for structural fields.
- Source no longer renders the Assistant internal experience through the old `WorkspaceHeader` plus two `SurfaceCard` pattern.
- Session/message functionality still passes existing smoke tests.
- No changes to schema, repositories, migrations, provider runtime, or non-Assistant workspaces.

**Verification commands:**

- `./scripts/test_native_app.sh`
- `git diff --check`

**Tester routing after implementation group:** `functional_tester`, `ui_tester`, `interaction_reviewer`

### ASSISTANT-UI-003 - Tighten Pending State And Exact Thinking Copy

**Goal:** Make pending send behavior visually and behaviorally consistent with the ChatGPT-style interaction slot.

**Owner:** `executor`

**Dependencies:** `ASSISTANT-UI-001`, `ASSISTANT-UI-002`

**Required inputs:**

- Updated chat shell from `ASSISTANT-UI-002`
- `WorkspaceStore.assistantSendPending` behavior in `Sources/FlowMacCore/State/WorkspaceStore.swift`
- Rendered-state pending assertions from `ASSISTANT-UI-001`

**Expected code outputs:**

- Use `store.assistantSendPending` as the only UI pending source.
- Composer text/input, send, new-chat, and session-switch interactions are disabled while pending.
- The visible pending interaction slot shows exactly `Thinking...`.
- Remove or suppress longer visible pending copy such as `Thinking... session switching is locked.`
- Rendered-state pending fields agree with the UI: `thinkingText == "Thinking..."`, composer disabled, rail disabled, no rail pending copy.

**Completion criteria:**

- Pending smoke assertions pass.
- No duplicate or expanded pending copy appears in the visible interaction path.
- Pending behavior still prevents duplicate sends and session switching.
- Send failure recovery still surfaces local assistant feedback after pending clears.

**Verification commands:**

- `./scripts/test_native_app.sh`
- `git diff --check`

**Tester routing after implementation group:** `functional_tester`, `interaction_reviewer`, `ui_tester`

### ASSISTANT-UI-004 - Preserve Proposal, Disclosure, And Recovery Semantics In The New Layout

**Goal:** Ensure the ChatGPT-style UI preserves existing assistant safety semantics without reintroducing an inspector/turn-driven mental model.

**Owner:** `executor`

**Dependencies:** `ASSISTANT-UI-002`, `ASSISTANT-UI-003`

**Required inputs:**

- `AssistantMessageBubble`, `AssistantProposalCard`, and `AssistantProvenanceDisclosure` equivalents in `AssistantView.swift`
- Existing smoke tests for proposal confirmation, dismissal, undo, disclosure, and failure feedback

**Expected code outputs:**

- Keep proposal confirm/dismiss actions explicit for pending assistant messages.
- Preserve proposal status visibility after confirm/dismiss.
- Keep provider/audit details accessible as secondary disclosure only.
- Do not present legacy `AssistantTurns` as the primary surface or navigation model.
- Preserve assistant-local feedback for confirm/dismiss/send/undo failures without duplicating feedback panels.

**Completion criteria:**

- Existing proposal and failure-feedback smoke tests pass.
- Rendered-state contract shows proposal actions only when the selected assistant message is actionable.
- UI no longer feels turn-list or inspector driven.
- No storage or repository compatibility APIs are removed.

**Verification commands:**

- `./scripts/test_native_app.sh`
- `git diff --check`

**Tester routing after implementation group:** `functional_tester`, `interaction_reviewer`, `ui_tester`

### ASSISTANT-UI-005 - Final Verification And Evidence Package

**Goal:** Run the complete required verification set and produce executor evidence for tester handoff.

**Owner:** `executor`

**Dependencies:** `ASSISTANT-UI-001`, `ASSISTANT-UI-002`, `ASSISTANT-UI-003`, `ASSISTANT-UI-004`

**Required inputs:**

- Final code diff from tasks `ASSISTANT-UI-001` through `ASSISTANT-UI-004`
- Project scripts

**Expected output:**

- Executor result file at `artifacts/agent-results/executor/ASSISTANT-UI-005.md` containing:
  - Changed files
  - Test-first failure evidence from `ASSISTANT-UI-001`
  - Final verification command results
  - Known limitations or risks
  - Confirmation that no data-layer/schema/runtime changes were made, or explicit disclosure if that changed unexpectedly

**Required verification commands:**

- `./scripts/test_native_app.sh`
- `./scripts/build_native_app.sh`
- `git diff --check`
- If any Python `flow/` or `tests/` behavior is touched unexpectedly:
  - Bootstrap/activate `.venv` per `AGENTS.md`
  - `pytest tests/unit -v`
  - Run `.codex/skills/code-review-flow/SKILL.md` review workflow before finalizing

**Completion criteria:**

- All required final verification commands pass or failures are documented as blockers.
- Result file is ready for functional, visual, and interaction testers.
- No task is marked complete without command evidence.

**Tester routing after implementation group:** `functional_tester`, `ui_tester`, `interaction_reviewer`

## Dependency Graph

```text
ASSISTANT-UI-001
  -> ASSISTANT-UI-002
      -> ASSISTANT-UI-003
      -> ASSISTANT-UI-004
          -> ASSISTANT-UI-005
```

Notes:

- `ASSISTANT-UI-003` depends on the chat shell from `ASSISTANT-UI-002` because pending presentation belongs in the final interaction slot.
- `ASSISTANT-UI-004` can proceed after the base chat shell exists and may run in parallel with final polish for `ASSISTANT-UI-003` only if the executor can avoid overlapping edits in the same message/composer subviews.
- `ASSISTANT-UI-005` must wait for all implementation tasks.

## Parallelizable Execution Groups

### Group 1 - Test Contract

- `ASSISTANT-UI-001`
- Parallelism: none; must run first.
- Expected state: test contract may fail before implementation.

### Group 2 - Main UI Implementation

- `ASSISTANT-UI-002`
- Parallelism: none recommended because most edits converge in `AssistantView.swift`.

### Group 3 - Behavior And Safety Refinement

- `ASSISTANT-UI-003`
- `ASSISTANT-UI-004`
- Parallelism: limited. Can be assigned to separate executor passes only with strict file-region ownership:
  - `ASSISTANT-UI-003`: composer/pending/session-disablement fields.
  - `ASSISTANT-UI-004`: message bubble/proposal/disclosure/feedback fields.

### Group 4 - Final Verification

- `ASSISTANT-UI-005`
- Parallelism: none; runs after implementation.

## Recommended Execution Order

1. `ASSISTANT-UI-001`
2. `ASSISTANT-UI-002`
3. `ASSISTANT-UI-003`
4. `ASSISTANT-UI-004`
5. `ASSISTANT-UI-005`

## Tester Routing

### functional_tester

Route after `ASSISTANT-UI-002` through `ASSISTANT-UI-005`.

Functional tester must verify:

- Existing smoke tests pass.
- Session creation, switching, reload/restore, and continuation still use the session/message lane.
- Empty send remains a no-op.
- Pending send blocks duplicate send, new chat, and session switching.
- Proposal confirm/dismiss/undo/failure feedback still works.
- Legacy turn-load fail-open behavior remains intact.
- No data migration, schema, repository, or provider/runtime changes were introduced.

Required functional commands:

- `./scripts/test_native_app.sh`
- `./scripts/build_native_app.sh` for final verification or if requested by orchestrator.
- If Python `flow/` or `tests/` files changed unexpectedly: `pytest tests/unit -v` after venv bootstrap.

### ui_tester

Route after `ASSISTANT-UI-002`, `ASSISTANT-UI-003`, `ASSISTANT-UI-004`, and final package.

UI tester must inspect:

- Layout reads as one internal Assistant chat workspace inside Flow's preserved outer shell.
- Conversation rail is compact and not a Flow metrics/card dashboard.
- Transcript readability, message alignment, spacing, hierarchy, and density are ChatGPT-like without cloning branding.
- Composer is visually anchored at the bottom of the transcript pane.
- `Thinking...` appears exactly in the intended interaction slot while pending.
- No obvious visual inconsistencies from mixed old/new chrome: `WorkspaceHeader`, dominant `SurfaceCard` wrappers, `StatusPill` clutter, duplicate feedback panels, or rail pending subtitle copy.
- Desktop and narrow/responsive behavior remain usable.

Suggested UI verification:

- Build and run the native app if practical.
- Prefer Computer Use when operating the app is required.
- Inspect source structure and rendered-state smoke assertions when full app operation is not practical.

### interaction_reviewer

Route after `ASSISTANT-UI-002`, `ASSISTANT-UI-003`, `ASSISTANT-UI-004`, and final package.

Interaction reviewer must verify:

- New chat flow is discoverable but not duplicated in a confusing way.
- Session switching is clear when idle and blocked while pending.
- Empty chat offers lightweight prompt suggestions without feeling like a dashboard.
- Sending clears composer after success and preserves local feedback on failure.
- Pending state gives timely feedback with exactly `Thinking...`.
- Proposal confirm/dismiss actions are understandable, explicit, and reversible where existing behavior supports undo.
- Provider/audit details are discoverable as secondary information, not the primary task flow.

Suggested interaction verification:

- Use native app operation via Computer Use when feasible.
- Otherwise inspect rendered-state contract plus source actions and smoke test behavior.

## Bug Routing Rules

- Every tester bug must include `bug_id`, `source_task_id`, `reported_by_responsibility`, `assigned_executor_responsibility`, `cycle_count`, `status`, and `result_path`.
- Route bugs back to `executor` for the source task owner.
- The same tester who reported a bug must retest that bug.
- Initial bug report starts at `cycle_count = 1`.
- Maximum retest chain is 3 cycles.
- After cycle 3, stop routing and escalate with blocker, risk, and remaining evidence.

## Task Ownership Seed

```json
{
  "ASSISTANT-UI-001": {
    "owner_responsibility": "executor",
    "status": "pending",
    "result_path": "artifacts/agent-results/executor/ASSISTANT-UI-001.md",
    "verification": {
      "functional_tester": "required",
      "ui_tester": "not_needed_until_ui_refactor",
      "interaction_reviewer": "not_needed_until_ui_refactor"
    }
  },
  "ASSISTANT-UI-002": {
    "owner_responsibility": "executor",
    "status": "pending",
    "result_path": "artifacts/agent-results/executor/ASSISTANT-UI-002.md",
    "verification": {
      "functional_tester": "required",
      "ui_tester": "required",
      "interaction_reviewer": "required"
    }
  },
  "ASSISTANT-UI-003": {
    "owner_responsibility": "executor",
    "status": "pending",
    "result_path": "artifacts/agent-results/executor/ASSISTANT-UI-003.md",
    "verification": {
      "functional_tester": "required",
      "ui_tester": "required",
      "interaction_reviewer": "required"
    }
  },
  "ASSISTANT-UI-004": {
    "owner_responsibility": "executor",
    "status": "pending",
    "result_path": "artifacts/agent-results/executor/ASSISTANT-UI-004.md",
    "verification": {
      "functional_tester": "required",
      "ui_tester": "required",
      "interaction_reviewer": "required"
    }
  },
  "ASSISTANT-UI-005": {
    "owner_responsibility": "executor",
    "status": "pending",
    "result_path": "artifacts/agent-results/executor/ASSISTANT-UI-005.md",
    "verification": {
      "functional_tester": "required",
      "ui_tester": "required",
      "interaction_reviewer": "required"
    }
  }
}
```

## Splitter Completion Criteria

- Stable task IDs defined.
- Dependencies and execution groups defined.
- TDD/test-first expectations included.
- Required verification commands included.
- Functional, UI, and interaction tester routing included.
- Output written to `artifacts/agent-results/splitter/SPLIT-ASSISTANT-CHATGPT-UI.md`.

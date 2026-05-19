# PLAN-ASSISTANT-CHATGPT-UI

## Goal

Change only the internal Flow Assistant workspace into a ChatGPT-style interface: a conversation/session rail, one main transcript surface, and a fixed bottom composer that shows exactly `Thinking...` while the assistant is working. Preserve Flow's outer workspace/sidebar model and do not perform data migration.

## Reconciled Current State

- Workspace tree: `git status --short` is clean during planning.
- Existing artifacts: no prior files were found under `artifacts/agent-results`; this is a fresh planner artifact.
- Existing model foundation is already present. `WorkspaceStore` exposes `assistantSessions`, `selectedAssistantSessionID`, `assistantMessages`, `selectedAssistantMessageID`, `assistantComposerText`, `assistantSendPending`, and proposal feedback state in `Sources/FlowMacCore/State/WorkspaceStore.swift`.
- Legacy turn state still exists only as compatibility state in `WorkspaceStore` (`assistantTurns`, `selectedAssistantTurnID`, `selectedAssistantTurn`) and is explicitly expected not to gate the session/message lane.
- Existing UI is partially chat-first but not yet ChatGPT-style. `Sources/FlowMacApp/UI/Assistant/AssistantView.swift` already uses `WorkspaceShell`, a rail, message bubbles, and a composer, but still renders Flow `WorkspaceHeader` metrics, `SurfaceCard` containers, `StatusPill`-heavy rows, proposal/audit disclosure chrome, `Session Rail` labels, duplicated feedback panels, and a rail lock subtitle that feels like a legacy Flow dashboard rather than ChatGPT.
- Existing tests already protect the session/message boundary in `tests/NativeSmoke/AssistantWorkflowSmokeTests.swift`, including load/continue/switch behavior, sidecar continuity, turn-load fail-open behavior, rendered chat surface state, and exact `Thinking...` label presence.
- The current rendered-state smoke is useful but now stale relative to the target. It asserts Flow-specific affordances such as `showsUndoAction`, `showsProposalActions`, provenance disclosure, and `sessionRailLockLabel == "Thinking... session switching is locked."`; downstream work should update this contract before UI implementation.

## Scope

In scope:

- Refactor `Sources/FlowMacApp/UI/Assistant/AssistantView.swift` so the Assistant internals visually and interactively match the reference pattern: left conversation rail, empty or populated central transcript, rounded bottom composer, and dark ChatGPT-like density.
- Keep `WorkspaceShell(store:)` as the outer shell entry point so the global Flow workspace/sidebar remains unchanged.
- Use existing `WorkspaceStore` session/message APIs; no schema, repository, or migration work is expected.
- Keep proposal confirmation/dismissal behavior available in the chat experience, but present it as inline assistant-message action content instead of a dominant inspector/turn experience.
- While `assistantSendPending == true`, the composer/message interaction box must visibly show exactly `Thinking...`; avoid additional text in that slot.
- Disable send/session-switch/new-chat interactions while pending, but do not show extra pending copy such as `Thinking... session switching is locked.` unless a tester explicitly approves it outside the composer/message box.

Out of scope:

- Do not change Flow's app-level sidebar, `FlowSection`, `WorkspaceShell`, or non-Assistant workspaces.
- Do not remove legacy `FlowAssistantTurn` compatibility APIs from repository/service layers.
- Do not perform database migrations or change stored assistant session/message semantics.
- Do not rewrite assistant provider/runtime behavior.

## Requirements

- The Assistant workspace must remain a first-class Flow workspace selected from the existing outer sidebar.
- The internal Assistant area must use a ChatGPT-style three-region layout: conversation rail, transcript, bottom composer.
- The conversation rail must list sessions, show enough title/preview metadata to switch conversations, and provide a new-chat affordance without looking like a Flow metrics dashboard.
- The central transcript must render user and assistant messages in chronological order for the selected session and restore correctly when switching sessions.
- Empty state should look like an empty chat surface with lightweight prompt suggestions, not a Flow card stack or legacy turn inspector.
- The bottom composer must be visually anchored at the bottom of the chat pane and stay in the interaction slot during pending sends.
- During assistant work, the visible message/composer box text must be exactly `Thinking...`.
- The UI must not expose `AssistantTurns` as the driving mental model; compatibility references can remain in storage/service tests and debug/provenance copy only if they do not dominate the Assistant user experience.
- The implementation should keep existing safety semantics: pending sends block duplicate sends; session switching is guarded while pending; proposal confirm/dismiss actions remain explicit and reversible where already supported.

## Implementation Path

1. Update the smoke contract first in `tests/NativeSmoke/AssistantWorkflowSmokeTests.swift`.
   - Modify `smokeTestAssistantViewUsesRenderedChatFirstSurface` and `AssistantRenderedSurfaceState` expectations to describe the target layout rather than the current Flow-card variant.
   - Add or rename rendered-state fields for layout intent, for example: `usesChatGPTStyleLayout`, `keepsOuterWorkspaceShell`, `hasConversationRail`, `hasMainTranscript`, `hasBottomComposer`, `thinkingText`, `showsLegacyTurnDrivenSurface`, `showsFlowDashboardHeader`, and `showsRailPendingCopy`.
   - Expected failing state before implementation: the test should fail because `AssistantView` still reports or renders Flow `WorkspaceHeader`/`SurfaceCard` framing and rail pending copy.

2. Refactor `AssistantView.swift` structure without touching data layers.
   - Keep `WorkspaceShell(store:)` as the outer wrapper.
   - Replace the internal `WorkspaceHeader` plus nested `SurfaceCard` layout with a dedicated chat shell view: rail on the left, transcript center, composer pinned at the bottom of the transcript pane.
   - Prefer small private subviews such as `AssistantChatShell`, `AssistantConversationRail`, `AssistantTranscript`, `AssistantComposer`, and `AssistantThinkingBubble` if the file starts to sprawl.
   - Preserve existing `WorkspaceStore` actions: `createAssistantSession`, `selectAssistantSession`, `sendAssistantMessage`, `confirmSelectedAssistantProposal`, `dismissSelectedAssistantProposal`, and `undoLastAssistantMutation` where still surfaced.

3. Redesign the visual presentation.
   - Use the existing Flow dark theme tokens where practical, but remove the heavy Flow card/dashboard feel from the Assistant internals.
   - Rail rows should be compact ChatGPT-like conversation entries, not card tiles with status pills and timestamps competing for attention.
   - Transcript should prioritize message content. Proposal/audit metadata can be secondary disclosure inside assistant messages, not always-on dashboard chrome.
   - Composer should be a rounded input bar/card at the bottom with placeholder text when idle and exactly `Thinking...` while pending.

4. Tighten pending behavior.
   - Keep `WorkspaceStore.assistantSendPending` as the single source of pending truth.
   - Composer input and send/new-chat/session switching should be disabled while pending.
   - Remove or suppress rail subtitle copy that expands `Thinking...` into longer text in the visible interaction path.
   - Ensure the rendered state and UI both agree that the pending text is exactly `Thinking...`.

5. Re-run and update smoke coverage.
   - Keep existing session/message persistence, reload, switching, proposal, sidecar, and turn-fail-open tests intact unless their assertions are only checking old UI chrome.
   - Add source-level or rendered-state assertions that `AssistantView.swift` no longer renders the internal Assistant experience through the old `WorkspaceHeader`/two-`SurfaceCard` pattern.
   - Do not assert brittle pixel positions; assert stable structure and user-facing strings.

## Assumptions

- The screenshot is a visual/interaction reference, not a requirement to clone ChatGPT branding exactly.
- Existing `FlowAssistantSession` and `FlowAssistantMessage` models are the correct source of truth.
- The phrase `no legacy AssistantTurns-feeling experience` means the UI should not be turn-list or inspector driven; it does not require deleting compatibility APIs.
- No data migration is needed because the existing session/message layer already persists and reloads conversations.

## Open Questions

- Should proposal confirm/dismiss actions remain visible inline by default, or move behind a disclosure/menu to make the transcript more ChatGPT-like?
- Should provider/audit details remain visible in the transcript, be hidden behind disclosure, or move to a debug-only affordance?
- Should the new chat button live only in the rail header, only in the composer row, or both?
- Is the target strictly dark-only for Assistant, or should it continue to inherit Flow theme behavior if light styling is added later?

## Verification Expectations

- Start with TDD where feasible: update the native smoke/rendered-state test and confirm it fails against the current UI before implementation.
- Run `./scripts/test_native_app.sh` after the UI/test changes.
- Run `./scripts/build_native_app.sh` after the smoke test passes.
- Run `git diff --check` before commit.
- If any Python `flow/` or `tests/` behavior is touched unexpectedly, bootstrap the venv per `AGENTS.md`, run `pytest tests/unit -v`, and use `.codex/skills/code-review-flow/SKILL.md` for review before finalizing.
- UI tester should inspect layout, spacing, visual hierarchy, rail density, transcript readability, composer anchoring, and whether the result clearly reads as one ChatGPT-style Assistant workspace inside Flow.
- Interaction reviewer should verify session switching, new chat, empty chat, sending, pending `Thinking...`, disabled pending actions, proposal handling, and recovery after send failure.

## Recommended Downstream Split

- `ASSISTANT-UI-001`: Update rendered-state/native smoke contract for ChatGPT-style Assistant internals.
- `ASSISTANT-UI-002`: Refactor `AssistantView.swift` into chat shell, rail, transcript, and bottom composer.
- `ASSISTANT-UI-003`: Tighten pending-state copy and disabled interactions around exact `Thinking...`.
- `ASSISTANT-UI-004`: Run functional, visual, interaction, smoke, and build verification.

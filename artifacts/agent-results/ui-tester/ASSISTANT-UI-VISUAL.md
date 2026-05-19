# ASSISTANT-UI-VISUAL

Result: **FAIL**

Scope reviewed:
- `ASSISTANT-UI-002..ASSISTANT-UI-005`
- `Sources/FlowMacApp/UI/Assistant/AssistantView.swift` (current diff/state)
- `tests/NativeSmoke/AssistantWorkflowSmokeTests.swift` (rendered-state contract)
- Build/test evidence:
  - `./scripts/test_native_app.sh` -> pass
  - `./scripts/build_native_app.sh` -> pass

## Must-Fix Defects

1. Transcript message chrome is still too dashboard-like and not ChatGPT-style.
- In each bubble, `StatusPill` role chips (`Assistant`/`You`), proposal status chips, and per-message timestamp in the bubble header create high visual noise and reduce transcript readability density.
- This conflicts with the target hierarchy of content-first chat transcript with minimal meta chrome.

2. Composer row still exposes legacy/internal control chrome that breaks the ChatGPT-style bottom input feel.
- The always-visible top row label `Composer` and `Undo Last Safe Write` button make the composer read like a tool panel, not a clean rounded chat input anchored at the bottom.
- This is a direct visual mismatch versus the reference layout goal.

## Polish Defects

1. Conversation rail metadata remains slightly busy.
- `Chats` + `<count> conversations` + row timestamp + preview is functional, but visual density is higher than the reference’s lighter session rail.
- Not a blocker, but simplifying metadata would improve hierarchy and scan speed.

2. Empty-state prompt cards are visually heavier than the target.
- The prompt grid cards and icon styling feel more “Flow surface cards” than neutral chat suggestions.
- Functional and readable, but could be flatter/subtler for closer match.

## Mixed Old/New Chrome Risk (Observed)

- File still contains legacy/private components and paths (`sessionRail`, `conversationPane`, `AssistantComposerCard`) with old-style chrome patterns. Current body renders `AssistantChatShell`, so this is not the active path now, but it increases regression risk of reintroducing old chrome in future edits.

## Bug Count

- Must-fix: 2
- Polish: 2
- Total: 4

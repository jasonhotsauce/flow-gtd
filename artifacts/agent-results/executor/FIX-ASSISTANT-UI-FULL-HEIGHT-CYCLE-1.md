# FIX-ASSISTANT-UI-FULL-HEIGHT-CYCLE-1

## Scope

- Fixed the Assistant full-height layout bug in `Sources/FlowMacApp/UI/Assistant/AssistantView.swift`.
- Added a stable rendered-state smoke assertion for the full-height chat pane intent.
- Left outer `WorkspaceShell`, session/message behavior, pending `Thinking...`, and prior visual fixes intact.

## Changes

- Forced the Assistant chat shell to claim the full geometry height instead of sizing to ideal content.
- Made the conversation rail and transcript pane expand to the available height.
- Kept the composer anchored at the bottom of the right transcript pane.
- Added `usesFullHeightChatPane` to the rendered-state smoke contract so the height intent is explicit.

## Verification

- `./scripts/test_native_app.sh` -> passed
- `./scripts/build_native_app.sh` -> passed
- `git diff --check` -> passed

## Notes

- No data-layer, schema, runtime, or non-Assistant workspace changes were made.
- The full-height behavior is now covered by a stable smoke assertion rather than a pixel check.

# FIX-ASSISTANT-UI-VISUAL-CYCLE-1

## Scope

- Fixed the two UI tester must-fix issues in `Sources/FlowMacApp/UI/Assistant/AssistantView.swift`.
- Left data, schema, runtime, repository, and non-Assistant workspace behavior unchanged.

## Changes

- Transcript bubbles no longer show dashboard-like header chrome.
- Removed visible role `StatusPill` chips, proposal status chips, and per-message timestamps from the bubble header.
- Composer now reads as a clean rounded chat input instead of a tool panel.
- Removed the always-visible `Composer` label.
- Moved undo out of the main composer row and into the transcript header as a secondary control so it remains available without dominating the input area.

## Verification

- `./scripts/test_native_app.sh` -> passed
- `./scripts/build_native_app.sh` -> passed
- `git diff --check` -> passed

## Notes

- Functional coverage remained intact from the prior batch.
- No test updates were required for this visual-only cycle.

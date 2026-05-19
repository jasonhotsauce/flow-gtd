# ASSISTANT-UI-005

## Scope

- Changed the Assistant internal workspace in `Sources/FlowMacApp/UI/Assistant/AssistantView.swift` to a ChatGPT-style internal shell with a conversation rail, main transcript, and bottom composer.
- Updated the rendered-state smoke contract in `tests/NativeSmoke/AssistantWorkflowSmokeTests.swift` to assert the target layout and exact pending copy behavior.
- Updated `tasks/todo.md` for batch tracking.
- No schema, repository, migration, or provider/runtime changes were made.

## Key File Areas

- `Sources/FlowMacApp/UI/Assistant/AssistantView.swift:6-13` switches the Assistant entry to `AssistantChatShell`.
- `Sources/FlowMacApp/UI/Assistant/AssistantView.swift:222-327` updates `renderedSurfaceState` and adds the new chat shell layout.
- `Sources/FlowMacApp/UI/Assistant/AssistantView.swift:330-714` defines the rail, transcript, status banner, empty state, composer, and exact `Thinking...` pending bubble.
- `tests/NativeSmoke/AssistantWorkflowSmokeTests.swift:459-554` asserts the new internal layout contract and exact pending behavior.

## Red Phase Evidence

Initial `./scripts/test_native_app.sh` run failed as intended after the contract update:

- `FlowDataError.message("Expected the Assistant internals to present a ChatGPT-style internal layout.")`

That failure confirmed the smoke contract was red before the UI refactor was completed.

## Final Verification

- `./scripts/test_native_app.sh` passed.
- `./scripts/build_native_app.sh` passed and produced `.build/native/Flow.app`.
- `git diff --check` passed.
- `.venv/bin/pytest tests/unit -v` passed with `229 passed`.

## Review Notes

- `code-review-flow` checklist was applied to the `tests/` change set.
- No material architecture, security, or dependency-direction issues were found in the scoped diff.
- Residual risk: the file still contains older Assistant helper methods that are no longer used by the live body. They are inert, but the file could be cleaned up further later if desired.

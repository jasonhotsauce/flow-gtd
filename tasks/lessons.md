# Lessons

- Date: 2026-02-28
- Pattern: For foundational storage changes where future backends are explicit (e.g., Obsidian now, Apple Notes later), do not recommend transitional dual-write designs as the default.
- Prevention rule: Start with a backend abstraction (`ResourceStore` contract) and keep backend-specific metadata/tag/search behavior inside each provider, with no mandatory SQLite dependency.

- Date: 2026-02-28
- Pattern: User-facing setup should avoid technical backend jargon; users choose outcomes/workflows, not implementation technologies.
- Prevention rule: In onboarding/config UX, present plain-language storage options and hide provider internals in config mapping.

- Date: 2026-03-01
- Pattern: Using new TCSS tokens only in `theme.tcss` is insufficient; screen-local TCSS files may not see those variables and can fail at runtime with undefined-variable errors.
- Prevention rule: Define tokens once in `flow/tui/common/ops_tokens.tcss` and include that file in every app/screen `CSS_PATH` tuple before screen-specific TCSS.

- Date: 2026-03-01
- Pattern: Design/implementation plan docs were saved in repo docs by default when the user expects all new design docs in the Obsidian vault.
- Prevention rule: For this user, save all new design and implementation plan artifacts under `/Users/wenbinzhang/Library/Mobile Documents/iCloud~md~obsidian/Documents/Personal/10 Projects/flow-gtd/` using stable `01-designs` and `02-implementation-plans` folders.

- Date: 2026-03-08
- Pattern: I created new Obsidian documents under `Personal/Projects/flow-gtd/` even though the existing vault structure already uses `Personal/10 Projects/flow-gtd/`.
- Prevention rule: Before saving any new Obsidian artifact for this user, verify the existing project root and always prefer the established `Personal/10 Projects/flow-gtd/` path over creating parallel folder trees.

- Date: 2026-03-08
- Pattern: I shipped a new split-pane TUI screen without direct numeric pane shortcuts or initial list focus, which made navigation unusable.
- Prevention rule: For every split-pane TUI screen in this project, provide explicit pane bindings (`1/2/3` as applicable), route `j/k` to the primary list, and focus the primary list after the screen populates.

- Date: 2026-03-08
- Pattern: I assumed a focused `OptionList` would make `Enter` work in a new TUI screen, but the list had no initial highlighted row and the screen did not handle `OptionList.OptionSelected`, so the primary action never fired.
- Prevention rule: For every new Textual `OptionList` screen, initialize the first selection explicitly after populating the list and wire `OptionList.OptionSelected` to the intended primary action whenever the list owns `Enter`.

- Date: 2026-03-08
- Pattern: I told the user to use an advertised TUI key before proving the actual focused-widget key path worked in runtime.
- Prevention rule: For any user-visible TUI shortcut, do not claim it works until a runtime test presses that exact key with the real focused widget state; if the widget contract is unreliable, change the shortcut and update all visible guidance in the same task.

- Date: 2026-03-01
- Pattern: After repeated UI rendering failures, I iterated on fixes without first isolating whether data was missing vs. present-but-not-painted.
- Prevention rule: For TUI visual bugs, first instrument the exact render path (`widget.renderable`, visibility flags, screenshot export) to confirm root cause before additional code changes.

- Date: 2026-03-01
- Pattern: I assumed the target state was empty-state rendering while runtime was actually in task-present mode (`has_task=True`), which delayed the real fix.
- Prevention rule: For any stateful UI bug, log/verify branch conditions first (for example `has_task`, selected item presence) before editing presentation code.

- Date: 2026-03-01
- Pattern: I transformed user-supplied ASCII content by escaping bracket characters, which changed intended output.
- Prevention rule: Treat user-provided ASCII/terminal art as immutable content; never mutate characters for styling. Apply color/style around raw lines only.

- Date: 2026-03-09
- Pattern: I treated a workflow skill requirement as mandatory even after the user explicitly told me to stay on the current branch and skip worktree setup.
- Prevention rule: When the user explicitly overrides an implementation workflow preference such as worktree usage, follow the override, record the deviation in `tasks/todo.md`, and continue execution without re-arguing the default workflow.

- Date: 2026-03-14
- Pattern: I patched confirmed-state pane focus by relabeling a shared list instead of verifying the implemented UI against the approved plan and the live layout, which hid that pane `3` was supposed to own its own selectable unplanned-task list and add chooser.
- Prevention rule: For any TUI pane redesign with an approved design/implementation plan, compare the live screen structure against that plan before shipping; if a pane is specified as interactive, implement a real widget in that pane and add a runtime test that exercises its focus, navigation, and primary action.

- Date: 2026-03-21
- Pattern: I started a repository release by manually editing version/release metadata and planning ad hoc git/gh commands instead of using the existing Makefile workflow the user expected.
- Prevention rule: For Flow release tasks, inspect the Makefile first and use its release targets (`make bump-*`, `make release`, `make publish`, `make brew-formula` as applicable) instead of manual version edits or hand-run git/GitHub release commands unless the user explicitly asks otherwise.

- Date: 2026-03-22
- Pattern: I claimed the startup daily recap could be acknowledged without verifying that the actual `w`/`x` key paths advanced the gated screen out of the prior-day recap.
- Prevention rule: For any gated TUI continuation flow in Flow, add or run a real Textual keypress test for the advertised acknowledgement keys and assert the screen transitions to the next state, not just that a handler method mutates backend state.

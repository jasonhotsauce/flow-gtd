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
- Prevention rule: For this user, save all new design and implementation plan artifacts under `/Users/wenbinzhang/Library/Mobile Documents/iCloud~md~obsidian/Documents/Personal/Projects/flow-gtd/` using stable `01-designs` and `02-implementation-plans` folders.

- Date: 2026-03-01
- Pattern: After repeated UI rendering failures, I iterated on fixes without first isolating whether data was missing vs. present-but-not-painted.
- Prevention rule: For TUI visual bugs, first instrument the exact render path (`widget.renderable`, visibility flags, screenshot export) to confirm root cause before additional code changes.

- Date: 2026-03-01
- Pattern: I assumed the target state was empty-state rendering while runtime was actually in task-present mode (`has_task=True`), which delayed the real fix.
- Prevention rule: For any stateful UI bug, log/verify branch conditions first (for example `has_task`, selected item presence) before editing presentation code.

- Date: 2026-03-01
- Pattern: I transformed user-supplied ASCII content by escaping bracket characters, which changed intended output.
- Prevention rule: Treat user-provided ASCII/terminal art as immutable content; never mutate characters for styling. Apply color/style around raw lines only.

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

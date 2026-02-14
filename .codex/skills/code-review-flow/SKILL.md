---
name: code-review-flow
description: Mandatory review checklist for Flow code changes in flow/ or tests/.
---

# Flow Code Review

Use this skill after any change to `flow/` or `tests/`.

## Critical Checks

- Security:
  - No secrets, credentials, or tokens in code.
  - No SQL string interpolation; parameterize all queries.
  - No unsafe path handling from user input.
- Privacy:
  - LLM payloads are limited to necessary sanitized task content.
  - Sensitive content is not logged.
- Architecture:
  - No dependency direction violations.
  - `flow/database/` and `flow/sync/` do not import from `flow/core/`.
  - `flow/models/` remains dependency-light domain code.

## High-Priority Checks

- Type hints on all new or changed public APIs.
- Async safety in Textual paths (no blocking calls on main loop).
- Graceful error handling in TUI flows.
- Correct file placement within existing module boundaries.
- Date/time safety:
  - Validate mixed naive/aware datetime handling before any comparison.
  - For defer/tickler behavior, verify timezone normalization does not raise runtime `TypeError`.

## Test Checks

- Existing tests updated or added for behavior changes.
- Run targeted tests for touched areas; use full unit suite when risk is broad.

## Output Format

- Report findings with severity and file references.
- If no material issues found, state that explicitly.

# Codex Setup for Flow GTD

This repository is configured for Codex-first collaboration.

## Scope

- Apply these instructions to all files in this repository.
- If instructions conflict, prefer explicit user instructions in the current chat, then this file.

## Project Snapshot

- Product: Local-first, AI-augmented GTD CLI for macOS users.
- Core stack: Python 3.11+, `typer`, `textual`, raw `sqlite3`, optional ChromaDB, PyObjC EventKit.
- LLM integration: `flow/utils/llm/` (Gemini, OpenAI, Ollama), config in `~/.flow/config.toml`.

## Architecture Guardrails

- Dependency flow must stay one-way:
  - Presentation (`flow/cli.py`, `flow/tui/`) -> Core (`flow/core/`) -> Models/Database/Sync.
- `flow/models/` stays pure domain models (no UI/DB imports).
- `flow/database/` and `flow/sync/` must not import from `flow/core/`.
- Keep file placement aligned with existing package layout; avoid creating ad-hoc top-level modules.

## Implementation Standards

- Use strict type hints on new/changed Python APIs.
- Prefer `pathlib` over `os.path`.
- Always bootstrap and activate the repository virtual environment before running Python scripts:
  - If `.venv` is missing, create it with Python 3.11+:
    - `python3.11 -m venv .venv` (preferred)
    - fallback only if `python3` is already 3.11+
  - Run `source .venv/bin/activate` first in the shell session.
  - Ensure dependency tooling exists in venv:
    - `pip3 install poetry`
  - Install project dependencies:
    - `poetry install` (preferred)
    - `make install` (wrapper target, equivalent for default setup)
  - After activation, use `python` / `pytest` from that active environment.
  - This project uses Poetry for dependency management; use `poetry` commands
    (for example `poetry install`, `poetry add`, `poetry update`) when changing dependencies.
- For datetime comparisons in defer/tickler logic:
  - Treat mixed naive/aware datetimes as a first-class risk.
  - Normalize timezone context before comparison.
- Keep Textual UI responsive:
  - No blocking work in handlers/composition.
  - Use workers or `asyncio.to_thread` for blocking operations.
- In TUI paths, fail gracefully with user-visible status/toast messaging.
- Use parameterized SQL queries only.

## Quality Bar

- For code changes in `flow/` or `tests/`, run `.codex/skills/code-review-flow/SKILL.md` before finalizing.
- The review must cover:
  - Security/privacy, architecture direction, placement, typing, async safety, and tests.
- Run targeted tests for touched behavior when practical:
  - `pytest tests/unit -v`

## Documentation Sync (Mandatory)

- If you change user-facing behavior, update docs in the same task:
  - CLI command behavior/options -> `README.md` and any affected docs under `docs/features/`.
  - Workflow/architecture behavior -> `docs/PRD.md` and/or `docs/patterns-and-lessons.md`.
- Keep `README.md` implementation-accurate; move speculative roadmap details to `docs/PRD.md`.
- Prefer concrete placeholders in docs (for example `<your-github-username>`) over unresolved template literals.

## Debugging Guardrails (Mandatory)

When handling bugs, regressions, or unexpected behavior, follow these rules:

1. **No fix before evidence**
- Reproduce first.
- Gather logs/traces at component boundaries before proposing code changes.

2. **Single-hypothesis iteration**
- One root-cause hypothesis at a time.
- One minimal code change to test that hypothesis.
- Re-verify before any additional change.

3. **Framework/API contract check first**
- Verify method signatures and behavior in the actual runtime/library before changing flow logic.

4. **No time-based UX control flow**
- Do not use arbitrary delays (for example `sleep`, magic milliseconds) to mask event-order issues.
- Use deterministic state/intent checks instead.

5. **Failing test before fix**
- Add/adjust a test that reproduces the observed failure path.
- Implement only after the test fails for the expected reason.

6. **Debug instrumentation discipline**
- Keep instrumentation scoped and temporary.
- Remove debug-only logs/probes once root cause is confirmed and fix is verified.

7. **Stop-and-reset rule**
- If two consecutive fixes fail, stop patching and return to root-cause investigation.
- Re-state evidence, hypothesis, and test plan before continuing.

## Codex Skills (Project Local)

- `.codex/skills/testing-flow/SKILL.md`
- `.codex/skills/textual-ui/SKILL.md`
- `.codex/skills/macos-eventkit/SKILL.md`
- `.codex/skills/code-review-flow/SKILL.md`

Use these skills when tasks match their domains.

## Migration Note

- Legacy Cursor config remains under `.cursor/` for reference only.
- New agent behavior should be encoded in this `AGENTS.md` and `.codex/skills/`.

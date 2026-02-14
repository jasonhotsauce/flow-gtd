# Codex Setup for Flow GTD

This repository is configured for Codex-first collaboration.

## Scope

- Apply these instructions to all files in this repository.
- If instructions conflict, prefer explicit user instructions in the current chat, then this file.

## Project Snapshot

- Product: Local-first, AI-augmented GTD CLI for macOS users.
- Core stack: Python 3.11+, `typer`, `textual`, raw `sqlite3`, PyObjC EventKit.
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
    - `make install`
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

## Codex Skills (Project Local)

- `.codex/skills/testing-flow/SKILL.md`
- `.codex/skills/textual-ui/SKILL.md`
- `.codex/skills/macos-eventkit/SKILL.md`
- `.codex/skills/code-review-flow/SKILL.md`

Use these skills when tasks match their domains.

## Migration Note

- Legacy Cursor config remains under `.cursor/` for reference only.
- New agent behavior should be encoded in this `AGENTS.md` and `.codex/skills/`.

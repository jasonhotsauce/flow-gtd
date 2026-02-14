---
name: testing-flow
description: Testing standards for Flow CLI/TUI, fixtures, and mocking external integrations.
---

# Testing Flow

Use this skill when writing or modifying tests in `tests/` or behavior validated by tests.

## Framework

- Use `pytest`.
- Use `pytest-asyncio` for async tests.
- Keep tests deterministic and isolated.

## Database Safety

- Never use the real `flow.db` in tests.
- Use temp DB fixtures from `tests/conftest.py` (`temp_db_path`, `db`, `sample_item`).

## Mocking Rules

- Mock all LLM/network provider calls.
- Mock EventKit/PyObjC calls. Tests must never touch a real reminders store.

## TUI Tests

- Use Textual test harness (`app.run_test()`) and pilot key simulation.
- Assert user-visible state transitions, not just internal implementation details.

## Test Placement

- Unit tests: `tests/unit/`
- Add integration coverage only when behavior crosses module boundaries.

## Validation

- Run focused tests first, then broader suites if needed:
  - `pytest tests/unit -v`

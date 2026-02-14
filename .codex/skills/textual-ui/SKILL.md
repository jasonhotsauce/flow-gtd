---
name: textual-ui
description: Build and style Textual TUI screens/widgets with Flow conventions.
---

# Textual UI Specialist

Use this skill when changing files under `flow/tui/` or any `.tcss` file.

## Core Rules

- Keep UI responsive; never block event handlers.
- Use `run_worker`, `run_worker_thread`, or `asyncio.to_thread` for heavy/blocking work.
- Keep screen-specific CSS colocated with its screen module.
- Do not move screen-specific styles into `flow/tui/common/theme.tcss`.

## Interaction Standards

- Support Vim-style navigation where list-like interactions exist:
  - `j/k` move, `enter` select, `escape` back.
- Prefer non-blocking user feedback (`Toast`/status updates).

## TCSS Safety

- Textual CSS is not web CSS; use only supported properties.
- `scrollbar-size` requires two integers (horizontal and vertical).
- Avoid unsupported web-only properties (for example `overflow-wrap`).

## Performance

- Keep `render()` lightweight.
- Avoid expensive work in `compose()`.
- Prefer reactives/cached state over repeated recomputation.

# Defer Feature Design (Hybrid GTD)

**Date:** 2026-02-14  
**Status:** Approved

## Goal

Design a GTD-aligned defer workflow that lets users choose among `Waiting For`, `Defer Until`, and `Someday/Maybe` when deferring actions from existing TUI entry points.

## Scope

First release scope:
- `flow projects` project detail screen (`f`)
- Process funnel Stage 3 (2-minute drill) (`f`)

Out of scope for first release:
- New global CLI defer command
- Action screen defer UX
- New dedicated Tickler review tab

## GTD Semantics

- **Waiting For**: Action is blocked by an external dependency (person/system/event).
- **Defer Until**: Action should not appear in actionable lists until a specific date/time (tickler behavior).
- **Someday/Maybe**: Idea or low-commitment option with no immediate commitment date.

## Chosen Approach

Use a **hybrid defer chooser** with existing statuses and minimal schema impact.

### Data model decisions

- `Waiting For` -> `status="waiting"`
- `Someday/Maybe` -> `status="someday"`
- `Defer Until` -> keep `status="active"`, store ISO datetime in `meta_payload.defer_until`

Optional note storage for waiting:
- `meta_payload.defer_note`

This avoids a new migration now and keeps implementation fast/low risk. If usage expands, a dedicated `defer_until` indexed column can be added later.

## UX Design

## Defer chooser

Pressing `f` opens a modal/action-sheet with:
- `Waiting For`
- `Defer Until`
- `Someday/Maybe`
- `Cancel`

## Defer Until input

Supported first-version input:
- Quick presets:
  - `Tomorrow (09:00 local)`
  - `Next week (same weekday, 09:00 local)`
- Manual input:
  - relative: `tomorrow`, `next week`
  - absolute: `YYYY-MM-DD`, `YYYY-MM-DD HH:MM`

Parse errors show a user-visible toast and keep user in the dialog.

## Architecture Changes

## Core (`flow/core/engine.py`)

Introduce explicit defer API:
- `defer_item(item_id, mode, defer_until=None, note=None)` where `mode in {"waiting", "until", "someday"}`

Behavior:
- waiting mode: set status to `waiting`
- someday mode: set status to `someday`
- until mode: keep status `active`, write `meta_payload.defer_until`

Add helper for action visibility:
- `is_deferred_until_active(item, now)` to filter out future-deferred active items.

Compatibility:
- Keep old `defer_item(item_id)` call path as wrapper to waiting mode if needed during transition.

## Presentation (`flow/tui/`)

- `flow/tui/screens/projects/project_detail.py`
  - `f` opens chooser
  - selected branch maps to engine defer mode

- `flow/tui/screens/process/process.py` (Stage 3)
  - `f` opens same chooser
  - apply selected defer mode to current item, then advance

All UI interactions should remain non-blocking and use worker/thread patterns where blocking may occur.

## Action Visibility Rules

In next-action views, include only:
- active items without `defer_until`
- active items with `defer_until <= now`

Exclude:
- active items with `defer_until > now`
- waiting items
- someday items

## Error Handling

- Invalid date/time parse: toast with accepted formats, stay in defer dialog.
- Missing/stale selected item: warning toast and refresh list.
- Any defer operation failure: non-crashing user-visible notification.

## Testing Strategy

## Unit tests (`tests/unit/test_engine.py`)

Add/extend tests for:
- waiting mode sets `status="waiting"`
- someday mode sets `status="someday"`
- until mode writes `meta_payload.defer_until` in ISO format while keeping active status
- list filtering excludes future-deferred active items
- list filtering includes due/past-deferred active items

## TUI behavior tests

Where existing test harness supports it:
- `f` opens chooser in project detail and process stage 3
- selecting each defer mode triggers expected engine call
- invalid manual defer-until input shows parse error toast

## Documentation Updates

Update:
- `docs/features/projects.md` to describe new defer chooser semantics

Add mapping note:
- `Waiting For` vs `Defer Until` vs `Someday/Maybe`

## Rollout Plan

1. Ship with `meta_payload.defer_until` (no schema migration).
2. Observe usage/performance.
3. If needed, introduce dedicated `defer_until` DB column + index in a later migration.

## Risks and Mitigations

- **Risk:** Tickler filtering logic spread across call sites.
  - **Mitigation:** Centralize filtering helper in core layer.
- **Risk:** Date parsing ambiguity.
  - **Mitigation:** Keep accepted formats narrow and documented in UI hint text.
- **Risk:** User confusion between waiting and someday.
  - **Mitigation:** One-line descriptions in chooser labels.

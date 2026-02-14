# Inbox Add-To-Existing-Project Design

## Goal

Allow users to assign a single Inbox task to an existing active project with a fast, keyboard-first flow that fits current Inbox behavior and GTD processing.

## Why

- Users can already create projects from cluster suggestions, but cannot quickly attach one-off Inbox tasks to existing projects.
- This causes Inbox clutter and friction during daily triage.
- The feature should preserve current fast-path shortcuts (`d`, `f`) while making assignment discoverable.

## User Experience

### Entry Point

- User highlights an Inbox task and presses `Enter`.
- `Enter` opens a compact **Process Task** menu.

### Process Task Menu

Menu options:

- `Do now`
- `Defer`
- `Add to project`
- `Delete`

Behavior:

- Keyboard-only navigation (`j/k`, `Enter`, `Esc`).
- Optional single-key accelerators for each menu item.
- Existing direct shortcuts (`d`, `f`) remain available for power users.

### Add To Project Flow

- Choosing `Add to project` opens a searchable **Project Picker** modal.
- Picker displays active projects only.
- Filtering happens as the user types.
- Each row shows project name and optional open-task count.
- `Enter` confirms assignment.

### Success and Refresh

- Show confirmation toast: `📁 Added to project: <project name>`.
- Refresh Inbox list immediately.
- Assigned item disappears from Inbox because it now has `parent_id`.

### Empty/Failure States

- If no active projects exist: show a clear message and return to Inbox.
- If selected task no longer exists: warning toast + refresh.
- If selected project is invalid/inactive: error toast, keep user in picker.

## Data and Domain Behavior

### Assignment Semantics

When assigning item `X` to project `P`:

- Set `X.parent_id = P.id`
- Set `X.type = "action"` (normalize project children as actions)
- Keep all other fields unchanged (`title`, `status`, `context_tags`, `meta_payload`, dates).

### Validation Rules

- Source item exists and is not `done`/`archived`.
- Target project exists, `type == "project"`, and `status == "active"`.
- Reject self-parenting and no-op assignment.

## Architecture Changes

### Core

- Add `Engine.assign_item_to_project(item_id: str, project_id: str) -> Item`.
- Keep all persistence logic in DB layer through existing `get_item` + `update_item`.
- Keep presentation -> core dependency direction intact.

### Presentation (TUI)

- Add `ProcessTaskDialog` used by Inbox `Enter`.
- Add `ProjectPickerDialog` opened from `ProcessTaskDialog`.
- Keep blocking DB work off UI thread where applicable (`asyncio.to_thread` for project list reads if needed).
- Show user-visible notifications for all failure cases.

## Interaction and Performance Notes

- Dialogs should be lightweight and non-blocking.
- Project list load should be responsive even with many projects.
- Search must not freeze the UI (local in-memory filter on prefetched list).

## Testing Strategy

### Unit Tests (Core)

- `assign_item_to_project` updates `parent_id` and `type`.
- Preserves unrelated fields.
- Raises/rejects invalid item/project/status combinations.

### Unit Tests (TUI)

- Inbox `Enter` opens process menu.
- Selecting `Add to project` opens picker.
- Confirming project calls engine assignment and refreshes list.
- No-project and missing-item states show expected notifications.

### Regression Coverage

- Existing Inbox shortcuts (`d`, `f`, navigation) keep behavior.
- `list_inbox()` still excludes assigned items (`parent_id IS NOT NULL`).

## Out of Scope (This Iteration)

- Multi-select batch assignment.
- Creating a new project from picker.
- Cross-screen assignment flows outside Inbox.

## Rollout

- Add docs update in `docs/features/projects.md` and Inbox help text.
- Keep flow additive with minimal behavior disruption.

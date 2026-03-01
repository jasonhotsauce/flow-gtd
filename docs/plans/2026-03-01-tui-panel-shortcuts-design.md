# TUI Panel Shortcuts + Named Headers Design

## Goal
Reduce friction when switching focus between split panels by adding direct panel shortcuts by number and by panel name abbreviation, and make panel targets visible with explicit headers.

## Scope
- `ActionScreen` (Tasks + Resources)
- `InboxScreen` (List + Detail)
- `ProjectsScreen` (List + Detail)

## UX Decisions
- Keep existing `Tab` behavior where already present (`ActionScreen`) for backward compatibility.
- Add numeric panel switching:
  - `1` -> first panel
  - `2` -> second panel
- Add per-screen name abbreviations (single key):
  - Action: `t` (Tasks), `r` (Resources)
  - Inbox: `l` (List), `e` (dEtail)
  - Projects: `l` (List), `d` (Detail)
- Add explicit panel headers that include shortcut hints:
  - `Action`: `[1] Tasks (t)`, `[2] Resources (r)`
  - `Inbox`: `[1] List (l)`, `[2] Detail (e)`
  - `Projects`: `[1] List (l)`, `[2] Detail (d)`

## Implementation Approach
1. Add new key bindings to each screen’s `BINDINGS`.
2. Add dedicated focus actions per panel (`action_focus_*`).
3. Wire existing compatibility action (`action_focus_sidecar`) to new resources action.
4. Update compose header labels for each panel.
5. Update help text strings for discoverability.
6. Add/extend unit tests for bindings and focus action routing.

## Error Handling / Safety
- Focus actions are lightweight and synchronous.
- They should not introduce async blocking or DB access.
- Existing navigation paths remain unchanged.

## Testing Strategy
- Unit tests validate new bindings are exposed.
- Unit tests validate focus actions target the expected widget IDs.
- Run targeted tests for action/inbox/projects binding and focus behavior.

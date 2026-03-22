# Daily Workspace Calendar Reuse Design

## Context
`Daily Workspace` is now the single execution surface for planned work, but the product still has an older strategic promise: use calendar context heuristically to recommend the best next task without forcing users into auto-scheduling or rigid time blocking. The current confirmed-mode `f` action does not reuse that capability. It simply recommends the first active `Top 3` item, then falls back to `Bonus`.

The result is a gap between product intent and shipped behavior. The workspace already owns the task-first execution flow, so calendar reuse should happen inside that flow instead of reviving a separate focus surface.

## Goals
- Reuse the existing calendar feature inside Daily Workspace confirmed mode.
- Improve `f` recommendation quality using near-term calendar availability.
- Keep the product task-first and preserve user agency.
- Preserve deterministic fallback behavior when calendar data is unavailable or unusable.

## Non-Goals
- No calendar pane in Daily Workspace.
- No automatic time blocking or schedule editing.
- No expansion of recommendation eligibility beyond active confirmed planned items.
- No requirement that every task has duration metadata before recommendation can work.

## Product Decision
Calendar reuse should be lightweight and advisory:
- The user continues to plan with `Top 3` and `Bonus`.
- In confirmed mode, `f` recommends the best next planned item using calendar-aware ranking.
- The workspace remains a task interface, not a schedule interface.

This keeps the mental model intact:
- `Daily Workspace` decides from today's plan.
- Calendar only influences which planned item is suggested next.

## User Experience
### Confirmed Mode Recommendation
When the user presses `f` in confirmed mode:
- Flow evaluates active confirmed `Top 3` and `Bonus` items.
- Flow reads a lightweight calendar availability summary for the near term.
- Flow recommends the planned item that best fits the next available work window.
- The highlighted item moves in the existing `Today` list as it does today.

### Recommendation Explanation
When a calendar-aware recommendation is made, the workspace should show a short explanation string in existing status/detail surfaces. Examples:
- `Fits before your next event`
- `Best fit for the next free block`
- `Calendar unavailable, using plan order`

The explanation should justify the recommendation without adding visual noise or exposing a full event list.

## Ranking Rules
### Eligibility
Only active confirmed planned items are eligible:
- active `Top 3`
- active `Bonus`

Unplanned work must remain ineligible.

### Primary Heuristic
If calendar availability is available:
- Prefer a planned item whose estimated duration fits the next free window.
- If multiple items fit, prefer `Top 3` before `Bonus`.
- Within the same bucket, preserve existing saved order as the deterministic tie-breaker.

### Fallback Heuristic
If there is no calendar summary, no usable free window, or no usable task-duration metadata:
- Fall back to the current deterministic behavior.
- That means first active `Top 3` item by saved order, then first active `Bonus` item by saved order.

### Scope Of Calendar Influence
Calendar should influence ranking, not eligibility and not persistence:
- it does not change the daily plan
- it does not reorder the saved plan
- it does not block selection of long tasks forever

This feature should feel like better dispatching, not covert scheduling.

## Data Flow
### Calendar Read Model
The workspace should consume a compact availability summary rather than raw EventKit event objects. A small read model is enough:
- whether calendar data is available
- minutes until next event, if any
- duration of the next free work window, if meaningful
- a stable explanation label suitable for UI copy

This read model should be produced below the TUI layer, likely through the engine/service boundary, so the screen never talks directly to EventKit.

### Task Metadata
Recommendation ranking can use duration metadata if it already exists on tasks. If duration is missing, the item remains eligible but should not claim a fit-based advantage over items with usable estimates.

The first version should not invent AI estimates or new required fields.

## Architecture
- `flow/core/focus.py` should own calendar-aware ranking logic because it already owns confirmed-plan recommendation behavior.
- `Engine` should expose a calendar availability summary through a small method the screen can call from its existing async/threaded refresh path or recommendation path.
- `DailyWorkspaceScreen` should remain responsible only for invoking the recommendation, highlighting the chosen item, and showing the explanation string.

This keeps dependency direction intact:
- TUI -> Engine/Core
- no direct TUI -> EventKit integration

## Error Handling
- Calendar access failures must not break recommendation.
- Any EventKit/PyObjC failure should degrade to deterministic plan-order fallback.
- The user-visible explanation should make fallback clear without exposing low-level errors.

## Testing Strategy
- Unit tests for recommendation ranking with:
  - no calendar context
  - a short next free window
  - a longer next free window
  - missing duration metadata
  - `Top 3` vs `Bonus` tie-break behavior
- Daily Workspace screen tests for:
  - `f` still highlighting the recommended item in confirmed mode
  - explanation messaging for calendar-aware and fallback recommendations
  - graceful behavior when no active planned items exist

## Documentation Impact
User-facing docs should describe the behavior at a high level:
- Daily Workspace reuses calendar context to suggest the best next planned item
- this is advisory only and does not auto-schedule the day

## Open Implementation Constraint
The current repository appears to keep only Reminders EventKit integration live in code. During implementation, verify whether calendar availability code already exists elsewhere in the branch history or needs a fresh small read-model/service layer. The product behavior above stays the same either way.

# Daily Workspace UI Refresh Design

## Context
The new daily workspace established the right product flow: `Plan -> Focus -> Daily Wrap`. The current UI does not yet support that flow well. Planning feels write-only because users cannot see the draft plan clearly, cannot remove or rebalance items easily, and do not get enough feedback about what is already in `Top 3` versus `Bonus`. After confirmation, the screen shifts too abruptly, which makes the mode change feel odd rather than intentional. The wrap experience is also too thin to give the user a meaningful sense of accomplishment or improvement.

The goal of this redesign is to keep the existing daily-workspace concept and professional-ops visual system, while making the interaction model more structured, modern, and self-explanatory. The visual direction should stay consistent with the current TUI palette, but apply a more terminal-native Material design approach for surface hierarchy, pane framing, focus cues, and feedback.

## Goals
- Make planning feel interactive and reversible, not write-only.
- Keep `Top 3` and `Bonus` visible during planning so users can evaluate the draft as they build it.
- Support direct plan editing on the same screen: add, remove, promote, demote, and reorder.
- Make confirmation feel like a smooth transition from planning into execution.
- Expand daily wrap so it explains what the user accomplished and where planning/execution could improve.
- Bring the pane structure up to the same visual standard across the whole workspace.

## Non-Goals
- No change to the core daily-plan persistence model.
- No separate full-screen wrap flow; wrap remains part of the workspace.
- No broader palette fork for the daily workspace; it should stay consistent with the current professional-ops theme.
- No speculative new AI-first workflow; AI wrap insight remains optional and additive.

## Workflow Design
### Planning Mode
Planning uses a three-column workspace on the same screen:

- Left pane: `Candidates`
- Center pane: `Top 3 Draft`
- Right pane: `Bonus Draft` with a detail card in the lower portion

`Candidates` remains grouped by:
- `Must`
- `Inbox`
- `Ready`
- `Suggested`

The draft plan is always visible while planning:
- `Top 3 Draft` shows fixed slots and explicit ordering.
- `Bonus Draft` shows all bonus items currently selected.
- The detail card shows the currently focused item's title, current planning status, and any short guidance text.

Supported planning interactions:
- Add the focused candidate to `Top 3`
- Add the focused candidate to `Bonus`
- Remove an item from `Top 3`
- Remove an item from `Bonus`
- Promote a `Bonus` item into `Top 3`
- Demote a `Top 3` item into `Bonus`
- Reorder `Top 3`

Planning status must always be legible:
- Show `Top 3` count and remaining slots
- Show `Bonus` count
- Show the focused item's current bucket: `Not planned`, `Top 3 #N`, or `Bonus`
- Show blocking or swap guidance when `Top 3` is full

### Focus Mode
Confirmation should not feel like a hard redraw into a different mental model. The layout should evolve in place.

After confirmation:
- `Candidates` collapses into a locked/minimized pane or is replaced by execution content in the same shell position
- `Top 3 Draft` and `Bonus Draft` merge into one ordered `Today` pane
- `Today` remains sectioned:
  - `Top 3`
  - `Bonus`
- The detail pane stays in the same location
- The wrap pane remains visible and becomes progressively more informative as work is completed

This preserves continuity. The user sees the plan they just built become the list they now execute.

## Visual Direction
### Design Language
Use a terminal-native Material approach:
- consistent surfaces
- explicit hierarchy
- restrained accent usage
- strong title/subtitle structure
- clear focus states
- summary chips for counts and planning status

This should not imitate a web UI. It should still feel natural in a terminal: framed panes, compact metadata, readable section headers, and low-noise visual emphasis.

### Surface Structure
Every major pane should share the same shell:
- border
- title row
- short purpose/status line
- content area

This applies to:
- `Candidates`
- `Top 3 Draft`
- `Bonus Draft`
- `Today`
- `Detail`
- `Wrap`

Only having a border on the list pane is no longer acceptable. The entire workspace needs one coherent surface grammar.

### Focus Cues
The focused pane should be obvious through:
- stronger border treatment
- brighter title/status line
- consistent selected-row styling inside interactive lists

The user should always be able to tell:
- which pane has focus
- which item is selected
- which bucket that item currently belongs to

## Pane Content Design
### Candidates Pane
Displays grouped planning sources with clear labels:
- `[Must]`
- `[Inbox]`
- `[Ready]`
- `[Suggested]`

The pane should prioritize scanability over density. Group labels should feel like section markers, not just row prefixes.

### Top 3 Draft Pane
Displays:
- three ordered slots
- current contents
- open-slot placeholders when incomplete

Examples of placeholders:
- `Slot 2 open`
- `Slot 3 open`

This should visually reinforce that `Top 3` is a constrained commitment, not just another list.

### Bonus Draft Pane
Displays:
- all selected bonus items
- promotion/removal affordances through key hints and detail-pane messaging

This pane should make bonus work feel secondary but still intentional.

### Detail Pane
During planning, the detail pane should explain the selected item in the context of the draft plan:
- title
- source bucket
- current planning status
- short action hint

Examples:
- `Not planned`
- `Currently Top 3 #2`
- `Currently Bonus`

After confirmation, the same pane becomes an execution detail card for the selected `Today` item.

### Wrap Pane
The wrap pane should be live throughout the day, not only when the user explicitly opens wrap mode.

Always-visible content:
- `Top 3 completed: X/Y`
- `Bonus completed: A/B`
- a short day-status headline

Expanded wrap content:
- completed `Top 3` items
- completed `Bonus` items
- unfinished planned items
- short coaching feedback
- optional AI insight

## Wrap Experience
Daily wrap should answer three questions:
- What got done?
- How did the day go?
- What should improve next time?

### Completion Summary
Show a high-level verdict based on deterministic rules:
- `Strong day`
- `Solid day`
- `Plan was too ambitious`

The verdict should be based on plan completion, especially `Top 3`.

### Accomplishments
List completed work in priority order:
- completed `Top 3` items first
- completed `Bonus` items second

### Carry-Forward
Explicitly show planned items that remain open. Unfinished work should not disappear.

### Coaching Feedback
Provide concise non-AI feedback even if AI is unavailable. Examples:
- praised realistic planning when `Top 3` completion is high and bonus load is reasonable
- flagged overloaded planning when `Top 3` is incomplete and bonus count was high
- noted under-commitment if the day was too light and all work finished early

AI insight remains optional and should extend, not replace, the default wrap value.

## Transition Design
Confirmation needs an explicit in-place transition so users know what happened.

On confirm:
- keep the overall shell and pane layout stable
- update pane titles and summaries in place
- replace planning guidance with execution guidance in the status strip
- show a transition line in the detail area such as `Plan confirmed. Today list is now active.`

The result should feel like state progression, not screen replacement.

## Interaction Summary
### Planning
- `t`: add to `Top 3`
- `b`: add to `Bonus`
- dedicated actions to remove from either draft bucket
- dedicated actions to promote/demote between buckets
- dedicated actions to reorder `Top 3`
- `x`: confirm plan

### Execution
- `Today` pane becomes the primary working list
- `c`: complete selected planned item
- `w`: expand wrap review state
- `I`: request AI wrap insight

The final key map can evolve during implementation, but the interaction model must support direct same-screen editing and a smooth confirm transition.

## Architecture Notes
- Keep daily-plan persistence in the existing first-class daily-plan layer.
- Reuse the current `DailyWorkspaceScreen` rather than creating a separate screen for planning or wrap.
- Treat this as a presentation and interaction redesign on top of the current engine APIs, with additional screen-level state/actions as needed.
- If wrap feedback requires deterministic summary logic beyond current counts, add it in the daily-plan service or engine layer rather than embedding business rules directly in the screen.

## Risks And Mitigations
- Risk: too many panes could become cramped on narrower terminals.
  - Mitigation: keep pane content concise and prioritize stable structure over decorative copy.
- Risk: additional plan-editing actions could become hard to discover.
  - Mitigation: show mode-specific key hints in pane headers, status strip, and detail messaging.
- Risk: focus management could become confusing with more interactive panes.
  - Mitigation: make focus treatment consistent and keep pane-switch shortcuts explicit.
- Risk: transition logic could feel brittle if implemented as a full re-render.
  - Mitigation: preserve shell structure and update pane content/title/state in place.

## Verification Strategy
- Add screen tests for visible draft-plan feedback and plan-editing flows.
- Add tests for promote/demote/remove/reorder behavior.
- Add tests for in-place confirm transition messaging and layout state changes.
- Add tests for richer wrap summaries and deterministic coaching feedback.
- Run targeted daily-workspace tests first, then the relevant unit suite, then the full `tests/unit` run if the change surface grows.

## Rollout Shape
Recommended implementation sequence:
1. Restructure the daily workspace layout and pane shells.
2. Add visible draft plan panes and same-screen edit actions.
3. Implement in-place confirm transition into `Today`.
4. Expand wrap content and deterministic coaching feedback.
5. Update docs and verify behavior with tests.

# Projects: GTD List and Proceed

## Summary

Flow’s **Projects** feature lets you review active projects and work through their next actions in line with GTD: each project is a multi-step outcome; you “proceed” by doing the suggested next action, then defining or doing the next one.

In the native macOS app, Projects is a first-class view in the sidebar. It is used for both review ("Do I have a next action for each?") and proceed work inside a native split-view layout.

## Capabilities

- **Project list (GTD review)**
  - See all active projects with a short next-action preview per line.
  - The native app shows project selection, detail, and related metadata in a desktop split-view layout.
  - Keyboard movement and selection follow the app’s native list behavior.

- **Project detail (proceed)**
  - List of active actions for one project with full task text, metadata, and supporting context.
  - Complete and defer actions are available from the native detail view:
    - `Waiting For` for external blockers
    - `Defer Until` for tickler-style resurface at a date/time
    - `Someday/Maybe` for low-commitment ideas
  - The list refreshes after each action; if no actions remain, Flow prompts you to define the next step.

- **Data and performance**
  - Projects and their actions are loaded through the app’s shared data layer so the UI remains responsive.
  - Detail content can load progressively without blocking the main window.

## Entry point

- Open **Projects** from the native app sidebar.

## GTD alignment

| GTD idea | How Flow supports it |
|----------|----------------------|
| Project list for review | Projects screen lists all active projects with next-action preview. |
| One next action per project | Shown in list and in detail; first task in the list is the suggested next action. |
| Proceed = do the next action | Project detail: complete or defer the selected action; list updates; next task becomes the new “next” or you add one. |
| Different defer intents | `Waiting For` maps to `status=waiting`; `Someday/Maybe` maps to `status=someday`; `Defer Until` keeps `status=active` and stores `meta_payload.defer_until`. |
| Weekly review | Review and Projects are adjacent native views, making project review part of the same desktop workflow. |

## Implementation notes

- **Engine**: `list_projects()`, `list_projects_with_actions()`, `get_project_next_action()`, `defer_item(mode=...)`, `is_deferred_until_active()`.  
- **DB**: `list_projects(status)` in `flow/database/sqlite.py`.  
- **Native app**: project presentation and selection live in `Sources/FlowMacApp/` and `Sources/FlowMacCore/`.

# Projects: GTD List and Proceed

## Summary

Flow’s **Projects** feature lets you review active projects and work through their next actions in line with GTD: each project is a multi-step outcome; you “proceed” by doing the suggested next action, then defining or doing the next one.

Projects are created in the **Process** funnel (Stage 2: Cluster), where the AI suggests groupings and you create a project and attach tasks. The Projects screen is for **review** (“Do I have a next action for each?”) and **proceed** (open a project and complete or defer actions).

## Capabilities

- **Project list (GTD review)**  
  - See all active projects with a short “next action” preview per line.  
  - Two-panel layout: left = project list, right = selected project’s name, **suggested next action** (full text + tags), and **task list** (all actions with the first marked as `[next]`).  
  - Navigate with j/k; Enter opens the project in the detail screen.

- **Project detail (proceed)**  
  - List of active actions for one project with full task text and tags in a side panel.  
  - **Complete (c)** marks the selected action done; **Defer (f)** sets it to waiting.  
  - List refreshes after each action; if no actions remain, a GTD-style reminder is shown.  
  - Esc returns to the project list.

- **Data and performance**  
  - Projects and their actions are loaded in one async call (`list_projects_with_actions`) so the UI stays responsive.  
  - Project detail loads actions in the background and shows a short loading state.

## Entry points

- **CLI**: `flow projects` — opens the TUI on the Projects screen.  
- **TUI**: From Inbox, Action, or Review, press **P** (or use **?** Help to see shortcuts) to open the Projects screen.

## GTD alignment

| GTD idea | How Flow supports it |
|----------|----------------------|
| Project list for review | Projects screen lists all active projects with next-action preview. |
| One next action per project | Shown in list and in detail; first task in the list is the suggested next action. |
| Proceed = do the next action | Project detail: complete or defer the selected action; list updates; next task becomes the new “next” or you add one. |
| Weekly review | Review screen can be used with Projects (e.g. “Review projects” then open Projects). |

## Implementation notes

- **Engine**: `list_projects()`, `list_projects_with_actions()`, `get_project_next_action()`, `defer_item()`.  
- **DB**: `list_projects(status)` in `flow/database/sqlite.py`.  
- **TUI**: `flow/tui/screens/projects/` — `ProjectsScreen` (list + detail panel), `ProjectDetailScreen` (proceed).  
- **Footer**: Cross-screen nav (a, i, r, P) is hidden from the footer but still works; **?** Help lists all shortcuts.

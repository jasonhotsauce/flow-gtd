export type AssistantToolEntity = "plan" | "project" | "task";
export type AssistantToolOperation = "create" | "read" | "update" | "delete";

export interface AssistantToolContract {
  entity: AssistantToolEntity;
  operation: AssistantToolOperation;
  toolName: string;
  description: string;
  confirmationRequired: boolean;
  readKind?: string;
  writeKind?: string;
  proposalActionType?: string;
}

export function createAssistantToolContracts(): AssistantToolContract[] {
  return [
    {
      entity: "plan",
      operation: "create",
      toolName: "save_daily_plan",
      description: "Create a daily plan from selected task ids.",
      confirmationRequired: true,
      writeKind: "save-daily-plan",
      proposalActionType: "save_daily_plan"
    },
    {
      entity: "plan",
      operation: "read",
      toolName: "read_daily_plan",
      description: "Read saved focus, bonus, candidate, and calendar-status context for a plan date.",
      confirmationRequired: false,
      readKind: "daily-plan"
    },
    {
      entity: "plan",
      operation: "update",
      toolName: "save_daily_plan",
      description: "Replace a daily plan with updated top and bonus task ids.",
      confirmationRequired: true,
      writeKind: "save-daily-plan",
      proposalActionType: "save_daily_plan"
    },
    {
      entity: "plan",
      operation: "delete",
      toolName: "delete_daily_plan",
      description: "Clear all saved entries for a plan date.",
      confirmationRequired: true,
      proposalActionType: "delete_daily_plan"
    },
    {
      entity: "project",
      operation: "create",
      toolName: "create_project",
      description: "Create a project outcome.",
      confirmationRequired: true,
      proposalActionType: "create_project"
    },
    {
      entity: "project",
      operation: "read",
      toolName: "read_projects",
      description: "Read active projects and their tasks from workspace context.",
      confirmationRequired: false,
      readKind: "workspace-snapshot"
    },
    {
      entity: "project",
      operation: "update",
      toolName: "update_project",
      description: "Update a project title or status.",
      confirmationRequired: true,
      proposalActionType: "update_project"
    },
    {
      entity: "project",
      operation: "delete",
      toolName: "delete_project",
      description: "Archive a project after confirmation.",
      confirmationRequired: true,
      proposalActionType: "delete_project"
    },
    {
      entity: "task",
      operation: "create",
      toolName: "create_task",
      description: "Create an inbox task or a project-linked next action.",
      confirmationRequired: true,
      writeKind: "capture",
      proposalActionType: "create_task"
    },
    {
      entity: "task",
      operation: "read",
      toolName: "read_tasks",
      description: "Read inbox, ready, planned, and project-linked tasks from workspace context.",
      confirmationRequired: false,
      readKind: "workspace-snapshot"
    },
    {
      entity: "task",
      operation: "update",
      toolName: "update_task",
      description: "Update task title, status, project, due date, or duration.",
      confirmationRequired: true,
      proposalActionType: "update_task"
    },
    {
      entity: "task",
      operation: "delete",
      toolName: "delete_task",
      description: "Archive a task after confirmation.",
      confirmationRequired: true,
      writeKind: "archive-task",
      proposalActionType: "delete_task"
    }
  ];
}

import type {
  AgentCapability,
  SpecialistKind,
  SpecialistStructuredOutput
} from "./contracts.js";

export interface SpecialistDefinition {
  kind: SpecialistKind;
  routeHints: string[];
  requiredCapabilities: AgentCapability[];
  allowedActionTypes: string[];
  fallbackSummary: string;
  validate(payload: SpecialistStructuredOutput): void;
}

function requireString(value: unknown, field: string): void {
  if (typeof value !== "string" || value.trim().length === 0) {
    throw new Error(`Expected non-empty string for ${field}.`);
  }
}

function requireStringArray(value: unknown, field: string): void {
  if (!Array.isArray(value) || value.some((entry) => typeof entry !== "string")) {
    throw new Error(`Expected string[] for ${field}.`);
  }
}

function requireArray(value: unknown, field: string): asserts value is unknown[] {
  if (!Array.isArray(value)) {
    throw new Error(`Expected array for ${field}.`);
  }
}

function validateBase(kind: SpecialistKind, payload: SpecialistStructuredOutput): void {
  if (payload.kind !== kind) {
    throw new Error(`Expected structured output kind ${kind}.`);
  }
  requireString(payload.summary, "summary");
  requireStringArray(payload.rationale, "rationale");
}

function validateAssistantOrchestrator(payload: SpecialistStructuredOutput): void {
  validateBase("assistant_orchestrator", payload);
}

function validateCaptureClarifier(payload: SpecialistStructuredOutput): void {
  validateBase("capture_clarifier", payload);
  requireArray(payload.clarifications, "clarifications");
}

function validateDailyPlanner(payload: SpecialistStructuredOutput): void {
  validateBase("daily_planner", payload);
  requireArray(payload.focusItems, "focusItems");
  if (payload.focusItems.length === 0) {
    throw new Error("daily_planner requires at least one focus item.");
  }
}

function validateWeeklyReviewer(payload: SpecialistStructuredOutput): void {
  validateBase("weekly_reviewer", payload);
  requireArray(payload.cleanupCandidates, "cleanupCandidates");
}

function validateProjectHealth(payload: SpecialistStructuredOutput): void {
  validateBase("project_health_analyst", payload);
  requireArray(payload.projects, "projects");
}

function validateMemoryCurator(payload: SpecialistStructuredOutput): void {
  validateBase("memory_curator", payload);
  requireArray(payload.memoryCandidates, "memoryCandidates");
}

export function createDefaultSpecialistRegistry(): Map<
  SpecialistKind,
  SpecialistDefinition
> {
  return new Map<SpecialistKind, SpecialistDefinition>([
    [
      "assistant_orchestrator",
      {
        kind: "assistant_orchestrator",
        routeHints: ["assistant", "assistant_orchestrator", "general"],
        requiredCapabilities: ["read_gtd_context"],
        allowedActionTypes: [],
        fallbackSummary: "General assistant routing fell back to a deterministic response.",
        validate: validateAssistantOrchestrator
      }
    ],
    [
      "capture_clarifier",
      {
        kind: "capture_clarifier",
        routeHints: ["capture", "clarify", "capture_clarifier"],
        requiredCapabilities: ["read_gtd_context", "propose_inbox_write"],
        allowedActionTypes: [
          "create_task",
          "edit_task",
          "clean_up_inbox",
          "reassign_project"
        ],
        fallbackSummary: "Capture clarification fell back to a deterministic response.",
        validate: validateCaptureClarifier
      }
    ],
    [
      "daily_planner",
      {
        kind: "daily_planner",
        routeHints: ["daily_plan", "daily_planner"],
        requiredCapabilities: ["read_gtd_context", "propose_planning_change"],
        allowedActionTypes: [
          "generate_daily_plan",
          "explain_daily_plan",
          "save_daily_plan",
          "delete_daily_plan",
          "create_project",
          "update_project",
          "delete_project",
          "create_task",
          "update_task",
          "delete_task",
          "edit_task"
        ],
        fallbackSummary: "Daily planning fell back to a deterministic response.",
        validate: validateDailyPlanner
      }
    ],
    [
      "weekly_reviewer",
      {
        kind: "weekly_reviewer",
        routeHints: ["review", "weekly_review", "weekly_reviewer"],
        requiredCapabilities: ["read_gtd_context", "propose_review_cleanup"],
        allowedActionTypes: [
          "clean_up_inbox",
          "start_weekly_review",
          "edit_task",
          "reassign_project"
        ],
        fallbackSummary: "Weekly review fell back to a deterministic response.",
        validate: validateWeeklyReviewer
      }
    ],
    [
      "project_health_analyst",
      {
        kind: "project_health_analyst",
        routeHints: ["project_health", "project_health_analyst"],
        requiredCapabilities: ["read_gtd_context", "propose_planning_change"],
        allowedActionTypes: ["create_task", "edit_task", "reassign_project", "generate_daily_plan"],
        fallbackSummary: "Project health analysis fell back to a deterministic response.",
        validate: validateProjectHealth
      }
    ],
    [
      "memory_curator",
      {
        kind: "memory_curator",
        routeHints: ["memory", "memory_curator"],
        requiredCapabilities: ["read_gtd_context", "propose_memory_write"],
        allowedActionTypes: ["save_memory"],
        fallbackSummary: "Memory curation fell back to a deterministic response.",
        validate: validateMemoryCurator
      }
    ]
  ]);
}

export function resolveSpecialist(
  registry: Map<SpecialistKind, SpecialistDefinition>,
  routeHint?: string,
  specialist?: SpecialistKind
): SpecialistDefinition {
  if (specialist) {
    const explicit = registry.get(specialist);
    if (!explicit) {
      throw new Error(`Unknown specialist ${specialist}.`);
    }
    return explicit;
  }

  const normalizedRouteHint = (routeHint ?? "assistant").trim().toLowerCase();
  for (const definition of registry.values()) {
    if (definition.routeHints.includes(normalizedRouteHint)) {
      return definition;
    }
  }

  return registry.get("assistant_orchestrator")!;
}

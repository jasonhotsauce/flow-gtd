import { bootstrapFlowDatabase } from "../db/database.js";
import { FlowReadRepository } from "../db/repositories/read-repository.js";

export type SidecarReadKind =
  | "workspace-snapshot"
  | "assistant-turns"
  | "assistant-sessions"
  | "assistant-messages"
  | "memory-records"
  | "daily-plan"
  | "weekly-review"
  | "notification-policy";

export interface SidecarReadOptions {
  kind: SidecarReadKind;
  planDate?: string;
  limit?: number;
  sessionID?: string;
  query?: string;
  includeDisabled?: boolean;
  referenceDate?: string;
}

export function executeRead(options: SidecarReadOptions): unknown {
  const owner = bootstrapFlowDatabase(
    process.env.FLOW_DB_PATH || undefined
  );
  try {
    const repository = new FlowReadRepository(owner.connection());
    switch (options.kind) {
      case "workspace-snapshot":
        return repository.loadWorkspaceSnapshot();
      case "assistant-turns":
        return repository.loadAssistantTurns(options.limit ?? 30);
      case "assistant-sessions":
        return repository.loadAssistantSessions(options.limit ?? 30);
      case "assistant-messages":
        if (!options.sessionID) {
          throw new Error("Missing --session-id for assistant-messages read.");
        }
        return repository.loadAssistantMessages(options.sessionID, options.limit ?? 30);
      case "memory-records":
        return repository.loadMemoryRecords(
          options.query,
          options.includeDisabled ?? true
        );
      case "daily-plan":
        if (!options.planDate) {
          throw new Error("Missing --plan-date for daily-plan read.");
        }
        return repository.loadDailyPlanState(options.planDate);
      case "weekly-review":
        return repository.loadWeeklyReviewPackage(
          options.referenceDate ? new Date(options.referenceDate) : new Date()
        );
      case "notification-policy":
        return repository.loadNotificationPolicy();
    }
  } finally {
    owner.close();
  }
}

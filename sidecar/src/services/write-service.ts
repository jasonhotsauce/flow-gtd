import { bootstrapFlowDatabase } from "../db/database.js";
import {
  FlowWriteRepository,
  type ClarifyDestination
} from "../db/repositories/write-repository.js";
import { AssistantSessionMessageService } from "./assistant-session-message-service.js";

export type SidecarWriteKind =
  | "capture"
  | "clarify-capture"
  | "reject-capture"
  | "mark-task-done"
  | "archive-task"
  | "create-session"
  | "send-message"
  | "confirm-message-proposal"
  | "dismiss-message-proposal"
  | "undo-last-mutation"
  | "create-memory-record"
  | "update-memory-record"
  | "set-memory-record-enabled"
  | "delete-memory-record"
  | "save-daily-plan"
  | "apply-weekly-review-actions"
  | "update-notification-permission";

export interface SidecarWriteOptions {
  kind: SidecarWriteKind;
  payload: Record<string, unknown>;
}

export async function executeWrite(options: SidecarWriteOptions): Promise<unknown> {
  const owner = bootstrapFlowDatabase(process.env.FLOW_DB_PATH || undefined);
  try {
    const repository = new FlowWriteRepository(owner.connection());
    const assistantRepository = new AssistantSessionMessageService(owner.connection());
    switch (options.kind) {
      case "create-session":
        return assistantRepository.createSession(String(options.payload.title ?? ""));
      case "send-message":
        return await assistantRepository.sendMessage(
          String(options.payload.sessionID ?? ""),
          String(options.payload.prompt ?? ""),
          String(options.payload.planDate ?? "")
        );
      case "confirm-message-proposal":
        return {
          message: assistantRepository.confirmMessage(
            String(options.payload.messageID ?? "")
          )
        };
      case "dismiss-message-proposal":
        assistantRepository.dismissMessage(
          String(options.payload.messageID ?? "")
        );
        return { ok: true };
      case "undo-last-mutation":
        return { message: assistantRepository.undoLastMutation() ?? null };
      case "capture":
        return repository.capture(String(options.payload.title ?? ""));
      case "clarify-capture":
        if (
          options.payload.destination !== "task" &&
          options.payload.destination !== "project"
        ) {
          throw new Error("Unsupported clarify destination.");
        }
        repository.clarifyCapture(
          String(options.payload.id ?? ""),
          String(options.payload.title ?? ""),
          options.payload.destination as ClarifyDestination,
          typeof options.payload.projectTitle === "string"
            ? options.payload.projectTitle
            : undefined
        );
        return { ok: true };
      case "reject-capture":
        repository.rejectCapture(String(options.payload.id ?? ""));
        return { ok: true };
      case "mark-task-done":
        repository.markTaskDone(String(options.payload.id ?? ""));
        return { ok: true };
      case "archive-task":
        repository.archiveTask(String(options.payload.id ?? ""));
        return { ok: true };
      case "create-memory-record":
        return repository.createMemoryRecord(
          String(options.payload.kind ?? ""),
          String(options.payload.scope ?? ""),
          String(options.payload.value ?? ""),
          String(options.payload.source ?? ""),
          Number(options.payload.confidence ?? 0),
          typeof options.payload.scopeRef === "string"
            ? options.payload.scopeRef
            : undefined
        );
      case "update-memory-record":
        repository.updateMemoryRecord(
          String(options.payload.id ?? ""),
          String(options.payload.value ?? "")
        );
        return { ok: true };
      case "set-memory-record-enabled":
        repository.setMemoryRecordEnabled(
          String(options.payload.id ?? ""),
          Boolean(options.payload.enabled)
        );
        return { ok: true };
      case "delete-memory-record":
        repository.deleteMemoryRecord(String(options.payload.id ?? ""));
        return { ok: true };
      case "save-daily-plan":
        repository.saveDailyPlan(
          String(options.payload.planDate ?? ""),
          Array.isArray(options.payload.topItemIDs)
            ? options.payload.topItemIDs.map(String)
            : [],
          Array.isArray(options.payload.bonusItemIDs)
            ? options.payload.bonusItemIDs.map(String)
            : []
        );
        return { ok: true };
      case "apply-weekly-review-actions":
        repository.applyWeeklyReviewActions(
          Array.isArray(options.payload.actionIDs)
            ? options.payload.actionIDs.map(String)
            : [],
          typeof options.payload.referenceDate === "string"
            ? new Date(options.payload.referenceDate)
            : new Date()
        );
        return { ok: true };
      case "update-notification-permission":
        repository.updateNotificationPermissionStatus(
          String(options.payload.status ?? "")
        );
        return { ok: true };
    }
  } finally {
    owner.close();
  }
}

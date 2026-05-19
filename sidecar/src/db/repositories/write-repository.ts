import type { DatabaseSync } from "node:sqlite";
import type {
  FlowMemoryRecord,
  FlowReviewCleanupAction,
  FlowTask
} from "../../domain/read-models.js";
import type { MutationProposal } from "../../domain/mutations.js";
import { FlowReadRepository } from "./read-repository.js";
import { MutationService } from "../../services/mutations/service.js";

export type ClarifyDestination = "task" | "project";

function nowIso(): string {
  return new Date().toISOString();
}

function trimRequired(value: string, message: string): string {
  const trimmed = value.trim();
  if (!trimmed) {
    throw new Error(message);
  }
  return trimmed;
}

export class FlowWriteRepository {
  private readonly readRepository: FlowReadRepository;
  private readonly mutationService: MutationService;

  constructor(private readonly db: DatabaseSync) {
    this.readRepository = new FlowReadRepository(db);
    this.mutationService = new MutationService(db);
  }

  capture(title: string): FlowTask {
    const trimmed = trimRequired(title, "Capture text cannot be empty.");
    const id = crypto.randomUUID();
    const now = nowIso();

    this.executeMutation(
      "capture",
      {
        actionType: "capture",
        targetTable: "items",
        targetID: id,
        previewText: trimmed,
        rationale: "Capture text into the inbox.",
        confidence: 1,
        requiresConfirmation: false,
        verificationStatus: "validated",
        idempotencyKey: `capture:${id}`,
        payload: { title: trimmed }
      },
      () => {
        this.db
          .prepare(
            `
              INSERT INTO items (
                id, type, title, status, context_tags, parent_id, created_at,
                due_date, meta_payload, original_ek_id, estimated_duration, updated_at
              ) VALUES (?, 'inbox', ?, 'active', '[]', NULL, ?, NULL, '{}', NULL, NULL, ?)
            `
          )
          .run(id, trimmed, now, now);
        this.db
          .prepare(
            `
              INSERT INTO raw_captures (id, source, raw_text, created_at)
              VALUES (?, 'manual_capture', ?, ?)
            `
          )
          .run(id, trimmed, now);
        this.db
          .prepare(
            `
              INSERT INTO inbox_items (
                id, raw_capture_id, origin_type, inbox_state, source_ref, imported_at,
                task_id, clarified_task_id, clarified_project_id, clarified_at, created_at, updated_at
              ) VALUES (?, ?, 'manual_capture', 'needs_clarification', NULL, NULL, NULL, NULL, NULL, NULL, ?, ?)
            `
          )
          .run(id, id, now, now);
      }
    );

    return {
      id,
      title: trimmed,
      summary: "Captured in the TypeScript sidecar.",
      status: "active",
      source: "capture",
      projectName: undefined,
      dueLabel: undefined,
      tags: [],
      estimatedMinutes: undefined,
      isFlagged: false,
      lastUpdatedLabel: "Captured just now"
    };
  }

  clarifyCapture(
    id: string,
    title: string,
    destination: ClarifyDestination,
    projectTitle?: string
  ): void {
    const trimmedTitle = trimRequired(title, "Clarified title cannot be empty.");
    const now = nowIso();
    const createdAt = this.requireExistingCreatedAt(id);

    this.executeMutation(
      "capture_clarify",
      {
        actionType: "clarify_accept",
        targetTable: destination === "task" ? "tasks" : "projects",
        targetID: id,
        previewText: trimmedTitle,
        rationale: `Clarify capture into a ${destination}.`,
        confidence: 1,
        requiresConfirmation: false,
        verificationStatus: "validated",
        idempotencyKey: `clarify:${id}:${destination}:${trimmedTitle}:${projectTitle ?? ""}`,
        payload: {
          destinationType: destination,
          title: trimmedTitle,
          projectTitle: projectTitle?.trim() ?? ""
        }
      },
      () => {
        if (destination === "task") {
          const linkedProjectID = this.findOrCreateProject(projectTitle, now);
          this.requireChanges(
            this.db
              .prepare(
                `
                  UPDATE items
                  SET type = 'action', title = ?, status = 'active', parent_id = ?, updated_at = ?
                  WHERE id = ?
                `
              )
              .run(trimmedTitle, linkedProjectID ?? null, now, id),
            `Capture ${id} does not exist.`
          );
          this.db
            .prepare(
              `
                INSERT INTO tasks (
                  id, title, status, project_id, source_inbox_item_id,
                  time_sensitivity, effort_band, created_at, updated_at
                ) VALUES (?, ?, 'active', ?, ?, 'flexible', 'medium', ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                  title = excluded.title,
                  status = excluded.status,
                  project_id = excluded.project_id,
                  source_inbox_item_id = excluded.source_inbox_item_id,
                  updated_at = excluded.updated_at
              `
            )
            .run(id, trimmedTitle, linkedProjectID ?? null, id, createdAt, now);
          this.requireChanges(
            this.db
              .prepare(
                `
                  UPDATE inbox_items
                  SET inbox_state = 'clarified',
                      task_id = ?,
                      clarified_task_id = ?,
                      clarified_project_id = ?,
                      clarified_at = ?,
                      updated_at = ?
                  WHERE id = ?
                `
              )
              .run(id, id, linkedProjectID ?? null, now, now, id),
            `Inbox item ${id} does not exist.`
          );
        } else {
          this.db.prepare("DELETE FROM tasks WHERE id = ?").run(id);
          this.requireChanges(
            this.db
              .prepare(
                `
                  UPDATE items
                  SET type = 'project', title = ?, status = 'active', parent_id = NULL, updated_at = ?
                  WHERE id = ?
                `
              )
              .run(trimmedTitle, now, id),
            `Capture ${id} does not exist.`
          );
          this.db
            .prepare(
              `
                INSERT INTO projects (id, name, status, created_at, updated_at)
                VALUES (?, ?, 'active', ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                  name = excluded.name,
                  status = excluded.status,
                  updated_at = excluded.updated_at
              `
            )
            .run(id, trimmedTitle, createdAt, now);
          this.requireChanges(
            this.db
              .prepare(
                `
                  UPDATE inbox_items
                  SET inbox_state = 'converted_to_project',
                      task_id = NULL,
                      clarified_task_id = NULL,
                      clarified_project_id = ?,
                      clarified_at = ?,
                      updated_at = ?
                  WHERE id = ?
                `
              )
              .run(id, now, now, id),
            `Inbox item ${id} does not exist.`
          );
        }
      }
    );
  }

  rejectCapture(id: string): void {
    const now = nowIso();
    this.executeMutation(
      "capture_clarify",
      {
        actionType: "clarify_reject",
        targetTable: "inbox_items",
        targetID: id,
        previewText: `Reject capture ${id}`,
        rationale: "Archive a capture that should not become work.",
        confidence: 1,
        requiresConfirmation: false,
        verificationStatus: "validated",
        idempotencyKey: `clarify-reject:${id}`,
        payload: { inboxItemID: id }
      },
      () => {
        this.updateItemStatus(id, "archived", now);
        this.requireChanges(
          this.db
            .prepare(
              `
                UPDATE inbox_items
                SET inbox_state = 'rejected',
                    task_id = NULL,
                    clarified_task_id = NULL,
                    clarified_project_id = NULL,
                    clarified_at = ?,
                    updated_at = ?
                WHERE id = ?
              `
            )
            .run(now, now, id),
          `Inbox item ${id} does not exist.`
        );
      }
    );
  }

  markTaskDone(id: string): void {
    this.mutateItemStatus(id, "done", "mark_done", "Mark task done.");
  }

  archiveTask(id: string): void {
    this.mutateItemStatus(id, "archived", "archive_task", "Archive task.");
  }

  createMemoryRecord(
    kind: string,
    scope: string,
    value: string,
    source: string,
    confidence: number,
    scopeRef?: string
  ): FlowMemoryRecord {
    const trimmedValue = trimRequired(value, "Memory value cannot be empty.");
    const id = crypto.randomUUID();
    const now = nowIso();

    this.executeMutation(
      "memory",
      {
        actionType: "memory_create",
        targetTable: "memory_entries",
        targetID: id,
        previewText: trimmedValue,
        rationale: "Persist explicit product memory.",
        confidence: 1,
        requiresConfirmation: false,
        verificationStatus: "validated",
        idempotencyKey: `memory-create:${id}`,
        payload: {
          kind,
          scope,
          scopeRef: scopeRef ?? "",
          value: trimmedValue,
          source,
          confidence: String(confidence)
        }
      },
      () => {
        this.db
          .prepare(
            `
              INSERT INTO memory_entries (
                id, kind, scope, scope_ref, value, source, confidence, enabled,
                created_at, updated_at, last_confirmed_at
              ) VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?)
            `
          )
          .run(id, kind, scope, scopeRef ?? null, trimmedValue, source, confidence, now, now, now);
      }
    );

    return this.mustLoadMemoryRecord(id);
  }

  updateMemoryRecord(id: string, value: string): void {
    const trimmedValue = trimRequired(value, "Memory value cannot be empty.");
    const now = nowIso();
    this.executeMutation(
      "memory",
      {
        actionType: "memory_update",
        targetTable: "memory_entries",
        targetID: id,
        previewText: trimmedValue,
        rationale: "Update a memory entry.",
        confidence: 1,
        requiresConfirmation: false,
        verificationStatus: "validated",
        idempotencyKey: `memory-update:${id}:${trimmedValue}`,
        payload: { value: trimmedValue }
      },
      () => {
        this.requireChanges(
          this.db
            .prepare("UPDATE memory_entries SET value = ?, updated_at = ? WHERE id = ?")
            .run(trimmedValue, now, id),
          `Memory record ${id} does not exist.`
        );
      }
    );
  }

  setMemoryRecordEnabled(id: string, enabled: boolean): void {
    const now = nowIso();
    this.executeMutation(
      "memory",
      {
        actionType: "memory_set_enabled",
        targetTable: "memory_entries",
        targetID: id,
        previewText: enabled ? "Enable memory entry" : "Disable memory entry",
        rationale: "Toggle memory visibility.",
        confidence: 1,
        requiresConfirmation: false,
        verificationStatus: "validated",
        idempotencyKey: `memory-enabled:${id}:${enabled ? "1" : "0"}`,
        payload: { enabled: enabled ? "true" : "false" }
      },
      () => {
        this.requireChanges(
          this.db
            .prepare("UPDATE memory_entries SET enabled = ?, updated_at = ? WHERE id = ?")
            .run(enabled ? 1 : 0, now, id),
          `Memory record ${id} does not exist.`
        );
      }
    );
  }

  deleteMemoryRecord(id: string): void {
    this.executeMutation(
      "memory",
      {
        actionType: "memory_delete",
        targetTable: "memory_entries",
        targetID: id,
        previewText: `Delete memory ${id}`,
        rationale: "Remove a memory entry.",
        confidence: 1,
        requiresConfirmation: false,
        verificationStatus: "validated",
        idempotencyKey: `memory-delete:${id}`,
        payload: { id }
      },
      () => {
        this.requireChanges(
          this.db.prepare("DELETE FROM memory_entries WHERE id = ?").run(id),
          `Memory record ${id} does not exist.`
        );
      }
    );
  }

  saveDailyPlan(
    planDate: string,
    topItemIDs: string[],
    bonusItemIDs: string[]
  ): void {
    this.executeMutation(
      "daily_plan",
      {
        actionType: "daily_plan_save",
        targetTable: "daily_plan_entries",
        targetID: planDate,
        previewText: `Save daily plan for ${planDate}`,
        rationale: "Persist the accepted top and bonus items.",
        confidence: 1,
        requiresConfirmation: false,
        verificationStatus: "validated",
        idempotencyKey: `daily-plan:${planDate}:${topItemIDs.join(",")}:${bonusItemIDs.join(",")}`,
        payload: {
          planDate,
          topItemIDs: JSON.stringify(topItemIDs),
          bonusItemIDs: JSON.stringify(bonusItemIDs)
        }
      },
      () => {
        const now = nowIso();
        this.db.prepare("DELETE FROM daily_plan_entries WHERE plan_date = ?").run(planDate);
        const insert = this.db.prepare(
          `
            INSERT INTO daily_plan_entries (plan_date, item_id, bucket, position, created_at)
            VALUES (?, ?, ?, ?, ?)
          `
        );
        topItemIDs.forEach((itemID, index) => {
          insert.run(planDate, itemID, "top", index + 1, now);
        });
        bonusItemIDs.forEach((itemID, index) => {
          insert.run(planDate, itemID, "bonus", index + 1, now);
        });
      }
    );
  }

  applyWeeklyReviewActions(
    actionIDs: string[],
    referenceDate: Date
  ): void {
    const requested = new Set(actionIDs);
    if (requested.size === 0) {
      return;
    }

    const weeklyReview = this.readRepository.loadWeeklyReviewPackage(referenceDate);
    const actions = weeklyReview.cleanupActions.filter((action) => requested.has(action.id));
    if (actions.length === 0) {
      throw new Error("No weekly review actions matched the requested IDs.");
    }

    this.executeMutation(
      "weekly_review",
      {
        actionType: "weekly_review_apply",
        targetTable: "items",
        targetID: referenceDate.toISOString(),
        previewText: `Apply ${actions.length} weekly review action(s)`,
        rationale: "Apply the selected weekly review cleanup actions atomically.",
        confidence: 1,
        requiresConfirmation: false,
        verificationStatus: "validated",
        idempotencyKey: `weekly-review-apply:${[...requested].sort().join(",")}`,
        payload: {
          actionIDs: JSON.stringify([...requested].sort()),
          referenceDate: referenceDate.toISOString()
        }
      },
      () => {
        for (const action of actions) {
          for (const targetID of action.targetIDs) {
            this.applyWeeklyReviewAction(action, targetID);
          }
        }
      }
    );
  }

  updateNotificationPermissionStatus(status: string): void {
    const allowed = new Set([
      "not_determined",
      "denied",
      "authorized",
      "provisional",
      "unavailable"
    ]);
    if (!allowed.has(status)) {
      throw new Error("Unsupported notification permission status.");
    }

    const now = nowIso();
    this.executeMutation(
      "notification_policy",
      {
        actionType: "notification_permission_update",
        targetTable: "notification_policy",
        targetID: "flow",
        previewText: status,
        rationale: "Persist notification permission state from the native shell.",
        confidence: 1,
        requiresConfirmation: false,
        verificationStatus: "validated",
        idempotencyKey: `notification-policy:${status}`,
        payload: { status }
      },
      () => {
        this.db
          .prepare(
            `
              INSERT INTO notification_policy (id, permission_status, updated_at)
              VALUES ('flow', ?, ?)
              ON CONFLICT(id) DO UPDATE SET
                permission_status = excluded.permission_status,
                updated_at = excluded.updated_at
            `
          )
          .run(status, now);
      }
    );
  }

  private applyWeeklyReviewAction(
    action: FlowReviewCleanupAction,
    targetID: string
  ): void {
    const now = nowIso();
    if (action.kind === "archive_stale_item") {
      this.updateItemStatus(targetID, "archived", now);
    }
  }

  private mutateItemStatus(
    id: string,
    status: "done" | "archived",
    actionType: string,
    rationale: string
  ): void {
    const now = nowIso();
    this.executeMutation(
      "task_state",
      {
        actionType,
        targetTable: "items",
        targetID: id,
        previewText: `${status}:${id}`,
        rationale,
        confidence: 1,
        requiresConfirmation: false,
        verificationStatus: "validated",
        idempotencyKey: `${actionType}:${id}`,
        payload: { status }
      },
      () => {
        this.updateItemStatus(id, status, now);
      }
    );
  }

  private updateItemStatus(
    id: string,
    status: string,
    updatedAt: string
  ): void {
    const itemResult = this.db
      .prepare("UPDATE items SET status = ?, updated_at = ? WHERE id = ?")
      .run(status, updatedAt, id);
    const taskResult = this.db
      .prepare("UPDATE tasks SET status = ?, updated_at = ? WHERE id = ?")
      .run(status, updatedAt, id);
    const projectResult = this.db
      .prepare("UPDATE projects SET status = ?, updated_at = ? WHERE id = ?")
      .run(status, updatedAt, id);

    const totalChanges =
      this.changeCount(itemResult) +
      this.changeCount(taskResult) +
      this.changeCount(projectResult);
    if (totalChanges === 0) {
      throw new Error(`Item ${id} does not exist.`);
    }
  }

  private findOrCreateProject(
    projectTitle: string | undefined,
    now: string
  ): string | undefined {
    const trimmed = projectTitle?.trim();
    if (!trimmed) {
      return undefined;
    }

    const existing = this.db
      .prepare(
        `
          SELECT id
          FROM items
          WHERE type = 'project' AND LOWER(title) = LOWER(?)
          ORDER BY updated_at DESC, created_at DESC
          LIMIT 1
        `
      )
      .get(trimmed) as { id?: string } | undefined;
    if (existing?.id) {
      this.db
        .prepare("UPDATE items SET updated_at = ? WHERE id = ?")
        .run(now, existing.id);
      return existing.id;
    }

    const id = crypto.randomUUID();
    this.db
      .prepare(
        `
          INSERT INTO items (
            id, type, title, status, context_tags, parent_id, created_at,
            due_date, meta_payload, original_ek_id, estimated_duration, updated_at
          ) VALUES (?, 'project', ?, 'active', '[]', NULL, ?, NULL, '{}', NULL, NULL, ?)
        `
      )
      .run(id, trimmed, now, now);
    this.db
      .prepare(
        `
          INSERT INTO projects (id, name, status, created_at, updated_at)
          VALUES (?, ?, 'active', ?, ?)
        `
      )
      .run(id, trimmed, now, now);
    return id;
  }

  private requireExistingCreatedAt(id: string): string {
    const row = this.db
      .prepare("SELECT created_at FROM items WHERE id = ? LIMIT 1")
      .get(id) as { created_at?: string | null } | undefined;
    if (!row?.created_at) {
      throw new Error(`Item ${id} does not exist.`);
    }
    return row.created_at;
  }

  private mustLoadMemoryRecord(id: string): FlowMemoryRecord {
    const record = this.readRepository
      .loadMemoryRecords(undefined, true)
      .find((entry) => entry.id === id);
    if (!record) {
      throw new Error(`Memory record ${id} was not persisted.`);
    }
    return record;
  }

  private executeMutation(
    source: string,
    proposal: MutationProposal,
    apply: () => void
  ): void {
    this.mutationService.executeProposal(source, proposal, () => apply());
  }

  private changeCount(result: unknown): number {
    const changes = (result as { changes?: number | bigint }).changes;
    if (typeof changes === "bigint") {
      return Number(changes);
    }
    return typeof changes === "number" ? changes : 0;
  }

  private requireChanges(result: unknown, message: string): void {
    if (this.changeCount(result) === 0) {
      throw new Error(message);
    }
  }
}

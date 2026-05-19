import { describe, expect, it } from "vitest";
import { mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { bootstrapFlowDatabase } from "../src/db/database.js";
import { MutationService } from "../src/services/mutations/service.js";

function withMutationService(
  fn: (service: MutationService, db: ReturnType<ReturnType<typeof bootstrapFlowDatabase>["connection"]>) => void
): void {
  const directory = mkdtempSync(join(tmpdir(), "flow-sidecar-mutations-"));
  const owner = bootstrapFlowDatabase(join(directory, "flow.sqlite"));
  const db = owner.connection();
  const service = new MutationService(db);
  try {
    fn(service, db);
  } finally {
    owner.close();
    rmSync(directory, { recursive: true, force: true });
  }
}

describe("MutationService", () => {
  it("persists mutation batches and audit records when execution succeeds", () => {
    withMutationService((service, db) => {
      db.prepare(
        `
          INSERT INTO items (
            id, type, title, status, context_tags, parent_id, created_at, due_date,
            meta_payload, original_ek_id, estimated_duration, updated_at
          ) VALUES ('task-1', 'action', 'Write tests', 'active', '[]', NULL, ?, NULL, '{}', NULL, 30, ?)
        `
      ).run("2026-05-02T10:00:00.000Z", "2026-05-02T10:00:00.000Z");

      const result = service.executeProposal(
        "assistant",
        {
          actionType: "update_status",
          targetTable: "items",
          targetID: "task-1",
          previewText: "Mark task-1 done",
          rationale: "User confirmed completion.",
          confidence: 0.98,
          requiresConfirmation: false,
          verificationStatus: "validated",
          idempotencyKey: "assistant:update_status:task-1",
          payload: {
            nextStatus: "done"
          }
        },
        () => {
          db.prepare("UPDATE items SET status = 'done' WHERE id = 'task-1'").run();
        }
      );

      expect(result.executed).toBe(true);
      const batchCount = db
        .prepare("SELECT COUNT(*) AS count FROM mutation_batches")
        .get() as { count: number };
      const record = db
        .prepare(
          "SELECT action, target_id, payload_json FROM mutation_records LIMIT 1"
        )
        .get() as {
        action: string;
        target_id: string;
        payload_json: string;
      };
      const item = db
        .prepare("SELECT status FROM items WHERE id = 'task-1'")
        .get() as { status: string };

      expect(batchCount.count).toBe(1);
      expect(record.action).toBe("update_status");
      expect(record.target_id).toBe("task-1");
      expect(record.payload_json).toContain("\"verificationStatus\":\"validated\"");
      expect(item.status).toBe("done");
    });
  });

  it("rolls back both business writes and audit rows when execution fails", () => {
    withMutationService((service, db) => {
      db.prepare(
        `
          INSERT INTO items (
            id, type, title, status, context_tags, parent_id, created_at, due_date,
            meta_payload, original_ek_id, estimated_duration, updated_at
          ) VALUES ('task-2', 'action', 'Broken update', 'active', '[]', NULL, ?, NULL, '{}', NULL, 30, ?)
        `
      ).run("2026-05-02T10:00:00.000Z", "2026-05-02T10:00:00.000Z");

      expect(() =>
        service.executeProposal(
          "assistant",
          {
            actionType: "update_status",
            targetTable: "items",
            targetID: "task-2",
            previewText: "Mark task-2 done",
            rationale: "Rollback test.",
            confidence: 0.75,
            requiresConfirmation: true,
            verificationStatus: "draft",
            payload: {
              nextStatus: "done"
            }
          },
          () => {
            db.prepare("UPDATE items SET status = 'done' WHERE id = 'task-2'").run();
            throw new Error("boom");
          }
        )
      ).toThrow("boom");

      const batchCount = db
        .prepare("SELECT COUNT(*) AS count FROM mutation_batches")
        .get() as { count: number };
      const recordCount = db
        .prepare("SELECT COUNT(*) AS count FROM mutation_records")
        .get() as { count: number };
      const item = db
        .prepare("SELECT status FROM items WHERE id = 'task-2'")
        .get() as { status: string };

      expect(batchCount.count).toBe(0);
      expect(recordCount.count).toBe(0);
      expect(item.status).toBe("active");
    });
  });

  it("skips duplicate execution for the same idempotency key", () => {
    withMutationService((service, db) => {
      db.prepare(
        `
          INSERT INTO items (
            id, type, title, status, context_tags, parent_id, created_at, due_date,
            meta_payload, original_ek_id, estimated_duration, updated_at
          ) VALUES ('task-3', 'action', 'Idempotent update', 'active', '[]', NULL, ?, NULL, '{}', NULL, 30, ?)
        `
      ).run("2026-05-02T10:00:00.000Z", "2026-05-02T10:00:00.000Z");

      const proposal = {
        actionType: "update_status",
        targetTable: "items",
        targetID: "task-3",
        previewText: "Mark task-3 done",
        rationale: "Avoid duplicate replay.",
        confidence: 0.82,
        requiresConfirmation: false,
        verificationStatus: "validated" as const,
        idempotencyKey: "assistant:update_status:task-3",
        payload: {
          nextStatus: "done"
        }
      };

      const first = service.executeProposal("assistant", proposal, () => {
        db.prepare("UPDATE items SET status = 'done' WHERE id = 'task-3'").run();
      });
      const second = service.executeProposal("assistant", proposal, () => {
        db.prepare("UPDATE items SET status = 'archived' WHERE id = 'task-3'").run();
      });

      const batchCount = db
        .prepare("SELECT COUNT(*) AS count FROM mutation_batches")
        .get() as { count: number };
      const recordCount = db
        .prepare("SELECT COUNT(*) AS count FROM mutation_records")
        .get() as { count: number };
      const item = db
        .prepare("SELECT status FROM items WHERE id = 'task-3'")
        .get() as { status: string };

      expect(first.executed).toBe(true);
      expect(second.executed).toBe(false);
      expect(second.skippedReason).toBe("idempotent_replay");
      expect(batchCount.count).toBe(1);
      expect(recordCount.count).toBe(1);
      expect(item.status).toBe("done");
    });
  });

  it("treats changed presentation metadata as the same replay when idempotency key matches", () => {
    withMutationService((service, db) => {
      db.prepare(
        `
          INSERT INTO items (
            id, type, title, status, context_tags, parent_id, created_at, due_date,
            meta_payload, original_ek_id, estimated_duration, updated_at
          ) VALUES ('task-4', 'action', 'Replay key', 'active', '[]', NULL, ?, NULL, '{}', NULL, 30, ?)
        `
      ).run("2026-05-02T10:00:00.000Z", "2026-05-02T10:00:00.000Z");

      const first = service.executeProposal(
        "assistant",
        {
          actionType: "update_status",
          targetTable: "items",
          targetID: "task-4",
          previewText: "Mark task-4 done",
          rationale: "first presentation copy",
          confidence: 0.82,
          requiresConfirmation: false,
          verificationStatus: "validated",
          idempotencyKey: "assistant:update_status:task-4",
          payload: {
            nextStatus: "done"
          }
        },
        () => {
          db.prepare("UPDATE items SET status = 'done' WHERE id = 'task-4'").run();
        }
      );
      const second = service.executeProposal(
        "assistant",
        {
          actionType: "update_status",
          targetTable: "items",
          targetID: "task-4",
          previewText: "Mark task-4 done with different copy",
          rationale: "second presentation copy",
          confidence: 0.82,
          requiresConfirmation: false,
          verificationStatus: "validated",
          idempotencyKey: "assistant:update_status:task-4",
          payload: {
            nextStatus: "done"
          }
        },
        () => {
          db.prepare("UPDATE items SET status = 'archived' WHERE id = 'task-4'").run();
        }
      );

      const item = db
        .prepare("SELECT status FROM items WHERE id = 'task-4'")
        .get() as { status: string };

      expect(first.executed).toBe(true);
      expect(second.executed).toBe(false);
      expect(second.skippedReason).toBe("idempotent_replay");
      expect(item.status).toBe("done");
    });
  });
});

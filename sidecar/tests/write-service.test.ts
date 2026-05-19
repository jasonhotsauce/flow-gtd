import { describe, expect, it } from "vitest";
import { mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { bootstrapFlowDatabase } from "../src/db/database.js";
import { FlowReadRepository } from "../src/db/repositories/read-repository.js";
import { executeWrite } from "../src/services/write-service.js";

async function withDatabase(
  test: (dbPath: string, readRepository: FlowReadRepository) => Promise<void> | void
): Promise<void> {
  const directory = mkdtempSync(join(tmpdir(), "flow-sidecar-write-"));
  const dbPath = join(directory, "flow.sqlite");
  const owner = bootstrapFlowDatabase(dbPath);
  const readRepository = new FlowReadRepository(owner.connection());
  try {
    await test(dbPath, readRepository);
  } finally {
    owner.close();
    rmSync(directory, { recursive: true, force: true });
  }
}

async function withFlowDBPath<T>(dbPath: string, fn: () => T | Promise<T>): Promise<T> {
  const previous = process.env.FLOW_DB_PATH;
  process.env.FLOW_DB_PATH = dbPath;
  try {
    return await fn();
  } finally {
    if (previous === undefined) {
      delete process.env.FLOW_DB_PATH;
    } else {
      process.env.FLOW_DB_PATH = previous;
    }
  }
}

describe("executeWrite", () => {
  it("captures, clarifies, saves a daily plan, and updates task status", async () => {
    await withDatabase(async (dbPath, readRepository) => {
      const capture = (await withFlowDBPath(dbPath, () =>
        executeWrite({
          kind: "capture",
          payload: { title: "Draft the sidecar write rollout" }
        })
      )) as { id: string; status: string; title: string };

      expect(capture.status).toBe("active");

      await withFlowDBPath(dbPath, () =>
        executeWrite({
          kind: "clarify-capture",
          payload: {
            id: capture.id,
            title: "Draft the sidecar write rollout plan",
            destination: "task",
            projectTitle: "TypeScript Rewrite"
          }
        })
      );

      let snapshot = readRepository.loadWorkspaceSnapshot();
      const project = snapshot.projects.find(
        (entry) => entry.title === "TypeScript Rewrite"
      );
      expect(project).toBeTruthy();
      expect(project?.tasks.map((task) => task.id)).toContain(capture.id);

      await withFlowDBPath(dbPath, () =>
        executeWrite({
          kind: "save-daily-plan",
          payload: {
            planDate: "2026-05-02",
            topItemIDs: [capture.id],
            bonusItemIDs: []
          }
        })
      );
      expect(readRepository.loadDailyPlanState("2026-05-02").topItems[0]?.id).toBe(
        capture.id
      );

      await withFlowDBPath(dbPath, () =>
        executeWrite({
          kind: "mark-task-done",
          payload: { id: capture.id }
        })
      );
      snapshot = readRepository.loadWorkspaceSnapshot();
      expect(
        snapshot.projects
          .flatMap((entry) => entry.tasks)
          .find((task) => task.id === capture.id)?.status
      ).toBe("done");
    });
  });

  it("rejects captures, manages memory, applies weekly review archives, and updates notification permission", async () => {
    await withDatabase(async (dbPath, readRepository) => {
      const rejected = (await withFlowDBPath(dbPath, () =>
        executeWrite({
          kind: "capture",
          payload: { title: "Discard this capture" }
        })
      )) as { id: string };
      await withFlowDBPath(dbPath, () =>
        executeWrite({
          kind: "reject-capture",
          payload: { id: rejected.id }
        })
      );
      expect(
        readRepository.loadWorkspaceSnapshot().inboxItems.some((task) => task.id === rejected.id)
      ).toBe(false);

      const createdMemory = (await withFlowDBPath(dbPath, () =>
        executeWrite({
          kind: "create-memory-record",
          payload: {
            kind: "explicit_preference",
            scope: "global",
            value: "Protect mornings for strategy work.",
            source: "manual",
            confidence: 1
          }
        })
      )) as { id: string; enabled: boolean };
      expect(createdMemory.enabled).toBe(true);

      await withFlowDBPath(dbPath, () =>
        executeWrite({
          kind: "set-memory-record-enabled",
          payload: { id: createdMemory.id, enabled: false }
        })
      );
      await withFlowDBPath(dbPath, () =>
        executeWrite({
          kind: "update-memory-record",
          payload: { id: createdMemory.id, value: "Protect afternoons for meetings." }
        })
      );
      const updatedMemory = readRepository
        .loadMemoryRecords(undefined, true)
        .find((record) => record.id === createdMemory.id);
      expect(updatedMemory?.enabled).toBe(false);
      expect(updatedMemory?.value).toContain("afternoons");

      const staleTask = (await withFlowDBPath(dbPath, () =>
        executeWrite({
          kind: "capture",
          payload: { title: "Old stale task" }
        })
      )) as { id: string };
      const db = (readRepository as unknown as { db: { prepare: Function } }).db;
      db.prepare(
        "UPDATE items SET type = 'action', updated_at = '2026-04-01T08:00:00.000Z' WHERE id = ?"
      ).run(staleTask.id);

      const weeklyReview = readRepository.loadWeeklyReviewPackage(
        new Date("2026-05-02T10:00:00.000Z")
      );
      const archiveAction = weeklyReview.cleanupActions.find(
        (action) => action.kind === "archive_stale_item" && action.targetIDs.includes(staleTask.id)
      );
      expect(archiveAction).toBeTruthy();
      await withFlowDBPath(dbPath, () =>
        executeWrite({
          kind: "apply-weekly-review-actions",
          payload: {
            actionIDs: [archiveAction?.id],
            referenceDate: "2026-05-02T10:00:00.000Z"
          }
        })
      );
      expect(
        readRepository
          .loadWeeklyReviewPackage(new Date("2026-05-02T10:00:00.000Z"))
          .staleItems.some((task) => task.id === staleTask.id)
      ).toBe(false);

      await withFlowDBPath(dbPath, () =>
        executeWrite({
          kind: "update-notification-permission",
          payload: { status: "authorized" }
        })
      );
      expect(readRepository.loadNotificationPolicy().permissionStatus).toBe(
        "authorized"
      );

      await withFlowDBPath(dbPath, () =>
        executeWrite({
          kind: "delete-memory-record",
          payload: { id: createdMemory.id }
        })
      );
      expect(
        readRepository
          .loadMemoryRecords(undefined, true)
          .some((record) => record.id === createdMemory.id)
      ).toBe(false);
    });
  });

  it("creates and mutates assistant sessions and messages through the new write kinds", async () => {
    await withDatabase(async (dbPath, readRepository) => {
      const session = (await withFlowDBPath(dbPath, () =>
        executeWrite({
          kind: "create-session",
          payload: { title: "Sidecar assistant chat" }
        })
      )) as { id: string; title: string };

      const message = (await withFlowDBPath(dbPath, () =>
        executeWrite({
          kind: "send-message",
          payload: {
            sessionID: session.id,
            prompt: "Add review the launch checklist",
            planDate: "2026-05-03"
          }
        })
      )) as { id: string; sessionID: string; proposalStatus: string };

      expect(readRepository.loadAssistantSessions()[0]?.id).toBe(session.id);
      expect(readRepository.loadAssistantMessages(session.id).map((entry) => entry.role)).toEqual([
        "user",
        "assistant"
      ]);

      await withFlowDBPath(dbPath, () =>
        executeWrite({
          kind: "confirm-message-proposal",
          payload: { messageID: message.id }
        })
      );
      await expect(
        withFlowDBPath(dbPath, () =>
          executeWrite({
            kind: "dismiss-message-proposal",
            payload: { messageID: message.id }
          })
        )
      ).rejects.toThrow(/pending/);
      const messagesAfterMutation = readRepository.loadAssistantMessages(session.id);
      expect(messagesAfterMutation[1]?.proposalStatus).toBe("confirmed");
      expect(
        readRepository
          .loadWorkspaceSnapshot()
          .inboxItems.some((task) => task.title.includes("review the launch checklist"))
      ).toBe(true);

      await withFlowDBPath(dbPath, () =>
        executeWrite({
          kind: "undo-last-mutation",
          payload: {}
        })
      );
      expect(
        readRepository
          .loadWorkspaceSnapshot()
          .inboxItems.some((task) => task.title.includes("review the launch checklist"))
      ).toBe(false);
    });
  });

  it("rejects malformed write payloads and missing targets instead of acknowledging success", async () => {
    await withDatabase(async (dbPath) => {
      await expect(
        withFlowDBPath(dbPath, () =>
          executeWrite({
            kind: "clarify-capture",
            payload: {
              id: "missing-capture",
              title: "Bad clarify",
              destination: "not-a-real-destination"
            }
          })
        )
      ).rejects.toThrow(/Unsupported clarify destination/);

      await expect(
        withFlowDBPath(dbPath, () =>
          executeWrite({
            kind: "mark-task-done",
            payload: { id: "missing-task" }
          })
        )
      ).rejects.toThrow(/does not exist/);

      await expect(
        withFlowDBPath(dbPath, () =>
          executeWrite({
            kind: "update-memory-record",
            payload: { id: "missing-memory", value: "new value" }
          })
        )
      ).rejects.toThrow(/does not exist/);
    });
  });
});

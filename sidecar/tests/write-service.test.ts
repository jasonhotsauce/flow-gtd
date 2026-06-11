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
  it("creates a new task directly inside an existing project", async () => {
    await withDatabase(async (dbPath, readRepository) => {
      const db = (readRepository as unknown as { db: { prepare: Function } }).db;
      const projectCapture = (await withFlowDBPath(dbPath, () =>
        executeWrite({
          kind: "capture",
          payload: { title: "Native Launch" }
        })
      )) as { id: string };
      await withFlowDBPath(dbPath, () =>
        executeWrite({
          kind: "clarify-capture",
          payload: {
            id: projectCapture.id,
            title: "Native Launch",
            destination: "project"
          }
        })
      );

      const task = (await withFlowDBPath(dbPath, () =>
        executeWrite({
          kind: "create-project-task",
          payload: {
            projectID: projectCapture.id,
            title: "Draft launch checklist"
          }
        })
      )) as {
        id: string;
        title: string;
        status: string;
        source: string;
        projectName?: string;
        projectID?: string;
      };

      expect(task.title).toBe("Draft launch checklist");
      expect(task.status).toBe("active");
      expect(task.source).toBe("project");
      expect(task.projectName).toBe("Native Launch");
      expect(task.projectID).toBe(projectCapture.id);

      const snapshot = readRepository.loadWorkspaceSnapshot();
      const project = snapshot.projects.find((entry) => entry.id === projectCapture.id);
      expect(project?.tasks.map((entry) => entry.id)).toContain(task.id);
      expect(snapshot.inboxItems.map((entry) => entry.id)).not.toContain(task.id);

      const legacyRow = db
        .prepare("SELECT type, parent_id FROM items WHERE id = ?")
        .get(task.id) as { type: string; parent_id: string | null };
      const taskRow = db
        .prepare("SELECT project_id FROM tasks WHERE id = ?")
        .get(task.id) as { project_id: string | null };
      expect(legacyRow).toEqual({ type: "action", parent_id: projectCapture.id });
      expect(taskRow.project_id).toBe(projectCapture.id);
    });
  });

  it("rejects direct project task creation without a real project", async () => {
    await withDatabase(async (dbPath, readRepository) => {
      const before = readRepository.loadWorkspaceSnapshot();

      await expect(
        withFlowDBPath(dbPath, () =>
          executeWrite({
            kind: "create-project-task",
            payload: {
              projectID: "missing-project",
              title: "Should not persist"
            }
          })
        )
      ).rejects.toThrow(/project/i);

      await expect(
        withFlowDBPath(dbPath, () =>
          executeWrite({
            kind: "create-project-task",
            payload: {
              projectID: "missing-project",
              title: "   "
            }
          })
        )
      ).rejects.toThrow(/title|task/i);

      expect(readRepository.loadWorkspaceSnapshot()).toEqual(before);
    });
  });

  it("assigns an existing task to an existing project", async () => {
    await withDatabase(async (dbPath, readRepository) => {
      const db = (readRepository as unknown as { db: { prepare: Function } }).db;
      const task = (await withFlowDBPath(dbPath, () =>
        executeWrite({
          kind: "capture",
          payload: { title: "Prepare launch notes" }
        })
      )) as { id: string };
      await withFlowDBPath(dbPath, () =>
        executeWrite({
          kind: "clarify-capture",
          payload: {
            id: task.id,
            title: "Prepare launch notes",
            destination: "task"
          }
        })
      );

      const projectCapture = (await withFlowDBPath(dbPath, () =>
        executeWrite({
          kind: "capture",
          payload: { title: "Launch Project" }
        })
      )) as { id: string };
      await withFlowDBPath(dbPath, () =>
        executeWrite({
          kind: "clarify-capture",
          payload: {
            id: projectCapture.id,
            title: "Launch Project",
            destination: "project"
          }
        })
      );

      await withFlowDBPath(dbPath, () =>
        executeWrite({
          kind: "assign-task-project",
          payload: { taskID: task.id, projectID: projectCapture.id }
        })
      );

      const snapshot = readRepository.loadWorkspaceSnapshot();
      const project = snapshot.projects.find((entry) => entry.id === projectCapture.id);
      const linkedTask = project?.tasks.find((entry) => entry.id === task.id);
      expect(linkedTask?.projectName).toBe("Launch Project");
      expect(linkedTask?.projectID).toBe(projectCapture.id);

      const legacyRow = db
        .prepare("SELECT parent_id FROM items WHERE id = ?")
        .get(task.id) as { parent_id: string | null };
      const taskRow = db
        .prepare("SELECT project_id FROM tasks WHERE id = ?")
        .get(task.id) as { project_id: string | null };
      expect(legacyRow.parent_id).toBe(projectCapture.id);
      expect(taskRow.project_id).toBe(projectCapture.id);
    });
  });

  it("rejects task assignment to a missing project without changing the task", async () => {
    await withDatabase(async (dbPath, readRepository) => {
      const db = (readRepository as unknown as { db: { prepare: Function } }).db;
      const task = (await withFlowDBPath(dbPath, () =>
        executeWrite({
          kind: "capture",
          payload: { title: "Keep this unlinked" }
        })
      )) as { id: string };
      await withFlowDBPath(dbPath, () =>
        executeWrite({
          kind: "clarify-capture",
          payload: {
            id: task.id,
            title: "Keep this unlinked",
            destination: "task"
          }
        })
      );

      await expect(
        withFlowDBPath(dbPath, () =>
          executeWrite({
            kind: "assign-task-project",
            payload: { taskID: task.id, projectID: "missing-project" }
          })
        )
      ).rejects.toThrow(/project/i);

      const legacyRow = db
        .prepare("SELECT parent_id FROM items WHERE id = ?")
        .get(task.id) as { parent_id: string | null };
      const taskRow = db
        .prepare("SELECT project_id FROM tasks WHERE id = ?")
        .get(task.id) as { project_id: string | null };
      expect(legacyRow.parent_id).toBeNull();
      expect(taskRow.project_id).toBeNull();
    });
  });

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

import { describe, expect, it } from "vitest";
import { bootstrapFlowDatabase } from "../src/db/database.js";
import { FlowReadRepository } from "../src/db/repositories/read-repository.js";
import { mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

function withRepository(
  fn: (repository: FlowReadRepository, close: () => void) => void
): void {
  const directory = mkdtempSync(join(tmpdir(), "flow-sidecar-read-"));
  const owner = bootstrapFlowDatabase(join(directory, "flow.sqlite"));
  const repository = new FlowReadRepository(owner.connection());
  try {
    fn(repository, () => owner.close());
  } finally {
    try {
      owner.close();
    } catch {
      // Ignore duplicate close in tests.
    }
    rmSync(directory, { recursive: true, force: true });
  }
}

function seedWorkspaceData(repository: FlowReadRepository): void {
  const db = (repository as unknown as { db: { prepare: Function } }).db;
  const now = Date.now();
  const yesterday = new Date(now - 24 * 60 * 60 * 1000).toISOString();
  const tomorrow = new Date(now + 24 * 60 * 60 * 1000).toISOString();
  const thirtyDaysAgo = new Date(now - 30 * 24 * 60 * 60 * 1000).toISOString();
  db.prepare(
    `
      INSERT INTO items (
        id, type, title, status, context_tags, parent_id, created_at, due_date,
        meta_payload, original_ek_id, estimated_duration, updated_at
      ) VALUES
      ('inbox-1', 'inbox', 'Clarify capture', 'active', '["email"]', NULL, '2026-05-02T08:00:00.000Z', NULL, '{}', NULL, NULL, '2026-05-02T08:00:00.000Z'),
      ('project-1', 'project', 'Ship sidecar', 'active', '[]', NULL, '2026-04-20T08:00:00.000Z', NULL, '{}', NULL, NULL, '2026-05-01T08:00:00.000Z'),
      ('action-1', 'action', 'Implement IPC', 'active', '["deep"]', 'project-1', '2026-04-20T09:00:00.000Z', '2026-05-03T09:00:00.000Z', '{}', NULL, 45, '2026-05-01T09:00:00.000Z'),
      ('action-2', 'action', 'Review logs', 'waiting', '[]', NULL, '2026-04-18T08:00:00.000Z', '2026-05-04T09:00:00.000Z', '{}', NULL, 20, '2026-04-18T08:00:00.000Z'),
      ('action-3', 'action', 'Close regressions', 'done', '[]', 'project-1', '2026-04-15T08:00:00.000Z', NULL, '{}', NULL, 30, '2026-05-02T07:00:00.000Z'),
      ('stale-1', 'action', 'Old loose task', 'active', '[]', NULL, '2026-04-01T08:00:00.000Z', NULL, '{}', NULL, 15, '2026-04-10T08:00:00.000Z')
    `
  ).run();
  db.prepare(
    `
      INSERT INTO daily_plan_entries (plan_date, item_id, bucket, position, created_at)
      VALUES
      ('2026-05-02', 'action-1', 'top', 1, '2026-05-02T08:30:00.000Z'),
      ('2026-05-02', 'inbox-1', 'bonus', 1, '2026-05-02T08:31:00.000Z')
    `
  ).run();
  db.prepare(
    `
      INSERT INTO assistant_turns (
        id, prompt, response, route, proposal_json, proposal_status, created_at, updated_at
      ) VALUES (
        'turn-1',
        'Add a next action',
        'I can add it.',
        'capture',
        '{"action_type":"create_task","title":"Implement IPC","detail":"Add the concrete next step.","requires_confirmation":true}',
        'pending',
        '2026-05-02T09:00:00.000Z',
        '2026-05-02T09:00:00.000Z'
      )
    `
  ).run();
  db.prepare(
    `
      INSERT INTO assistant_audit_steps (id, turn_id, stage, status, summary, payload_json, created_at)
      VALUES (
        'audit-1',
        'turn-1',
        'provider',
        'ok',
        'Codex completed successfully.',
        '{"provider":"codex","provider_status":"success","provider_runtime":"codex exec","provider_detail":"Codex completed successfully."}',
        '2026-05-02T09:00:01.000Z'
      )
    `
  ).run();
  db.prepare(
    `
      INSERT INTO assistant_audit_steps (id, turn_id, stage, status, summary, payload_json, created_at)
      VALUES ('audit-2', 'turn-1', 'plan', 'ok', 'Planned the task.', '{}', '2026-05-02T09:00:02.000Z')
    `
  ).run();
  db.prepare(
    `
      INSERT INTO memory_entries (
        id, kind, scope, scope_ref, value, source, confidence, enabled, created_at, updated_at, last_confirmed_at
      ) VALUES
      ('memory-1', 'planning_preference', 'global', NULL, 'Keep daily focus small', 'assistant-chat', 0.9, 1, '2026-05-02T09:10:00.000Z', '2026-05-02T09:10:00.000Z', '2026-05-02T09:10:00.000Z'),
      ('memory-2', 'project_context', 'project', 'project-1', 'Sidecar work is blocked on IPC', 'manual', 0.8, 0, '2026-05-02T09:11:00.000Z', '2026-05-02T09:11:00.000Z', '2026-05-02T09:11:00.000Z')
    `
  ).run();
  db.prepare("UPDATE items SET due_date = ? WHERE id = 'action-1'").run(tomorrow);
  db.prepare("UPDATE items SET updated_at = ? WHERE id = 'action-3'").run(yesterday);
  db.prepare("UPDATE items SET updated_at = ? WHERE id = 'stale-1'").run(thirtyDaysAgo);
  db.prepare(
    `
      INSERT INTO notification_policy (id, permission_status, updated_at)
      VALUES ('flow', 'authorized', '2026-05-02T09:20:00.000Z')
    `
  ).run();
}

describe("FlowReadRepository", () => {
  it("loads workspace snapshot, daily plan, weekly review, and notification policy", () => {
    withRepository((repository) => {
      seedWorkspaceData(repository);

      const snapshot = repository.loadWorkspaceSnapshot();
      const dailyPlan = repository.loadDailyPlanState("2026-05-02");
      const weeklyReview = repository.loadWeeklyReviewPackage(
        new Date("2026-05-02T10:00:00.000Z")
      );
      const notificationPolicy = repository.loadNotificationPolicy();

      expect(snapshot.inboxItems.map((task) => task.id)).toContain("inbox-1");
      expect(snapshot.todayItems.map((task) => task.id)).toContain("action-1");
      expect(snapshot.projects[0]?.nextActionTitle).toBe("Implement IPC");
      expect(snapshot.projects[0]?.tasks[0]?.projectID).toBe("project-1");
      expect(snapshot.review.completedThisWeek).toBe(1);
      expect(snapshot.staleItems.map((task) => task.id)).toContain("stale-1");
      expect(snapshot.assistantSuggestions.length).toBeGreaterThan(0);
      expect(snapshot.memoryEntries.length).toBeGreaterThan(0);

      expect(dailyPlan.topItems.map((task) => task.id)).toEqual(["action-1"]);
      expect(dailyPlan.bonusItems.map((task) => task.id)).toEqual(["inbox-1"]);
      expect(dailyPlan.readyActions.map((task) => task.id)).not.toContain("action-1");

      expect(weeklyReview.completedWork.map((task) => task.id)).toContain("action-3");
      expect(weeklyReview.projectHealth[0]?.title).toBe("Ship sidecar");
      expect(weeklyReview.cleanupActions.length).toBeGreaterThan(0);

      expect(notificationPolicy.deliveryMode).toBe("flow_owned_local");
      expect(notificationPolicy.pendingNotifications.length).toBeGreaterThan(0);
    });
  });

  it("loads assistant turns and memory records with filtering", () => {
    withRepository((repository) => {
      seedWorkspaceData(repository);

      const turns = repository.loadAssistantTurns();
      const enabledMemory = repository.loadMemoryRecords(undefined, false);
      const allMemory = repository.loadMemoryRecords(undefined, true);
      const filteredMemory = repository.loadMemoryRecords("daily focus", true);

      expect(turns).toHaveLength(1);
      expect(turns[0]?.proposal?.actionType).toBe("create_task");
      expect(turns[0]?.provider).toBe("codex");
      expect(turns[0]?.providerStatus).toBe("success");
      expect(turns[0]?.auditSteps[0]?.stage).toBe("provider");
      expect(turns[0]?.auditSteps[0]?.payload.provider).toBe("codex");

      expect(enabledMemory.map((record) => record.id)).toEqual(["memory-1"]);
      expect(allMemory).toHaveLength(2);
      expect(filteredMemory.map((record) => record.id)).toEqual(["memory-1"]);
    });
  });
});

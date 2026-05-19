import { mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { afterEach, describe, expect, it } from "vitest";
import { bootstrapFlowDatabase } from "../src/db/database.js";
import { defaultFlowDatabasePath } from "../src/db/schema.js";

const cleanupPaths: string[] = [];

afterEach(() => {
  while (cleanupPaths.length > 0) {
    const path = cleanupPaths.pop();
    if (path) {
      rmSync(path, { recursive: true, force: true });
    }
  }
});

function tempDatabasePath(): string {
  const directory = mkdtempSync(join(tmpdir(), "flow-sidecar-db-"));
  cleanupPaths.push(directory);
  return join(directory, "flow.sqlite");
}

describe("FlowDatabaseOwner", () => {
  it("bootstraps the current launch-critical schema on a fresh database", () => {
    const owner = bootstrapFlowDatabase(tempDatabasePath());
    const db = owner.connection();

    const tables = new Set(
      (
        db.prepare("SELECT name FROM sqlite_master WHERE type = 'table'").all() as Array<{
          name: string;
        }>
      ).map((row) => row.name)
    );

    expect(tables).toContain("items");
    expect(tables).toContain("raw_captures");
    expect(tables).toContain("inbox_items");
    expect(tables).toContain("tasks");
    expect(tables).toContain("projects");
    expect(tables).toContain("reminder_links");
    expect(tables).toContain("calendar_event_links");
    expect(tables).toContain("notification_policy");

    owner.close();
  });

  it("adds missing legacy item columns without changing current names", () => {
    const owner = bootstrapFlowDatabase(tempDatabasePath());
    const db = owner.connection();

    db.exec("DROP TABLE items");
    db.exec(`
      CREATE TABLE items (
        id TEXT PRIMARY KEY,
        type TEXT,
        title TEXT,
        status TEXT,
        context_tags TEXT,
        parent_id TEXT,
        created_at DATETIME,
        due_date DATETIME,
        meta_payload TEXT,
        original_ek_id TEXT
      )
    `);

    owner.bootstrap();

    const columns = (
      db.prepare("PRAGMA table_info(items)").all() as Array<{ name: string }>
    ).map((row) => row.name);

    expect(columns).toContain("estimated_duration");
    expect(columns).toContain("updated_at");

    owner.close();
  });

  it("migrates existing inbox rows into native workflow tables", () => {
    const owner = bootstrapFlowDatabase(tempDatabasePath());
    const db = owner.connection();

    db.prepare(
      `
        INSERT INTO items (
          id, type, title, status, context_tags, parent_id, created_at, due_date,
          meta_payload, original_ek_id, estimated_duration, updated_at
        ) VALUES (?, ?, ?, ?, '[]', NULL, ?, NULL, '{}', NULL, NULL, ?)
      `
    ).run(
      "legacy-inbox-1",
      "inbox",
      "Legacy inbox item",
      "active",
      "2026-04-19T10:00:00+00:00",
      "2026-04-19T10:00:00+00:00"
    );

    owner.bootstrap();

    const rawCaptureCount = db
      .prepare("SELECT COUNT(*) AS count FROM raw_captures")
      .get() as { count: number };
    const inboxItemCount = db
      .prepare("SELECT COUNT(*) AS count FROM inbox_items")
      .get() as { count: number };

    expect(rawCaptureCount.count).toBeGreaterThanOrEqual(1);
    expect(inboxItemCount.count).toBeGreaterThanOrEqual(1);

    owner.close();
  });

  it("preserves reminder-backed inbox origin metadata during migration", () => {
    const owner = bootstrapFlowDatabase(tempDatabasePath());
    const db = owner.connection();

    db.prepare(
      `
        INSERT INTO items (
          id, type, title, status, context_tags, parent_id, created_at, due_date,
          meta_payload, original_ek_id, estimated_duration, updated_at
        ) VALUES (?, ?, ?, ?, '[]', NULL, ?, NULL, '{}', ?, NULL, ?)
      `
    ).run(
      "legacy-reminder-1",
      "inbox",
      "Imported reminder",
      "active",
      "2026-04-19T10:00:00+00:00",
      "ek-123",
      "2026-04-19T11:00:00+00:00"
    );

    owner.bootstrap();

    const row = db
      .prepare(
        `
          SELECT origin_type, source_ref, imported_at, inbox_state
          FROM inbox_items
          WHERE id = 'legacy-reminder-1'
        `
      )
      .get() as {
      origin_type: string;
      source_ref: string;
      imported_at: string;
      inbox_state: string;
    };

    expect(row).toEqual({
      origin_type: "reminders_import",
      source_ref: "ek-123",
      imported_at: "2026-04-19T10:00:00+00:00",
      inbox_state: "needs_clarification"
    });

    owner.close();
  });

  it("migrates legacy projects and actions into normalized tables", () => {
    const owner = bootstrapFlowDatabase(tempDatabasePath());
    const db = owner.connection();

    db.prepare(
      `
        INSERT INTO items (
          id, type, title, status, context_tags, parent_id, created_at, due_date,
          meta_payload, original_ek_id, estimated_duration, updated_at
        ) VALUES (?, ?, ?, ?, '[]', NULL, ?, NULL, '{}', NULL, NULL, ?)
      `
    ).run(
      "legacy-project-1",
      "project",
      "Legacy project",
      "active",
      "2026-04-19T10:00:00+00:00",
      "2026-04-19T11:00:00+00:00"
    );
    db.prepare(
      `
        INSERT INTO items (
          id, type, title, status, context_tags, parent_id, created_at, due_date,
          meta_payload, original_ek_id, estimated_duration, updated_at
        ) VALUES (?, ?, ?, ?, '[]', ?, ?, NULL, '{}', NULL, 30, ?)
      `
    ).run(
      "legacy-action-1",
      "action",
      "Legacy action",
      "waiting",
      "legacy-project-1",
      "2026-04-19T10:05:00+00:00",
      "2026-04-19T11:05:00+00:00"
    );

    owner.bootstrap();

    const project = db
      .prepare("SELECT name, status FROM projects WHERE id = 'legacy-project-1'")
      .get() as { name: string; status: string };
    const task = db
      .prepare(
        `
          SELECT title, status, project_id, effort_band
          FROM tasks
          WHERE id = 'legacy-action-1'
        `
      )
      .get() as {
      title: string;
      status: string;
      project_id: string;
      effort_band: string;
    };

    expect(project).toEqual({
      name: "Legacy project",
      status: "active"
    });
    expect(task).toEqual({
      title: "Legacy action",
      status: "waiting",
      project_id: "legacy-project-1",
      effort_band: "medium"
    });

    owner.close();
  });

  it("preserves the current default database location assumption", () => {
    expect(defaultFlowDatabasePath("/Users/example")).toBe(
      "/Users/example/.flow/data/flow.db"
    );
  });
});

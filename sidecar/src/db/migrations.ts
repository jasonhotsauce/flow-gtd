import type { DatabaseSync } from "node:sqlite";
import { BASELINE_SCHEMA_STATEMENTS } from "./schema.js";

interface LegacyItemRow {
  id: string;
  type: string | null;
  title: string | null;
  status: string | null;
  parent_id: string | null;
  created_at: string | null;
  updated_at: string | null;
  original_ek_id: string | null;
}

function nowIso(): string {
  return new Date().toISOString();
}

function tableExists(db: DatabaseSync, tableName: string): boolean {
  const row = db
    .prepare(
      "SELECT name FROM sqlite_master WHERE type = 'table' AND name = ? LIMIT 1"
    )
    .get(tableName) as { name?: string } | undefined;
  return row?.name === tableName;
}

function listColumns(db: DatabaseSync, tableName: string): string[] {
  return (
    db.prepare(`PRAGMA table_info(${tableName})`).all() as Array<{
      name: string;
    }>
  ).map((row) => row.name);
}

function ensureItemsTable(db: DatabaseSync): void {
  db.exec(BASELINE_SCHEMA_STATEMENTS[0]);
  db.exec(BASELINE_SCHEMA_STATEMENTS[1]);
  db.exec(BASELINE_SCHEMA_STATEMENTS[2]);
}

function migrateItemsColumns(db: DatabaseSync): void {
  const columns = listColumns(db, "items");

  if (!columns.includes("estimated_duration")) {
    db.exec("ALTER TABLE items ADD COLUMN estimated_duration INTEGER");
  }

  if (!columns.includes("updated_at")) {
    db.exec("ALTER TABLE items ADD COLUMN updated_at DATETIME");
    db.exec(
      "UPDATE items SET updated_at = created_at WHERE updated_at IS NULL"
    );
  }
}

function ensureBaselineTables(db: DatabaseSync): void {
  for (const statement of BASELINE_SCHEMA_STATEMENTS.slice(3)) {
    db.exec(statement);
  }
}

function insertNativeCaptureAndInboxRows(
  db: DatabaseSync,
  row: LegacyItemRow,
  originType: string,
  sourceRef: string | null
): void {
  const createdValue = row.created_at ?? nowIso();
  const updatedValue = row.updated_at ?? createdValue;

  db.prepare(
    `
      INSERT OR IGNORE INTO raw_captures (id, source, raw_text, created_at)
      VALUES (?, ?, ?, ?)
    `
  ).run(row.id, originType, row.title ?? "", createdValue);

  db.prepare(
    `
      INSERT OR IGNORE INTO inbox_items (
        id, raw_capture_id, origin_type, inbox_state, source_ref,
        imported_at, task_id, created_at, updated_at
      )
      VALUES (?, ?, ?, ?, ?, ?, NULL, ?, ?)
    `
  ).run(
    row.id,
    row.id,
    originType,
    "needs_clarification",
    sourceRef,
    sourceRef ? createdValue : null,
    createdValue,
    updatedValue
  );
}

function insertNativeProjectRow(db: DatabaseSync, row: LegacyItemRow): void {
  const createdValue = row.created_at ?? nowIso();
  const updatedValue = row.updated_at ?? createdValue;

  db.prepare(
    `
      INSERT OR IGNORE INTO projects (id, name, status, created_at, updated_at)
      VALUES (?, ?, ?, ?, ?)
    `
  ).run(row.id, row.title ?? "", row.status ?? "active", createdValue, updatedValue);
}

function insertNativeTaskRow(db: DatabaseSync, row: LegacyItemRow): void {
  const createdValue = row.created_at ?? nowIso();
  const updatedValue = row.updated_at ?? createdValue;

  db.prepare(
    `
      INSERT OR IGNORE INTO tasks (
        id, title, status, project_id, time_sensitivity, effort_band, created_at, updated_at
      )
      VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    `
  ).run(
    row.id,
    row.title ?? "",
    row.status ?? "active",
    row.parent_id,
    "none",
    "medium",
    createdValue,
    updatedValue
  );
}

function migrateLegacyItemsToNativeWorkflow(db: DatabaseSync): void {
  if (!tableExists(db, "items")) {
    return;
  }

  const rows = db.prepare(
    `
      SELECT id, type, title, status, parent_id, created_at, updated_at, original_ek_id
      FROM items
    `
  ).all() as unknown as LegacyItemRow[];

  for (const row of rows) {
    switch (row.type) {
      case "inbox":
        insertNativeCaptureAndInboxRows(
          db,
          row,
          row.original_ek_id ? "reminders_import" : "manual_capture",
          row.original_ek_id
        );
        break;
      case "project":
        insertNativeProjectRow(db, row);
        break;
      case "action":
        insertNativeTaskRow(db, row);
        break;
      default:
        break;
    }
  }
}

export function bootstrapSchema(db: DatabaseSync): void {
  ensureItemsTable(db);
  migrateItemsColumns(db);
  ensureBaselineTables(db);
  migrateLegacyItemsToNativeWorkflow(db);
}

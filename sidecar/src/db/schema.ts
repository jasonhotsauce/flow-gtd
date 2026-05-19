import { homedir } from "node:os";
import { join } from "node:path";

export const FLOW_DATABASE_RELATIVE_PATH = [".flow", "data", "flow.db"] as const;

export function defaultFlowDatabasePath(
  homeDirectory: string = homedir()
): string {
  return join(homeDirectory, ...FLOW_DATABASE_RELATIVE_PATH);
}

export const BASELINE_SCHEMA_STATEMENTS = [
  `
    CREATE TABLE IF NOT EXISTS items (
      id TEXT PRIMARY KEY,
      type TEXT,
      title TEXT,
      status TEXT,
      context_tags TEXT,
      parent_id TEXT,
      created_at DATETIME,
      due_date DATETIME,
      meta_payload TEXT,
      original_ek_id TEXT,
      estimated_duration INTEGER,
      updated_at DATETIME
    )
  `,
  "CREATE INDEX IF NOT EXISTS idx_status_type ON items(status, type)",
  "CREATE INDEX IF NOT EXISTS idx_parent ON items(parent_id)",
  `
    CREATE TABLE IF NOT EXISTS index_jobs (
      id TEXT PRIMARY KEY,
      resource_id TEXT NOT NULL,
      content_type TEXT NOT NULL,
      source TEXT NOT NULL,
      title TEXT,
      summary TEXT,
      status TEXT NOT NULL,
      error TEXT,
      created_at DATETIME NOT NULL,
      updated_at DATETIME NOT NULL
    )
  `,
  "CREATE INDEX IF NOT EXISTS idx_index_jobs_status_created ON index_jobs(status, created_at)",
  `
    CREATE TABLE IF NOT EXISTS daily_plan_entries (
      plan_date TEXT NOT NULL,
      item_id TEXT NOT NULL,
      bucket TEXT NOT NULL,
      position INTEGER NOT NULL,
      created_at DATETIME NOT NULL,
      PRIMARY KEY (plan_date, item_id),
      FOREIGN KEY (item_id) REFERENCES items(id)
    )
  `,
  "CREATE INDEX IF NOT EXISTS idx_daily_plan_date_bucket_position ON daily_plan_entries(plan_date, bucket, position)",
  `
    CREATE TABLE IF NOT EXISTS daily_wrap_status (
      plan_date TEXT PRIMARY KEY,
      wrapped_at DATETIME NOT NULL
    )
  `,
  `
    CREATE TABLE IF NOT EXISTS assistant_turns (
      id TEXT PRIMARY KEY,
      prompt TEXT NOT NULL,
      response TEXT NOT NULL,
      route TEXT NOT NULL,
      proposal_json TEXT,
      proposal_status TEXT NOT NULL,
      created_at DATETIME NOT NULL,
      updated_at DATETIME NOT NULL
    )
  `,
  "CREATE INDEX IF NOT EXISTS idx_assistant_turns_created_at ON assistant_turns(created_at DESC)",
  `
    CREATE TABLE IF NOT EXISTS assistant_audit_steps (
      id TEXT PRIMARY KEY,
      turn_id TEXT NOT NULL,
      stage TEXT NOT NULL,
      status TEXT NOT NULL,
      summary TEXT NOT NULL,
      payload_json TEXT NOT NULL,
      created_at DATETIME NOT NULL,
      FOREIGN KEY (turn_id) REFERENCES assistant_turns(id)
    )
  `,
  "CREATE INDEX IF NOT EXISTS idx_assistant_audit_turn_created ON assistant_audit_steps(turn_id, created_at ASC)",
  `
    CREATE TABLE IF NOT EXISTS assistant_sessions (
      id TEXT PRIMARY KEY,
      title TEXT NOT NULL,
      latest_preview TEXT NOT NULL,
      message_count INTEGER NOT NULL,
      created_at DATETIME NOT NULL,
      updated_at DATETIME NOT NULL
    )
  `,
  "CREATE INDEX IF NOT EXISTS idx_assistant_sessions_updated_at ON assistant_sessions(updated_at DESC)",
  `
    CREATE TABLE IF NOT EXISTS assistant_messages (
      id TEXT PRIMARY KEY,
      session_id TEXT NOT NULL,
      role TEXT NOT NULL,
      content TEXT NOT NULL,
      route TEXT NOT NULL,
      proposal_json TEXT,
      proposal_status TEXT NOT NULL,
      provider TEXT NOT NULL,
      provider_status TEXT NOT NULL,
      provider_detail TEXT NOT NULL,
      provider_model TEXT,
      source_turn_id TEXT,
      created_at DATETIME NOT NULL,
      updated_at DATETIME NOT NULL,
      FOREIGN KEY (session_id) REFERENCES assistant_sessions(id)
    )
  `,
  "CREATE INDEX IF NOT EXISTS idx_assistant_messages_session_created_at ON assistant_messages(session_id, created_at ASC)",
  `
    CREATE TABLE IF NOT EXISTS assistant_message_audit_steps (
      id TEXT PRIMARY KEY,
      message_id TEXT NOT NULL,
      stage TEXT NOT NULL,
      status TEXT NOT NULL,
      summary TEXT NOT NULL,
      payload_json TEXT NOT NULL,
      created_at DATETIME NOT NULL,
      FOREIGN KEY (message_id) REFERENCES assistant_messages(id)
    )
  `,
  "CREATE INDEX IF NOT EXISTS idx_assistant_message_audit_message_created ON assistant_message_audit_steps(message_id, created_at ASC)",
  `
    CREATE TABLE IF NOT EXISTS memory_entries (
      id TEXT PRIMARY KEY,
      kind TEXT NOT NULL,
      scope TEXT NOT NULL,
      scope_ref TEXT,
      value TEXT NOT NULL,
      source TEXT NOT NULL,
      confidence REAL NOT NULL,
      enabled INTEGER NOT NULL,
      created_at DATETIME NOT NULL,
      updated_at DATETIME NOT NULL,
      last_confirmed_at DATETIME
    )
  `,
  "CREATE INDEX IF NOT EXISTS idx_memory_entries_kind_scope ON memory_entries(kind, scope)",
  `
    CREATE TABLE IF NOT EXISTS raw_captures (
      id TEXT PRIMARY KEY,
      source TEXT NOT NULL,
      raw_text TEXT NOT NULL,
      created_at DATETIME NOT NULL
    )
  `,
  `
    CREATE TABLE IF NOT EXISTS inbox_items (
      id TEXT PRIMARY KEY,
      raw_capture_id TEXT NOT NULL,
      origin_type TEXT NOT NULL,
      inbox_state TEXT NOT NULL,
      source_ref TEXT,
      imported_at DATETIME,
      task_id TEXT,
      clarified_task_id TEXT,
      clarified_project_id TEXT,
      clarified_at DATETIME,
      created_at DATETIME NOT NULL,
      updated_at DATETIME NOT NULL
    )
  `,
  `
    CREATE TABLE IF NOT EXISTS tasks (
      id TEXT PRIMARY KEY,
      title TEXT NOT NULL,
      status TEXT NOT NULL,
      project_id TEXT,
      source_inbox_item_id TEXT,
      time_sensitivity TEXT NOT NULL,
      effort_band TEXT NOT NULL,
      created_at DATETIME NOT NULL,
      updated_at DATETIME NOT NULL
    )
  `,
  `
    CREATE TABLE IF NOT EXISTS projects (
      id TEXT PRIMARY KEY,
      name TEXT NOT NULL,
      status TEXT NOT NULL,
      created_at DATETIME NOT NULL,
      updated_at DATETIME NOT NULL
    )
  `,
  `
    CREATE TABLE IF NOT EXISTS reminder_links (
      id TEXT PRIMARY KEY,
      task_id TEXT NOT NULL,
      external_id TEXT NOT NULL,
      sync_status TEXT NOT NULL,
      conflict_status TEXT NOT NULL,
      last_synced_at DATETIME,
      source_modified_at DATETIME,
      tombstoned_at DATETIME
    )
  `,
  `
    CREATE TABLE IF NOT EXISTS calendar_event_links (
      id TEXT PRIMARY KEY,
      task_id TEXT NOT NULL,
      external_id TEXT NOT NULL,
      sync_status TEXT NOT NULL,
      conflict_status TEXT NOT NULL,
      last_synced_at DATETIME,
      source_modified_at DATETIME,
      tombstoned_at DATETIME
    )
  `,
  `
    CREATE TABLE IF NOT EXISTS notification_policy (
      id TEXT PRIMARY KEY,
      permission_status TEXT NOT NULL,
      updated_at DATETIME NOT NULL
    )
  `,
  `
    CREATE TABLE IF NOT EXISTS mutation_batches (
      id TEXT PRIMARY KEY,
      source TEXT NOT NULL,
      requires_confirmation INTEGER NOT NULL,
      created_at DATETIME NOT NULL
    )
  `,
  `
    CREATE TABLE IF NOT EXISTS mutation_records (
      id TEXT PRIMARY KEY,
      batch_id TEXT NOT NULL,
      target_table TEXT NOT NULL,
      target_id TEXT NOT NULL,
      action TEXT NOT NULL,
      payload_json TEXT NOT NULL,
      created_at DATETIME NOT NULL
    )
  `
] as const;

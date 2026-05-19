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
    original_ek_id TEXT,
    estimated_duration INTEGER,
    updated_at DATETIME
);

CREATE INDEX idx_status_type ON items(status, type);
CREATE INDEX idx_parent ON items(parent_id);

CREATE TABLE assistant_turns (
    id TEXT PRIMARY KEY,
    prompt TEXT NOT NULL,
    response TEXT NOT NULL,
    route TEXT NOT NULL,
    proposal_json TEXT,
    proposal_status TEXT NOT NULL,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL
);

CREATE TABLE assistant_audit_steps (
    id TEXT PRIMARY KEY,
    turn_id TEXT NOT NULL,
    stage TEXT NOT NULL,
    status TEXT NOT NULL,
    summary TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    created_at DATETIME NOT NULL
);

CREATE TABLE assistant_sessions (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    latest_preview TEXT NOT NULL,
    message_count INTEGER NOT NULL,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL
);

CREATE TABLE assistant_messages (
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
    updated_at DATETIME NOT NULL
);

CREATE TABLE assistant_message_audit_steps (
    id TEXT PRIMARY KEY,
    message_id TEXT NOT NULL,
    stage TEXT NOT NULL,
    status TEXT NOT NULL,
    summary TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    created_at DATETIME NOT NULL
);

CREATE TABLE memory_entries (
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
);

CREATE TABLE raw_captures (
    id TEXT PRIMARY KEY,
    source TEXT NOT NULL,
    raw_text TEXT NOT NULL,
    created_at DATETIME NOT NULL
);

CREATE TABLE inbox_items (
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
);

CREATE TABLE projects (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL
);

CREATE TABLE tasks (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    status TEXT NOT NULL,
    project_id TEXT,
    source_inbox_item_id TEXT,
    time_sensitivity TEXT NOT NULL,
    effort_band TEXT NOT NULL,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL
);

INSERT INTO items (
    id, type, title, status, context_tags, parent_id, created_at,
    due_date, meta_payload, original_ek_id, estimated_duration, updated_at
) VALUES (
    'current-inbox-1', 'inbox', 'Current inbox item', 'active', '[]', NULL,
    '2026-04-20T09:00:00+00:00', NULL, '{}', NULL, NULL, '2026-04-20T09:00:00+00:00'
);

INSERT INTO items (
    id, type, title, status, context_tags, parent_id, created_at,
    due_date, meta_payload, original_ek_id, estimated_duration, updated_at
) VALUES (
    'current-project-1', 'project', 'Current project', 'active', '[]', NULL,
    '2026-04-20T10:00:00+00:00', NULL, '{}', NULL, NULL, '2026-04-20T10:00:00+00:00'
);

INSERT INTO items (
    id, type, title, status, context_tags, parent_id, created_at,
    due_date, meta_payload, original_ek_id, estimated_duration, updated_at
) VALUES (
    'current-action-1', 'action', 'Current action', 'active', '[]', 'current-project-1',
    '2026-04-20T10:05:00+00:00', NULL, '{}', NULL, 15, '2026-04-20T10:05:00+00:00'
);

INSERT INTO assistant_turns (
    id, prompt, response, route, proposal_json, proposal_status, created_at, updated_at
) VALUES (
    'turn-1', 'Prompt', 'Response', 'assistant_orchestrator', NULL, 'none',
    '2026-04-20T11:00:00+00:00', '2026-04-20T11:00:00+00:00'
);

INSERT INTO assistant_audit_steps (
    id, turn_id, stage, status, summary, payload_json, created_at
) VALUES (
    'audit-1', 'turn-1', 'plan', 'completed', 'summary', '{}', '2026-04-20T11:01:00+00:00'
);

INSERT INTO memory_entries (
    id, kind, scope, scope_ref, value, source, confidence, enabled, created_at, updated_at, last_confirmed_at
) VALUES (
    'memory-1', 'preference', 'global', NULL, 'Use TypeScript sidecar', 'seed', 0.9, 1,
    '2026-04-20T11:02:00+00:00', '2026-04-20T11:02:00+00:00', NULL
);

INSERT INTO raw_captures (id, source, raw_text, created_at) VALUES (
    'current-inbox-1', 'manual_capture', 'Current inbox item', '2026-04-20T09:00:00+00:00'
);

INSERT INTO inbox_items (
    id, raw_capture_id, origin_type, inbox_state, source_ref, imported_at,
    task_id, clarified_task_id, clarified_project_id, clarified_at, created_at, updated_at
) VALUES (
    'current-inbox-1', 'current-inbox-1', 'manual_capture', 'needs_clarification', NULL, NULL,
    NULL, NULL, NULL, NULL, '2026-04-20T09:00:00+00:00', '2026-04-20T09:00:00+00:00'
);

INSERT INTO projects (id, name, status, created_at, updated_at) VALUES (
    'current-project-1', 'Current project', 'active', '2026-04-20T10:00:00+00:00', '2026-04-20T10:00:00+00:00'
);

INSERT INTO tasks (
    id, title, status, project_id, source_inbox_item_id, time_sensitivity, effort_band, created_at, updated_at
) VALUES (
    'current-action-1', 'Current action', 'active', 'current-project-1', NULL, 'none', 'medium',
    '2026-04-20T10:05:00+00:00', '2026-04-20T10:05:00+00:00'
);

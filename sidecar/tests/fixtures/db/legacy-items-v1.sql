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
);

INSERT INTO items (
    id, type, title, status, context_tags, parent_id, created_at,
    due_date, meta_payload, original_ek_id
) VALUES (
    'legacy-inbox-1', 'inbox', 'Legacy inbox item', 'active', '[]', NULL,
    '2026-04-19T10:00:00+00:00', NULL, '{}', NULL
);

INSERT INTO items (
    id, type, title, status, context_tags, parent_id, created_at,
    due_date, meta_payload, original_ek_id
) VALUES (
    'legacy-reminder-1', 'inbox', 'Imported reminder', 'active', '[]', NULL,
    '2026-04-19T11:00:00+00:00', NULL, '{}', 'ek-123'
);

INSERT INTO items (
    id, type, title, status, context_tags, parent_id, created_at,
    due_date, meta_payload, original_ek_id
) VALUES (
    'legacy-project-1', 'project', 'Legacy project', 'active', '[]', NULL,
    '2026-04-19T12:00:00+00:00', NULL, '{}', NULL
);

INSERT INTO items (
    id, type, title, status, context_tags, parent_id, created_at,
    due_date, meta_payload, original_ek_id
) VALUES (
    'legacy-action-1', 'action', 'Legacy action', 'waiting', '[]', 'legacy-project-1',
    '2026-04-19T12:05:00+00:00', NULL, '{}', NULL
);

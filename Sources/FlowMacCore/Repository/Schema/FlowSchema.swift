import Foundation

enum FlowSchema {
    static let nativeWorkflowTableStatements = [
        """
        CREATE TABLE IF NOT EXISTS raw_captures (
            id TEXT PRIMARY KEY,
            source TEXT NOT NULL,
            raw_text TEXT NOT NULL,
            created_at DATETIME NOT NULL
        )
        """,
        """
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
        """,
        """
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
        """,
        """
        CREATE TABLE IF NOT EXISTS projects (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            status TEXT NOT NULL,
            created_at DATETIME NOT NULL,
            updated_at DATETIME NOT NULL
        )
        """,
        """
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
        """,
        """
        CREATE TABLE IF NOT EXISTS assistant_audit_steps (
            id TEXT PRIMARY KEY,
            turn_id TEXT NOT NULL,
            stage TEXT NOT NULL,
            status TEXT NOT NULL,
            summary TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            created_at DATETIME NOT NULL
        )
        """,
        """
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
        """,
        """
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
        """,
        """
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
        """,
        """
        CREATE TABLE IF NOT EXISTS notification_policy (
            id TEXT PRIMARY KEY,
            permission_status TEXT NOT NULL,
            updated_at DATETIME NOT NULL
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS mutation_batches (
            id TEXT PRIMARY KEY,
            source TEXT NOT NULL,
            requires_confirmation INTEGER NOT NULL,
            created_at DATETIME NOT NULL
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS mutation_records (
            id TEXT PRIMARY KEY,
            batch_id TEXT NOT NULL,
            target_table TEXT NOT NULL,
            target_id TEXT NOT NULL,
            action TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            created_at DATETIME NOT NULL
        )
        """
    ]
}

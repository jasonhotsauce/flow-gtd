import Foundation
import SQLite3

enum WorkflowStorageSmokeTests {
    private static let sqliteTransient = unsafeBitCast(-1, to: sqlite3_destructor_type.self)

    static func run() throws {
        try smokeTestWorkflowTablesExist()
        try smokeTestCaptureCreatesRawCaptureAndInboxItem()
        try smokeTestLegacyProjectAndActionPromotion()
    }

    private static func smokeTestWorkflowTablesExist() throws {
        let databaseURL = temporaryDatabaseURL()
        let repository = LegacyFlowRepository(databaseURL: databaseURL)
        _ = try repository.loadWorkspaceSnapshot()

        let expectedTables = [
            "raw_captures",
            "inbox_items",
            "tasks",
            "projects",
            "reminder_links",
            "calendar_event_links",
            "mutation_batches",
            "mutation_records",
        ]

        let existingTables = try withDatabase(at: databaseURL) { db in
            try fetchTableNames(db: db)
        }

        for table in expectedTables where existingTables.contains(table) == false {
            throw FlowDataError.message("Expected workflow table '\(table)' to exist after bootstrap.")
        }
    }

    private static func smokeTestCaptureCreatesRawCaptureAndInboxItem() throws {
        let databaseURL = temporaryDatabaseURL()
        let repository = LegacyFlowRepository(databaseURL: databaseURL)
        let created = try repository.capture(title: "Draft native PRD migration plan")

        let counts = try withDatabase(at: databaseURL) { db in
            (
                try countRows(db: db, table: "raw_captures", whereColumn: "id", equals: created.id),
                try countRows(db: db, table: "inbox_items", whereColumn: "id", equals: created.id)
            )
        }

        guard counts.0 == 1 else {
            throw FlowDataError.message("Expected capture to persist one raw capture row.")
        }

        guard counts.1 == 1 else {
            throw FlowDataError.message("Expected capture to persist one inbox item row.")
        }
    }

    private static func smokeTestLegacyProjectAndActionPromotion() throws {
        let databaseURL = temporaryDatabaseURL()
        try withDatabase(at: databaseURL) { db in
            try exec(
                db,
                """
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
                )
                """
            )
            try exec(
                db,
                """
                INSERT INTO items (
                    id, type, title, status, context_tags, parent_id, created_at,
                    due_date, meta_payload, original_ek_id, estimated_duration, updated_at
                ) VALUES (
                    'legacy-project-1', 'project', 'Legacy project', 'active', '[]', NULL,
                    '2026-04-19T10:00:00+00:00', NULL, '{}', NULL, NULL, '2026-04-19T10:00:00+00:00'
                )
                """
            )
            try exec(
                db,
                """
                INSERT INTO items (
                    id, type, title, status, context_tags, parent_id, created_at,
                    due_date, meta_payload, original_ek_id, estimated_duration, updated_at
                ) VALUES (
                    'legacy-action-1', 'action', 'Legacy action', 'waiting', '[]', 'legacy-project-1',
                    '2026-04-19T10:05:00+00:00', NULL, '{}', NULL, 30, '2026-04-19T10:05:00+00:00'
                )
                """
            )
        }

        let repository = LegacyFlowRepository(databaseURL: databaseURL)
        _ = try repository.loadWorkspaceSnapshot()

        let counts = try withDatabase(at: databaseURL) { db in
            (
                try countRows(db: db, table: "projects", whereColumn: "id", equals: "legacy-project-1"),
                try countRows(db: db, table: "tasks", whereColumn: "id", equals: "legacy-action-1")
            )
        }

        guard counts.0 == 1 else {
            throw FlowDataError.message("Expected legacy project to be promoted into normalized projects.")
        }

        guard counts.1 == 1 else {
            throw FlowDataError.message("Expected legacy action to be promoted into normalized tasks.")
        }
    }

    private static func temporaryDatabaseURL() -> URL {
        URL(fileURLWithPath: NSTemporaryDirectory())
            .appendingPathComponent(UUID().uuidString)
            .appendingPathExtension("sqlite")
    }

    private static func withDatabase<T>(
        at url: URL,
        _ block: (OpaquePointer?) throws -> T
    ) throws -> T {
        var db: OpaquePointer?
        guard sqlite3_open(url.path, &db) == SQLITE_OK else {
            throw FlowDataError.message("Unable to open workflow smoke test database.")
        }
        defer { sqlite3_close(db) }
        return try block(db)
    }

    private static func fetchTableNames(db: OpaquePointer?) throws -> Set<String> {
        let sql = "SELECT name FROM sqlite_master WHERE type = 'table'"
        var statement: OpaquePointer?
        guard sqlite3_prepare_v2(db, sql, -1, &statement, nil) == SQLITE_OK else {
            throw FlowDataError.message("Unable to prepare sqlite_master query.")
        }
        defer { sqlite3_finalize(statement) }

        var names: Set<String> = []
        while sqlite3_step(statement) == SQLITE_ROW {
            if let cString = sqlite3_column_text(statement, 0) {
                names.insert(String(cString: cString))
            }
        }
        return names
    }

    private static func countRows(
        db: OpaquePointer?,
        table: String,
        whereColumn: String,
        equals value: String
    ) throws -> Int {
        let sql = "SELECT COUNT(*) FROM \(table) WHERE \(whereColumn) = ?"
        var statement: OpaquePointer?
        guard sqlite3_prepare_v2(db, sql, -1, &statement, nil) == SQLITE_OK else {
            throw FlowDataError.message("Unable to prepare count query for \(table).")
        }
        defer { sqlite3_finalize(statement) }

        sqlite3_bind_text(statement, 1, value, -1, sqliteTransient)
        guard sqlite3_step(statement) == SQLITE_ROW else {
            throw FlowDataError.message("Unable to count rows in \(table).")
        }
        return Int(sqlite3_column_int(statement, 0))
    }

    private static func exec(_ db: OpaquePointer?, _ sql: String) throws {
        var errorPointer: UnsafeMutablePointer<Int8>?
        guard sqlite3_exec(db, sql, nil, nil, &errorPointer) == SQLITE_OK else {
            let fallback = errorPointer.map { String(cString: $0) } ?? "SQLite execution error."
            sqlite3_free(errorPointer)
            throw FlowDataError.message(fallback)
        }
    }
}

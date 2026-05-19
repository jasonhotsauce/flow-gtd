import Foundation
import SQLite3

enum CaptureClarifySmokeTests {
    static func run() throws {
        try smokeTestCapturePersistsPendingClarifyState()
        try smokeTestInboxSchemaReservesStructuredClarifyFields()
        try smokeTestTasksSchemaReservesSourceInboxLink()
        try smokeTestClarifyAcceptPromotesCaptureIntoTaskAndProject()
        try smokeTestClarifyProjectConversionPromotesCaptureIntoProject()
        try smokeTestClarifyRejectArchivesInboxItemAndRetainsRawCapture()
        try smokeTestRejectedCaptureDoesNotTriggerSampleFallback()
        try smokeTestMemoryOnlyWorkspaceDoesNotTriggerSampleFallback()
    }

    private static let sqliteTransient = unsafeBitCast(-1, to: sqlite3_destructor_type.self)

    private static func smokeTestCapturePersistsPendingClarifyState() throws {
        let databaseURL = temporaryDatabaseURL()
        let repository = LegacyFlowRepository(databaseURL: databaseURL)
        let created = try repository.capture(title: "Draft project kickoff note")

        let row = try withDatabase(at: databaseURL) { db in
            try fetchPendingCaptureRow(db: db, id: created.id)
        }

        guard row.source == "manual_capture" else {
            throw FlowDataError.message("Expected raw capture source to be manual_capture before clarify.")
        }
        guard row.rawText == "Draft project kickoff note" else {
            throw FlowDataError.message("Expected raw capture text to preserve the original capture draft.")
        }
        guard row.rawCaptureID == created.id else {
            throw FlowDataError.message("Expected inbox item to reference the raw capture before clarify.")
        }
        guard row.inboxState == "needs_clarification" else {
            throw FlowDataError.message("Expected new captures to stay pending clarification.")
        }
        guard row.taskCount == 0, row.projectCount == 0 else {
            throw FlowDataError.message("Expected capture to avoid structured task/project rows before clarify.")
        }
    }

    private static func smokeTestInboxSchemaReservesStructuredClarifyFields() throws {
        let databaseURL = temporaryDatabaseURL()
        let repository = LegacyFlowRepository(databaseURL: databaseURL)
        _ = try repository.loadWorkspaceSnapshot()

        let columns = try withDatabase(at: databaseURL) { db in
            try fetchColumnNames(db: db, table: "inbox_items")
        }

        guard columns.contains("clarified_task_id") else {
            throw FlowDataError.message("Expected inbox_items to reserve clarified_task_id for task conversion.")
        }
        guard columns.contains("clarified_project_id") else {
            throw FlowDataError.message("Expected inbox_items to reserve clarified_project_id for project routing.")
        }
        guard columns.contains("clarified_at") else {
            throw FlowDataError.message("Expected inbox_items to record clarified_at when structured interpretation is accepted.")
        }
    }

    private static func smokeTestTasksSchemaReservesSourceInboxLink() throws {
        let databaseURL = temporaryDatabaseURL()
        let repository = LegacyFlowRepository(databaseURL: databaseURL)
        _ = try repository.loadWorkspaceSnapshot()

        let columns = try withDatabase(at: databaseURL) { db in
            try fetchColumnNames(db: db, table: "tasks")
        }

        guard columns.contains("source_inbox_item_id") else {
            throw FlowDataError.message("Expected tasks to reserve source_inbox_item_id for clarify provenance.")
        }
    }

    private static func smokeTestClarifyAcceptPromotesCaptureIntoTaskAndProject() throws {
        let databaseURL = temporaryDatabaseURL()
        let repository = LegacyFlowRepository(databaseURL: databaseURL)
        let created = try repository.capture(title: "Call Alice about launch plan")

        try repository.clarifyCapture(
            id: created.id,
            title: "Call Alice to confirm launch checklist",
            destination: .task,
            projectTitle: "Launch Prep"
        )

        let row = try withDatabase(at: databaseURL) { db in
            try fetchClarifyResolutionRow(db: db, id: created.id)
        }

        guard row.itemType == "action" else {
            throw FlowDataError.message("Expected clarify acceptance to convert the legacy item row into an action.")
        }
        guard row.itemTitle == "Call Alice to confirm launch checklist" else {
            throw FlowDataError.message("Expected clarify acceptance to keep the edited task title.")
        }
        guard row.inboxState == "clarified" else {
            throw FlowDataError.message("Expected clarify acceptance to update inbox state to clarified.")
        }
        guard row.taskID == created.id, row.clarifiedTaskID == created.id else {
            throw FlowDataError.message("Expected clarify acceptance to link the task back to the inbox item.")
        }
        guard row.projectName == "Launch Prep" else {
            throw FlowDataError.message("Expected clarify acceptance to create or attach a project row.")
        }
        guard row.taskProjectID == row.clarifiedProjectID else {
            throw FlowDataError.message("Expected clarified task and inbox item to agree on the linked project.")
        }
        guard row.mutationRecordCount >= 2 else {
            throw FlowDataError.message("Expected clarify acceptance to record mutation details.")
        }
    }

    private static func smokeTestClarifyProjectConversionPromotesCaptureIntoProject() throws {
        let databaseURL = temporaryDatabaseURL()
        let repository = LegacyFlowRepository(databaseURL: databaseURL)
        let created = try repository.capture(title: "Plan the offsite")

        try repository.clarifyCapture(
            id: created.id,
            title: "Q3 Offsite",
            destination: .project,
            projectTitle: nil
        )

        let row = try withDatabase(at: databaseURL) { db in
            try fetchClarifyResolutionRow(db: db, id: created.id)
        }

        guard row.itemType == "project" else {
            throw FlowDataError.message("Expected project clarify acceptance to convert the item into a project.")
        }
        guard row.inboxState == "converted_to_project" else {
            throw FlowDataError.message("Expected project clarify acceptance to set converted_to_project state.")
        }
        guard row.taskID == nil, row.clarifiedTaskID == nil else {
            throw FlowDataError.message("Expected project conversion to avoid task linkage.")
        }
        guard row.clarifiedProjectID == created.id, row.projectName == "Q3 Offsite" else {
            throw FlowDataError.message("Expected project conversion to use the capture id as the project id.")
        }
    }

    private static func smokeTestClarifyRejectArchivesInboxItemAndRetainsRawCapture() throws {
        let databaseURL = temporaryDatabaseURL()
        let repository = LegacyFlowRepository(databaseURL: databaseURL)
        let created = try repository.capture(title: "Maybe someday idea")

        try repository.rejectCapture(id: created.id)

        let row = try withDatabase(at: databaseURL) { db in
            try fetchClarifyResolutionRow(db: db, id: created.id)
        }

        guard row.itemStatus == "archived" else {
            throw FlowDataError.message("Expected rejected capture to archive the legacy inbox row.")
        }
        guard row.inboxState == "rejected" else {
            throw FlowDataError.message("Expected reject flow to persist rejected inbox state.")
        }
        guard row.rawText == "Maybe someday idea" else {
            throw FlowDataError.message("Expected reject flow to preserve the original raw capture text.")
        }
        guard row.mutationRecordCount == 1 else {
            throw FlowDataError.message("Expected reject flow to record one mutation detail entry.")
        }
    }

    private static func smokeTestRejectedCaptureDoesNotTriggerSampleFallback() throws {
        let databaseURL = temporaryDatabaseURL()
        let repository = LegacyFlowRepository(databaseURL: databaseURL)
        let created = try repository.capture(title: "Maybe someday idea")
        try repository.rejectCapture(id: created.id)

        let snapshot = try repository.loadWorkspaceSnapshot()

        guard snapshot.inboxItems.isEmpty else {
            throw FlowDataError.message("Expected rejected capture to leave the inbox empty.")
        }
        guard snapshot.todayItems.isEmpty else {
            throw FlowDataError.message("Expected rejected capture to avoid sample today items.")
        }
        guard snapshot.projects.isEmpty else {
            throw FlowDataError.message("Expected rejected capture to avoid sample projects.")
        }
        guard snapshot.focusHeadline == "Quiet system, ready for a thoughtful start" else {
            throw FlowDataError.message("Expected persisted-but-empty workspace state instead of sample fallback.")
        }
    }

    private static func smokeTestMemoryOnlyWorkspaceDoesNotTriggerSampleFallback() throws {
        let databaseURL = temporaryDatabaseURL()
        let repository = LegacyFlowRepository(databaseURL: databaseURL)
        _ = try repository.createMemoryRecord(
            kind: "planning_preference",
            scope: "global",
            value: "Prefer deep work before meetings.",
            source: "explicit",
            confidence: 1.0,
            scopeRef: nil
        )

        let snapshot = try repository.loadWorkspaceSnapshot()

        guard snapshot.inboxItems.isEmpty else {
            throw FlowDataError.message("Expected memory-only workspace to avoid sample inbox items.")
        }
        guard snapshot.todayItems.isEmpty else {
            throw FlowDataError.message("Expected memory-only workspace to avoid sample today items.")
        }
        guard snapshot.projects.isEmpty else {
            throw FlowDataError.message("Expected memory-only workspace to avoid sample projects.")
        }
        guard snapshot.focusHeadline == "Quiet system, ready for a thoughtful start" else {
            throw FlowDataError.message("Expected memory-only workspace state instead of sample fallback.")
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
            throw FlowDataError.message("Unable to open capture/clarify smoke test database.")
        }
        defer { sqlite3_close(db) }
        return try block(db)
    }

    private static func fetchPendingCaptureRow(
        db: OpaquePointer?,
        id: String
    ) throws -> (
        source: String,
        rawText: String,
        rawCaptureID: String,
        inboxState: String,
        taskCount: Int,
        projectCount: Int
    ) {
        let sql = """
            SELECT
                rc.source,
                rc.raw_text,
                ii.raw_capture_id,
                ii.inbox_state,
                (SELECT COUNT(*) FROM tasks),
                (SELECT COUNT(*) FROM projects)
            FROM raw_captures rc
            JOIN inbox_items ii ON ii.id = rc.id
            WHERE rc.id = ?
        """

        var statement: OpaquePointer?
        guard sqlite3_prepare_v2(db, sql, -1, &statement, nil) == SQLITE_OK else {
            throw FlowDataError.message("Unable to prepare capture/clarify row query.")
        }
        defer { sqlite3_finalize(statement) }

        sqlite3_bind_text(statement, 1, id, -1, sqliteTransient)
        guard sqlite3_step(statement) == SQLITE_ROW else {
            throw FlowDataError.message("Expected a pending capture row for the new capture.")
        }

        return (
            text(statement, column: 0),
            text(statement, column: 1),
            text(statement, column: 2),
            text(statement, column: 3),
            Int(sqlite3_column_int(statement, 4)),
            Int(sqlite3_column_int(statement, 5))
        )
    }

    private static func fetchColumnNames(
        db: OpaquePointer?,
        table: String
    ) throws -> Set<String> {
        let sql = "PRAGMA table_info(\(table))"
        var statement: OpaquePointer?
        guard sqlite3_prepare_v2(db, sql, -1, &statement, nil) == SQLITE_OK else {
            throw FlowDataError.message("Unable to inspect schema for \(table).")
        }
        defer { sqlite3_finalize(statement) }

        var columns: Set<String> = []
        while sqlite3_step(statement) == SQLITE_ROW {
            if let cString = sqlite3_column_text(statement, 1) {
                columns.insert(String(cString: cString))
            }
        }
        return columns
    }

    private static func fetchClarifyResolutionRow(
        db: OpaquePointer?,
        id: String
    ) throws -> (
        rawText: String,
        itemType: String,
        itemTitle: String,
        itemStatus: String,
        inboxState: String,
        taskID: String?,
        clarifiedTaskID: String?,
        clarifiedProjectID: String?,
        taskProjectID: String?,
        projectName: String?,
        mutationRecordCount: Int
    ) {
        let sql = """
            SELECT
                rc.raw_text,
                i.type,
                i.title,
                i.status,
                ii.inbox_state,
                ii.task_id,
                ii.clarified_task_id,
                ii.clarified_project_id,
                t.project_id,
                p.name,
                (
                    SELECT COUNT(*)
                    FROM mutation_records mr
                    WHERE mr.batch_id = (
                        SELECT id
                        FROM mutation_batches mb
                        ORDER BY mb.created_at DESC
                        LIMIT 1
                    )
                )
            FROM raw_captures rc
            JOIN inbox_items ii ON ii.id = rc.id
            JOIN items i ON i.id = ii.id
            LEFT JOIN tasks t ON t.id = ii.clarified_task_id
            LEFT JOIN projects p ON p.id = ii.clarified_project_id
            WHERE rc.id = ?
        """

        var statement: OpaquePointer?
        guard sqlite3_prepare_v2(db, sql, -1, &statement, nil) == SQLITE_OK else {
            throw FlowDataError.message("Unable to prepare clarify resolution query.")
        }
        defer { sqlite3_finalize(statement) }

        sqlite3_bind_text(statement, 1, id, -1, sqliteTransient)
        guard sqlite3_step(statement) == SQLITE_ROW else {
            throw FlowDataError.message("Expected a clarify resolution row.")
        }

        return (
            text(statement, column: 0),
            text(statement, column: 1),
            text(statement, column: 2),
            text(statement, column: 3),
            text(statement, column: 4),
            nullableText(statement, column: 5),
            nullableText(statement, column: 6),
            nullableText(statement, column: 7),
            nullableText(statement, column: 8),
            nullableText(statement, column: 9),
            Int(sqlite3_column_int(statement, 10))
        )
    }

    private static func text(_ statement: OpaquePointer?, column: Int32) -> String {
        guard let cString = sqlite3_column_text(statement, column) else {
            return ""
        }
        return String(cString: cString)
    }

    private static func nullableText(_ statement: OpaquePointer?, column: Int32) -> String? {
        guard let cString = sqlite3_column_text(statement, column) else {
            return nil
        }
        return String(cString: cString)
    }
}

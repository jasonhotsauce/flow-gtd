import Foundation
import SQLite3

enum WeeklyReviewWorkflowSmokeTests {
    private static let sqliteTransient = unsafeBitCast(-1, to: sqlite3_destructor_type.self)

    static func run() throws {
        try smokeTestWeeklyReviewPackageAndBatchCleanup()
        try smokeTestProjectNextActionProposalConfirmation()
    }

    private static func smokeTestWeeklyReviewPackageAndBatchCleanup() throws {
        let databaseURL = temporaryDatabaseURL()
        let repository = LegacyFlowRepository(databaseURL: databaseURL)
        let referenceDate = ISO8601DateFormatter().date(from: "2026-03-22T09:00:00Z")!
        _ = try repository.loadWorkspaceSnapshot()

        try withDatabase(at: databaseURL) { db in
            try insertItem(
                db: db,
                id: "done-1",
                type: "action",
                title: "Complete review setup",
                status: "done",
                parentID: nil,
                dueDate: nil,
                createdAt: "2026-03-18T09:00:00+00:00",
                updatedAt: "2026-03-21T09:00:00+00:00"
            )
            try insertItem(
                db: db,
                id: "stale-1",
                type: "action",
                title: "Revisit launch follow-up",
                status: "active",
                parentID: nil,
                dueDate: nil,
                createdAt: "2026-03-01T09:00:00+00:00",
                updatedAt: "2026-03-01T09:00:00+00:00"
            )
            try insertItem(
                db: db,
                id: "due-1",
                type: "action",
                title: "Prepare Monday deadline",
                status: "active",
                parentID: nil,
                dueDate: "2026-03-23T09:00:00+00:00",
                createdAt: "2026-03-20T09:00:00+00:00",
                updatedAt: "2026-03-20T09:00:00+00:00"
            )
        }
        _ = try repository.capture(title: "Clarify weekly review inbox item")

        let package = try repository.loadWeeklyReviewPackage(referenceDate: referenceDate)

        guard package.completedWork.contains(where: { $0.id == "done-1" }) else {
            throw FlowDataError.message("Expected weekly review package to include completed work.")
        }
        guard package.staleItems.contains(where: { $0.id == "stale-1" }) else {
            throw FlowDataError.message("Expected weekly review package to include stale tasks.")
        }
        guard package.inboxItems.contains(where: { $0.title == "Clarify weekly review inbox item" }) else {
            throw FlowDataError.message("Expected weekly review package to include inbox cleanup candidates.")
        }
        guard package.upcomingDeadlines.contains(where: { $0.id == "due-1" }) else {
            throw FlowDataError.message("Expected weekly review package to include upcoming deadlines.")
        }
        guard package.projectHealth.contains(where: { $0.statusLabel == "No active projects" }) else {
            throw FlowDataError.message("Expected weekly review package to include project health.")
        }

        let archiveActionIDs = package.cleanupActions
            .filter { $0.kind == "archive_stale_item" && $0.targetIDs.contains("stale-1") }
            .map(\.id)
        guard archiveActionIDs.isEmpty == false else {
            throw FlowDataError.message("Expected weekly review package to propose stale-item cleanup actions.")
        }

        let allActionIDs = package.cleanupActions.map(\.id)
        try repository.applyWeeklyReviewActions(actionIDs: allActionIDs, referenceDate: referenceDate)

        let result = try withDatabase(at: databaseURL) { db in
            (
                try fetchStatus(db: db, id: "stale-1"),
                try countReviewMutations(db: db, targetID: "stale-1"),
                try countAllReviewMutations(db: db)
            )
        }
        guard result.0 == "archived" else {
            throw FlowDataError.message("Expected weekly review batch cleanup to archive accepted stale items.")
        }
        guard result.1 == archiveActionIDs.count else {
            throw FlowDataError.message("Expected weekly review cleanup to record mutation audit rows.")
        }
        guard result.2 >= allActionIDs.count else {
            throw FlowDataError.message("Expected every accepted weekly review action to have an audit record.")
        }

    }

    private static func smokeTestProjectNextActionProposalConfirmation() throws {
        let databaseURL = temporaryDatabaseURL()
        let repository = LegacyFlowRepository(databaseURL: databaseURL)
        let referenceDate = ISO8601DateFormatter().date(from: "2026-03-22T09:00:00Z")!
        _ = try repository.loadWorkspaceSnapshot()

        try withDatabase(at: databaseURL) { db in
            try insertItem(
                db: db,
                id: "project-1",
                type: "project",
                title: "Launch prep",
                status: "active",
                parentID: nil,
                dueDate: nil,
                createdAt: "2026-03-10T09:00:00+00:00",
                updatedAt: "2026-03-20T09:00:00+00:00"
            )
        }

        let initialPackage = try repository.loadWeeklyReviewPackage(referenceDate: referenceDate)
        guard initialPackage.cleanupActions.contains(where: {
            $0.kind == "project_next_action_review" && $0.targetIDs.contains("project-1")
        }) else {
            throw FlowDataError.message("Expected weekly review package to flag projects missing a next action.")
        }

        let turn = try repository.proposeProjectNextActionReview(projectID: "project-1")
        guard turn.proposalStatus == "pending", turn.proposal?.actionType == "create_task" else {
            throw FlowDataError.message("Expected project next-action review to create a pending assistant proposal.")
        }

        let confirmation = try repository.confirmAssistantProposal(turnID: turn.id)
        guard confirmation.contains("Launch prep") else {
            throw FlowDataError.message("Expected project next-action confirmation to mention the target project.")
        }

        let refreshedPackage = try repository.loadWeeklyReviewPackage(referenceDate: referenceDate)
        guard refreshedPackage.cleanupActions.contains(where: {
            $0.kind == "project_next_action_review" && $0.targetIDs.contains("project-1")
        }) == false else {
            throw FlowDataError.message("Expected confirmed project next action to remove the missing-next-action review prompt.")
        }
        guard refreshedPackage.projectHealth.contains(where: {
            $0.id == "project-1" && $0.detail.contains("Next action:")
        }) else {
            throw FlowDataError.message("Expected project health to expose the newly created next action after confirmation.")
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
            throw FlowDataError.message("Unable to open weekly review smoke test database.")
        }
        defer { sqlite3_close(db) }
        return try block(db)
    }

    private static func insertItem(
        db: OpaquePointer?,
        id: String,
        type: String,
        title: String,
        status: String,
        parentID: String?,
        dueDate: String?,
        createdAt: String,
        updatedAt: String
    ) throws {
        let sql = """
            INSERT INTO items (
                id, type, title, status, context_tags, parent_id, created_at, due_date,
                meta_payload, original_ek_id, estimated_duration, updated_at
            ) VALUES (?, ?, ?, ?, '[]', ?, ?, ?, '{}', NULL, NULL, ?)
        """
        var statement: OpaquePointer?
        guard sqlite3_prepare_v2(db, sql, -1, &statement, nil) == SQLITE_OK else {
            throw FlowDataError.message("Unable to prepare weekly review setup insert.")
        }
        defer { sqlite3_finalize(statement) }

        sqlite3_bind_text(statement, 1, id, -1, sqliteTransient)
        sqlite3_bind_text(statement, 2, type, -1, sqliteTransient)
        sqlite3_bind_text(statement, 3, title, -1, sqliteTransient)
        sqlite3_bind_text(statement, 4, status, -1, sqliteTransient)
        if let parentID {
            sqlite3_bind_text(statement, 5, parentID, -1, sqliteTransient)
        } else {
            sqlite3_bind_null(statement, 5)
        }
        sqlite3_bind_text(statement, 6, createdAt, -1, sqliteTransient)
        if let dueDate {
            sqlite3_bind_text(statement, 7, dueDate, -1, sqliteTransient)
        } else {
            sqlite3_bind_null(statement, 7)
        }
        sqlite3_bind_text(statement, 8, updatedAt, -1, sqliteTransient)

        guard sqlite3_step(statement) == SQLITE_DONE else {
            throw FlowDataError.message("Unable to insert weekly review setup item.")
        }
    }

    private static func fetchStatus(db: OpaquePointer?, id: String) throws -> String {
        let sql = "SELECT status FROM items WHERE id = ?"
        var statement: OpaquePointer?
        guard sqlite3_prepare_v2(db, sql, -1, &statement, nil) == SQLITE_OK else {
            throw FlowDataError.message("Unable to prepare weekly review status query.")
        }
        defer { sqlite3_finalize(statement) }

        sqlite3_bind_text(statement, 1, id, -1, sqliteTransient)
        guard sqlite3_step(statement) == SQLITE_ROW else {
            throw FlowDataError.message("Expected weekly review item status row.")
        }
        return String(cString: sqlite3_column_text(statement, 0))
    }

    private static func countReviewMutations(db: OpaquePointer?, targetID: String) throws -> Int {
        let sql = """
            SELECT COUNT(*)
            FROM mutation_records mr
            JOIN mutation_batches mb ON mb.id = mr.batch_id
            WHERE mb.source = 'weekly_review' AND mr.target_id = ?
        """
        var statement: OpaquePointer?
        guard sqlite3_prepare_v2(db, sql, -1, &statement, nil) == SQLITE_OK else {
            throw FlowDataError.message("Unable to prepare weekly review mutation query.")
        }
        defer { sqlite3_finalize(statement) }

        sqlite3_bind_text(statement, 1, targetID, -1, sqliteTransient)
        guard sqlite3_step(statement) == SQLITE_ROW else {
            throw FlowDataError.message("Expected weekly review mutation count.")
        }
        return Int(sqlite3_column_int(statement, 0))
    }

    private static func countAllReviewMutations(db: OpaquePointer?) throws -> Int {
        let sql = """
            SELECT COUNT(*)
            FROM mutation_records mr
            JOIN mutation_batches mb ON mb.id = mr.batch_id
            WHERE mb.source = 'weekly_review'
        """
        var statement: OpaquePointer?
        guard sqlite3_prepare_v2(db, sql, -1, &statement, nil) == SQLITE_OK else {
            throw FlowDataError.message("Unable to prepare all weekly review mutation query.")
        }
        defer { sqlite3_finalize(statement) }

        guard sqlite3_step(statement) == SQLITE_ROW else {
            throw FlowDataError.message("Expected all weekly review mutation count.")
        }
        return Int(sqlite3_column_int(statement, 0))
    }
}

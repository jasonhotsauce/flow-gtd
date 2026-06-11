import Foundation
import SQLite3

enum SidecarWriteRepositorySmokeTests {
    private static let sqliteTransient = unsafeBitCast(-1, to: sqlite3_destructor_type.self)

    static func run() throws {
        try smokeTestSidecarRepositoryOwnsWriteFlows()
        try smokeTestSidecarWriteFailureDoesNotFallBackToLegacy()
    }

    private static func smokeTestSidecarRepositoryOwnsWriteFlows() throws {
        let databaseURL = temporaryDatabaseURL()
        let legacy = LegacyFlowRepository(databaseURL: databaseURL)
        _ = try legacy.loadWorkspaceSnapshot()

        let repository = SidecarFlowRepository(
            fallback: legacy,
            environment: ["FLOW_DB_PATH": databaseURL.path]
        )

        let captured = try repository.capture(title: "Draft sidecar write migration")
        try repository.clarifyCapture(
            id: captured.id,
            title: "Draft sidecar write migration plan",
            destination: .task,
            projectTitle: "TypeScript Rewrite"
        )
        try repository.saveDailyPlan(
            planDate: "2026-05-02",
            topItemIDs: [captured.id],
            bonusItemIDs: []
        )
        let dailyPlanBeforeCompletion = try repository.loadDailyPlanState(planDate: "2026-05-02")
        guard dailyPlanBeforeCompletion.topItems.map(\.id) == [captured.id] else {
            throw FlowDataError.message("Expected sidecar-owned daily plan save to persist accepted ordering before task completion.")
        }
        try repository.markTaskDone(id: captured.id)

        let projectCapture = try repository.capture(title: "Promote into a project")
        try repository.clarifyCapture(
            id: projectCapture.id,
            title: "Project Promotion",
            destination: .project,
            projectTitle: nil
        )
        let directProjectTask = try repository.createProjectTask(
            projectID: projectCapture.id,
            title: "Draft project launch checklist"
        )
        let linkedTask = try repository.capture(title: "Link this existing task")
        try repository.clarifyCapture(
            id: linkedTask.id,
            title: "Link this existing task",
            destination: .task,
            projectTitle: nil
        )
        try repository.assignTaskToProject(taskID: linkedTask.id, projectID: projectCapture.id)

        let memory = try repository.createMemoryRecord(
            kind: "explicit_preference",
            scope: "global",
            value: "Protect mornings for strategy work.",
            source: "manual",
            confidence: 1.0,
            scopeRef: nil
        )
        try repository.updateMemoryRecord(id: memory.id, value: "Protect afternoons for meetings.")
        try repository.setMemoryRecordEnabled(id: memory.id, enabled: false)

        let stale = try repository.capture(title: "Archive from weekly review")
        try withDatabase(at: databaseURL) { db in
            try updateSeedItem(
                db: db,
                id: stale.id,
                type: "action",
                status: "active",
                updatedAt: "2026-04-01T08:00:00.000Z"
            )
        }
        let weeklyReview = try repository.loadWeeklyReviewPackage(
            referenceDate: ISO8601DateFormatter().date(from: "2026-05-02T10:00:00+00:00") ?? Date()
        )
        guard let archiveAction = weeklyReview.cleanupActions.first(where: {
            $0.kind == "archive_stale_item" && $0.targetIDs.contains(stale.id)
        }) else {
            throw FlowDataError.message("Expected seeded stale task to produce an archive weekly review action.")
        }
        try repository.applyWeeklyReviewActions(
            actionIDs: [archiveAction.id],
            referenceDate: ISO8601DateFormatter().date(from: "2026-05-02T10:00:00+00:00") ?? Date()
        )
        try repository.updateNotificationPermissionStatus("authorized")
        try repository.deleteMemoryRecord(id: memory.id)

        let snapshot = try repository.loadWorkspaceSnapshot()
        let notificationPolicy = try repository.loadNotificationPolicy()
        let allMemory = try repository.listMemoryRecords(query: nil, includeDisabled: true)

        guard snapshot.projects.contains(where: { $0.title == "TypeScript Rewrite" }) else {
            throw FlowDataError.message("Expected sidecar-owned clarify flow to create the project item.")
        }
        guard snapshot.projects.contains(where: { $0.id == projectCapture.id && $0.title == "Project Promotion" }) else {
            throw FlowDataError.message("Expected sidecar-owned project clarify flow to work without an optional project title payload.")
        }
        guard snapshot.projects.contains(where: { project in
            project.id == projectCapture.id
                && project.tasks.contains(where: { $0.id == directProjectTask.id && $0.projectID == projectCapture.id })
        }) else {
            throw FlowDataError.message("Expected sidecar-owned direct project task creation to link the new task to the selected project.")
        }
        guard snapshot.projects.contains(where: { project in
            project.id == projectCapture.id
                && project.tasks.contains(where: { $0.id == linkedTask.id && $0.projectID == projectCapture.id })
        }) else {
            throw FlowDataError.message("Expected sidecar-owned task project assignment to link the existing task to the selected project.")
        }
        guard snapshot.projects.flatMap(\.tasks).contains(where: { $0.id == captured.id && $0.status == .done }) else {
            throw FlowDataError.message("Expected sidecar-owned task status updates to persist through the sidecar repository.")
        }
        guard notificationPolicy.permissionStatus == "authorized" else {
            throw FlowDataError.message("Expected sidecar-owned notification permission update to persist.")
        }
        guard allMemory.contains(where: { $0.id == memory.id }) == false else {
            throw FlowDataError.message("Expected sidecar-owned memory delete to remove the entry.")
        }

        let stalePackage = try repository.loadWeeklyReviewPackage(
            referenceDate: ISO8601DateFormatter().date(from: "2026-05-02T10:00:00+00:00") ?? Date()
        )
        guard stalePackage.staleItems.contains(where: { $0.id == stale.id }) == false else {
            throw FlowDataError.message("Expected sidecar-owned weekly review archive action to remove the stale task from active review state.")
        }
    }

    private static func smokeTestSidecarWriteFailureDoesNotFallBackToLegacy() throws {
        let databaseURL = temporaryDatabaseURL()
        let legacy = LegacyFlowRepository(databaseURL: databaseURL)
        _ = try legacy.loadWorkspaceSnapshot()

        let repository = SidecarFlowRepository(
            fallback: legacy,
            mutationClient: ThrowingSidecarMutationClient(),
            environment: ["FLOW_DB_PATH": databaseURL.path]
        )

        do {
            _ = try repository.capture(title: "Should not fall back")
            throw FlowDataError.message("Expected sidecar write failure to surface instead of mutating through legacy fallback.")
        } catch {}

        let itemCount = try withDatabase(at: databaseURL) { db in
            try countRows(db: db, table: "items")
        }
        guard itemCount == 0 else {
            throw FlowDataError.message("Expected failed sidecar writes to avoid mutating the underlying database.")
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
            throw FlowDataError.message("Unable to open sidecar write repository smoke database.")
        }
        defer { sqlite3_close(db) }
        return try block(db)
    }

    private static func exec(_ db: OpaquePointer?, _ sql: String) throws {
        var errorPointer: UnsafeMutablePointer<Int8>?
        guard sqlite3_exec(db, sql, nil, nil, &errorPointer) == SQLITE_OK else {
            let fallback = errorPointer.map { String(cString: $0) } ?? "SQLite execution error."
            sqlite3_free(errorPointer)
            throw FlowDataError.message(fallback)
        }
    }

    private static func updateSeedItem(
        db: OpaquePointer?,
        id: String,
        type: String,
        status: String,
        updatedAt: String
    ) throws {
        let sql = "UPDATE items SET type = ?, status = ?, updated_at = ? WHERE id = ?"
        var statement: OpaquePointer?
        guard sqlite3_prepare_v2(db, sql, -1, &statement, nil) == SQLITE_OK else {
            throw FlowDataError.message("Unable to prepare sidecar write repository seed update.")
        }
        defer { sqlite3_finalize(statement) }

        sqlite3_bind_text(statement, 1, type, -1, sqliteTransient)
        sqlite3_bind_text(statement, 2, status, -1, sqliteTransient)
        sqlite3_bind_text(statement, 3, updatedAt, -1, sqliteTransient)
        sqlite3_bind_text(statement, 4, id, -1, sqliteTransient)

        guard sqlite3_step(statement) == SQLITE_DONE else {
            throw FlowDataError.message("Unable to update sidecar write repository seed item.")
        }
    }

    private static func countRows(db: OpaquePointer?, table: String) throws -> Int {
        let sql = "SELECT COUNT(*) FROM \(table)"
        var statement: OpaquePointer?
        guard sqlite3_prepare_v2(db, sql, -1, &statement, nil) == SQLITE_OK else {
            throw FlowDataError.message("Unable to prepare count query for \(table).")
        }
        defer { sqlite3_finalize(statement) }
        guard sqlite3_step(statement) == SQLITE_ROW else {
            throw FlowDataError.message("Unable to count rows in \(table).")
        }
        return Int(sqlite3_column_int(statement, 0))
    }
}

private struct ThrowingSidecarMutationClient: SidecarMutationClient {
    func mutatePayload<Payload: Decodable>(
        configuration: SidecarLaunchConfiguration,
        timeout: TimeInterval,
        as type: Payload.Type
    ) throws -> Payload {
        throw FlowDataError.message("synthetic sidecar mutation failure")
    }
}

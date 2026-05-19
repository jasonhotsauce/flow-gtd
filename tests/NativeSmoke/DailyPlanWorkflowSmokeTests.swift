import Foundation
import SQLite3

@MainActor
enum DailyPlanWorkflowSmokeTests {
    static func run() throws {
        try smokeTestDailyPlanDateUsesProvidedLocalTimeZone()
        try smokeTestDailyPlanCandidatesAndAcceptance()
    }

    private static let sqliteTransient = unsafeBitCast(-1, to: sqlite3_destructor_type.self)

    private static func smokeTestDailyPlanDateUsesProvidedLocalTimeZone() throws {
        let service = DailyPlanWorkflowService(repository: LegacyFlowRepository(databaseURL: temporaryDatabaseURL()))
        let formatter = ISO8601DateFormatter()
        guard let instant = formatter.date(from: "2026-03-08T07:30:00Z") else {
            throw FlowDataError.message("Unable to construct daily plan date smoke test instant.")
        }
        guard let pacific = TimeZone(identifier: "America/Los_Angeles") else {
            throw FlowDataError.message("Unable to construct Pacific time zone for daily plan smoke test.")
        }

        let planDate = service.planDateString(for: instant, timeZone: pacific)

        guard planDate == "2026-03-07" else {
            throw FlowDataError.message("Expected daily plan date keys to use the user's local calendar day.")
        }
    }

    private static func smokeTestDailyPlanCandidatesAndAcceptance() throws {
        let databaseURL = temporaryDatabaseURL()
        let repository = LegacyFlowRepository(databaseURL: databaseURL)
        _ = try repository.capture(title: "Clarify native app launch notes")

        try withDatabase(at: databaseURL) { db in
            try insertItem(
                db: db,
                id: "due-task-1",
                type: "action",
                title: "Ship beta notes",
                status: "active",
                parentID: nil,
                dueDate: "2026-03-08T09:00:00+00:00"
            )
            try insertItem(
                db: db,
                id: "ready-task-1",
                type: "action",
                title: "Tighten review copy",
                status: "active",
                parentID: nil,
                dueDate: nil
            )
            try insertItem(
                db: db,
                id: "project-1",
                type: "project",
                title: "Native Launch",
                status: "active",
                parentID: nil,
                dueDate: nil
            )
            try insertItem(
                db: db,
                id: "project-task-1",
                type: "action",
                title: "Draft rollout notes",
                status: "active",
                parentID: "project-1",
                dueDate: nil
            )
        }

        var state = try repository.loadDailyPlanState(planDate: "2026-03-08")

        guard state.mustAddress.contains(where: { $0.id == "due-task-1" }) else {
            throw FlowDataError.message("Expected due actions to appear in must-address daily plan candidates.")
        }
        guard state.inbox.contains(where: { $0.source == .capture }) else {
            throw FlowDataError.message("Expected inbox captures to appear in daily plan candidates.")
        }
        guard state.readyActions.contains(where: { $0.id == "ready-task-1" }) else {
            throw FlowDataError.message("Expected ungrouped active actions to appear in ready-actions candidates.")
        }
        guard state.projectTasks.contains(where: { $0.id == "project-task-1" }) else {
            throw FlowDataError.message("Expected project-linked actions to appear in project-task candidates.")
        }
        guard state.calendarStatus.localizedCaseInsensitiveContains("calendar") else {
            throw FlowDataError.message("Expected daily plan state to expose a calendar/degraded reasoning note.")
        }

        try repository.saveDailyPlan(
            planDate: "2026-03-08",
            topItemIDs: ["due-task-1", "ready-task-1"],
            bonusItemIDs: ["project-task-1"]
        )
        state = try repository.loadDailyPlanState(planDate: "2026-03-08")

        guard state.topItems.map(\.id) == ["due-task-1", "ready-task-1"] else {
            throw FlowDataError.message("Expected accepted daily plan top items to persist in order.")
        }
        guard state.bonusItems.map(\.id) == ["project-task-1"] else {
            throw FlowDataError.message("Expected accepted daily plan bonus items to persist in order.")
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
            throw FlowDataError.message("Unable to open daily plan smoke test database.")
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
        dueDate: String?
    ) throws {
        let sql = """
            INSERT INTO items (
                id, type, title, status, context_tags, parent_id, created_at, due_date,
                meta_payload, original_ek_id, estimated_duration, updated_at
            ) VALUES (?, ?, ?, ?, '[]', ?, '2026-03-08T08:00:00+00:00', ?, '{}', NULL, NULL, '2026-03-08T08:00:00+00:00')
        """
        var statement: OpaquePointer?
        guard sqlite3_prepare_v2(db, sql, -1, &statement, nil) == SQLITE_OK else {
            throw FlowDataError.message("Unable to prepare daily plan setup insert.")
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
        if let dueDate {
            sqlite3_bind_text(statement, 6, dueDate, -1, sqliteTransient)
        } else {
            sqlite3_bind_null(statement, 6)
        }

        guard sqlite3_step(statement) == SQLITE_DONE else {
            throw FlowDataError.message("Unable to insert daily plan setup item.")
        }
    }
}

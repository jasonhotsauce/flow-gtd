import Foundation
import SQLite3

enum NotificationPolicySmokeTests {
    private static let sqliteTransient = unsafeBitCast(-1, to: sqlite3_destructor_type.self)

    static func run() throws {
        try smokeTestNotificationPolicyPermissionAndDegradedState()
    }

    private static func smokeTestNotificationPolicyPermissionAndDegradedState() throws {
        let databaseURL = temporaryDatabaseURL()
        let repository = LegacyFlowRepository(databaseURL: databaseURL)
        _ = try repository.loadWorkspaceSnapshot()

        var policy = try repository.loadNotificationPolicy()
        guard policy.permissionStatus == "not_determined" else {
            throw FlowDataError.message("Expected notification policy to default to not_determined permission.")
        }
        guard policy.deliveryMode == "degraded" else {
            throw FlowDataError.message("Expected notification delivery to degrade before permission is granted.")
        }
        guard policy.degradedReasons.isEmpty == false else {
            throw FlowDataError.message("Expected notification policy to explain degraded delivery.")
        }

        try repository.updateNotificationPermissionStatus("denied")
        policy = try repository.loadNotificationPolicy()
        guard policy.permissionStatus == "denied" else {
            throw FlowDataError.message("Expected notification permission status to persist denied state.")
        }
        guard policy.degradedReasons.contains(where: { $0.localizedCaseInsensitiveContains("denied") }) else {
            throw FlowDataError.message("Expected denied notification permission to surface a degraded reason.")
        }

        try withDatabase(at: databaseURL) { db in
            try insertReminderCandidate(db: db, id: "notify-1", title: "Prepare reminder policy review")
        }
        try repository.updateNotificationPermissionStatus("authorized")
        policy = try repository.loadNotificationPolicy()

        guard policy.deliveryMode == "flow_owned_local" else {
            throw FlowDataError.message("Expected authorized notification policy to use Flow-owned local delivery.")
        }
        guard policy.pendingNotifications.contains(where: { $0.taskID == "notify-1" }) else {
            throw FlowDataError.message("Expected due tasks to appear as pending Flow-owned notification candidates.")
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
            throw FlowDataError.message("Unable to open notification policy smoke test database.")
        }
        defer { sqlite3_close(db) }
        return try block(db)
    }

    private static func insertReminderCandidate(db: OpaquePointer?, id: String, title: String) throws {
        let sql = """
            INSERT INTO items (
                id, type, title, status, context_tags, parent_id, created_at, due_date,
                meta_payload, original_ek_id, estimated_duration, updated_at
            ) VALUES (?, 'action', ?, 'active', '[]', NULL, '2026-03-08T08:00:00+00:00',
                '2026-03-08T09:00:00+00:00', '{}', NULL, 30, '2026-03-08T08:00:00+00:00')
        """
        var statement: OpaquePointer?
        guard sqlite3_prepare_v2(db, sql, -1, &statement, nil) == SQLITE_OK else {
            throw FlowDataError.message("Unable to prepare notification candidate insert.")
        }
        defer { sqlite3_finalize(statement) }

        sqlite3_bind_text(statement, 1, id, -1, sqliteTransient)
        sqlite3_bind_text(statement, 2, title, -1, sqliteTransient)

        guard sqlite3_step(statement) == SQLITE_DONE else {
            throw FlowDataError.message("Unable to insert notification candidate.")
        }
    }
}

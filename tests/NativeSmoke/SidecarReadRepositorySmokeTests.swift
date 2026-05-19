import Foundation
import SQLite3

enum SidecarReadRepositorySmokeTests {
    private static let sqliteTransient = unsafeBitCast(-1, to: sqlite3_destructor_type.self)

    static func run() throws {
        try smokeTestSidecarRepositoryLoadsWorkspaceAndDailyPlan()
        try smokeTestSidecarRepositoryFallsBackToLegacyRead()
    }

    private static func smokeTestSidecarRepositoryLoadsWorkspaceAndDailyPlan() throws {
        let databaseURL = temporaryDatabaseURL()
        let legacy = LegacyFlowRepository(databaseURL: databaseURL)
        _ = try legacy.loadWorkspaceSnapshot()

        try withDatabase(at: databaseURL) { db in
            try insertSeedItem(
                db: db,
                id: "sidecar-project-1",
                type: "project",
                title: "Ship sidecar reads",
                status: "active",
                parentID: nil,
                dueDate: nil,
                createdAt: "2026-05-02T08:00:00+00:00",
                updatedAt: "2026-05-02T08:00:00+00:00"
            )
            try insertSeedItem(
                db: db,
                id: "sidecar-action-1",
                type: "action",
                title: "Wire read repository",
                status: "active",
                parentID: "sidecar-project-1",
                dueDate: "2026-05-03T09:00:00+00:00",
                createdAt: "2026-05-02T08:10:00+00:00",
                updatedAt: "2026-05-02T08:10:00+00:00"
            )
            try insertSeedItem(
                db: db,
                id: "sidecar-inbox-1",
                type: "inbox",
                title: "Clarify bridge fallback",
                status: "active",
                parentID: nil,
                dueDate: nil,
                createdAt: "2026-05-02T08:20:00+00:00",
                updatedAt: "2026-05-02T08:20:00+00:00"
            )
            try insertDailyPlanEntry(
                db: db,
                planDate: "2026-05-02",
                itemID: "sidecar-action-1",
                bucket: "top",
                position: 1,
                createdAt: "2026-05-02T08:30:00+00:00"
            )
            try insertAssistantTurn(
                db: db,
                id: "turn-1",
                prompt: "Add a next action",
                response: "I can add it.",
                route: "capture",
                proposalJSON: "{\"action_type\":\"create_task\",\"title\":\"Wire read repository\",\"detail\":\"Add the concrete next step.\",\"requires_confirmation\":true}",
                proposalStatus: "pending",
                createdAt: "2026-05-02T09:00:00+00:00"
            )
            try insertAssistantAuditStep(
                db: db,
                id: "audit-1",
                turnID: "turn-1",
                stage: "provider",
                status: "ok",
                summary: "Codex completed successfully.",
                payloadJSON: "{\"provider\":\"codex\",\"provider_status\":\"success\",\"provider_runtime\":\"codex exec\",\"provider_detail\":\"Codex completed successfully.\"}",
                createdAt: "2026-05-02T09:00:01+00:00"
            )
            try insertAssistantAuditStep(
                db: db,
                id: "audit-2",
                turnID: "turn-1",
                stage: "plan",
                status: "ok",
                summary: "Planned the task.",
                payloadJSON: "{}",
                createdAt: "2026-05-02T09:00:01+00:00"
            )
            try insertMemoryEntry(
                db: db,
                id: "memory-1",
                kind: "planning_preference",
                scope: "global",
                scopeRef: nil,
                value: "Keep daily focus small",
                source: "assistant-chat",
                confidence: 0.9,
                enabled: true,
                createdAt: "2026-05-02T09:10:00+00:00",
                updatedAt: "2026-05-02T09:10:00+00:00"
            )
        }

        try legacy.updateNotificationPermissionStatus("authorized")

        let repository = SidecarFlowRepository(
            fallback: legacy,
            environment: ["FLOW_DB_PATH": databaseURL.path]
        )

        let snapshot = try repository.loadWorkspaceSnapshot()
        let turns = try repository.loadAssistantTurns(limit: 10)
        let memory = try repository.listMemoryRecords(query: nil, includeDisabled: true)
        let dailyPlan = try repository.loadDailyPlanState(planDate: "2026-05-02")
        let weeklyReview = try repository.loadWeeklyReviewPackage(referenceDate: ISO8601DateFormatter().date(from: "2026-05-02T10:00:00+00:00") ?? Date())
        let notificationPolicy = try repository.loadNotificationPolicy()

        guard snapshot.projects.contains(where: { $0.id == "sidecar-project-1" }) else {
            throw FlowDataError.message("Expected sidecar-backed workspace snapshot to include the seeded project.")
        }
        guard snapshot.inboxItems.contains(where: { $0.id == "sidecar-inbox-1" }) else {
            throw FlowDataError.message("Expected sidecar-backed workspace snapshot to include the seeded inbox item.")
        }
        guard dailyPlan.topItems.map(\.id) == ["sidecar-action-1"] else {
            throw FlowDataError.message("Expected sidecar-backed daily plan state to include the seeded top item.")
        }
        guard turns.first?.id == "turn-1" else {
            throw FlowDataError.message("Expected sidecar-backed assistant turns to decode the seeded turn.")
        }
        guard turns.first?.provider == "codex" else {
            throw FlowDataError.message("Expected sidecar-backed assistant turns to preserve provider evidence.")
        }
        guard turns.first?.auditSteps.first?.payload["provider"] == "codex" else {
            throw FlowDataError.message("Expected sidecar-backed assistant audit payload to decode provider details.")
        }
        guard memory.contains(where: { $0.id == "memory-1" }) else {
            throw FlowDataError.message("Expected sidecar-backed memory reads to decode the seeded memory record.")
        }
        guard weeklyReview.projectHealth.contains(where: { $0.id == "sidecar-project-1" }) else {
            throw FlowDataError.message("Expected sidecar-backed weekly review package to include seeded project health.")
        }
        guard notificationPolicy.deliveryMode == "flow_owned_local" else {
            throw FlowDataError.message("Expected sidecar-backed notification policy to reflect authorized local delivery.")
        }
    }

    private static func smokeTestSidecarRepositoryFallsBackToLegacyRead() throws {
        let databaseURL = temporaryDatabaseURL()
        let legacy = LegacyFlowRepository(databaseURL: databaseURL)
        let captured = try legacy.capture(title: "Fallback capture")

        let repository = SidecarFlowRepository(
            fallback: legacy,
            readClient: ThrowingSidecarReadClient(),
            environment: ["FLOW_DB_PATH": databaseURL.path]
        )

        let snapshot = try repository.loadWorkspaceSnapshot()

        guard snapshot.inboxItems.contains(where: { $0.id == captured.id }) else {
            throw FlowDataError.message("Expected sidecar repository to fall back to legacy workspace snapshot reads when sidecar decoding fails.")
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
            throw FlowDataError.message("Unable to open sidecar read repository smoke database.")
        }
        defer { sqlite3_close(db) }
        return try block(db)
    }

    private static func insertSeedItem(
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
            ) VALUES (?, ?, ?, ?, '[]', ?, ?, ?, '{}', NULL, 30, ?)
        """
        var statement: OpaquePointer?
        guard sqlite3_prepare_v2(db, sql, -1, &statement, nil) == SQLITE_OK else {
            throw FlowDataError.message("Unable to prepare sidecar read repository seed insert.")
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
            throw FlowDataError.message("Unable to insert sidecar read repository seed item.")
        }
    }

    private static func insertDailyPlanEntry(
        db: OpaquePointer?,
        planDate: String,
        itemID: String,
        bucket: String,
        position: Int,
        createdAt: String
    ) throws {
        let sql = """
            INSERT INTO daily_plan_entries (plan_date, item_id, bucket, position, created_at)
            VALUES (?, ?, ?, ?, ?)
        """
        var statement: OpaquePointer?
        guard sqlite3_prepare_v2(db, sql, -1, &statement, nil) == SQLITE_OK else {
            throw FlowDataError.message("Unable to prepare sidecar read repository daily plan insert.")
        }
        defer { sqlite3_finalize(statement) }

        sqlite3_bind_text(statement, 1, planDate, -1, sqliteTransient)
        sqlite3_bind_text(statement, 2, itemID, -1, sqliteTransient)
        sqlite3_bind_text(statement, 3, bucket, -1, sqliteTransient)
        sqlite3_bind_int(statement, 4, Int32(position))
        sqlite3_bind_text(statement, 5, createdAt, -1, sqliteTransient)

        guard sqlite3_step(statement) == SQLITE_DONE else {
            throw FlowDataError.message("Unable to insert sidecar read repository daily plan entry.")
        }
    }

    private static func insertAssistantTurn(
        db: OpaquePointer?,
        id: String,
        prompt: String,
        response: String,
        route: String,
        proposalJSON: String,
        proposalStatus: String,
        createdAt: String
    ) throws {
        let sql = """
            INSERT INTO assistant_turns (
                id, prompt, response, route, proposal_json, proposal_status, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """
        var statement: OpaquePointer?
        guard sqlite3_prepare_v2(db, sql, -1, &statement, nil) == SQLITE_OK else {
            throw FlowDataError.message("Unable to prepare sidecar read repository assistant turn insert.")
        }
        defer { sqlite3_finalize(statement) }

        sqlite3_bind_text(statement, 1, id, -1, sqliteTransient)
        sqlite3_bind_text(statement, 2, prompt, -1, sqliteTransient)
        sqlite3_bind_text(statement, 3, response, -1, sqliteTransient)
        sqlite3_bind_text(statement, 4, route, -1, sqliteTransient)
        sqlite3_bind_text(statement, 5, proposalJSON, -1, sqliteTransient)
        sqlite3_bind_text(statement, 6, proposalStatus, -1, sqliteTransient)
        sqlite3_bind_text(statement, 7, createdAt, -1, sqliteTransient)
        sqlite3_bind_text(statement, 8, createdAt, -1, sqliteTransient)

        guard sqlite3_step(statement) == SQLITE_DONE else {
            throw FlowDataError.message("Unable to insert sidecar read repository assistant turn.")
        }
    }

    private static func insertAssistantAuditStep(
        db: OpaquePointer?,
        id: String,
        turnID: String,
        stage: String,
        status: String,
        summary: String,
        payloadJSON: String,
        createdAt: String
    ) throws {
        let sql = """
            INSERT INTO assistant_audit_steps (
                id, turn_id, stage, status, summary, payload_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """
        var statement: OpaquePointer?
        guard sqlite3_prepare_v2(db, sql, -1, &statement, nil) == SQLITE_OK else {
            throw FlowDataError.message("Unable to prepare sidecar read repository assistant audit insert.")
        }
        defer { sqlite3_finalize(statement) }

        sqlite3_bind_text(statement, 1, id, -1, sqliteTransient)
        sqlite3_bind_text(statement, 2, turnID, -1, sqliteTransient)
        sqlite3_bind_text(statement, 3, stage, -1, sqliteTransient)
        sqlite3_bind_text(statement, 4, status, -1, sqliteTransient)
        sqlite3_bind_text(statement, 5, summary, -1, sqliteTransient)
        sqlite3_bind_text(statement, 6, payloadJSON, -1, sqliteTransient)
        sqlite3_bind_text(statement, 7, createdAt, -1, sqliteTransient)

        guard sqlite3_step(statement) == SQLITE_DONE else {
            throw FlowDataError.message("Unable to insert sidecar read repository assistant audit step.")
        }
    }

    private static func insertMemoryEntry(
        db: OpaquePointer?,
        id: String,
        kind: String,
        scope: String,
        scopeRef: String?,
        value: String,
        source: String,
        confidence: Double,
        enabled: Bool,
        createdAt: String,
        updatedAt: String
    ) throws {
        let sql = """
            INSERT INTO memory_entries (
                id, kind, scope, scope_ref, value, source, confidence, enabled, created_at, updated_at, last_confirmed_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        var statement: OpaquePointer?
        guard sqlite3_prepare_v2(db, sql, -1, &statement, nil) == SQLITE_OK else {
            throw FlowDataError.message("Unable to prepare sidecar read repository memory insert.")
        }
        defer { sqlite3_finalize(statement) }

        sqlite3_bind_text(statement, 1, id, -1, sqliteTransient)
        sqlite3_bind_text(statement, 2, kind, -1, sqliteTransient)
        sqlite3_bind_text(statement, 3, scope, -1, sqliteTransient)
        if let scopeRef {
            sqlite3_bind_text(statement, 4, scopeRef, -1, sqliteTransient)
        } else {
            sqlite3_bind_null(statement, 4)
        }
        sqlite3_bind_text(statement, 5, value, -1, sqliteTransient)
        sqlite3_bind_text(statement, 6, source, -1, sqliteTransient)
        sqlite3_bind_double(statement, 7, confidence)
        sqlite3_bind_int(statement, 8, enabled ? 1 : 0)
        sqlite3_bind_text(statement, 9, createdAt, -1, sqliteTransient)
        sqlite3_bind_text(statement, 10, updatedAt, -1, sqliteTransient)
        sqlite3_bind_text(statement, 11, updatedAt, -1, sqliteTransient)

        guard sqlite3_step(statement) == SQLITE_DONE else {
            throw FlowDataError.message("Unable to insert sidecar read repository memory entry.")
        }
    }
}

private struct ThrowingSidecarReadClient: SidecarReadClient {
    func readPayload<Payload>(
        configuration: SidecarLaunchConfiguration,
        timeout: TimeInterval,
        as type: Payload.Type
    ) throws -> Payload where Payload : Decodable {
        throw FlowDataError.message("Injected sidecar read failure")
    }
}

import Foundation
import SQLite3

enum SidecarAssistantRepositorySmokeTests {
    private static let sqliteTransient = unsafeBitCast(-1, to: sqlite3_destructor_type.self)

    static func run() throws {
        try smokeTestAssistantSessionMessageSidecarContractNames()
        try smokeTestSidecarAssistantSessionMessageBoundaryContract()
        try smokeTestSidecarAssistantRuntimeRequestShapes()
        try smokeTestSidecarAssistantCaptureProposalRoundTrip()
        try smokeTestSidecarAssistantDismissLeavesMemoryUntouched()
        try smokeTestSidecarAssistantUndoRevertsLastSafeWrite()
        try smokeTestSidecarProjectNextActionReviewFlow()
    }

    private static func smokeTestAssistantSessionMessageSidecarContractNames() throws {
        guard AssistantSessionMessageSidecarContract.assistantSessionsReadKind == "assistant-sessions",
              AssistantSessionMessageSidecarContract.assistantMessagesReadKind == "assistant-messages",
              AssistantSessionMessageSidecarContract.createSessionMode == "create-session",
              AssistantSessionMessageSidecarContract.sendMessageMode == "send-message",
              AssistantSessionMessageSidecarContract.confirmMessageProposalMode == "confirm-message-proposal",
              AssistantSessionMessageSidecarContract.dismissMessageProposalMode == "dismiss-message-proposal",
              AssistantSessionMessageSidecarContract.sessionMessagePayloadKeys == ["sessionID", "prompt", "planDate", "messageID"] else {
            throw FlowDataError.message("Expected the session/message sidecar contract names and payload keys to stay pinned for AST-03R.")
        }
    }

    private static func smokeTestSidecarAssistantSessionMessageBoundaryContract() throws {
        let databaseURL = temporaryDatabaseURL()
        let store = RecordingAssistantStore()
        let repository = SidecarFlowRepository(
            fallback: LegacyFlowRepository(databaseURL: databaseURL),
            readClient: RecordingSidecarReadClient(store: store),
            mutationClient: RecordingSidecarMutationClient(store: store),
            environment: [
                "FLOW_DB_PATH": databaseURL.path,
                "FLOW_AGENT_RUNTIME_PROVIDER": "deterministic"
            ]
        )

        let session = try repository.createAssistantSession(title: "Plan my day")
        let message = try repository.sendAssistantMessage(
            sessionID: session.id,
            prompt: "Add review the launch checklist.",
            planDate: "2026-03-08"
        )

        let sessions = try repository.loadAssistantSessions(limit: 10)
        guard sessions.first?.id == session.id else {
            throw FlowDataError.message("Expected the sidecar repository to expose the created assistant session.")
        }

        let messages = try repository.loadAssistantMessages(sessionID: session.id, limit: 10)
        guard messages.map(\.role) == ["user", "assistant"] else {
            throw FlowDataError.message("Expected the sidecar repository to expose the new assistant session messages in order.")
        }

        _ = try repository.confirmAssistantMessageProposal(messageID: message.id)
        do {
            try repository.dismissAssistantMessageProposal(messageID: message.id)
            throw FlowDataError.message("Expected dismissing a confirmed assistant proposal to fail.")
        } catch {
            guard String(describing: error).localizedCaseInsensitiveContains("pending") else {
                throw error
            }
        }

        let updatedMessages = try repository.loadAssistantMessages(sessionID: session.id, limit: 10)
        guard updatedMessages.first(where: { $0.role == "assistant" })?.proposalStatus == "confirmed" else {
            throw FlowDataError.message("Expected the sidecar repository to keep a confirmed assistant message confirmed until undo.")
        }
    }

    private static func smokeTestSidecarAssistantRuntimeRequestShapes() throws {
        let databaseURL = temporaryDatabaseURL()
        let store = RecordingAssistantStore()
        let readClient = RecordingSidecarReadClient(store: store)
        let mutationClient = RecordingSidecarMutationClient(store: store)
        let repository = SidecarFlowRepository(
            fallback: LegacyFlowRepository(databaseURL: databaseURL),
            readClient: readClient,
            mutationClient: mutationClient,
            environment: [
                "FLOW_DB_PATH": databaseURL.path,
                "FLOW_AGENT_RUNTIME_PROVIDER": "deterministic"
            ]
        )

        let session = try repository.createAssistantSession(title: "Plan my day")
        let message = try repository.sendAssistantMessage(
            sessionID: session.id,
            prompt: "Add review the launch checklist",
            planDate: "2026-03-08"
        )
        _ = try repository.loadAssistantSessions(limit: 7)
        _ = try repository.loadAssistantMessages(sessionID: session.id, limit: 7)
        _ = try repository.confirmAssistantMessageProposal(messageID: message.id)
        do {
            try repository.dismissAssistantMessageProposal(messageID: message.id)
            throw FlowDataError.message("Expected dismissing a confirmed assistant proposal to fail.")
        } catch {
            guard String(describing: error).localizedCaseInsensitiveContains("pending") else {
                throw error
            }
        }
        _ = try repository.undoLastAssistantMutation()
        _ = try repository.loadAssistantTurns(limit: 7)
        _ = try repository.sendAssistantPrompt("Plan my day", planDate: "2026-03-08")
        _ = try repository.proposeProjectNextActionReview(projectID: "project-1")
        _ = try repository.confirmAssistantProposal(turnID: "turn-1")
        try repository.dismissAssistantProposal(turnID: "turn-2")

        guard readClient.requestKinds == [
            "assistant-sessions",
            "assistant-messages",
            "assistant-turns"
        ] else {
            throw FlowDataError.message("Expected the shipped assistant read path to request the session/message and legacy turn reads in order.")
        }
        guard readClient.assistantTurnLimit == 7 else {
            throw FlowDataError.message("Expected assistant-turn reads to preserve the requested limit.")
        }

        guard mutationClient.writeKinds == [
            "create-session",
            "send-message",
            "confirm-message-proposal",
            "dismiss-message-proposal",
            "undo-last-mutation"
        ] else {
            throw FlowDataError.message("Expected the shipped assistant message writes to use the new session/message sidecar write kinds.")
        }
        guard mutationClient.timeoutByWriteKind["send-message"] == 60.0 else {
            throw FlowDataError.message("Expected assistant message sends to use a longer sidecar timeout than the default 10 seconds.")
        }
        guard mutationClient.timeoutByWriteKind["create-session"] == 10.0 else {
            throw FlowDataError.message("Expected quick assistant session creation to keep the default sidecar timeout.")
        }

        guard mutationClient.assistantModes == [
            "send-prompt",
            "project-next-action-review",
            "confirm-proposal",
            "dismiss-proposal"
        ] else {
            throw FlowDataError.message("Expected the shipped assistant mutation path to send the real runtime modes in order.")
        }

        guard mutationClient.payloadsByMode["send-prompt"]?["prompt"] == "Plan my day" else {
            throw FlowDataError.message("Expected send-prompt to forward the user prompt through the sidecar adapter.")
        }
        guard mutationClient.payloadsByMode["send-prompt"]?["planDate"] == "2026-03-08" else {
            throw FlowDataError.message("Expected send-prompt to forward the plan date through the sidecar adapter.")
        }
        guard mutationClient.payloadsByMode["confirm-proposal"]?["turnID"] == "turn-1" else {
            throw FlowDataError.message("Expected proposal confirmation to target the selected assistant turn id.")
        }
        guard mutationClient.payloadsByMode["dismiss-proposal"]?["turnID"] == "turn-2" else {
            throw FlowDataError.message("Expected proposal dismissal to target the selected assistant turn id.")
        }
        guard mutationClient.payloadsByMode["send-message"]?["sessionID"] == session.id else {
            throw FlowDataError.message("Expected send-message to target the created assistant session id.")
        }
        guard mutationClient.payloadsByMode["confirm-message-proposal"]?["messageID"] == message.id else {
            throw FlowDataError.message("Expected confirm-message-proposal to target the assistant message id.")
        }
        guard mutationClient.payloadsByMode["dismiss-message-proposal"]?["messageID"] == message.id else {
            throw FlowDataError.message("Expected dismiss-message-proposal to target the assistant message id.")
        }
    }

    private static func smokeTestSidecarAssistantCaptureProposalRoundTrip() throws {
        let databaseURL = temporaryDatabaseURL()
        let legacy = LegacyFlowRepository(databaseURL: databaseURL)
        let repository = SidecarFlowRepository(
            fallback: legacy,
            environment: [
                "FLOW_DB_PATH": databaseURL.path,
                "FLOW_AGENT_RUNTIME_PROVIDER": "deterministic"
            ]
        )

        let turn = try repository.sendAssistantPrompt(
            "Add review the launch checklist",
            planDate: "2026-03-08"
        )

        guard turn.route == "capture" else {
            throw FlowDataError.message("Expected sidecar assistant prompt to route to capture.")
        }
        guard turn.proposalStatus == "pending" else {
            throw FlowDataError.message("Expected sidecar capture proposal to stay pending before confirmation.")
        }
        guard turn.proposal?.actionType == "create_task" else {
            throw FlowDataError.message("Expected sidecar capture proposal payload for assistant turn.")
        }
        guard turn.provider == "deterministic" else {
            throw FlowDataError.message("Expected assistant smoke test to preserve the deterministic provider override.")
        }
        guard turn.auditSteps.first(where: { $0.stage == "provider" })?.payload["provider"] == "deterministic" else {
            throw FlowDataError.message("Expected assistant audit payload to preserve the deterministic provider evidence.")
        }

        _ = try repository.confirmAssistantProposal(turnID: turn.id)
        let snapshot = try repository.loadWorkspaceSnapshot()

        guard snapshot.inboxItems.contains(where: { $0.title.localizedCaseInsensitiveContains("review the launch checklist") }) else {
            throw FlowDataError.message("Expected confirmed sidecar assistant capture to create an inbox item.")
        }
    }

    private static func smokeTestSidecarAssistantDismissLeavesMemoryUntouched() throws {
        let databaseURL = temporaryDatabaseURL()
        let legacy = LegacyFlowRepository(databaseURL: databaseURL)
        let repository = SidecarFlowRepository(
            fallback: legacy,
            environment: [
                "FLOW_DB_PATH": databaseURL.path,
                "FLOW_AGENT_RUNTIME_PROVIDER": "deterministic"
            ]
        )

        let turn = try repository.sendAssistantPrompt(
            "Remember that I prefer deep work before lunch.",
            planDate: "2026-03-08"
        )
        try repository.dismissAssistantProposal(turnID: turn.id)
        let turns = try repository.loadAssistantTurns(limit: 5)

        guard turns.first?.proposalStatus == "dismissed" else {
            throw FlowDataError.message("Expected sidecar assistant dismissal to persist dismissed proposal status.")
        }

        let memories = try repository.listMemoryRecords(query: nil, includeDisabled: true)
        guard memories.isEmpty else {
            throw FlowDataError.message("Expected dismissing a sidecar memory proposal to avoid writes.")
        }
    }

    private static func smokeTestSidecarAssistantUndoRevertsLastSafeWrite() throws {
        let databaseURL = temporaryDatabaseURL()
        let legacy = LegacyFlowRepository(databaseURL: databaseURL)
        let repository = SidecarFlowRepository(
            fallback: legacy,
            environment: [
                "FLOW_DB_PATH": databaseURL.path,
                "FLOW_AGENT_RUNTIME_PROVIDER": "deterministic"
            ]
        )

        let turn = try repository.sendAssistantPrompt(
            "Remember that I prefer maker mornings.",
            planDate: "2026-03-08"
        )
        _ = try repository.confirmAssistantProposal(turnID: turn.id)

        guard try repository.listMemoryRecords(query: "maker mornings", includeDisabled: true).count == 1 else {
            throw FlowDataError.message("Expected confirmed sidecar assistant memory proposal to create a memory entry.")
        }

        let undoMessage = try repository.undoLastAssistantMutation()
        guard undoMessage?.localizedCaseInsensitiveContains("undid") == true else {
            throw FlowDataError.message("Expected sidecar assistant undo to report a reverted write.")
        }

        guard try repository.listMemoryRecords(query: "maker mornings", includeDisabled: true).isEmpty else {
            throw FlowDataError.message("Expected sidecar undo to remove the last safe assistant write.")
        }
    }

    private static func smokeTestSidecarProjectNextActionReviewFlow() throws {
        let databaseURL = temporaryDatabaseURL()
        let legacy = LegacyFlowRepository(databaseURL: databaseURL)
        _ = try legacy.loadWorkspaceSnapshot()
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

        let repository = SidecarFlowRepository(
            fallback: legacy,
            environment: [
                "FLOW_DB_PATH": databaseURL.path,
                "FLOW_AGENT_RUNTIME_PROVIDER": "deterministic"
            ]
        )
        let referenceDate = ISO8601DateFormatter().date(from: "2026-03-21T09:00:00+00:00") ?? Date()
        let initialPackage = try repository.loadWeeklyReviewPackage(referenceDate: referenceDate)
        guard initialPackage.cleanupActions.contains(where: {
            $0.kind == "project_next_action_review" && $0.targetIDs.contains("project-1")
        }) else {
            throw FlowDataError.message("Expected sidecar weekly review package to flag projects missing a next action.")
        }

        let turn = try repository.proposeProjectNextActionReview(projectID: "project-1")
        guard turn.proposalStatus == "pending", turn.proposal?.actionType == "create_task" else {
            throw FlowDataError.message("Expected sidecar project next-action review to create a pending assistant proposal.")
        }
        guard turn.provider == "deterministic" else {
            throw FlowDataError.message("Expected project next-action review to use the deterministic provider override in smoke tests.")
        }

        let confirmation = try repository.confirmAssistantProposal(turnID: turn.id)
        guard confirmation.contains("Launch prep") else {
            throw FlowDataError.message("Expected sidecar project next-action confirmation to mention the target project.")
        }

        let refreshedPackage = try repository.loadWeeklyReviewPackage(referenceDate: referenceDate)
        guard refreshedPackage.cleanupActions.contains(where: {
            $0.kind == "project_next_action_review" && $0.targetIDs.contains("project-1")
        }) == false else {
            throw FlowDataError.message("Expected confirmed sidecar project next action to remove the missing-next-action review prompt.")
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
            throw FlowDataError.message("Unable to open sidecar assistant smoke database.")
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
            ) VALUES (?, ?, ?, ?, '[]', ?, ?, ?, '{}', NULL, 30, ?)
        """
        var statement: OpaquePointer?
        guard sqlite3_prepare_v2(db, sql, -1, &statement, nil) == SQLITE_OK else {
            throw FlowDataError.message("Unable to prepare sidecar assistant seed insert.")
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
            throw FlowDataError.message("Unable to insert sidecar assistant seed item.")
        }
    }

}

private final class RecordingAssistantStore {
    private var nextID = 1
    private var clock = 1
    private var sessions: [RecordingAssistantSession] = []
    private var messages: [RecordingAssistantMessage] = []
    private var lastMutationMessage: String?

    func loadSessions(limit: Int) -> [FlowAssistantSession] {
        sessions
            .sorted {
                if $0.updatedAt == $1.updatedAt {
                    return $0.createdAt > $1.createdAt
                }
                return $0.updatedAt > $1.updatedAt
            }
            .prefix(limit)
            .map { $0.snapshot }
    }

    func loadMessages(sessionID: String, limit: Int) -> [FlowAssistantMessage] {
        messages
            .filter { $0.sessionID == sessionID }
            .sorted { $0.createdAt < $1.createdAt }
            .suffix(limit)
            .map { $0.snapshot }
    }

    func createSession(title: String, sessionID: String? = nil) -> FlowAssistantSession {
        let id = sessionID ?? makeID(prefix: "session")
        let timestamp = tick()
        let session = RecordingAssistantSession(
            id: id,
            title: title.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty ? "New Chat" : title,
            latestPreview: "",
            messageCount: 0,
            createdAt: timestamp,
            updatedAt: timestamp
        )
        upsertSession(session)
        return session.snapshot
    }

    func sendMessage(sessionID: String, prompt: String, planDate: String) -> FlowAssistantMessage {
        let normalizedPrompt = prompt.trimmingCharacters(in: .whitespacesAndNewlines)
        let route = detectRoute(normalizedPrompt)
        let assistantID = makeID(prefix: "message")
        let session = ensureSession(sessionID: sessionID, title: normalizedPrompt)
        let userMessage = RecordingAssistantMessage(
            id: makeID(prefix: "user"),
            sessionID: session.id,
            role: "user",
            content: normalizedPrompt,
            route: "user",
            proposal: nil,
            proposalStatus: "none",
            auditSteps: [],
            provider: "user",
            providerStatus: "success",
            providerDetail: "",
            providerModel: nil,
            sourceTurnID: nil,
            createdAt: tick(),
            updatedAt: tick()
        )
        let assistantMessage = RecordingAssistantMessage(
            id: assistantID,
            sessionID: session.id,
            role: "assistant",
            content: "Response for \(normalizedPrompt)",
            route: route,
            proposal: makeProposal(for: normalizedPrompt, route: route),
            proposalStatus: "pending",
            auditSteps: [
                .init(id: "\(assistantID)-provider", stage: "provider", status: "ok", summary: "Provider completed the request.", payload: ["provider": "deterministic"]),
                .init(id: "\(assistantID)-validation", stage: "validation", status: "ok", summary: "Proposal is ready for confirmation.", payload: [:])
            ],
            provider: "deterministic",
            providerStatus: "success",
            providerDetail: "Deterministic provider completed the request.",
            providerModel: nil,
            sourceTurnID: assistantID,
            createdAt: tick(),
            updatedAt: tick()
        )
        messages.append(userMessage)
        messages.append(assistantMessage)
        updateSession(id: session.id, latestPreview: assistantMessage.content, increment: 2)
        lastMutationMessage = assistantMessage.id
        return assistantMessage.snapshot
    }

    func confirmMessage(messageID: String) throws -> String {
        guard let index = messages.firstIndex(where: { $0.id == messageID }) else {
            throw FlowDataError.message("Assistant message could not be found.")
        }
        guard messages[index].proposalStatus == "pending" else {
            throw FlowDataError.message("Assistant message proposal is not pending.")
        }
        messages[index].proposalStatus = "confirmed"
        touchSession(id: messages[index].sessionID)
        lastMutationMessage = messageID
        return "Confirmed assistant proposal"
    }

    func dismissMessage(messageID: String) throws {
        guard let index = messages.firstIndex(where: { $0.id == messageID }) else {
            return
        }
        guard messages[index].proposalStatus == "pending" else {
            throw FlowDataError.message("Assistant message proposal is not pending.")
        }
        messages[index].proposalStatus = "dismissed"
        touchSession(id: messages[index].sessionID)
    }

    func undoLastMutation() -> String? {
        guard lastMutationMessage != nil else {
            return "Undid assistant write"
        }
        lastMutationMessage = nil
        return "Undid assistant write"
    }

    private func ensureSession(sessionID: String, title: String) -> RecordingAssistantSession {
        if let existing = sessions.first(where: { $0.id == sessionID }) {
            return existing
        }
        let created = RecordingAssistantSession(
            id: sessionID,
            title: title.isEmpty ? "New Chat" : title,
            latestPreview: "",
            messageCount: 0,
            createdAt: tick(),
            updatedAt: tick()
        )
        upsertSession(created)
        return created
    }

    private func upsertSession(_ session: RecordingAssistantSession) {
        if let index = sessions.firstIndex(where: { $0.id == session.id }) {
            sessions[index] = session
        } else {
            sessions.append(session)
        }
    }

    private func updateSession(id: String, latestPreview: String, increment: Int) {
        guard let index = sessions.firstIndex(where: { $0.id == id }) else { return }
        sessions[index].latestPreview = latestPreview
        sessions[index].messageCount += increment
        sessions[index].updatedAt = tick()
    }

    private func touchSession(id: String) {
        guard let index = sessions.firstIndex(where: { $0.id == id }) else { return }
        sessions[index].updatedAt = tick()
    }

    private func makeProposal(for prompt: String, route: String) -> FlowAssistantProposal? {
        if route == "memory" || prompt.lowercased().contains("remember") {
            return FlowAssistantProposal(
                actionType: "save_memory",
                title: "Save Memory",
                detail: "Save the preference for later.",
                requiresConfirmation: true
            )
        }
        return FlowAssistantProposal(
            actionType: "create_task",
            title: "Draft next action",
            detail: "Draft a next action for \(prompt)",
            requiresConfirmation: true
        )
    }

    private func detectRoute(_ prompt: String) -> String {
        let lowered = prompt.lowercased()
        if lowered.contains("remember") || lowered.contains("prefer") {
            return "memory"
        }
        if lowered.contains("review") || lowered.contains("launch checklist") || lowered.contains("add ") {
            return "capture"
        }
        return "general"
    }

    private func tick() -> Int {
        defer { clock += 1 }
        return clock
    }

    private func makeID(prefix: String) -> String {
        defer { nextID += 1 }
        return "\(prefix)-\(nextID)"
    }
}

private struct RecordingAssistantSession {
    let id: String
    var title: String
    var latestPreview: String
    var messageCount: Int
    let createdAt: Int
    var updatedAt: Int

    var snapshot: FlowAssistantSession {
        FlowAssistantSession(
            id: id,
            title: title,
            latestPreview: latestPreview,
            messageCount: messageCount,
            createdAtLabel: "Now",
            updatedAtLabel: "Now"
        )
    }
}

private struct RecordingAssistantMessage {
    let id: String
    let sessionID: String
    var role: String
    var content: String
    var route: String
    var proposal: FlowAssistantProposal?
    var proposalStatus: String
    var auditSteps: [FlowAssistantAuditStep]
    var provider: String
    var providerStatus: String
    var providerDetail: String
    var providerModel: String?
    var sourceTurnID: String?
    let createdAt: Int
    var updatedAt: Int

    var snapshot: FlowAssistantMessage {
        FlowAssistantMessage(
            id: id,
            sessionID: sessionID,
            role: role,
            content: content,
            route: route,
            proposal: proposal,
            proposalStatus: proposalStatus,
            auditSteps: auditSteps,
            provider: provider,
            providerStatus: providerStatus,
            providerDetail: providerDetail,
            providerModel: providerModel,
            sourceTurnID: sourceTurnID,
            createdAtLabel: "Now",
            updatedAtLabel: "Now"
        )
    }
}

private final class RecordingSidecarReadClient: SidecarReadClient {
    private let store: RecordingAssistantStore
    private(set) var requestKinds: [String] = []
    private(set) var assistantTurnLimit: Int?
    private(set) var assistantSessionIDs: [String] = []

    init(store: RecordingAssistantStore) {
        self.store = store
    }

    func readPayload<Payload>(
        configuration: SidecarLaunchConfiguration,
        timeout: TimeInterval,
        as type: Payload.Type
    ) throws -> Payload where Payload: Decodable {
        if let kind = configuration.arguments.value(after: "--read") {
            requestKinds.append(kind)
        }
        assistantTurnLimit = configuration.arguments.intValue(after: "--limit")

        if let sessionID = configuration.arguments.value(after: "--session-id") {
            assistantSessionIDs.append(sessionID)
        }

        if Payload.self == [FlowAssistantSession].self {
            return store.loadSessions(limit: assistantTurnLimit ?? 30) as! Payload
        }
        if Payload.self == [FlowAssistantMessage].self {
            let sessionID = assistantSessionIDs.last ?? ""
            return store.loadMessages(sessionID: sessionID, limit: assistantTurnLimit ?? 30) as! Payload
        }
        if Payload.self == [FlowAssistantTurn].self {
            return [] as! Payload
        }
        if Payload.self == [FlowMemoryRecord].self {
            return [] as! Payload
        }
        if Payload.self == FlowDailyPlanState.self {
            return FlowDailyPlanState.empty(planDate: configuration.arguments.value(after: "--plan-date") ?? "2026-05-02") as! Payload
        }
        if Payload.self == FlowWeeklyReviewPackage.self {
            return FlowWeeklyReviewPackage.empty as! Payload
        }
        if Payload.self == FlowNotificationPolicyState.self {
            return FlowNotificationPolicyState.empty as! Payload
        }

        fatalError("Unexpected sidecar read payload type: \(Payload.self)")
    }
}

private final class RecordingSidecarMutationClient: SidecarMutationClient {
    private let store: RecordingAssistantStore
    private(set) var writeKinds: [String] = []
    private(set) var assistantModes: [String] = []
    private(set) var payloadsByMode: [String: [String: String]] = [:]
    private(set) var timeoutByWriteKind: [String: TimeInterval] = [:]

    init(store: RecordingAssistantStore) {
        self.store = store
    }

    func mutatePayload<Payload>(
        configuration: SidecarLaunchConfiguration,
        timeout: TimeInterval,
        as type: Payload.Type
    ) throws -> Payload where Payload: Decodable {
        if let kind = configuration.arguments.value(after: "--write") {
            writeKinds.append(kind)
            timeoutByWriteKind[kind] = timeout
            let payload = decodeAssistantPayload(from: configuration)
            payloadsByMode[kind] = payload

            switch kind {
            case "create-session":
                return store.createSession(title: payload["title"] ?? "") as! Payload
            case "send-message":
                return store.sendMessage(
                    sessionID: payload["sessionID"] ?? "",
                    prompt: payload["prompt"] ?? "",
                    planDate: payload["planDate"] ?? ""
                ) as! Payload
            case "confirm-message-proposal":
                let responseJSON = #"{"message":"\#(try store.confirmMessage(messageID: payload["messageID"] ?? ""))"}"#
                guard let responseData = responseJSON.data(using: .utf8) else {
                    fatalError("Unable to encode confirm-message-proposal response.")
                }
                return try JSONDecoder().decode(Payload.self, from: responseData)
            case "dismiss-message-proposal":
                try store.dismissMessage(messageID: payload["messageID"] ?? "")
                let responseJSON = #"{"ok":true}"#
                guard let responseData = responseJSON.data(using: .utf8) else {
                    fatalError("Unable to encode dismiss-message-proposal response.")
                }
                return try JSONDecoder().decode(Payload.self, from: responseData)
            case "undo-last-mutation":
                let responseJSON = #"{"message":"\#(store.undoLastMutation() ?? "Undid assistant write")"}"#
                guard let responseData = responseJSON.data(using: .utf8) else {
                    fatalError("Unable to encode undo-last-mutation response.")
                }
                return try JSONDecoder().decode(Payload.self, from: responseData)
            default:
                return fallbackWriteResponse(kind: kind, payload: payload)
            }
        }

        guard let mode = configuration.arguments.value(after: "--assistant-mode") else {
            fatalError("Expected assistant mode to be present in mutation configuration.")
        }
        assistantModes.append(mode)
        payloadsByMode[mode] = decodeAssistantPayload(from: configuration)

        if Payload.self == FlowAssistantTurn.self {
            return makeAssistantTurn(prompt: payloadsByMode[mode]?["prompt"] ?? mode) as! Payload
        }

        let responseJSON: String
        switch mode {
        case "confirm-proposal":
            responseJSON = #"{"message":"Confirmed assistant proposal"}"#
        case "dismiss-proposal", "send-prompt", "project-next-action-review":
            responseJSON = #"{"ok":true}"#
        case "undo-last-mutation":
            responseJSON = #"{"message":"Undid assistant mutation"}"#
        default:
            responseJSON = #"{"ok":true}"#
        }

        guard let responseData = responseJSON.data(using: .utf8) else {
            fatalError("Unable to encode sidecar mutation response.")
        }

        return try JSONDecoder().decode(Payload.self, from: responseData)
    }

    private func fallbackWriteResponse<Payload: Decodable>(kind: String, payload: [String: String]) -> Payload {
        let responseJSON: String
        switch kind {
        case "create-session":
            responseJSON = #"{}"#
        case "send-message":
            responseJSON = #"{}"#
        case "confirm-message-proposal":
            responseJSON = #"{"message":"Confirmed assistant proposal"}"#
        case "dismiss-message-proposal", "undo-last-mutation":
            responseJSON = #"{"ok":true}"#
        default:
            responseJSON = #"{"ok":true}"#
        }
        guard let responseData = responseJSON.data(using: .utf8) else {
            fatalError("Unable to encode sidecar response.")
        }
        return try! JSONDecoder().decode(Payload.self, from: responseData)
    }

    private func makeAssistantTurn(prompt: String) -> FlowAssistantTurn {
        let turnIndex = assistantModes.count
        return FlowAssistantTurn(
            id: "turn-\(turnIndex)",
            prompt: prompt,
            response: "Response for \(prompt)",
            route: "capture",
            proposal: FlowAssistantProposal(
                actionType: "create_task",
                title: "Draft next action",
                detail: "Draft a next action for \(prompt)",
                requiresConfirmation: true
            ),
            proposalStatus: "pending",
            auditSteps: [
                FlowAssistantAuditStep(
                    id: "turn-\(turnIndex)-provider",
                    stage: "provider",
                    status: "ok",
                    summary: "Provider completed the request.",
                    payload: ["provider": "deterministic"]
                ),
                FlowAssistantAuditStep(
                    id: "turn-\(turnIndex)-validation",
                    stage: "validation",
                    status: "ok",
                    summary: "Proposal is ready for confirmation.",
                    payload: [:]
                )
            ],
            provider: "deterministic",
            providerStatus: "success",
            providerDetail: "Deterministic provider completed the request.",
            providerModel: nil,
            createdAtLabel: "Now"
        )
    }
}

private extension Array where Element == String {
    func value(after flag: String) -> String? {
        guard let index = firstIndex(of: flag), index + 1 < count else { return nil }
        return self[index + 1]
    }

    func intValue(after flag: String) -> Int? {
        value(after: flag).flatMap(Int.init)
    }
}

private func decodeAssistantPayload(from configuration: SidecarLaunchConfiguration) -> [String: String] {
    guard let payloadIndex = configuration.arguments.firstIndex(of: "--payload-base64"),
          payloadIndex + 1 < configuration.arguments.count,
          let payloadData = Data(base64Encoded: configuration.arguments[payloadIndex + 1]),
          let json = try? JSONSerialization.jsonObject(with: payloadData) as? [String: Any] else {
        return [:]
    }

    var payload: [String: String] = [:]
    for (key, value) in json {
        if let stringValue = value as? String {
            payload[key] = stringValue
        } else if let numberValue = value as? NSNumber {
            payload[key] = numberValue.stringValue
        }
    }
    return payload
}

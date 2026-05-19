import Foundation

final class SidecarFlowRepository: FlowRepository {
    private let fallback: FlowRepository
    private let readClient: SidecarReadClient
    private let mutationClient: SidecarMutationClient
    private let timeout: TimeInterval
    private let assistantTimeout: TimeInterval
    private let environment: [String: String]

    init(
        fallback: FlowRepository,
        readClient: SidecarReadClient = ProcessSidecarProbeClient(),
        mutationClient: SidecarMutationClient = ProcessSidecarProbeClient(),
        timeout: TimeInterval = 10.0,
        assistantTimeout: TimeInterval = 60.0,
        environment: [String: String] = [:]
    ) {
        self.fallback = fallback
        self.readClient = readClient
        self.mutationClient = mutationClient
        self.timeout = timeout
        self.assistantTimeout = assistantTimeout
        self.environment = environment
    }

    func loadWorkspaceSnapshot() throws -> WorkspaceSnapshot {
        try readOrFallback {
            try readClient.readPayload(
                configuration: .runtimeRead(
                    kind: "workspace-snapshot",
                    environment: environment
                ),
                timeout: timeout,
                as: WorkspaceSnapshot.self
            )
        } fallback: {
            try fallback.loadWorkspaceSnapshot()
        }
    }

    func capture(title: String) throws -> FlowTask {
        try mutate(
            kind: "capture",
            payload: ["title": title],
            as: FlowTask.self
        )
    }

    func clarifyCapture(id: String, title: String, destination: ClarifyDestination, projectTitle: String?) throws {
        var payload: [String: Any] = [
            "id": id,
            "title": title,
            "destination": destination.rawValue
        ]
        if let projectTitle {
            payload["projectTitle"] = projectTitle
        }

        try mutateAck(
            kind: "clarify-capture",
            payload: payload
        )
    }

    func rejectCapture(id: String) throws {
        try mutateAck(
            kind: "reject-capture",
            payload: ["id": id]
        )
    }

    func loadAssistantSessions(limit: Int) throws -> [FlowAssistantSession] {
        try readClient.readPayload(
            configuration: .runtimeRead(
                kind: AssistantSessionMessageSidecarContract.assistantSessionsReadKind,
                limit: limit,
                environment: environment
            ),
            timeout: timeout,
            as: [FlowAssistantSession].self
        )
    }

    func loadAssistantMessages(sessionID: String, limit: Int) throws -> [FlowAssistantMessage] {
        try readClient.readPayload(
            configuration: .runtimeRead(
                kind: AssistantSessionMessageSidecarContract.assistantMessagesReadKind,
                limit: limit,
                sessionID: sessionID,
                environment: environment
            ),
            timeout: timeout,
            as: [FlowAssistantMessage].self
        )
    }

    func createAssistantSession(title: String) throws -> FlowAssistantSession {
        try mutate(
            kind: AssistantSessionMessageSidecarContract.createSessionMode,
            payload: ["title": title],
            as: FlowAssistantSession.self
        )
    }

    func sendAssistantMessage(sessionID: String, prompt: String, planDate: String) throws -> FlowAssistantMessage {
        try mutate(
            kind: AssistantSessionMessageSidecarContract.sendMessageMode,
            payload: [
                "sessionID": sessionID,
                "prompt": prompt,
                "planDate": planDate
            ],
            timeout: assistantTimeout,
            as: FlowAssistantMessage.self
        )
    }

    func confirmAssistantMessageProposal(messageID: String) throws -> String {
        let result = try mutate(
            kind: AssistantSessionMessageSidecarContract.confirmMessageProposalMode,
            payload: ["messageID": messageID],
            as: SidecarAssistantMessage.self
        )
        return result.message
    }

    func dismissAssistantMessageProposal(messageID: String) throws {
        try mutateAck(
            kind: AssistantSessionMessageSidecarContract.dismissMessageProposalMode,
            payload: ["messageID": messageID]
        )
    }

    func sendAssistantPrompt(_ prompt: String, planDate: String) throws -> FlowAssistantTurn {
        try mutateAssistant(
            kind: "send-prompt",
            assistantPayload: [
                "prompt": prompt,
                "planDate": planDate
            ],
            timeout: assistantTimeout,
            as: FlowAssistantTurn.self
        )
    }

    func proposeProjectNextActionReview(projectID: String) throws -> FlowAssistantTurn {
        try mutateAssistant(
            kind: "project-next-action-review",
            assistantPayload: ["projectID": projectID],
            timeout: assistantTimeout,
            as: FlowAssistantTurn.self
        )
    }

    func loadAssistantTurns(limit: Int) throws -> [FlowAssistantTurn] {
        try readOrFallback {
            try readClient.readPayload(
                configuration: .runtimeRead(
                    kind: "assistant-turns",
                    limit: limit,
                    environment: environment
                ),
                timeout: timeout,
                as: [FlowAssistantTurn].self
            )
        } fallback: {
            try fallback.loadAssistantTurns(limit: limit)
        }
    }

    func confirmAssistantProposal(turnID: String) throws -> String {
        let result = try mutateAssistant(
            kind: "confirm-proposal",
            assistantPayload: ["turnID": turnID],
            as: SidecarAssistantMessage.self
        )
        return result.message
    }

    func dismissAssistantProposal(turnID: String) throws {
        _ = try mutateAssistant(
            kind: "dismiss-proposal",
            assistantPayload: ["turnID": turnID],
            as: SidecarMutationAck.self
        )
    }

    func undoLastAssistantMutation() throws -> String? {
        let result = try mutate(
            kind: "undo-last-mutation",
            payload: [:],
            as: SidecarOptionalAssistantMessage.self
        )
        return result.message
    }

    func listMemoryRecords(query: String?, includeDisabled: Bool) throws -> [FlowMemoryRecord] {
        try readOrFallback {
            try readClient.readPayload(
                configuration: .runtimeRead(
                    kind: "memory-records",
                    query: query,
                    includeDisabled: includeDisabled,
                    environment: environment
                ),
                timeout: timeout,
                as: [FlowMemoryRecord].self
            )
        } fallback: {
            try fallback.listMemoryRecords(query: query, includeDisabled: includeDisabled)
        }
    }

    func createMemoryRecord(kind: String, scope: String, value: String, source: String, confidence: Double, scopeRef: String?) throws -> FlowMemoryRecord {
        var payload: [String: Any] = [
            "kind": kind,
            "scope": scope,
            "value": value,
            "source": source,
            "confidence": confidence
        ]
        if let scopeRef {
            payload["scopeRef"] = scopeRef
        }

        return try mutate(
            kind: "create-memory-record",
            payload: payload,
            as: FlowMemoryRecord.self
        )
    }

    func updateMemoryRecord(id: String, value: String) throws {
        try mutateAck(
            kind: "update-memory-record",
            payload: [
                "id": id,
                "value": value
            ],
        )
    }

    func setMemoryRecordEnabled(id: String, enabled: Bool) throws {
        try mutateAck(
            kind: "set-memory-record-enabled",
            payload: [
                "id": id,
                "enabled": enabled
            ],
        )
    }

    func deleteMemoryRecord(id: String) throws {
        try mutateAck(
            kind: "delete-memory-record",
            payload: ["id": id]
        )
    }

    func loadDailyPlanState(planDate: String) throws -> FlowDailyPlanState {
        try readOrFallback {
            try readClient.readPayload(
                configuration: .runtimeRead(
                    kind: "daily-plan",
                    planDate: planDate,
                    environment: environment
                ),
                timeout: timeout,
                as: FlowDailyPlanState.self
            )
        } fallback: {
            try fallback.loadDailyPlanState(planDate: planDate)
        }
    }

    func saveDailyPlan(planDate: String, topItemIDs: [String], bonusItemIDs: [String]) throws {
        try mutateAck(
            kind: "save-daily-plan",
            payload: [
                "planDate": planDate,
                "topItemIDs": topItemIDs,
                "bonusItemIDs": bonusItemIDs
            ],
        )
    }

    func loadWeeklyReviewPackage(referenceDate: Date) throws -> FlowWeeklyReviewPackage {
        try readOrFallback {
            try readClient.readPayload(
                configuration: .runtimeRead(
                    kind: "weekly-review",
                    referenceDate: ISO8601DateFormatter().string(from: referenceDate),
                    environment: environment
                ),
                timeout: timeout,
                as: FlowWeeklyReviewPackage.self
            )
        } fallback: {
            try fallback.loadWeeklyReviewPackage(referenceDate: referenceDate)
        }
    }

    func applyWeeklyReviewActions(actionIDs: [String], referenceDate: Date) throws {
        try mutateAck(
            kind: "apply-weekly-review-actions",
            payload: [
                "actionIDs": actionIDs,
                "referenceDate": ISO8601DateFormatter().string(from: referenceDate)
            ],
        )
    }

    func loadNotificationPolicy() throws -> FlowNotificationPolicyState {
        try readOrFallback {
            try readClient.readPayload(
                configuration: .runtimeRead(
                    kind: "notification-policy",
                    environment: environment
                ),
                timeout: timeout,
                as: FlowNotificationPolicyState.self
            )
        } fallback: {
            try fallback.loadNotificationPolicy()
        }
    }

    func updateNotificationPermissionStatus(_ status: String) throws {
        try mutateAck(
            kind: "update-notification-permission",
            payload: ["status": status]
        )
    }

    func markTaskDone(id: String) throws {
        try mutateAck(
            kind: "mark-task-done",
            payload: ["id": id]
        )
    }

    func archiveTask(id: String) throws {
        try mutateAck(
            kind: "archive-task",
            payload: ["id": id]
        )
    }

    private func readOrFallback<Value>(
        _ sidecarRead: () throws -> Value,
        fallback fallbackRead: () throws -> Value
    ) throws -> Value {
        do {
            return try sidecarRead()
        } catch {
            return try fallbackRead()
        }
    }

    private func mutate<Payload: Decodable>(
        kind: String,
        payload: [String: Any],
        timeout: TimeInterval? = nil,
        as type: Payload.Type
    ) throws -> Payload {
        let data = try JSONSerialization.data(withJSONObject: payload, options: [.sortedKeys])
        return try mutationClient.mutatePayload(
            configuration: .runtimeWrite(
                kind: kind,
                payloadData: data,
                environment: environment
            ),
            timeout: timeout ?? self.timeout,
            as: type
        )
    }

    private func mutateAssistant<Payload: Decodable>(
        kind: String,
        assistantPayload payload: [String: Any],
        timeout: TimeInterval? = nil,
        as type: Payload.Type
    ) throws -> Payload {
        let data = try JSONSerialization.data(withJSONObject: payload, options: [.sortedKeys])
        return try mutationClient.mutatePayload(
            configuration: .runtimeAssistant(
                mode: kind,
                payloadData: data,
                environment: environment
            ),
            timeout: timeout ?? self.timeout,
            as: type
        )
    }

    private func mutateAck(
        kind: String,
        payload: [String: Any]
    ) throws {
        let ack = try mutate(
            kind: kind,
            payload: payload,
            as: SidecarMutationAck.self
        )
        guard ack.ok else {
            throw FlowDataError.message("Sidecar mutation \(kind) did not acknowledge success.")
        }
    }
}

enum AssistantSessionMessageSidecarContract {
    static let assistantSessionsReadKind = "assistant-sessions"
    static let assistantMessagesReadKind = "assistant-messages"
    static let createSessionMode = "create-session"
    static let sendMessageMode = "send-message"
    static let confirmMessageProposalMode = "confirm-message-proposal"
    static let dismissMessageProposalMode = "dismiss-message-proposal"

    static let sessionMessagePayloadKeys = [
        "sessionID",
        "prompt",
        "planDate",
        "messageID"
    ]
}

private struct SidecarMutationAck: Decodable {
    let ok: Bool
}

private struct SidecarAssistantMessage: Decodable {
    let message: String
}

private struct SidecarOptionalAssistantMessage: Decodable {
    let message: String?
}

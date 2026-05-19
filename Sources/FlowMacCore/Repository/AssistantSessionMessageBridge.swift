import Foundation

final class AssistantSessionMessageBridge {
    private struct SessionState {
        var session: FlowAssistantSession
        var messages: [FlowAssistantMessage]
        var createdAt: Date
        var updatedAt: Date
    }

    private var sessions: [String: SessionState] = [:]
    private var lastMutationSessionID: String?

    func loadSessions(limit: Int) -> [FlowAssistantSession] {
        sessions.values
            .sorted {
                if $0.updatedAt == $1.updatedAt {
                    return $0.createdAt > $1.createdAt
                }
                return $0.updatedAt > $1.updatedAt
            }
            .prefix(limit)
            .map { state in
                makeSessionSnapshot(from: state)
            }
    }

    func loadMessages(sessionID: String, limit: Int) -> [FlowAssistantMessage] {
        guard let state = sessions[sessionID] else { return [] }
        return Array(state.messages.suffix(limit))
    }

    func createSession(title: String, sessionID: String? = nil) -> FlowAssistantSession {
        let trimmedTitle = title.trimmingCharacters(in: .whitespacesAndNewlines)
        let now = Date()
        let id = sessionID ?? UUID().uuidString
        let session = FlowAssistantSession(
            id: id,
            title: trimmedTitle.isEmpty ? "New Chat" : trimmedTitle,
            latestPreview: "",
            messageCount: 0,
            createdAtLabel: "Just now",
            updatedAtLabel: "Just now"
        )
        sessions[id] = SessionState(session: session, messages: [], createdAt: now, updatedAt: now)
        return session
    }

    func sendMessage(
        sessionID: String,
        prompt: String,
        planDate: String,
        routeTurn: (String, String) throws -> FlowAssistantTurn
    ) rethrows -> FlowAssistantMessage {
        let targetSession = ensureSession(id: sessionID, title: prompt)
        let turn = try routeTurn(prompt, planDate)
        let nowLabel = "Just now"
        let userMessage = FlowAssistantMessage(
            id: "\(turn.id)-user",
            sessionID: targetSession.id,
            role: "user",
            content: prompt,
            route: "user",
            proposal: nil,
            proposalStatus: "none",
            auditSteps: [],
            provider: "user",
            providerStatus: "success",
            providerDetail: "",
            providerModel: nil,
            sourceTurnID: nil,
            createdAtLabel: nowLabel,
            updatedAtLabel: nowLabel
        )
        let assistantMessage = FlowAssistantMessage(
            id: turn.id,
            sessionID: targetSession.id,
            role: "assistant",
            content: turn.response,
            route: turn.route,
            proposal: turn.proposal,
            proposalStatus: turn.proposalStatus,
            auditSteps: turn.auditSteps,
            provider: turn.provider,
            providerStatus: turn.providerStatus,
            providerDetail: turn.providerDetail,
            providerModel: turn.providerModel,
            sourceTurnID: turn.id,
            createdAtLabel: turn.createdAtLabel,
            updatedAtLabel: turn.createdAtLabel
        )

        updateSession(id: targetSession.id) { state in
            state.messages.append(userMessage)
            state.messages.append(assistantMessage)
            state.session.latestPreview = assistantMessage.content
            state.session.messageCount = state.messages.count
            state.session.updatedAtLabel = nowLabel
        }

        return assistantMessage
    }

    func confirm(
        messageID: String,
        backingTurn: (String) throws -> String
    ) throws -> String {
        guard let lookup = lookupAssistantMessage(messageID: messageID) else {
            throw FlowDataError.message("Assistant message \(messageID) could not be found.")
        }
        guard lookup.message.proposalStatus == "pending" else {
            throw FlowDataError.message("Assistant message proposal is not pending.")
        }

        if let backingTurnID = lookup.message.sourceTurnID {
            let result = try backingTurn(backingTurnID)
            updateMessage(id: messageID) { message in
                message.proposalStatus = "confirmed"
                message.updatedAtLabel = "Just now"
            }
            lastMutationSessionID = lookup.sessionID
            return result
        }

        updateMessage(id: messageID) { message in
            message.proposalStatus = "confirmed"
            message.updatedAtLabel = "Just now"
        }
        lastMutationSessionID = lookup.sessionID
        return "Confirmed assistant message \(messageID)"
    }

    func dismiss(
        messageID: String,
        backingTurn: (String) throws -> Void
    ) throws {
        guard let lookup = lookupAssistantMessage(messageID: messageID) else {
            throw FlowDataError.message("Assistant message \(messageID) could not be found.")
        }
        guard lookup.message.proposalStatus == "pending" else {
            throw FlowDataError.message("Assistant message proposal is not pending.")
        }

        if let backingTurnID = lookup.message.sourceTurnID {
            try backingTurn(backingTurnID)
        }

        updateMessage(id: messageID) { message in
            message.proposalStatus = "dismissed"
            message.updatedAtLabel = "Just now"
        }
        lastMutationSessionID = lookup.sessionID
    }

    func undoLastMutation(backingUndo: () throws -> String?) rethrows -> String? {
        guard let result = try backingUndo(), result.isEmpty == false else {
            return nil
        }

        guard let sessionID = lastMutationSessionID else {
            return result
        }

        removeLastAssistantConversation(sessionID: sessionID)
        lastMutationSessionID = nil
        return result
    }

    private func ensureSession(id: String, title: String) -> FlowAssistantSession {
        if let state = sessions[id] {
            return state.session
        }
        return createSession(title: title, sessionID: id)
    }

    private func updateSession(id: String, mutate: (inout SessionState) -> Void) {
        guard var state = sessions[id] else { return }
        mutate(&state)
        state.updatedAt = Date()
        sessions[id] = state
    }

    private func updateMessage(id: String, mutate: (inout FlowAssistantMessage) -> Void) {
        guard let sessionID = sessions.first(where: { $0.value.messages.contains(where: { $0.id == id }) })?.key,
              var state = sessions[sessionID],
              let index = state.messages.firstIndex(where: { $0.id == id }) else {
            return
        }

        mutate(&state.messages[index])
        state.updatedAt = Date()
        state.session.updatedAtLabel = "Just now"
        state.session.latestPreview = state.messages.last?.content ?? state.session.latestPreview
        state.session.messageCount = state.messages.count
        sessions[sessionID] = state
    }

    private func lookupAssistantMessage(messageID: String) -> (sessionID: String, message: FlowAssistantMessage)? {
        for (sessionID, state) in sessions {
            if let message = state.messages.first(where: { $0.id == messageID && $0.role == "assistant" }) {
                return (sessionID, message)
            }
        }
        return nil
    }

    private func removeLastAssistantConversation(sessionID: String) {
        guard var state = sessions[sessionID],
              let assistantIndex = state.messages.lastIndex(where: { $0.role == "assistant" }) else {
            return
        }

        guard assistantIndex > 0 else { return }
        let userIndex = max(assistantIndex - 1, 0)
        if state.messages.indices.contains(userIndex) {
            state.messages.remove(at: assistantIndex)
            state.messages.remove(at: userIndex)
        }

        state.session.messageCount = state.messages.count
        state.session.latestPreview = state.messages.last?.content ?? ""
        state.updatedAt = Date()
        sessions[sessionID] = state
    }

    private func makeSessionSnapshot(from state: SessionState) -> FlowAssistantSession {
        var snapshot = state.session
        snapshot.messageCount = state.messages.count
        snapshot.latestPreview = state.messages.last?.content ?? snapshot.latestPreview
        return snapshot
    }
}

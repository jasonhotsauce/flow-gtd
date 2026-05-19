import Foundation

@MainActor
final class AssistantWorkflowService {
    private let repository: FlowRepository
    private let planDateProvider: () -> String

    init(repository: FlowRepository, planDateProvider: @escaping () -> String) {
        self.repository = repository
        self.planDateProvider = planDateProvider
    }

    func loadSessions(limit: Int = 100) throws -> [FlowAssistantSession] {
        try repository.loadAssistantSessions(limit: limit)
    }

    func loadMessages(sessionID: String, limit: Int = 100) throws -> [FlowAssistantMessage] {
        try repository.loadAssistantMessages(sessionID: sessionID, limit: limit)
    }

    func createSession(title: String) throws -> FlowAssistantSession {
        try repository.createAssistantSession(title: title)
    }

    func sendMessage(sessionID: String, prompt: String) throws -> FlowAssistantMessage {
        try repository.sendAssistantMessage(sessionID: sessionID, prompt: prompt, planDate: planDateProvider())
    }

    func confirmMessage(messageID: String) throws -> String {
        try repository.confirmAssistantMessageProposal(messageID: messageID)
    }

    func dismissMessage(messageID: String) throws {
        try repository.dismissAssistantMessageProposal(messageID: messageID)
    }

    func confirm(messageID: String) throws -> String {
        try repository.confirmAssistantMessageProposal(messageID: messageID)
    }

    func dismiss(messageID: String) throws {
        try repository.dismissAssistantMessageProposal(messageID: messageID)
    }

    func loadTurns(limit: Int = 30) throws -> [FlowAssistantTurn] {
        try repository.loadAssistantTurns(limit: limit)
    }

    func send(prompt: String) throws -> FlowAssistantTurn {
        try repository.sendAssistantPrompt(prompt, planDate: planDateProvider())
    }

    func proposeProjectNextActionReview(projectID: String) throws -> FlowAssistantTurn {
        try repository.proposeProjectNextActionReview(projectID: projectID)
    }

    func confirm(turnID: String) throws -> String {
        try repository.confirmAssistantProposal(turnID: turnID)
    }

    func dismiss(turnID: String) throws {
        try repository.dismissAssistantProposal(turnID: turnID)
    }

    func undoLastMutation() throws -> String? {
        try repository.undoLastAssistantMutation()
    }
}

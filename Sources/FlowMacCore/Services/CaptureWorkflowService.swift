import Foundation

enum ClarifyDestination: String, CaseIterable, Identifiable {
    case task
    case project

    var id: String { rawValue }

    var title: String {
        switch self {
        case .task:
            return "Task"
        case .project:
            return "Project"
        }
    }
}

struct ClarifyDraft: Identifiable, Equatable {
    let id: String
    let inboxItemID: String
    let rawText: String
    var title: String
    var destination: ClarifyDestination
    var projectTitle: String

    init(
        inboxItemID: String,
        rawText: String,
        title: String,
        destination: ClarifyDestination = .task,
        projectTitle: String = ""
    ) {
        self.id = inboxItemID
        self.inboxItemID = inboxItemID
        self.rawText = rawText
        self.title = title
        self.destination = destination
        self.projectTitle = projectTitle
    }
}

@MainActor
final class CaptureWorkflowService {
    private let repository: FlowRepository

    init(repository: FlowRepository) {
        self.repository = repository
    }

    func makeDraft(for task: FlowTask) -> ClarifyDraft {
        ClarifyDraft(
            inboxItemID: task.id,
            rawText: task.title,
            title: task.title
        )
    }

    func submit(_ draft: ClarifyDraft) throws {
        let trimmedTitle = draft.title.trimmingCharacters(in: .whitespacesAndNewlines)
        guard trimmedTitle.isEmpty == false else {
            throw FlowDataError.message("Clarified title cannot be empty.")
        }

        let trimmedProject = draft.projectTitle.trimmingCharacters(in: .whitespacesAndNewlines)
        try repository.clarifyCapture(
            id: draft.inboxItemID,
            title: trimmedTitle,
            destination: draft.destination,
            projectTitle: trimmedProject.isEmpty ? nil : trimmedProject
        )
    }

    func reject(inboxItemID: String) throws {
        try repository.rejectCapture(id: inboxItemID)
    }
}

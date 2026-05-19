import Combine
import Foundation

enum FlowSelectionDirection {
    case previous
    case next
}

@MainActor
final class WorkspaceStore: ObservableObject {
    @Published var selectedSection: FlowSection = .today
    @Published var snapshot: WorkspaceSnapshot = WorkspaceSnapshot.empty
    @Published var searchText: String = ""
    @Published var selectedTaskID: String?
    @Published var isInspectorPresented = false
    @Published var isCapturePresented = false
    @Published var captureDraft = ""
    @Published var clarifyDraft: ClarifyDraft?
    @Published var assistantPrompt = ""
    @Published var assistantComposerText = ""
    @Published var assistantSessions: [FlowAssistantSession] = []
    @Published var selectedAssistantSessionID: String?
    @Published var assistantMessages: [FlowAssistantMessage] = []
    @Published var selectedAssistantMessageID: String?
    @Published var assistantSendPending = false
    @Published private(set) var assistantQueuedMessageCount = 0
    @Published var assistantProposalActionPending = false
    @Published var assistantActionFeedback: String?
    // Legacy compatibility for review-guidance and migration-era assistant turn reads.
    @Published var assistantTurns: [FlowAssistantTurn] = []
    // Legacy compatibility only; the rendered Assistant workspace is session/message-first.
    @Published var selectedAssistantTurnID: String?
    @Published var memoryRecords: [FlowMemoryRecord] = []
    @Published var selectedMemoryID: String?
    @Published var memoryEditorText = ""
    @Published var dailyPlanState: FlowDailyPlanState
    @Published var dailyPlanDraftTopItemIDs: [String] = []
    @Published var dailyPlanDraftBonusItemIDs: [String] = []
    @Published var weeklyReviewPackage: FlowWeeklyReviewPackage = .empty
    @Published var selectedReviewActionIDs: Set<String> = []
    @Published var reviewLastActionFeedback: String?
    @Published var notificationPolicy: FlowNotificationPolicyState = .empty
    @Published var errorMessage: String?

    private let dailyPlanTopLimit = 3
    private let dailyPlanBonusLimit = 2
    private let repository: FlowRepository
    private let captureWorkflow: CaptureWorkflowService
    private let assistantWorkflow: AssistantWorkflowService
    private let memoryWorkflow: MemoryWorkflowService
    private let dailyPlanWorkflow: DailyPlanWorkflowService
    private var assistantQueuedPrompts: [String] = []
    private var assistantActiveSendTask: Task<Void, Never>?
    private var assistantActiveSendID: UUID?

    init(repository: FlowRepository) {
        self.repository = repository
        self.captureWorkflow = CaptureWorkflowService(repository: repository)
        let dailyPlanWorkflow = DailyPlanWorkflowService(repository: repository)
        self.dailyPlanWorkflow = dailyPlanWorkflow
        self.assistantWorkflow = AssistantWorkflowService(
            repository: repository,
            planDateProvider: { dailyPlanWorkflow.planDateString() }
        )
        self.memoryWorkflow = MemoryWorkflowService(repository: repository)
        self.snapshot = SampleWorkspaceFactory.makeSnapshot()
        self.dailyPlanState = .empty(planDate: dailyPlanWorkflow.planDateString())
        self.selectedTaskID = snapshot.todayItems.first?.id
    }

    func refresh() {
        do {
            snapshot = try repository.loadWorkspaceSnapshot()
            assistantSessions = try assistantWorkflow.loadSessions()
            reconcileAssistantSessionSelection()
            loadSelectedAssistantMessages()
            do {
                assistantTurns = try assistantWorkflow.loadTurns()
            } catch {
                assistantTurns = []
            }
            if let selectedAssistantTurnID, assistantTurns.contains(where: { $0.id == selectedAssistantTurnID }) == false {
                self.selectedAssistantTurnID = assistantTurns.first?.id
            } else if self.selectedAssistantTurnID == nil {
                self.selectedAssistantTurnID = assistantTurns.first?.id
            }

            memoryRecords = try memoryWorkflow.load(query: nil)
            if let selectedMemoryID, memoryRecords.contains(where: { $0.id == selectedMemoryID }) == false {
                self.selectedMemoryID = memoryRecords.first?.id
                self.memoryEditorText = memoryRecords.first?.value ?? ""
            } else if self.selectedMemoryID == nil {
                self.selectedMemoryID = memoryRecords.first?.id
                self.memoryEditorText = memoryRecords.first?.value ?? ""
            }

            let planDate = dailyPlanWorkflow.planDateString()
            dailyPlanState = try dailyPlanWorkflow.load(planDate: planDate)
            dailyPlanDraftTopItemIDs = dailyPlanState.topItems.map(\.id)
            dailyPlanDraftBonusItemIDs = dailyPlanState.bonusItems.map(\.id)
            weeklyReviewPackage = try repository.loadWeeklyReviewPackage(referenceDate: Date())
            selectedReviewActionIDs.formIntersection(weeklyReviewPackage.cleanupActions.map(\.id))
            notificationPolicy = try repository.loadNotificationPolicy()
            reconcileSelection()
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    func capture() {
        do {
            let created = try repository.capture(title: captureDraft)
            captureDraft = ""
            isCapturePresented = false
            refresh()
            selectedSection = .inbox
            selectedTaskID = created.id
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    func beginClarify() {
        guard selectedSection == .inbox, let selectedTask else { return }
        clarifyDraft = captureWorkflow.makeDraft(for: selectedTask)
    }

    func cancelClarify() {
        clarifyDraft = nil
    }

    func confirmClarify() {
        guard let clarifyDraft else { return }
        do {
            try captureWorkflow.submit(clarifyDraft)
            self.clarifyDraft = nil
            refresh()
            selectedSection = clarifyDraft.destination == .project ? .projects : .today
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    func rejectClarify() {
        guard let clarifyDraft else { return }
        do {
            try captureWorkflow.reject(inboxItemID: clarifyDraft.inboxItemID)
            self.clarifyDraft = nil
            refresh()
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    func sendAssistantPrompt() {
        assistantComposerText = assistantPrompt
        sendAssistantMessage()
    }

    func createAssistantSession(title: String? = nil) {
        guard assistantSendPending == false else { return }
        let trimmed = (title ?? assistantComposerText).trimmingCharacters(in: .whitespacesAndNewlines)
        do {
            let session = try assistantWorkflow.createSession(title: trimmed.isEmpty ? "New Chat" : trimmed)
            selectedAssistantSessionID = session.id
            assistantMessages = try assistantWorkflow.loadMessages(sessionID: session.id)
            selectedAssistantMessageID = assistantMessages.last(where: { $0.role == "assistant" })?.id
            assistantPrompt = ""
            assistantComposerText = ""
            assistantActionFeedback = nil
            refresh()
            selectedSection = .assistant
            selectedAssistantSessionID = session.id
            selectedAssistantMessageID = assistantMessages.last(where: { $0.role == "assistant" })?.id
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    func sendAssistantMessage() {
        let trimmed = assistantComposerText.trimmingCharacters(in: .whitespacesAndNewlines)
        guard trimmed.isEmpty == false else { return }

        if assistantSendPending {
            queueAssistantMessage(trimmed)
            return
        }

        beginAssistantSend(prompt: trimmed)
    }

    func stopAssistantMessage() {
        guard assistantSendPending || assistantActiveSendTask != nil else { return }

        assistantActiveSendTask?.cancel()
        assistantActiveSendTask = nil
        assistantActiveSendID = nil
        assistantQueuedPrompts.removeAll()
        assistantQueuedMessageCount = 0
        assistantSendPending = false
        assistantActionFeedback = "Stopped assistant response."
    }

    private func queueAssistantMessage(_ prompt: String) {
        let sendContext = currentAssistantSendContext()
        assistantQueuedPrompts.append(prompt)
        assistantQueuedMessageCount = assistantQueuedPrompts.count
        assistantComposerText = ""
        selectedSection = .assistant
        assistantMessages.append(
            pendingUserMessage(
                sessionID: sendContext.pendingSessionID,
                content: prompt,
                route: "queued",
                providerStatus: "queued",
                providerDetail: "Queued for the next assistant turn.",
                createdAtLabel: "Queued",
                updatedAtLabel: "Queued"
            )
        )
    }

    private func beginAssistantSend(prompt: String) {
        assistantSendPending = true
        assistantActionFeedback = nil
        assistantComposerText = ""
        selectedSection = .assistant

        let sendID = UUID()
        let repository = repository
        let planDate = dailyPlanWorkflow.planDateString()
        let sendContext = currentAssistantSendContext()
        let selectedSessionID = sendContext.selectedSessionID
        let hasValidSelectedSession = sendContext.hasValidSelectedSession
        assistantActiveSendID = sendID
        assistantMessages.append(pendingUserMessage(sessionID: sendContext.pendingSessionID, content: prompt))

        assistantActiveSendTask = Task.detached(priority: .userInitiated) {
            do {
                let sessionID: String
                if let selectedSessionID, hasValidSelectedSession {
                    sessionID = selectedSessionID
                } else {
                    let createdSession = try repository.createAssistantSession(title: prompt)
                    sessionID = createdSession.id
                }

                let message = try repository.sendAssistantMessage(sessionID: sessionID, prompt: prompt, planDate: planDate)
                let sessions = try repository.loadAssistantSessions(limit: 100)
                let messages = try repository.loadAssistantMessages(sessionID: sessionID, limit: 100)
                let turns = (try? repository.loadAssistantTurns(limit: 30)) ?? []

                guard Task.isCancelled == false else { return }
                await MainActor.run {
                    guard self.assistantActiveSendID == sendID else { return }
                    self.assistantSessions = sessions
                    self.assistantMessages = messages
                    self.assistantTurns = turns
                    self.assistantPrompt = prompt
                    self.assistantActionFeedback = nil
                    self.selectedSection = .assistant
                    self.selectedAssistantSessionID = sessionID
                    self.selectedAssistantMessageID = message.id
                    self.assistantPrompt = ""
                    self.assistantSendPending = false
                    self.assistantActiveSendTask = nil
                    self.assistantActiveSendID = nil
                    self.sendNextQueuedAssistantMessageIfNeeded()
                }
            } catch {
                guard Task.isCancelled == false else { return }
                await MainActor.run {
                    guard self.assistantActiveSendID == sendID else { return }
                    self.assistantActionFeedback = "Could not send assistant message: \(error.localizedDescription)"
                    self.errorMessage = error.localizedDescription
                    self.assistantSendPending = false
                    self.assistantActiveSendTask = nil
                    self.assistantActiveSendID = nil
                }
            }
        }
    }

    private func sendNextQueuedAssistantMessageIfNeeded() {
        guard assistantSendPending == false else { return }
        let pendingDraft = assistantComposerText.trimmingCharacters(in: .whitespacesAndNewlines)
        if assistantQueuedPrompts.isEmpty, pendingDraft.isEmpty == false {
            assistantQueuedPrompts.append(pendingDraft)
            assistantComposerText = ""
        }
        guard assistantQueuedPrompts.isEmpty == false else { return }

        let nextPrompt = assistantQueuedPrompts.removeFirst()
        assistantQueuedMessageCount = assistantQueuedPrompts.count
        beginAssistantSend(prompt: nextPrompt)
    }

    private func currentAssistantSendContext() -> (selectedSessionID: String?, hasValidSelectedSession: Bool, pendingSessionID: String) {
        let selectedSessionID = selectedAssistantSessionID
        let hasValidSelectedSession = selectedAssistantSession.map { session in
            assistantSessions.contains(where: { $0.id == session.id })
        } ?? false
        let pendingSessionID = hasValidSelectedSession ? (selectedSessionID ?? "pending-assistant-session") : "pending-assistant-session"
        return (selectedSessionID, hasValidSelectedSession, pendingSessionID)
    }

    private func pendingUserMessage(
        sessionID: String,
        content: String,
        route: String = "pending",
        providerStatus: String = "pending",
        providerDetail: String = "Waiting for assistant response.",
        createdAtLabel: String = "Sending",
        updatedAtLabel: String = "Sending"
    ) -> FlowAssistantMessage {
        FlowAssistantMessage(
            id: "pending-user-\(UUID().uuidString)",
            sessionID: sessionID,
            role: "user",
            content: content,
            route: route,
            proposal: nil,
            proposalStatus: "none",
            auditSteps: [],
            provider: "local",
            providerStatus: providerStatus,
            providerDetail: providerDetail,
            providerModel: nil,
            sourceTurnID: nil,
            createdAtLabel: createdAtLabel,
            updatedAtLabel: updatedAtLabel
        )
    }

    func confirmSelectedAssistantProposal() {
        guard assistantProposalActionPending == false else { return }
        guard let message = selectedAssistantMessage ?? assistantMessages.last(where: { $0.role == "assistant" }) else { return }
        guard message.proposalStatus == "pending" else {
            let feedback = "Could not confirm assistant proposal: Assistant proposal is not pending."
            assistantActionFeedback = feedback
            errorMessage = feedback
            return
        }
        do {
            assistantProposalActionPending = true
            defer { assistantProposalActionPending = false }

            let messageID = message.id
            _ = try assistantWorkflow.confirm(messageID: messageID)
            assistantActionFeedback = "Confirmed assistant proposal."
            refresh()
            selectedAssistantMessageID = messageID
        } catch {
            let feedback = "Could not confirm assistant proposal: \(error.localizedDescription)"
            assistantActionFeedback = feedback
            errorMessage = error.localizedDescription
        }
    }

    func dismissSelectedAssistantProposal() {
        guard assistantProposalActionPending == false else { return }
        guard let message = selectedAssistantMessage ?? assistantMessages.last(where: { $0.role == "assistant" }) else { return }
        guard message.proposalStatus == "pending" else {
            let feedback = "Could not dismiss assistant proposal: Assistant proposal is not pending."
            assistantActionFeedback = feedback
            errorMessage = feedback
            return
        }
        do {
            assistantProposalActionPending = true
            defer { assistantProposalActionPending = false }

            let messageID = message.id
            try assistantWorkflow.dismiss(messageID: messageID)
            assistantActionFeedback = "Dismissed assistant proposal."
            refresh()
            selectedAssistantMessageID = messageID
        } catch {
            let feedback = "Could not dismiss assistant proposal: \(error.localizedDescription)"
            assistantActionFeedback = feedback
            errorMessage = error.localizedDescription
        }
    }

    func undoLastAssistantMutation() {
        do {
            let feedback = try assistantWorkflow.undoLastMutation()
            assistantActionFeedback = feedback ?? "No assistant writes were available to undo."
            refresh()
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    func selectAssistantTurn(id: String) {
        selectedAssistantTurnID = id
    }

    func selectAssistantSession(id: String) {
        guard assistantSendPending == false else { return }
        selectedAssistantSessionID = id
        loadSelectedAssistantMessages()
    }

    func selectAssistantMessage(id: String) {
        selectedAssistantMessageID = id
    }

    var selectedAssistantTurn: FlowAssistantTurn? {
        assistantTurns.first(where: { $0.id == selectedAssistantTurnID }) ?? assistantTurns.first
    }

    var selectedAssistantSession: FlowAssistantSession? {
        assistantSessions.first(where: { $0.id == selectedAssistantSessionID }) ?? assistantSessions.first
    }

    var selectedAssistantMessage: FlowAssistantMessage? {
        assistantMessages.first(where: { $0.id == selectedAssistantMessageID })
            ?? assistantMessages.last(where: { $0.role == "assistant" })
            ?? assistantMessages.last
    }

    var selectedAssistantMessageDisclosureSummary: String? {
        selectedAssistantMessage.map(assistantMessageDisclosureSummary(for:))
    }

    var assistantMessageDisclosureSummaries: [String] {
        assistantMessages.map(assistantMessageDisclosureSummary(for:))
    }

    var filteredMemoryRecords: [FlowMemoryRecord] {
        let query = normalizedQuery
        guard query.isEmpty == false else { return memoryRecords }
        return memoryRecords.filter {
            $0.value.localizedCaseInsensitiveContains(query)
                || $0.kind.localizedCaseInsensitiveContains(query)
                || $0.scope.localizedCaseInsensitiveContains(query)
                || $0.whyItMatters.localizedCaseInsensitiveContains(query)
        }
    }

    func selectMemory(id: String) {
        selectedMemoryID = id
        memoryEditorText = memoryRecords.first(where: { $0.id == id })?.value ?? ""
    }

    var selectedMemoryRecord: FlowMemoryRecord? {
        filteredMemoryRecords.first(where: { $0.id == selectedMemoryID })
            ?? memoryRecords.first(where: { $0.id == selectedMemoryID })
            ?? filteredMemoryRecords.first
    }

    func saveSelectedMemoryEdit() {
        guard let selectedMemoryRecord else { return }
        do {
            try memoryWorkflow.update(id: selectedMemoryRecord.id, value: memoryEditorText)
            refresh()
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    func toggleSelectedMemoryEnabled() {
        guard let selectedMemoryRecord else { return }
        do {
            try memoryWorkflow.setEnabled(id: selectedMemoryRecord.id, enabled: selectedMemoryRecord.enabled == false)
            refresh()
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    func deleteSelectedMemory() {
        guard let selectedMemoryRecord else { return }
        do {
            try memoryWorkflow.delete(id: selectedMemoryRecord.id)
            refresh()
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    func addDailyPlanTopItem(id: String) {
        guard dailyPlanDraftTopItemIDs.contains(id) == false else { return }
        guard dailyPlanDraftTopItemIDs.count < dailyPlanTopLimit else { return }

        dailyPlanDraftBonusItemIDs.removeAll { $0 == id }
        dailyPlanDraftTopItemIDs.append(id)
    }

    func addDailyPlanBonusItem(id: String) {
        guard dailyPlanDraftBonusItemIDs.contains(id) == false else { return }
        guard dailyPlanDraftBonusItemIDs.count < dailyPlanBonusLimit else { return }

        dailyPlanDraftTopItemIDs.removeAll { $0 == id }
        dailyPlanDraftBonusItemIDs.append(id)
    }

    func removeDailyPlanItem(id: String) {
        dailyPlanDraftTopItemIDs.removeAll { $0 == id }
        dailyPlanDraftBonusItemIDs.removeAll { $0 == id }
    }

    func saveDailyPlan() {
        do {
            let planDate = dailyPlanWorkflow.planDateString()
            try dailyPlanWorkflow.save(
                planDate: planDate,
                topItemIDs: Array(dailyPlanDraftTopItemIDs.prefix(dailyPlanTopLimit)),
                bonusItemIDs: Array(dailyPlanDraftBonusItemIDs.prefix(dailyPlanBonusLimit))
            )
            refresh()
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    func markDone(_ task: FlowTask) {
        do {
            try repository.markTaskDone(id: task.id)
            refresh()
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    func archive(_ task: FlowTask) {
        do {
            try repository.archiveTask(id: task.id)
            refresh()
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    func toggleReviewAction(id: String) {
        guard reviewArchiveActions.contains(where: { $0.id == id }) else { return }
        reviewLastActionFeedback = nil
        if selectedReviewActionIDs.contains(id) {
            selectedReviewActionIDs.remove(id)
        } else {
            selectedReviewActionIDs.insert(id)
        }
    }

    func applySelectedReviewActions() {
        let actionIDs = Array(selectedReviewActionIDs)
        let archiveCount = actionIDs.count
        guard archiveCount > 0 else { return }
        do {
            try repository.applyWeeklyReviewActions(actionIDs: actionIDs, referenceDate: Date())
            selectedReviewActionIDs.removeAll()
            reviewLastActionFeedback = archiveCount == 1
                ? "Archived 1 stale item. Follow-up actions still need to be handled in their workspace."
                : "Archived \(archiveCount) stale items. Follow-up actions still need to be handled in their workspace."
            refresh()
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    func openReviewGuidance(for action: FlowReviewCleanupAction) {
        let destination = reviewGuidanceDestination(for: action)
        select(section: destination)
        reviewLastActionFeedback = guidanceFeedback(for: action, destination: destination)
    }

    func triggerReviewGuidedAction(_ action: FlowReviewCleanupAction) {
        do {
            if action.kind == "project_next_action_review",
               let projectID = action.targetIDs.first {
                let session = try assistantWorkflow.createSession(title: action.title)
                let prompt = "Draft a next action for project \(projectID): \(action.detail)"
                let message = try assistantWorkflow.sendMessage(sessionID: session.id, prompt: prompt)
                assistantComposerText = ""
                assistantActionFeedback = nil
                refresh()
                selectedSection = .assistant
                selectedAssistantSessionID = session.id
                assistantMessages = try assistantWorkflow.loadMessages(sessionID: session.id)
                selectedAssistantMessageID = message.id
                selectedAssistantTurnID = nil
                reviewLastActionFeedback = "Opened Assistant with a session draft for the next action review."
                return
            }

            openReviewGuidance(for: action)
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    func reviewGuidanceDestination(for action: FlowReviewCleanupAction) -> FlowSection {
        switch action.kind {
        case "clarify_inbox":
            return .inbox
        case "project_next_action_review":
            return .projects
        case "deadline_review":
            return .today
        default:
            return .review
        }
    }

    func reviewGuidanceButtonTitle(for action: FlowReviewCleanupAction) -> String {
        switch reviewGuidanceDestination(for: action) {
        case .inbox:
            return "Open Inbox"
        case .projects:
            return action.kind == "project_next_action_review" ? "Draft Next Action" : "Open Projects"
        case .today:
            return "Open Today"
        case .review:
            return "Stay in Review"
        case .assistant:
            return "Open Assistant"
        case .memory:
            return "Open Memory"
        }
    }

    var reviewArchiveActions: [FlowReviewCleanupAction] {
        weeklyReviewPackage.cleanupActions.filter { $0.kind == "archive_stale_item" }
    }

    var reviewGuidedActions: [FlowReviewCleanupAction] {
        weeklyReviewPackage.cleanupActions.filter { $0.kind != "archive_stale_item" }
    }

    var reviewArchiveSelectionSummary: String {
        let count = selectedReviewActionIDs.count
        if count == 0 {
            return reviewArchiveActions.isEmpty
                ? "No stale items need archiving right now."
                : "Select the stale items that should leave the live system."
        }
        if count == 1 {
            return "1 stale item selected for archive."
        }
        return "\(count) stale items selected for archive."
    }

    var reviewApplyButtonTitle: String {
        let count = selectedReviewActionIDs.count
        if count == 0 {
            return "Archive Selected"
        }
        if count == 1 {
            return "Archive 1 Selected Item"
        }
        return "Archive \(count) Selected Items"
    }

    var selectedTask: FlowTask? {
        allTasks.first(where: { $0.id == selectedTaskID }) ?? visibleTasks.first
    }

    var visibleTasks: [FlowTask] {
        switch selectedSection {
        case .today:
            return filteredTodayItems + filteredLaterItems
        case .inbox:
            return filteredInboxItems
        case .projects:
            return filteredProjectTasks
        case .review:
            return filteredStaleItems
        case .assistant:
            return filteredTodayItems + filteredInboxItems
        case .memory:
            return filteredTodayItems
        }
    }

    var filteredInboxItems: [FlowTask] {
        filter(snapshot.inboxItems)
    }

    var filteredTodayItems: [FlowTask] {
        filter(snapshot.todayItems)
    }

    var filteredLaterItems: [FlowTask] {
        filter(snapshot.laterItems)
    }

    var filteredStaleItems: [FlowTask] {
        filter(snapshot.staleItems)
    }

    var filteredProjects: [FlowProject] {
        let query = normalizedQuery
        guard query.isEmpty == false else { return snapshot.projects }

        return snapshot.projects.filter { project in
            project.title.localizedCaseInsensitiveContains(query)
                || project.summary.localizedCaseInsensitiveContains(query)
                || project.tasks.contains(where: { matches(task: $0, query: query) })
        }
    }

    var filteredProjectTasks: [FlowTask] {
        filteredProjects.flatMap(\.tasks)
    }

    var focusMetrics: [(String, String)] {
        [
            ("Today", "\(snapshot.todayItems.count)"),
            ("Inbox", "\(snapshot.inboxItems.count)"),
            ("Projects", "\(snapshot.projects.count)"),
            ("Stale", "\(snapshot.review.staleCount)")
        ]
    }

    func clearError() {
        errorMessage = nil
    }

    func select(section: FlowSection) {
        selectedSection = section
        selectedTaskID = visibleTasks.first?.id
        isInspectorPresented = false
    }

    func select(task: FlowTask) {
        selectedTaskID = task.id
        isInspectorPresented = true
    }

    func toggleInspector() {
        isInspectorPresented.toggle()
    }

    func moveSelection(_ direction: FlowSelectionDirection) {
        let tasks = visibleTasks
        guard tasks.isEmpty == false else {
            selectedTaskID = nil
            isInspectorPresented = false
            return
        }

        guard let selectedTaskID,
              let currentIndex = tasks.firstIndex(where: { $0.id == selectedTaskID }) else {
            self.selectedTaskID = tasks.first?.id
            isInspectorPresented = true
            return
        }

        let step = direction == .next ? 1 : -1
        let nextIndex = min(max(currentIndex + step, 0), tasks.count - 1)
        self.selectedTaskID = tasks[nextIndex].id
        isInspectorPresented = true
    }

    private var allTasks: [FlowTask] {
        snapshot.inboxItems
            + snapshot.todayItems
            + snapshot.laterItems
            + snapshot.projects.flatMap(\.tasks)
            + snapshot.staleItems
    }

    private var normalizedQuery: String {
        searchText.trimmingCharacters(in: .whitespacesAndNewlines)
    }

    private func filter(_ tasks: [FlowTask]) -> [FlowTask] {
        let query = normalizedQuery
        guard query.isEmpty == false else { return tasks }
        return tasks.filter { matches(task: $0, query: query) }
    }

    private func matches(task: FlowTask, query: String) -> Bool {
        task.title.localizedCaseInsensitiveContains(query)
            || task.summary.localizedCaseInsensitiveContains(query)
            || (task.projectName?.localizedCaseInsensitiveContains(query) ?? false)
            || task.tags.contains(where: { $0.localizedCaseInsensitiveContains(query) })
    }

    private func guidanceFeedback(for action: FlowReviewCleanupAction, destination: FlowSection) -> String {
        switch action.kind {
        case "clarify_inbox":
            return "Opened Inbox so you can clarify the captures that still need decisions."
        case "project_next_action_review":
            return "Opened Projects so you can add the next actions that are still missing."
        case "deadline_review":
            return "Opened Today so you can review the upcoming deadlines in context."
        default:
            return "Opened \(destination.title) so you can continue this review step."
        }
    }

    func assistantMessageDisclosureSummary(for message: FlowAssistantMessage) -> String {
        var parts = [
            "Provider: \(message.provider)",
            "Status: \(message.providerStatus)"
        ]

        if message.providerDetail.isEmpty == false {
            parts.append("Detail: \(message.providerDetail)")
        }

        if let providerModel = message.providerModel, providerModel.isEmpty == false {
            parts.append("Model: \(providerModel)")
        }

        if let sourceTurnID = message.sourceTurnID {
            parts.append("Source Turn: \(sourceTurnID)")
        } else {
            parts.append("Source Turn: none")
        }

        if message.auditSteps.isEmpty == false {
            parts.append(contentsOf: message.auditSteps.map { "\($0.stage): \($0.summary)" })
        } else {
            parts.append("Audit: none")
        }

        return parts.joined(separator: " | ")
    }

    private func reconcileAssistantSessionSelection() {
        if let selectedAssistantSessionID,
           assistantSessions.contains(where: { $0.id == selectedAssistantSessionID }) == false {
            self.selectedAssistantSessionID = assistantSessions.first?.id
        } else if self.selectedAssistantSessionID == nil {
            self.selectedAssistantSessionID = assistantSessions.first?.id
        }

        loadSelectedAssistantMessages()
    }

    private func loadSelectedAssistantMessages() {
        guard let selectedAssistantSessionID else {
            assistantMessages = []
            selectedAssistantMessageID = nil
            return
        }

        do {
            assistantMessages = try assistantWorkflow.loadMessages(sessionID: selectedAssistantSessionID)
            if let selectedAssistantMessageID,
               assistantMessages.contains(where: { $0.id == selectedAssistantMessageID }) == false {
                self.selectedAssistantMessageID = assistantMessages.last(where: { $0.role == "assistant" })?.id
            } else if self.selectedAssistantMessageID == nil {
                self.selectedAssistantMessageID = assistantMessages.last(where: { $0.role == "assistant" })?.id
            }
        } catch {
            assistantMessages = []
            selectedAssistantMessageID = nil
            errorMessage = error.localizedDescription
        }
    }

    private func reconcileSelection() {
        if let selectedTaskID, allTasks.contains(where: { $0.id == selectedTaskID }) {
            return
        }
        selectedTaskID = visibleTasks.first?.id
    }
}

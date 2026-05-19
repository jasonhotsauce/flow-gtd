import Foundation

enum FlowSection: String, CaseIterable, Identifiable {
    case today
    case inbox
    case projects
    case review
    case assistant
    case memory

    var id: String { rawValue }

    var title: String {
        switch self {
        case .today: return "Today"
        case .inbox: return "Inbox"
        case .projects: return "Projects"
        case .review: return "Review"
        case .assistant: return "Assistant"
        case .memory: return "Memory"
        }
    }

    var subtitle: String {
        switch self {
        case .today: return "Focused execution"
        case .inbox: return "Captured intent"
        case .projects: return "Active outcomes"
        case .review: return "System health"
        case .assistant: return "Guided actions"
        case .memory: return "Behavior signals"
        }
    }

    var symbolName: String {
        switch self {
        case .today: return "sparkles.square.filled.on.square"
        case .inbox: return "tray.full"
        case .projects: return "square.grid.2x2.fill"
        case .review: return "checklist.checked"
        case .assistant: return "bubble.left.and.text.bubble.right.fill"
        case .memory: return "brain.head.profile"
        }
    }
}

enum FlowTaskStatus: String, Codable {
    case active
    case done
    case waiting
    case someday
    case archived

    var label: String {
        switch self {
        case .active: return "Active"
        case .done: return "Done"
        case .waiting: return "Waiting"
        case .someday: return "Someday"
        case .archived: return "Archived"
        }
    }
}

enum FlowTaskSource: String, Codable {
    case capture
    case planned
    case project
    case reminders
    case assistant
}

struct FlowTask: Identifiable, Hashable, Codable {
    let id: String
    var title: String
    var summary: String
    var status: FlowTaskStatus
    var source: FlowTaskSource
    var projectName: String?
    var dueLabel: String?
    var tags: [String]
    var estimatedMinutes: Int?
    var isFlagged: Bool
    var lastUpdatedLabel: String?
}

struct FlowProject: Identifiable, Hashable, Codable {
    let id: String
    var title: String
    var summary: String
    var nextActionTitle: String?
    var activeCount: Int
    var completedCount: Int
    var tasks: [FlowTask]
}

struct ReviewSummary: Hashable, Codable {
    var completedThisWeek: Int
    var staleCount: Int
    var dueSoonCount: Int
    var headline: String
    var prompt: String
}

struct FlowProjectHealth: Identifiable, Hashable, Codable {
    let id: String
    var title: String
    var statusLabel: String
    var detail: String
}

struct FlowReviewCleanupAction: Identifiable, Hashable, Codable {
    let id: String
    var kind: String
    var title: String
    var detail: String
    var targetIDs: [String]
    var destructive: Bool
}

struct FlowWeeklyReviewPackage: Hashable, Codable {
    var generatedAtLabel: String
    var completedWork: [FlowTask]
    var staleItems: [FlowTask]
    var inboxItems: [FlowTask]
    var projectHealth: [FlowProjectHealth]
    var upcomingDeadlines: [FlowTask]
    var cleanupActions: [FlowReviewCleanupAction]

    static let empty = FlowWeeklyReviewPackage(
        generatedAtLabel: "Not generated",
        completedWork: [],
        staleItems: [],
        inboxItems: [],
        projectHealth: [],
        upcomingDeadlines: [],
        cleanupActions: []
    )
}

struct AssistantSuggestion: Identifiable, Hashable, Codable {
    let id: String
    var title: String
    var detail: String
    var outcomeLabel: String
}

struct FlowAssistantProposal: Hashable, Codable {
    var actionType: String
    var title: String
    var detail: String
    var requiresConfirmation: Bool
}

struct FlowAssistantAuditStep: Identifiable, Hashable, Codable {
    let id: String
    var stage: String
    var status: String
    var summary: String
    var payload: [String: String] = [:]
}

struct FlowAssistantTurn: Identifiable, Hashable, Codable {
    let id: String
    var prompt: String
    var response: String
    var route: String
    var proposal: FlowAssistantProposal?
    var proposalStatus: String
    var auditSteps: [FlowAssistantAuditStep]
    var provider: String = "unknown"
    var providerStatus: String = "unknown"
    var providerDetail: String = ""
    var providerModel: String?
    var createdAtLabel: String
}

struct FlowAssistantSession: Identifiable, Hashable, Codable {
    let id: String
    var title: String
    var latestPreview: String
    var messageCount: Int
    var createdAtLabel: String
    var updatedAtLabel: String
}

struct FlowAssistantMessage: Identifiable, Hashable, Codable {
    let id: String
    var sessionID: String
    var role: String
    var content: String
    var route: String
    var proposal: FlowAssistantProposal?
    var proposalStatus: String
    var auditSteps: [FlowAssistantAuditStep]
    var provider: String = "unknown"
    var providerStatus: String = "unknown"
    var providerDetail: String = ""
    var providerModel: String?
    var sourceTurnID: String?
    var createdAtLabel: String
    var updatedAtLabel: String
}

struct MemoryEntry: Identifiable, Hashable, Codable {
    let id: String
    var title: String
    var detail: String
    var confidenceLabel: String
    var scopeLabel: String
}

struct FlowMemoryRecord: Identifiable, Hashable, Codable {
    let id: String
    var kind: String
    var scope: String
    var scopeRef: String?
    var value: String
    var source: String
    var confidence: Double
    var enabled: Bool
    var updatedAtLabel: String
    var whyItMatters: String
}

struct FlowDailyPlanState: Hashable, Codable {
    var planDate: String
    var topItems: [FlowTask]
    var bonusItems: [FlowTask]
    var mustAddress: [FlowTask]
    var inbox: [FlowTask]
    var readyActions: [FlowTask]
    var projectTasks: [FlowTask]
    var riskFlags: [String]
    var calendarStatus: String

    static func empty(planDate: String) -> FlowDailyPlanState {
        FlowDailyPlanState(
            planDate: planDate,
            topItems: [],
            bonusItems: [],
            mustAddress: [],
            inbox: [],
            readyActions: [],
            projectTasks: [],
            riskFlags: [],
            calendarStatus: "Calendar integration unavailable."
        )
    }
}

struct FlowNotificationCandidate: Identifiable, Hashable, Codable {
    let id: String
    var taskID: String
    var title: String
    var fireAtLabel: String
    var policyLabel: String
}

struct FlowNotificationPolicyState: Hashable, Codable {
    var permissionStatus: String
    var deliveryMode: String
    var degradedReasons: [String]
    var pendingNotifications: [FlowNotificationCandidate]
    var offlineDescription: String

    static let empty = FlowNotificationPolicyState(
        permissionStatus: "not_determined",
        deliveryMode: "degraded",
        degradedReasons: ["Local notification permission has not been requested."],
        pendingNotifications: [],
        offlineDescription: "Flow will keep tasks local and show degraded delivery until notification permission is available."
    )
}

struct WorkspaceSnapshot: Hashable, Codable {
    var inboxItems: [FlowTask]
    var todayItems: [FlowTask]
    var laterItems: [FlowTask]
    var projects: [FlowProject]
    var staleItems: [FlowTask]
    var review: ReviewSummary
    var assistantSuggestions: [AssistantSuggestion]
    var memoryEntries: [MemoryEntry]
    var focusHeadline: String

    static let empty = WorkspaceSnapshot(
        inboxItems: [],
        todayItems: [],
        laterItems: [],
        projects: [],
        staleItems: [],
        review: ReviewSummary(
            completedThisWeek: 0,
            staleCount: 0,
            dueSoonCount: 0,
            headline: "Ready for a calm start",
            prompt: "Capture a few priorities and shape the day."
        ),
        assistantSuggestions: [],
        memoryEntries: [],
        focusHeadline: "No live data yet"
    )
}

enum FlowDataError: LocalizedError {
    case message(String)

    var errorDescription: String? {
        switch self {
        case .message(let message):
            return message
        }
    }
}

enum SampleWorkspaceFactory {
    static func makeSnapshot() -> WorkspaceSnapshot {
        let todayItems = [
            FlowTask(
                id: "sample-today-1",
                title: "Draft the native launch narrative",
                summary: "Turn the migration scope into a concise story for the first beta.",
                status: .active,
                source: .planned,
                projectName: "Native App Launch",
                dueLabel: "Today",
                tags: ["launch", "messaging"],
                estimatedMinutes: 45,
                isFlagged: true,
                lastUpdatedLabel: "Edited 10m ago"
            ),
            FlowTask(
                id: "sample-today-2",
                title: "Trim onboarding to one clear capture flow",
                summary: "Reduce setup friction and keep the first session focused.",
                status: .active,
                source: .planned,
                projectName: "First Run",
                dueLabel: "2 PM",
                tags: ["onboarding", "ux"],
                estimatedMinutes: 30,
                isFlagged: false,
                lastUpdatedLabel: "Edited 35m ago"
            ),
            FlowTask(
                id: "sample-today-3",
                title: "Review reminder copy for ownership clarity",
                summary: "Make sure imported reminders and Flow notifications are clearly separated.",
                status: .active,
                source: .planned,
                projectName: "Trust",
                dueLabel: "Tomorrow",
                tags: ["reminders", "copy"],
                estimatedMinutes: 20,
                isFlagged: false,
                lastUpdatedLabel: "Edited 1h ago"
            ),
        ]

        let laterItems = [
            FlowTask(
                id: "sample-later-1",
                title: "Define verifier rule copy for risky assistant writes",
                summary: "Clarify how warnings and blocks show up before confirmation.",
                status: .waiting,
                source: .assistant,
                projectName: "Assistant Safety",
                dueLabel: "This week",
                tags: ["assistant", "verifier"],
                estimatedMinutes: 50,
                isFlagged: false,
                lastUpdatedLabel: "Edited 3h ago"
            ),
            FlowTask(
                id: "sample-later-2",
                title: "Refine memory card language",
                summary: "Keep preferences inspectable without exposing internals.",
                status: .active,
                source: .project,
                projectName: "Memory UX",
                dueLabel: nil,
                tags: ["memory", "content"],
                estimatedMinutes: 25,
                isFlagged: false,
                lastUpdatedLabel: "Edited yesterday"
            ),
        ]

        let inboxItems = [
            FlowTask(
                id: "sample-inbox-1",
                title: "Ask Jason if weekly review should surface project drift",
                summary: "Open question from the native migration pass.",
                status: .active,
                source: .capture,
                projectName: nil,
                dueLabel: nil,
                tags: ["review", "question"],
                estimatedMinutes: nil,
                isFlagged: false,
                lastUpdatedLabel: "Captured 4m ago"
            ),
            FlowTask(
                id: "sample-inbox-2",
                title: "Collect screenshots of polished Mac productivity apps",
                summary: "Use them to calibrate spacing, material, and hierarchy.",
                status: .active,
                source: .capture,
                projectName: nil,
                dueLabel: nil,
                tags: ["visual", "reference"],
                estimatedMinutes: nil,
                isFlagged: false,
                lastUpdatedLabel: "Captured 18m ago"
            ),
        ]

        let launchProject = FlowProject(
            id: "sample-project-1",
            title: "Native App Launch",
            summary: "Turn Flow into a true Mac app without losing trusted local-first behavior.",
            nextActionTitle: todayItems.first?.title,
            activeCount: 4,
            completedCount: 2,
            tasks: todayItems + [
                FlowTask(
                    id: "sample-project-3",
                    title: "Polish empty states for the native shell",
                    summary: "Keep them useful, understated, and desktop-appropriate.",
                    status: .active,
                    source: .project,
                    projectName: "Native App Launch",
                    dueLabel: nil,
                    tags: ["ui", "empty-state"],
                    estimatedMinutes: 20,
                    isFlagged: false,
                    lastUpdatedLabel: "Edited yesterday"
                )
            ]
        )

        let review = ReviewSummary(
            completedThisWeek: 9,
            staleCount: 3,
            dueSoonCount: 2,
            headline: "Strong foundation, tighten the edges",
            prompt: "Clear three stale items and keep today to a realistic top set."
        )

        let assistantSuggestions = [
            AssistantSuggestion(
                id: "assistant-1",
                title: "Plan a lighter afternoon",
                detail: "You already have two medium-effort items on deck. Shift research work to later.",
                outcomeLabel: "Suggested"
            ),
            AssistantSuggestion(
                id: "assistant-2",
                title: "Clarify the open design question",
                detail: "One inbox item looks like it should become a project decision rather than a task.",
                outcomeLabel: "Needs review"
            ),
        ]

        let memoryEntries = [
            MemoryEntry(
                id: "memory-1",
                title: "Prefers a smaller focus set",
                detail: "Recent accepted plans skew toward 2-3 primary items, not wide daily lists.",
                confidenceLabel: "High confidence",
                scopeLabel: "Global"
            ),
            MemoryEntry(
                id: "memory-2",
                title: "Reminder copy should stay explicit",
                detail: "User repeatedly prefers wording that distinguishes imported reminders from Flow-owned notifications.",
                confidenceLabel: "Confirmed",
                scopeLabel: "Notifications"
            ),
        ]

        return WorkspaceSnapshot(
            inboxItems: inboxItems,
            todayItems: todayItems,
            laterItems: laterItems,
            projects: [launchProject],
            staleItems: [laterItems[1]],
            review: review,
            assistantSuggestions: assistantSuggestions,
            memoryEntries: memoryEntries,
            focusHeadline: "Three deliberate priorities, room to think"
        )
    }
}

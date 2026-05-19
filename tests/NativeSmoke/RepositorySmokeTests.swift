import Foundation
import SQLite3

@MainActor
@main
struct RepositorySmokeTests {
    static func main() throws {
        try smokeTestSampleFallback()
        try smokeTestCaptureRoundTrip()
        try smokeTestWorkspaceShowsAllTodayAndProjectTasks()
        try WorkflowStorageSmokeTests.run()
        try CaptureClarifySmokeTests.run()
        try AssistantWorkflowSmokeTests.run()
        try MemoryWorkflowSmokeTests.run()
        try DailyPlanWorkflowSmokeTests.run()
        try WeeklyReviewWorkflowSmokeTests.run()
        try NotificationPolicySmokeTests.run()
        try AppleBridgeStubSmokeTests.run()
        try SidecarReadRepositorySmokeTests.run()
        try SidecarWriteRepositorySmokeTests.run()
        try SidecarAssistantRepositorySmokeTests.run()
        try smokeTestSelectionNavigation()
        try smokeTestInspectorInteractionContract()
        try smokeTestWindowChromeClearance()
        try smokeTestMainWindowAdjustabilityContract()
        try smokeTestTodayLayoutDensity()
        try smokeTestTodayActionLayoutContract()
        try smokeTestDailyPlanShowsAllCandidateTasks()
        try smokeTestDailyPlanLimitsAreEnforcedInStore()
        try smokeTestProjectsLayoutAlignment()
        try smokeTestReviewGuidanceContract()
        print("Flow native smoke tests passed")
    }

    private static func smokeTestSampleFallback() throws {
        let databaseURL = URL(fileURLWithPath: NSTemporaryDirectory())
            .appendingPathComponent(UUID().uuidString)
            .appendingPathExtension("sqlite")

        let repository = LegacyFlowRepository(databaseURL: databaseURL)
        let snapshot = try repository.loadWorkspaceSnapshot()

        guard snapshot.inboxItems.isEmpty == false else {
            throw FlowDataError.message("Expected sample fallback inbox items.")
        }
        guard snapshot.todayItems.isEmpty == false else {
            throw FlowDataError.message("Expected sample fallback focus items.")
        }
    }

    private static func smokeTestCaptureRoundTrip() throws {
        let databaseURL = URL(fileURLWithPath: NSTemporaryDirectory())
            .appendingPathComponent(UUID().uuidString)
            .appendingPathExtension("sqlite")

        let repository = LegacyFlowRepository(databaseURL: databaseURL)
        let created = try repository.capture(title: "Follow up on native shell polish")
        let snapshot = try repository.loadWorkspaceSnapshot()

        guard snapshot.inboxItems.contains(where: { $0.id == created.id }) else {
            throw FlowDataError.message("Expected captured task to appear in inbox snapshot.")
        }
    }

    private static func smokeTestWorkspaceShowsAllTodayAndProjectTasks() throws {
        let databaseURL = URL(fileURLWithPath: NSTemporaryDirectory())
            .appendingPathComponent(UUID().uuidString)
            .appendingPathExtension("sqlite")

        let repository = LegacyFlowRepository(databaseURL: databaseURL)
        _ = try repository.loadWorkspaceSnapshot()

        try withDatabase(at: databaseURL) { db in
            try deleteSeedItems(db: db)

            try insertSeedItem(
                db: db,
                id: "project-overflow",
                type: "project",
                title: "Project Overflow",
                status: "active",
                parentID: nil,
                dueDate: nil,
                createdAt: "2026-05-01T08:00:00+00:00",
                updatedAt: "2026-05-01T08:00:00+00:00"
            )

            for index in 1...10 {
                try insertSeedItem(
                    db: db,
                    id: "project-task-\(index)",
                    type: "action",
                    title: "Project Task \(index)",
                    status: "active",
                    parentID: "project-overflow",
                    dueDate: nil,
                    createdAt: "2026-05-01T08:00:00+00:00",
                    updatedAt: String(format: "2026-05-%02dT08:00:00+00:00", index)
                )
            }

            for index in 1...28 {
                try insertSeedItem(
                    db: db,
                    id: "today-task-\(index)",
                    type: "action",
                    title: "Today Task \(index)",
                    status: "active",
                    parentID: nil,
                    dueDate: nil,
                    createdAt: "2026-05-01T08:00:00+00:00",
                    updatedAt: String(format: "2026-05-%02dT09:00:00+00:00", min(index, 28))
                )
            }
        }

        let snapshot = try repository.loadWorkspaceSnapshot()

        guard let project = snapshot.projects.first(where: { $0.id == "project-overflow" }) else {
            throw FlowDataError.message("Expected seeded project to appear in the Projects workspace snapshot.")
        }
        guard project.tasks.count == 10 else {
            throw FlowDataError.message("Expected Projects workspace to load all project tasks instead of truncating the list.")
        }
        let expectedLaterCount = 38
        guard snapshot.laterItems.count == expectedLaterCount else {
            throw FlowDataError.message(
                "Expected Today workspace to load all visible later tasks instead of truncating the queue. Found \(snapshot.laterItems.count) of \(expectedLaterCount)."
            )
        }
    }

    private static func smokeTestSelectionNavigation() throws {
        let store = WorkspaceStore(repository: StubRepository())

        guard store.selectedTask?.id == store.snapshot.todayItems.first?.id else {
            throw FlowDataError.message("Expected today workspace to start with the first focus item selected.")
        }
        guard store.isInspectorPresented == false else {
            throw FlowDataError.message("Expected the inspector to default to collapsed even when a task is selected.")
        }

        store.moveSelection(.next)
        guard store.selectedTask?.id == store.snapshot.todayItems.dropFirst().first?.id else {
            throw FlowDataError.message("Expected moving selection forward to choose the next visible today item.")
        }
        guard store.isInspectorPresented else {
            throw FlowDataError.message("Expected keyboard task navigation to reveal the inspector on demand.")
        }

        store.moveSelection(.previous)
        guard store.selectedTask?.id == store.snapshot.todayItems.first?.id else {
            throw FlowDataError.message("Expected moving selection backward to choose the previous visible today item.")
        }

        store.select(section: .inbox)
        guard store.selectedSection == .inbox else {
            throw FlowDataError.message("Expected section selection to update the active workspace.")
        }
        guard store.isInspectorPresented == false else {
            throw FlowDataError.message("Expected changing workspace sections to collapse the inspector.")
        }
        guard store.selectedTask?.id == store.snapshot.inboxItems.first?.id else {
            throw FlowDataError.message("Expected section selection to reconcile to the first visible task in that section.")
        }
    }

    private static func smokeTestInspectorInteractionContract() throws {
        guard WorkspaceInspectorMetrics.collapsedByDefault else {
            throw FlowDataError.message("Expected the workspace inspector contract to default to collapsed.")
        }

        guard WorkspaceInspectorMetrics.inspectorWidth <= 380 else {
            throw FlowDataError.message("Expected the inspector to remain narrow enough to preserve the main action workspace.")
        }

        let projectRootURL = URL(fileURLWithPath: #filePath)
            .deletingLastPathComponent()
            .deletingLastPathComponent()
            .deletingLastPathComponent()
        let workspaceSourceURL = projectRootURL.appendingPathComponent("Sources/FlowMacApp/UI/Workspace/Workspaces.swift")
        let workspaceSource = try String(contentsOf: workspaceSourceURL)

        guard workspaceSource.contains("if store.isInspectorPresented") else {
            throw FlowDataError.message("Expected WorkspaceShell to render the inspector conditionally.")
        }

        guard workspaceSource.contains("SurfaceCard(title: \"Memory Lens\"") == false else {
            throw FlowDataError.message("Expected memory context to stop living in the always-visible task inspector.")
        }

        guard workspaceSource.contains("SurfaceCard(title: \"Assistant Context\"") == false else {
            throw FlowDataError.message("Expected assistant context to stop living in the always-visible task inspector.")
        }
    }

    private static func smokeTestWindowChromeClearance() throws {
        guard WindowChromeMetrics.sidebarTopPadding >= WindowChromeMetrics.contentTopPadding else {
            throw FlowDataError.message("Expected sidebar clearance to stay at least as large as the main content clearance.")
        }

        guard WindowChromeMetrics.contentTopPadding <= 24 else {
            throw FlowDataError.message("Expected main content clearance to stay small once the split view already clears the toolbar.")
        }

        guard WindowChromeMetrics.sidebarTopPadding <= 36 else {
            throw FlowDataError.message("Expected sidebar clearance to stay compact enough to avoid a dead band under the toolbar.")
        }
    }

    private static func smokeTestTodayLayoutDensity() throws {
        guard TodayWorkspaceLayoutMetrics.heroMinimumHeight <= 196 else {
            throw FlowDataError.message("Expected the Today hero to stay compact enough to keep work cards above the fold.")
        }

        guard TodayWorkspaceLayoutMetrics.metricRailWidth <= 232 else {
            throw FlowDataError.message("Expected the Today metric cluster to stay compact instead of reintroducing a tall dashboard header.")
        }

        guard TodayWorkspaceLayoutMetrics.supportRailWidth <= 292 else {
            throw FlowDataError.message("Expected the Today support rail to stay narrow enough to preserve task density.")
        }

        guard TodayWorkspaceLayoutMetrics.compactCardSpacing <= 18 else {
            throw FlowDataError.message("Expected Today workspace spacing to remain tighter than the generic oversized layout.")
        }
    }

    private static func smokeTestTodayActionLayoutContract() throws {
        guard DailyPlanLayoutMetrics.primaryTaskLimit == 3 else {
            throw FlowDataError.message("Expected Daily Plan to preserve the PRD limit of three primary tasks.")
        }

        guard DailyPlanLayoutMetrics.secondaryTaskLimit == 2 else {
            throw FlowDataError.message("Expected Daily Plan to preserve the PRD limit of two secondary tasks.")
        }

        let projectRootURL = URL(fileURLWithPath: #filePath)
            .deletingLastPathComponent()
            .deletingLastPathComponent()
            .deletingLastPathComponent()
        let workspaceSourceURL = projectRootURL.appendingPathComponent("Sources/FlowMacApp/UI/Workspace/Workspaces.swift")
        let workspaceSource = try String(contentsOf: workspaceSourceURL)

        guard workspaceSource.contains("TodayActionHeader(store: store)") else {
            throw FlowDataError.message("Expected Today to use the compact action header.")
        }

        guard workspaceSource.contains("TodayHeroCard(store: store)") == false else {
            throw FlowDataError.message("Expected Today to stop rendering the oversized hero card.")
        }

        guard workspaceSource.contains("TodaySupportRail(store: store)") == false else {
            throw FlowDataError.message("Expected Today to stop rendering the support rail in the main action path.")
        }
    }

    private static func smokeTestDailyPlanShowsAllCandidateTasks() throws {
        let projectRootURL = URL(fileURLWithPath: #filePath)
            .deletingLastPathComponent()
            .deletingLastPathComponent()
            .deletingLastPathComponent()
        let dailyPlanSourceURL = projectRootURL.appendingPathComponent("Sources/FlowMacApp/UI/Planning/DailyPlanView.swift")
        let dailyPlanSource = try String(contentsOf: dailyPlanSourceURL)

        guard dailyPlanSource.contains("ForEach(tasks.prefix(4))") == false else {
            throw FlowDataError.message("Expected Daily Plan candidate sections to render all tasks instead of truncating each bucket after four rows.")
        }
    }

    private static func smokeTestDailyPlanLimitsAreEnforcedInStore() throws {
        let store = WorkspaceStore(repository: StubRepository())
        let allCandidateIDs = [
            "candidate-primary-1",
            "candidate-primary-2",
            "candidate-primary-3",
            "candidate-primary-4",
            "candidate-primary-5",
            "candidate-secondary-1",
            "candidate-secondary-2",
            "candidate-secondary-3",
            "candidate-secondary-4",
        ]

        for id in allCandidateIDs.prefix(5) {
            store.addDailyPlanTopItem(id: id)
        }
        guard store.dailyPlanDraftTopItemIDs.count == DailyPlanLayoutMetrics.primaryTaskLimit else {
            throw FlowDataError.message("Expected store-level Daily Plan primary additions to enforce the 3-task limit.")
        }

        for id in allCandidateIDs.suffix(4) {
            store.addDailyPlanBonusItem(id: id)
        }
        guard store.dailyPlanDraftBonusItemIDs.count == DailyPlanLayoutMetrics.secondaryTaskLimit else {
            throw FlowDataError.message("Expected store-level Daily Plan secondary additions to enforce the 2-task limit.")
        }

        let originalBonusIDs = store.dailyPlanDraftBonusItemIDs
        if let bonusID = originalBonusIDs.first {
            store.addDailyPlanTopItem(id: bonusID)
        }
        guard store.dailyPlanDraftBonusItemIDs == originalBonusIDs else {
            throw FlowDataError.message("Expected a full primary bucket not to drop an existing secondary item during promotion.")
        }

        let originalTopIDs = store.dailyPlanDraftTopItemIDs
        if let topID = originalTopIDs.first {
            store.addDailyPlanBonusItem(id: topID)
        }
        guard store.dailyPlanDraftTopItemIDs == originalTopIDs else {
            throw FlowDataError.message("Expected a full secondary bucket not to drop an existing primary item during demotion.")
        }
    }

    private static func smokeTestProjectsLayoutAlignment() throws {
        guard ProjectsWorkspaceLayoutMetrics.projectCardSpacing <= 18 else {
            throw FlowDataError.message("Expected Projects cards to stay close enough for a scannable full-width list.")
        }

        let projectRootURL = URL(fileURLWithPath: #filePath)
            .deletingLastPathComponent()
            .deletingLastPathComponent()
            .deletingLastPathComponent()
        let workspacesSourceURL = projectRootURL.appendingPathComponent("Sources/FlowMacApp/UI/Workspace/Workspaces.swift")
        let workspacesSource = try String(contentsOf: workspacesSourceURL)
        guard
            let projectsStart = workspacesSource.range(of: "struct ProjectsWorkspaceView"),
            let reviewStart = workspacesSource.range(of: "struct ReviewWorkspaceView")
        else {
            throw FlowDataError.message("Expected workspace source to contain Projects and Review view boundaries.")
        }
        let projectsSource = String(workspacesSource[projectsStart.lowerBound..<reviewStart.lowerBound])

        guard projectsSource.contains("LazyVStack(alignment: .leading, spacing: ProjectsWorkspaceLayoutMetrics.projectCardSpacing)") else {
            throw FlowDataError.message("Expected Projects workspace to use a full-width vertical list instead of an adaptive grid.")
        }

        guard projectsSource.contains(".frame(maxWidth: .infinity, alignment: .leading)") else {
            throw FlowDataError.message("Expected Projects cards to opt into the full content rail width.")
        }

        guard projectsSource.contains("LazyVGrid(columns: workspaceColumns") == false else {
            throw FlowDataError.message("Expected Projects workspace not to fall back to the generic adaptive grid.")
        }

        guard projectsSource.contains("project.tasks.prefix(3)") == false else {
            throw FlowDataError.message("Expected Projects workspace to render the full project task list instead of truncating after three rows.")
        }
    }

    private static func smokeTestReviewGuidanceContract() throws {
        let package = FlowWeeklyReviewPackage(
            generatedAtLabel: "May 2",
            completedWork: [],
            staleItems: [],
            inboxItems: [],
            projectHealth: [],
            upcomingDeadlines: [],
            cleanupActions: [
                FlowReviewCleanupAction(
                    id: "archive-stale-1",
                    kind: "archive_stale_item",
                    title: "Archive stale: Old follow-up",
                    detail: "Archive it.",
                    targetIDs: ["stale-1"],
                    destructive: true
                ),
                FlowReviewCleanupAction(
                    id: "clarify-inbox",
                    kind: "clarify_inbox",
                    title: "Clarify inbox",
                    detail: "Go clarify inbox.",
                    targetIDs: ["inbox-1"],
                    destructive: false
                ),
                FlowReviewCleanupAction(
                    id: "project-next-actions",
                    kind: "project_next_action_review",
                    title: "Fix projects",
                    detail: "Add next actions.",
                    targetIDs: ["project-1"],
                    destructive: false
                ),
                FlowReviewCleanupAction(
                    id: "deadline-check",
                    kind: "deadline_review",
                    title: "Check deadlines",
                    detail: "Review this week.",
                    targetIDs: ["task-1"],
                    destructive: false
                )
            ]
        )
        let repository = StubRepository(weeklyReviewPackage: package)
        let store = WorkspaceStore(repository: repository)
        store.refresh()

        guard store.reviewArchiveActions.map(\.id) == ["archive-stale-1"] else {
            throw FlowDataError.message("Expected review archive actions to isolate the real mutation path.")
        }
        guard store.reviewGuidedActions.map(\.id) == ["clarify-inbox", "project-next-actions", "deadline-check"] else {
            throw FlowDataError.message("Expected review guided actions to stay separate from archive batch cleanup.")
        }
        guard store.reviewGuidanceDestination(for: package.cleanupActions[1]) == .inbox else {
            throw FlowDataError.message("Expected inbox review guidance to route into the Inbox workspace.")
        }
        guard store.reviewGuidanceDestination(for: package.cleanupActions[2]) == .projects else {
            throw FlowDataError.message("Expected project review guidance to route into the Projects workspace.")
        }
        guard store.reviewGuidanceDestination(for: package.cleanupActions[3]) == .today else {
            throw FlowDataError.message("Expected deadline review guidance to route into the Today workspace.")
        }

        store.toggleReviewAction(id: "archive-stale-1")
        guard store.reviewArchiveSelectionSummary.contains("1 stale item") else {
            throw FlowDataError.message("Expected review archive selection copy to reflect the selected stale count.")
        }

        store.applySelectedReviewActions()
        guard repository.appliedWeeklyReviewActionIDs == ["archive-stale-1"] else {
            throw FlowDataError.message("Expected review apply to send only the selected archive actions.")
        }
        guard store.reviewLastActionFeedback?.contains("Archived 1 stale item") == true else {
            throw FlowDataError.message("Expected review apply to surface visible archive feedback.")
        }

        store.triggerReviewGuidedAction(package.cleanupActions[2])
        guard store.selectedSection == .assistant else {
            throw FlowDataError.message("Expected project next-action review to open Assistant for confirmation.")
        }
        guard let selectedSessionID = store.selectedAssistantSessionID else {
            throw FlowDataError.message("Expected the review handoff to select the new assistant session.")
        }
        guard store.assistantMessages.map(\.role) == ["user", "assistant"] else {
            throw FlowDataError.message("Expected the review handoff to land in the session/message lane with a visible draft.")
        }
        guard selectedSessionID.isEmpty == false else {
            throw FlowDataError.message("Expected the review handoff to keep a concrete assistant session selection.")
        }
        guard store.assistantMessages.allSatisfy({ $0.sessionID == selectedSessionID }) else {
            throw FlowDataError.message("Expected the review handoff to keep the drafted messages attached to the selected session.")
        }
        guard store.selectedAssistantMessage?.proposalStatus == "pending" else {
            throw FlowDataError.message("Expected the review-generated assistant draft to require confirmation.")
        }
        guard store.selectedAssistantMessage?.proposal?.actionType == "create_task" else {
            throw FlowDataError.message("Expected review-generated assistant draft to keep the bounded create-task proposal.")
        }
        guard store.selectedAssistantMessage?.provider == "deterministic" else {
            throw FlowDataError.message("Expected review-generated assistant draft to preserve provider provenance.")
        }
        guard store.selectedAssistantMessage?.providerStatus == "success" else {
            throw FlowDataError.message("Expected review-generated assistant draft to preserve provider status.")
        }
        guard store.selectedAssistantMessage?.providerDetail.isEmpty == false else {
            throw FlowDataError.message("Expected review-generated assistant draft to preserve provider detail.")
        }
        guard store.selectedAssistantTurnID == nil else {
            throw FlowDataError.message("Expected the review handoff to avoid selecting a legacy assistant turn.")
        }
        guard store.reviewLastActionFeedback?.contains("session draft") == true else {
            throw FlowDataError.message("Expected review-generated proposal flow to explain that the draft continues in Assistant session state.")
        }

        store.openReviewGuidance(for: package.cleanupActions[3])
        guard store.selectedSection == .today else {
            throw FlowDataError.message("Expected non-project review guidance to keep using workspace navigation.")
        }
        guard store.reviewLastActionFeedback?.contains("Today") == true else {
            throw FlowDataError.message("Expected deadline guidance to explain the follow-up workspace.")
        }

        let projectRootURL = URL(fileURLWithPath: #filePath)
            .deletingLastPathComponent()
            .deletingLastPathComponent()
            .deletingLastPathComponent()
        let workspacesSourceURL = projectRootURL.appendingPathComponent("Sources/FlowMacApp/UI/Workspace/Workspaces.swift")
        let workspacesSource = try String(contentsOf: workspacesSourceURL)
        guard
            let reviewStart = workspacesSource.range(of: "struct ReviewWorkspaceView"),
            let assistantStart = workspacesSource.range(of: "struct AssistantWorkspaceView")
        else {
            throw FlowDataError.message("Expected workspace source to contain Review and Assistant view boundaries.")
        }
        let reviewSource = String(workspacesSource[reviewStart.lowerBound..<assistantStart.lowerBound])

        guard reviewSource.contains("Archive Stale Items") else {
            throw FlowDataError.message("Expected Review UI to label the real mutation path as stale-item archiving.")
        }
        guard reviewSource.contains("Open Inbox") else {
            throw FlowDataError.message("Expected Review UI to expose explicit Inbox guidance instead of a fake apply path.")
        }
        guard reviewSource.contains("Draft Next Action") else {
            throw FlowDataError.message("Expected Review UI to expose a draft-oriented project next-action affordance.")
        }
        guard reviewSource.contains("Open Today") else {
            throw FlowDataError.message("Expected Review UI to expose explicit Today guidance instead of a fake apply path.")
        }
        guard reviewSource.contains("Batch Cleanup") == false else {
            throw FlowDataError.message("Expected Review UI to stop presenting all weekly review actions as one batch cleanup card.")
        }
    }

    private static func smokeTestMainWindowAdjustabilityContract() throws {
        let projectRootURL = URL(fileURLWithPath: #filePath)
            .deletingLastPathComponent()
            .deletingLastPathComponent()
            .deletingLastPathComponent()
        let appSourceURL = projectRootURL.appendingPathComponent("Sources/FlowMacApp/FlowMacApp.swift")
        let configuratorSourceURL = projectRootURL.appendingPathComponent(
            "Sources/FlowMacApp/App/MainWindowConfigurator.swift"
        )
        let appSource = try String(contentsOf: appSourceURL)
        let configuratorSource = try String(contentsOf: configuratorSourceURL)

        guard appSource.contains(".defaultSize(") else {
            throw FlowDataError.message("Expected the main window scene to use a default size instead of forcing the launch size through the root content frame.")
        }

        guard appSource.contains("MainWindowConfigurator()") else {
            throw FlowDataError.message("Expected the main window scene to attach a window configurator so the dense chrome still leaves a drag affordance.")
        }

        guard configuratorSource.contains("window.isMovableByWindowBackground = true") else {
            throw FlowDataError.message("Expected the window configurator to enable background dragging on the native window.")
        }

        guard appSource.contains(".frame(minWidth: 1440, minHeight: 900)") == false else {
            throw FlowDataError.message("Expected the root content to stop pinning the main window to a 1440x900 minimum size.")
        }
    }
}

private func withDatabase<T>(
    at url: URL,
    _ block: (OpaquePointer?) throws -> T
) throws -> T {
    var db: OpaquePointer?
    guard sqlite3_open(url.path, &db) == SQLITE_OK else {
        throw FlowDataError.message("Unable to open repository smoke test database.")
    }
    defer { sqlite3_close(db) }
    return try block(db)
}

private func deleteSeedItems(db: OpaquePointer?) throws {
    let sql = "DELETE FROM items"
    guard sqlite3_exec(db, sql, nil, nil, nil) == SQLITE_OK else {
        throw FlowDataError.message("Unable to clear repository smoke test seed items.")
    }
}

private func insertSeedItem(
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
    let sqliteTransient = unsafeBitCast(-1, to: sqlite3_destructor_type.self)
    let sql = """
        INSERT INTO items (
            id, type, title, status, context_tags, parent_id, created_at, due_date,
            meta_payload, original_ek_id, estimated_duration, updated_at
        ) VALUES (?, ?, ?, ?, '[]', ?, ?, ?, '{}', NULL, 30, ?)
    """
    var statement: OpaquePointer?
    guard sqlite3_prepare_v2(db, sql, -1, &statement, nil) == SQLITE_OK else {
        throw FlowDataError.message("Unable to prepare repository smoke test seed insert.")
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
        throw FlowDataError.message("Unable to insert repository smoke test seed item.")
    }
}

private final class StubRepository: FlowRepository {
    let weeklyReviewPackage: FlowWeeklyReviewPackage
    private(set) var appliedWeeklyReviewActionIDs: [String] = []
    private var assistantTurns: [FlowAssistantTurn] = []
    private var assistantSessions: [FlowAssistantSession] = []
    private var assistantMessages: [FlowAssistantMessage] = []
    private var nextAssistantSessionIndex = 1
    private var nextAssistantMessageIndex = 1

    init(weeklyReviewPackage: FlowWeeklyReviewPackage = .empty) {
        self.weeklyReviewPackage = weeklyReviewPackage
    }

    func loadWorkspaceSnapshot() throws -> WorkspaceSnapshot {
        SampleWorkspaceFactory.makeSnapshot()
    }

    func capture(title: String) throws -> FlowTask {
        SampleWorkspaceFactory.makeSnapshot().inboxItems.first!
    }

    func clarifyCapture(id: String, title: String, destination: ClarifyDestination, projectTitle: String?) throws {}

    func rejectCapture(id: String) throws {}

    func loadAssistantSessions(limit: Int) throws -> [FlowAssistantSession] {
        Array(assistantSessions.prefix(limit))
    }

    func loadAssistantMessages(sessionID: String, limit: Int) throws -> [FlowAssistantMessage] {
        Array(assistantMessages.filter { $0.sessionID == sessionID }.prefix(limit))
    }

    func createAssistantSession(title: String) throws -> FlowAssistantSession {
        let trimmedTitle = title.trimmingCharacters(in: .whitespacesAndNewlines)
        let session = FlowAssistantSession(
            id: "stub-session-\(nextAssistantSessionIndex)",
            title: trimmedTitle.isEmpty ? "New Chat" : trimmedTitle,
            latestPreview: "",
            messageCount: 0,
            createdAtLabel: "Just now",
            updatedAtLabel: "Just now"
        )
        nextAssistantSessionIndex += 1
        assistantSessions.insert(session, at: 0)
        return session
    }

    func sendAssistantMessage(sessionID: String, prompt: String, planDate: String) throws -> FlowAssistantMessage {
        let userMessage = FlowAssistantMessage(
            id: "stub-message-\(nextAssistantMessageIndex)",
            sessionID: sessionID,
            role: "user",
            content: prompt,
            route: "capture",
            proposal: nil,
            proposalStatus: "none",
            auditSteps: [],
            provider: "deterministic",
            providerStatus: "success",
            providerDetail: "Stub",
            providerModel: nil,
            sourceTurnID: "stub-turn-\(nextAssistantMessageIndex)",
            createdAtLabel: "Just now",
            updatedAtLabel: "Just now"
        )
        nextAssistantMessageIndex += 1
        let assistantMessage = FlowAssistantMessage(
            id: "stub-message-\(nextAssistantMessageIndex)",
            sessionID: sessionID,
            role: "assistant",
            content: prompt,
            route: "capture",
            proposal: FlowAssistantProposal(
                actionType: "create_task",
                title: "Draft next action",
                detail: "Draft a next action for \(prompt)",
                requiresConfirmation: true
            ),
            proposalStatus: "pending",
            auditSteps: [],
            provider: "deterministic",
            providerStatus: "success",
            providerDetail: "Stub",
            providerModel: nil,
            sourceTurnID: "stub-turn-\(nextAssistantMessageIndex)",
            createdAtLabel: "Just now",
            updatedAtLabel: "Just now"
        )
        nextAssistantMessageIndex += 1
        assistantMessages.append(userMessage)
        assistantMessages.append(assistantMessage)
        if let index = assistantSessions.firstIndex(where: { $0.id == sessionID }) {
            assistantSessions[index].latestPreview = assistantMessage.content
            assistantSessions[index].messageCount += 2
        }
        return assistantMessage
    }

    func confirmAssistantMessageProposal(messageID: String) throws -> String { "Confirmed" }

    func dismissAssistantMessageProposal(messageID: String) throws {}

    func sendAssistantPrompt(_ prompt: String, planDate: String) throws -> FlowAssistantTurn {
        let turn = FlowAssistantTurn(
            id: "stub-turn",
            prompt: prompt,
            response: "Stub",
            route: "general",
            proposal: nil,
            proposalStatus: "none",
            auditSteps: [],
            createdAtLabel: "Just now"
        )
        assistantTurns.insert(turn, at: 0)
        return turn
    }

    func proposeProjectNextActionReview(projectID: String) throws -> FlowAssistantTurn {
        let turn = FlowAssistantTurn(
            id: "stub-review-proposal",
            prompt: "Review project next action",
            response: "Stub review proposal",
            route: "project_health",
            proposal: FlowAssistantProposal(
                actionType: "create_task",
                title: "Draft next action",
                detail: "Create next action for Flow Enhancement",
                requiresConfirmation: true
            ),
            proposalStatus: "pending",
            auditSteps: [],
            createdAtLabel: "Just now"
        )
        assistantTurns.insert(turn, at: 0)
        return turn
    }

    func loadAssistantTurns(limit: Int) throws -> [FlowAssistantTurn] { Array(assistantTurns.prefix(limit)) }

    func confirmAssistantProposal(turnID: String) throws -> String { "Confirmed" }

    func dismissAssistantProposal(turnID: String) throws {}

    func undoLastAssistantMutation() throws -> String? { nil }

    func listMemoryRecords(query: String?, includeDisabled: Bool) throws -> [FlowMemoryRecord] { [] }

    func createMemoryRecord(kind: String, scope: String, value: String, source: String, confidence: Double, scopeRef: String?) throws -> FlowMemoryRecord {
        FlowMemoryRecord(
            id: "stub-memory",
            kind: kind,
            scope: scope,
            scopeRef: scopeRef,
            value: value,
            source: source,
            confidence: confidence,
            enabled: true,
            updatedAtLabel: "Just now",
            whyItMatters: "Stub"
        )
    }

    func updateMemoryRecord(id: String, value: String) throws {}

    func setMemoryRecordEnabled(id: String, enabled: Bool) throws {}

    func deleteMemoryRecord(id: String) throws {}

    func loadDailyPlanState(planDate: String) throws -> FlowDailyPlanState { .empty(planDate: planDate) }

    func saveDailyPlan(planDate: String, topItemIDs: [String], bonusItemIDs: [String]) throws {}

    func loadWeeklyReviewPackage(referenceDate: Date) throws -> FlowWeeklyReviewPackage { weeklyReviewPackage }

    func applyWeeklyReviewActions(actionIDs: [String], referenceDate: Date) throws {
        appliedWeeklyReviewActionIDs = actionIDs
    }

    func loadNotificationPolicy() throws -> FlowNotificationPolicyState { .empty }

    func updateNotificationPermissionStatus(_ status: String) throws {}

    func markTaskDone(id: String) throws {}

    func archiveTask(id: String) throws {}
}

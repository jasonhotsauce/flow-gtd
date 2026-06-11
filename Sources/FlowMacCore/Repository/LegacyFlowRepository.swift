import Foundation
import SQLite3

protocol FlowRepository {
    func loadWorkspaceSnapshot() throws -> WorkspaceSnapshot
    func capture(title: String) throws -> FlowTask
    func createProjectTask(projectID: String, title: String) throws -> FlowTask
    func assignTaskToProject(taskID: String, projectID: String) throws
    func clarifyCapture(id: String, title: String, destination: ClarifyDestination, projectTitle: String?) throws
    func rejectCapture(id: String) throws
    func loadAssistantSessions(limit: Int) throws -> [FlowAssistantSession]
    func loadAssistantMessages(sessionID: String, limit: Int) throws -> [FlowAssistantMessage]
    func createAssistantSession(title: String) throws -> FlowAssistantSession
    func sendAssistantMessage(sessionID: String, prompt: String, planDate: String) throws -> FlowAssistantMessage
    func confirmAssistantMessageProposal(messageID: String) throws -> String
    func dismissAssistantMessageProposal(messageID: String) throws
    func sendAssistantPrompt(_ prompt: String, planDate: String) throws -> FlowAssistantTurn
    func proposeProjectNextActionReview(projectID: String) throws -> FlowAssistantTurn
    func loadAssistantTurns(limit: Int) throws -> [FlowAssistantTurn]
    func confirmAssistantProposal(turnID: String) throws -> String
    func dismissAssistantProposal(turnID: String) throws
    func undoLastAssistantMutation() throws -> String?
    func listMemoryRecords(query: String?, includeDisabled: Bool) throws -> [FlowMemoryRecord]
    func createMemoryRecord(kind: String, scope: String, value: String, source: String, confidence: Double, scopeRef: String?) throws -> FlowMemoryRecord
    func updateMemoryRecord(id: String, value: String) throws
    func setMemoryRecordEnabled(id: String, enabled: Bool) throws
    func deleteMemoryRecord(id: String) throws
    func loadDailyPlanState(planDate: String) throws -> FlowDailyPlanState
    func saveDailyPlan(planDate: String, topItemIDs: [String], bonusItemIDs: [String]) throws
    func loadWeeklyReviewPackage(referenceDate: Date) throws -> FlowWeeklyReviewPackage
    func applyWeeklyReviewActions(actionIDs: [String], referenceDate: Date) throws
    func loadNotificationPolicy() throws -> FlowNotificationPolicyState
    func updateNotificationPermissionStatus(_ status: String) throws
    func markTaskDone(id: String) throws
    func archiveTask(id: String) throws
}

final class LegacyFlowRepository: FlowRepository {
    let databaseURL: URL
    private let fileManager = FileManager.default
    private let assistantConversationBridge = AssistantSessionMessageBridge()

    init(databaseURL: URL = LegacyFlowRepository.defaultDatabaseURL()) {
        self.databaseURL = databaseURL
    }

    static func defaultDatabaseURL() -> URL {
        if let override = ProcessInfo.processInfo.environment["FLOW_DB_PATH"], override.isEmpty == false {
            return URL(fileURLWithPath: override)
        }
        return FileManager.default.homeDirectoryForCurrentUser
            .appendingPathComponent(".flow", isDirectory: true)
            .appendingPathComponent("data", isDirectory: true)
            .appendingPathComponent("flow.db", isDirectory: false)
    }

    func loadWorkspaceSnapshot() throws -> WorkspaceSnapshot {
        let databaseExists = fileManager.fileExists(atPath: databaseURL.path)
        try bootstrapDatabaseIfNeeded()

        let snapshot = try withDatabase { db in
            let inbox = try fetchInboxItems(db)
            let today = try fetchPlannedItems(db)
            let later = try fetchLaterItems(db, excluding: Set(today.map(\.id)))
            let projects = try fetchProjects(db)
            let stale = try fetchStaleItems(db)
            let review = try buildReviewSummary(db, staleCount: stale.count)
            let assistant = buildAssistantSuggestions(inbox: inbox, today: today, stale: stale)
            let memory = buildMemoryEntries(projects: projects, inbox: inbox)
            let headline = buildFocusHeadline(todayCount: today.count, inboxCount: inbox.count)

            return WorkspaceSnapshot(
                inboxItems: inbox,
                todayItems: today,
                laterItems: later,
                projects: projects,
                staleItems: stale,
                review: review,
                assistantSuggestions: assistant,
                memoryEntries: memory,
                focusHeadline: headline
            )
        }

        let hasPersistedContent = try withDatabase { db in
            let itemCount = try scalarCount(db, sql: "SELECT COUNT(*) FROM items", bindings: [])
            let captureCount = try scalarCount(db, sql: "SELECT COUNT(*) FROM raw_captures", bindings: [])
            let assistantCount = try scalarCount(db, sql: "SELECT COUNT(*) FROM assistant_turns", bindings: [])
            let memoryCount = try scalarCount(db, sql: "SELECT COUNT(*) FROM memory_entries", bindings: [])
            let planCount = try scalarCount(db, sql: "SELECT COUNT(*) FROM daily_plan_entries", bindings: [])
            return itemCount > 0 || captureCount > 0 || assistantCount > 0 || memoryCount > 0 || planCount > 0
        }

        if databaseExists == false || hasPersistedContent == false {
            return SampleWorkspaceFactory.makeSnapshot()
        }

        return snapshot
    }

    func capture(title: String) throws -> FlowTask {
        let trimmed = title.trimmingCharacters(in: .whitespacesAndNewlines)
        guard trimmed.isEmpty == false else {
            throw FlowDataError.message("Capture text cannot be empty.")
        }

        try bootstrapDatabaseIfNeeded()

        let task = FlowTask(
            id: UUID().uuidString,
            title: trimmed,
            summary: "Captured in the native macOS shell.",
            status: .active,
            source: .capture,
            projectID: nil,
            projectName: nil,
            dueLabel: nil,
            tags: [],
            estimatedMinutes: nil,
            isFlagged: false,
            lastUpdatedLabel: "Captured just now"
        )

        try withDatabase { db in
            let sql = """
                INSERT INTO items (
                    id, type, title, status, context_tags, parent_id, created_at,
                    due_date, meta_payload, original_ek_id, estimated_duration, updated_at
                ) VALUES (?, 'inbox', ?, 'active', '[]', NULL, ?, NULL, '{}', NULL, NULL, ?)
            """
            var statement: OpaquePointer?
            guard sqlite3_prepare_v2(db, sql, -1, &statement, nil) == SQLITE_OK else {
                throw sqliteError(db, fallback: "Unable to prepare capture insert.")
            }
            defer { sqlite3_finalize(statement) }

            bindText(task.id, to: statement, index: 1)
            bindText(task.title, to: statement, index: 2)
            let now = isoTimestamp()
            bindText(now, to: statement, index: 3)
            bindText(now, to: statement, index: 4)

            guard sqlite3_step(statement) == SQLITE_DONE else {
                throw sqliteError(db, fallback: "Unable to insert captured item.")
            }

            try insertRawCapture(
                db,
                record: RawCaptureRecord(
                    id: task.id,
                    source: .manualCapture,
                    rawText: task.title,
                    createdAt: now
                )
            )
            try insertInboxItem(
                db,
                record: InboxItemRecord(
                    id: task.id,
                    rawCaptureID: task.id,
                    originType: .manualCapture,
                    inboxState: "needs_clarification",
                    sourceRef: nil,
                    importedAt: nil,
                    createdAt: now,
                    updatedAt: now
                )
            )
        }

        return task
    }

    func createProjectTask(projectID: String, title: String) throws -> FlowTask {
        let trimmedProjectID = projectID.trimmingCharacters(in: .whitespacesAndNewlines)
        let trimmedTitle = title.trimmingCharacters(in: .whitespacesAndNewlines)
        guard trimmedProjectID.isEmpty == false else {
            throw FlowDataError.message("Project ID cannot be empty.")
        }
        guard trimmedTitle.isEmpty == false else {
            throw FlowDataError.message("Project task title cannot be empty.")
        }

        try bootstrapDatabaseIfNeeded()

        return try withDatabase { db in
            let projectTitle = try requireActiveProjectTitle(db, projectID: trimmedProjectID)
            let taskID = UUID().uuidString
            let now = isoTimestamp()
            let batchID = try insertMutationBatch(
                db,
                source: "project_task",
                requiresConfirmation: false,
                createdAt: now
            )

            let sql = """
                INSERT INTO items (
                    id, type, title, status, context_tags, parent_id, created_at,
                    due_date, meta_payload, original_ek_id, estimated_duration, updated_at
                ) VALUES (?, 'action', ?, 'active', '[]', ?, ?, NULL, '{}', NULL, NULL, ?)
            """
            var statement: OpaquePointer?
            guard sqlite3_prepare_v2(db, sql, -1, &statement, nil) == SQLITE_OK else {
                throw sqliteError(db, fallback: "Unable to prepare project task insert.")
            }
            defer { sqlite3_finalize(statement) }

            bindText(taskID, to: statement, index: 1)
            bindText(trimmedTitle, to: statement, index: 2)
            bindText(trimmedProjectID, to: statement, index: 3)
            bindText(now, to: statement, index: 4)
            bindText(now, to: statement, index: 5)

            guard sqlite3_step(statement) == SQLITE_DONE else {
                throw sqliteError(db, fallback: "Unable to insert project task.")
            }

            try upsertTask(
                db,
                id: taskID,
                title: trimmedTitle,
                status: "active",
                projectID: trimmedProjectID,
                sourceInboxItemID: taskID,
                createdAt: now,
                updatedAt: now
            )
            try insertMutationRecord(
                db,
                batchID: batchID,
                targetTable: "tasks",
                targetID: taskID,
                action: "project_task_create",
                payloadJSON: mutationPayloadJSON([
                    "project_id": trimmedProjectID,
                    "title": trimmedTitle
                ]),
                createdAt: now
            )

            return FlowTask(
                id: taskID,
                title: trimmedTitle,
                summary: "Linked to \(projectTitle).",
                status: .active,
                source: .project,
                projectID: trimmedProjectID,
                projectName: projectTitle,
                dueLabel: nil,
                tags: [],
                estimatedMinutes: nil,
                isFlagged: false,
                lastUpdatedLabel: "Created just now"
            )
        }
    }

    func assignTaskToProject(taskID: String, projectID: String) throws {
        let trimmedTaskID = taskID.trimmingCharacters(in: .whitespacesAndNewlines)
        let trimmedProjectID = projectID.trimmingCharacters(in: .whitespacesAndNewlines)
        guard trimmedTaskID.isEmpty == false else {
            throw FlowDataError.message("Task ID cannot be empty.")
        }
        guard trimmedProjectID.isEmpty == false else {
            throw FlowDataError.message("Project ID cannot be empty.")
        }

        try bootstrapDatabaseIfNeeded()

        try withDatabase { db in
            _ = try requireActiveProjectTitle(db, projectID: trimmedProjectID)
            let task = try requireAssignableTask(db, taskID: trimmedTaskID)
            let now = isoTimestamp()
            let batchID = try insertMutationBatch(
                db,
                source: "project_task",
                requiresConfirmation: false,
                createdAt: now
            )

            let updateSQL = """
                UPDATE items
                SET type = 'action', parent_id = ?, updated_at = ?
                WHERE id = ?
            """
            var update: OpaquePointer?
            guard sqlite3_prepare_v2(db, updateSQL, -1, &update, nil) == SQLITE_OK else {
                throw sqliteError(db, fallback: "Unable to prepare task project assignment.")
            }
            defer { sqlite3_finalize(update) }

            bindText(trimmedProjectID, to: update, index: 1)
            bindText(now, to: update, index: 2)
            bindText(trimmedTaskID, to: update, index: 3)

            guard sqlite3_step(update) == SQLITE_DONE else {
                throw sqliteError(db, fallback: "Unable to assign task to project.")
            }

            try upsertTask(
                db,
                id: trimmedTaskID,
                title: task.title,
                status: task.status,
                projectID: trimmedProjectID,
                sourceInboxItemID: task.sourceInboxItemID ?? trimmedTaskID,
                createdAt: task.createdAt,
                updatedAt: now
            )
            try updateInboxClarifyState(
                db,
                id: trimmedTaskID,
                inboxState: "clarified",
                taskID: trimmedTaskID,
                clarifiedTaskID: trimmedTaskID,
                clarifiedProjectID: trimmedProjectID,
                clarifiedAt: now,
                updatedAt: now
            )
            try insertMutationRecord(
                db,
                batchID: batchID,
                targetTable: "tasks",
                targetID: trimmedTaskID,
                action: "assign_project",
                payloadJSON: mutationPayloadJSON([
                    "project_id": trimmedProjectID,
                    "task_id": trimmedTaskID
                ]),
                createdAt: now
            )
        }
    }

    func markTaskDone(id: String) throws {
        try updateTask(id: id, status: "done")
    }

    func clarifyCapture(id: String, title: String, destination: ClarifyDestination, projectTitle: String?) throws {
        let trimmedTitle = title.trimmingCharacters(in: .whitespacesAndNewlines)
        guard trimmedTitle.isEmpty == false else {
            throw FlowDataError.message("Clarified title cannot be empty.")
        }

        try bootstrapDatabaseIfNeeded()

        try withDatabase { db in
            let createdAt = try fetchCreatedAt(db, id: id) ?? isoTimestamp()
            let now = isoTimestamp()
            let batchID = try insertMutationBatch(
                db,
                source: "capture_clarify",
                requiresConfirmation: false,
                createdAt: now
            )

            switch destination {
            case .task:
                let projectID = try findOrCreateProject(
                    db,
                    title: projectTitle,
                    createdAt: now,
                    batchID: batchID
                )
                try updateLegacyItemForClarifiedTask(
                    db,
                    id: id,
                    title: trimmedTitle,
                    projectID: projectID,
                    updatedAt: now
                )
                try upsertTask(
                    db,
                    id: id,
                    title: trimmedTitle,
                    status: "active",
                    projectID: projectID,
                    sourceInboxItemID: id,
                    createdAt: createdAt,
                    updatedAt: now
                )
                try updateInboxClarifyState(
                    db,
                    id: id,
                    inboxState: "clarified",
                    taskID: id,
                    clarifiedTaskID: id,
                    clarifiedProjectID: projectID,
                    clarifiedAt: now,
                    updatedAt: now
                )
                try insertMutationRecord(
                    db,
                    batchID: batchID,
                    targetTable: "tasks",
                    targetID: id,
                    action: "clarify_accept",
                    payloadJSON: mutationPayloadJSON(
                        [
                            "destination_type": "task",
                            "project_id": projectID ?? "",
                            "title": trimmedTitle
                        ]
                    ),
                    createdAt: now
                )
            case .project:
                try updateLegacyItemForClarifiedProject(
                    db,
                    id: id,
                    title: trimmedTitle,
                    updatedAt: now
                )
                try deleteTaskRow(db, id: id)
                try upsertProject(
                    db,
                    id: id,
                    name: trimmedTitle,
                    status: "active",
                    createdAt: createdAt,
                    updatedAt: now
                )
                try updateInboxClarifyState(
                    db,
                    id: id,
                    inboxState: "converted_to_project",
                    taskID: nil,
                    clarifiedTaskID: nil,
                    clarifiedProjectID: id,
                    clarifiedAt: now,
                    updatedAt: now
                )
                try insertMutationRecord(
                    db,
                    batchID: batchID,
                    targetTable: "projects",
                    targetID: id,
                    action: "clarify_accept",
                    payloadJSON: mutationPayloadJSON(
                        [
                            "destination_type": "project",
                            "title": trimmedTitle
                        ]
                    ),
                    createdAt: now
                )
            }
        }
    }

    func rejectCapture(id: String) throws {
        try bootstrapDatabaseIfNeeded()
        try withDatabase { db in
            let now = isoTimestamp()
            let batchID = try insertMutationBatch(
                db,
                source: "capture_clarify",
                requiresConfirmation: false,
                createdAt: now
            )
            try updateTask(id: id, status: "archived", db: db)
            try updateInboxClarifyState(
                db,
                id: id,
                inboxState: "rejected",
                taskID: nil,
                clarifiedTaskID: nil,
                clarifiedProjectID: nil,
                clarifiedAt: now,
                updatedAt: now
            )
            try insertMutationRecord(
                db,
                batchID: batchID,
                targetTable: "inbox_items",
                targetID: id,
                action: "clarify_reject",
                payloadJSON: mutationPayloadJSON(["inbox_item_id": id]),
                createdAt: now
            )
        }
    }

    func loadAssistantSessions(limit: Int) throws -> [FlowAssistantSession] {
        assistantConversationBridge.loadSessions(limit: limit)
    }

    func loadAssistantMessages(sessionID: String, limit: Int) throws -> [FlowAssistantMessage] {
        assistantConversationBridge.loadMessages(sessionID: sessionID, limit: limit)
    }

    func createAssistantSession(title: String) throws -> FlowAssistantSession {
        assistantConversationBridge.createSession(title: title)
    }

    func sendAssistantMessage(sessionID: String, prompt: String, planDate: String) throws -> FlowAssistantMessage {
        try assistantConversationBridge.sendMessage(
            sessionID: sessionID,
            prompt: prompt,
            planDate: planDate,
            routeTurn: sendAssistantPrompt(_:planDate:)
        )
    }

    func confirmAssistantMessageProposal(messageID: String) throws -> String {
        try assistantConversationBridge.confirm(
            messageID: messageID,
            backingTurn: confirmAssistantProposal(turnID:)
        )
    }

    func dismissAssistantMessageProposal(messageID: String) throws {
        try assistantConversationBridge.dismiss(
            messageID: messageID,
            backingTurn: dismissAssistantProposal(turnID:)
        )
    }

    func archiveTask(id: String) throws {
        try updateTask(id: id, status: "archived")
    }

    func sendAssistantPrompt(_ prompt: String, planDate: String) throws -> FlowAssistantTurn {
        let normalizedPrompt = prompt.trimmingCharacters(in: .whitespacesAndNewlines)
        guard normalizedPrompt.isEmpty == false else {
            throw FlowDataError.message("Prompt must not be empty.")
        }

        try bootstrapDatabaseIfNeeded()

        return try withDatabase { db in
            let route = detectAssistantRoute(prompt: normalizedPrompt)
            let context = try buildAssistantContextSnapshot(db, planDate: planDate)
            let turnID = UUID().uuidString
            var proposal: FlowAssistantProposal?
            var proposalPayloadJSON = "null"
            var proposalStatus = "none"
            var response = buildAssistantFallbackResponse(context)
            var auditSteps = [
                FlowAssistantAuditStep(
                    id: UUID().uuidString,
                    stage: "orchestrator",
                    status: "ok",
                    summary: "Routed request to \(route).",
                    payload: [
                        "provider": "deterministic"
                    ]
                )
            ]

            switch route {
            case "capture":
                let title = extractAssistantCaptureTitle(normalizedPrompt)
                proposal = FlowAssistantProposal(
                    actionType: "create_task",
                    title: "Add to Inbox",
                    detail: "Create inbox item: \(title)",
                    requiresConfirmation: true
                )
                proposalPayloadJSON = assistantPayloadJSON(
                    [
                        "title": title,
                        "agent_contract": makeAssistantAgentContract(
                            requestID: turnID,
                            actionType: "create_task",
                            inputSummary: normalizedPrompt,
                            proposedChanges: ["Create inbox item"],
                            fieldDeltas: ["title": title],
                            previewText: "Create inbox item: \(title)",
                            rationale: "User asked Flow to capture a task-like item.",
                            confidence: 0.95,
                            requiresConfirmation: true,
                            verificationStatus: "pass"
                        )
                    ]
                )
                proposalStatus = "pending"
                response = "I can add this to Inbox: \(title)"
                auditSteps.append(
                    FlowAssistantAuditStep(
                        id: UUID().uuidString,
                        stage: "capture_specialist",
                        status: "ok",
                        summary: "Prepared a confirmation-gated inbox capture.",
                        payload: [
                            "provider": "deterministic"
                        ]
                    )
                )
            case "memory":
                let value = extractAssistantMemoryValue(normalizedPrompt)
                proposal = FlowAssistantProposal(
                    actionType: "save_memory",
                    title: "Save Memory",
                    detail: "Remember preference: \(value)",
                    requiresConfirmation: true
                )
                proposalPayloadJSON = assistantPayloadJSON(
                    [
                        "kind": "explicit_preference",
                        "scope": "global",
                        "value": value,
                        "source": "assistant-chat",
                        "confidence": "1.0",
                        "agent_contract": makeAssistantAgentContract(
                            requestID: turnID,
                            actionType: "save_memory",
                            inputSummary: normalizedPrompt,
                            proposedChanges: ["Save explicit preference memory"],
                            fieldDeltas: ["value": value],
                            previewText: "Remember preference: \(value)",
                            rationale: "User made an explicit preference statement.",
                            confidence: 1.0,
                            requiresConfirmation: true,
                            verificationStatus: "pass"
                        )
                    ]
                )
                proposalStatus = "pending"
                response = "I can save this as a preference memory: \(value)"
                auditSteps.append(
                    FlowAssistantAuditStep(
                        id: UUID().uuidString,
                        stage: "memory_specialist",
                        status: "ok",
                        summary: "Prepared an explicit preference memory.",
                        payload: [
                            "provider": "deterministic"
                        ]
                    )
                )
            case "daily_plan":
                response = try buildAssistantDailyPlanResponse(db, planDate: planDate)
                auditSteps.append(
                    FlowAssistantAuditStep(
                        id: UUID().uuidString,
                        stage: "planning_specialist",
                        status: "ok",
                        summary: "Summarized the current daily planning state.",
                        payload: [
                            "provider": "deterministic"
                        ]
                    )
                )
            case "review":
                response = try buildAssistantReviewResponse(db)
                auditSteps.append(
                    FlowAssistantAuditStep(
                        id: UUID().uuidString,
                        stage: "review_specialist",
                        status: "ok",
                        summary: "Summarized stale work and review pressure.",
                        payload: [
                            "provider": "deterministic"
                        ]
                    )
                )
            default:
                auditSteps.append(
                    FlowAssistantAuditStep(
                        id: UUID().uuidString,
                        stage: "general_specialist",
                        status: "ok",
                        summary: "Answered using the current GTD system summary.",
                        payload: [
                            "provider": "deterministic"
                        ]
                    )
                )
            }

            auditSteps.append(
                FlowAssistantAuditStep(
                    id: UUID().uuidString,
                    stage: "verifier",
                    status: "ok",
                    summary: "Checked that the proposal is bounded and requires confirmation before writes.",
                    payload: [:]
                )
            )

            let now = isoTimestamp()
            try insertAssistantTurn(
                db,
                id: turnID,
                prompt: normalizedPrompt,
                response: response,
                route: route,
                proposalJSON: proposalPayloadJSON == "null" ? nil : assistantProposalJSON(proposal: proposal!, payloadJSON: proposalPayloadJSON),
                proposalStatus: proposalStatus,
                createdAt: now,
                updatedAt: now
            )
            try insertAssistantAuditSteps(db, turnID: turnID, steps: auditSteps, createdAt: now)
            return FlowAssistantTurn(
                id: turnID,
                prompt: normalizedPrompt,
                response: response,
                route: route,
                proposal: proposal,
                proposalStatus: proposalStatus,
                auditSteps: auditSteps,
                provider: "deterministic",
                providerStatus: "success",
                providerDetail: "Prepared a deterministic assistant response.",
                providerModel: nil,
                createdAtLabel: relativeTimestampLabel(rawValue: now) ?? "Just now"
            )
        }
    }

    func proposeProjectNextActionReview(projectID: String) throws -> FlowAssistantTurn {
        try bootstrapDatabaseIfNeeded()

        return try withDatabase { db in
            let projects = try fetchProjects(db)
            guard let project = projects.first(where: { $0.id == projectID }) else {
                throw FlowDataError.message("Project no longer exists for review.")
            }

            let suggestedTitle = suggestNextActionTitle(for: project)
            let turnID = UUID().uuidString
            let proposal = FlowAssistantProposal(
                actionType: "create_task",
                title: "Create Project Next Action",
                detail: "Create next action for \(project.title): \(suggestedTitle)",
                requiresConfirmation: true
            )
            let proposalPayloadJSON = assistantPayloadJSON(
                [
                    "title": suggestedTitle,
                    "project_id": project.id,
                    "project_title": project.title,
                    "agent_contract": makeAssistantAgentContract(
                        requestID: turnID,
                        actionType: "create_task",
                        targetEntityIDs: [project.id],
                        inputSummary: "Review project next action: \(project.title)",
                        proposedChanges: ["Create one active next action under the project"],
                        fieldDeltas: ["title": suggestedTitle, "project_id": project.id],
                        previewText: "Create next action in \(project.title): \(suggestedTitle)",
                        rationale: "This project has no current next action, so Review should propose one bounded next step.",
                        confidence: 0.86,
                        requiresConfirmation: true,
                        verificationStatus: "pass"
                    )
                ]
            )
            let response = "I found a project in Review that needs a next action. I drafted one bounded next step for \(project.title) from the current local project context and left it pending for confirmation."
            let auditSteps = [
                FlowAssistantAuditStep(
                    id: UUID().uuidString,
                    stage: "provider",
                    status: "ok",
                    summary: "Prepared deterministic project-health next action draft.",
                    payload: [
                        "provider": "deterministic",
                        "provider_status": "success",
                        "provider_runtime": "deterministic",
                        "provider_detail": "Prepared deterministic project-health next action draft."
                    ]
                ),
                FlowAssistantAuditStep(
                    id: UUID().uuidString,
                    stage: "orchestrator",
                    status: "ok",
                    summary: "Routed Review follow-up into the native assistant confirmation flow.",
                    payload: [
                        "provider": "deterministic"
                    ]
                ),
                FlowAssistantAuditStep(
                    id: UUID().uuidString,
                    stage: "project_health_specialist",
                    status: "ok",
                    summary: "Prepared one confirmation-gated project next-action draft from local project context without an external agent runtime call.",
                    payload: [
                        "provider": "deterministic"
                    ]
                ),
                FlowAssistantAuditStep(
                    id: UUID().uuidString,
                    stage: "verifier",
                    status: "ok",
                    summary: "Checked that the Review-generated draft next action is bounded and confirmation-gated.",
                    payload: [:]
                )
            ]

            let now = isoTimestamp()
            try insertAssistantTurn(
                db,
                id: turnID,
                prompt: "Review project next action: \(project.title)",
                response: response,
                route: "project_health",
                proposalJSON: assistantProposalJSON(proposal: proposal, payloadJSON: proposalPayloadJSON),
                proposalStatus: "pending",
                createdAt: now,
                updatedAt: now
            )
            try insertAssistantAuditSteps(db, turnID: turnID, steps: auditSteps, createdAt: now)
            return FlowAssistantTurn(
                id: turnID,
                prompt: "Review project next action: \(project.title)",
                response: response,
                route: "project_health",
                proposal: proposal,
                proposalStatus: "pending",
                auditSteps: auditSteps,
                provider: "deterministic",
                providerStatus: "success",
                providerDetail: "Prepared deterministic project-health next action draft.",
                providerModel: nil,
                createdAtLabel: relativeTimestampLabel(rawValue: now) ?? "Just now"
            )
        }
    }

    func loadAssistantTurns(limit: Int = 30) throws -> [FlowAssistantTurn] {
        try bootstrapDatabaseIfNeeded()
        return try withDatabase { db in
            try fetchAssistantTurns(db, limit: limit)
        }
    }

    func confirmAssistantProposal(turnID: String) throws -> String {
        try bootstrapDatabaseIfNeeded()
        return try withDatabase { db in
            let turn = try fetchAssistantTurnRow(db, turnID: turnID)
            guard turn.proposalStatus == "pending" else {
                throw FlowDataError.message("Assistant proposal is not pending.")
            }
            guard let proposal = turn.proposal else {
                throw FlowDataError.message("Assistant turn has no proposal.")
            }

            let payload = jsonDictionary(from: turn.proposalPayloadJSON)
            let now = isoTimestamp()
            let batchID = try insertMutationBatch(
                db,
                source: "assistant",
                requiresConfirmation: false,
                createdAt: now
            )

            let message: String
            switch proposal.actionType {
            case "create_task", "capture_task":
                let title = payload["title"] ?? ""
                if let projectID = payload["project_id"], projectID.isEmpty == false {
                    let task = try createAssistantProjectTask(
                        db,
                        title: title,
                        projectID: projectID,
                        createdAt: now
                    )
                    try insertMutationRecord(
                        db,
                        batchID: batchID,
                        targetTable: "items",
                        targetID: task.id,
                        action: "assistant_project_next_action_confirm",
                        payloadJSON: mutationPayloadJSON(
                            [
                                "item_id": task.id,
                                "project_id": projectID,
                                "kind": proposal.actionType
                            ]
                        ),
                        createdAt: now
                    )
                    let projectTitle = payload["project_title"] ?? "the project"
                    message = "Added next action to \(projectTitle): \(title)"
                } else {
                    let task = try capture(title: title)
                    try insertMutationRecord(
                        db,
                        batchID: batchID,
                        targetTable: "items",
                        targetID: task.id,
                        action: "assistant_capture_confirm",
                        payloadJSON: mutationPayloadJSON(["item_id": task.id, "kind": proposal.actionType]),
                        createdAt: now
                    )
                    message = "Added to Inbox: \(title)"
                }
            case "save_memory":
                let created = try createMemoryRecordInternal(
                    db,
                    kind: payload["kind"] ?? "explicit_preference",
                    scope: payload["scope"] ?? "global",
                    value: payload["value"] ?? "",
                    source: payload["source"] ?? "assistant-chat",
                    confidence: Double(payload["confidence"] ?? "1.0") ?? 1.0,
                    scopeRef: nil,
                    createdAt: now
                )
                try insertMutationRecord(
                    db,
                    batchID: batchID,
                    targetTable: "memory_entries",
                    targetID: created.id,
                    action: "assistant_memory_confirm",
                    payloadJSON: mutationPayloadJSON(["memory_id": created.id, "kind": "save_memory"]),
                    createdAt: now
                )
                message = "Saved preference to Memory."
            default:
                message = "Proposal confirmed."
            }

            try updateAssistantProposalStatus(db, turnID: turnID, status: "confirmed", updatedAt: now)
            return message
        }
    }

    func dismissAssistantProposal(turnID: String) throws {
        try bootstrapDatabaseIfNeeded()
        try withDatabase { db in
            try updateAssistantProposalStatus(db, turnID: turnID, status: "dismissed", updatedAt: isoTimestamp())
        }
    }

    func undoLastAssistantMutation() throws -> String? {
        try assistantConversationBridge.undoLastMutation {
            try bootstrapDatabaseIfNeeded()
            return try withDatabase { db in
                guard let latest = try fetchLatestAssistantMutation(db) else {
                    return nil
                }

                switch latest.action {
                case "assistant_capture_confirm":
                    let payload = jsonDictionary(from: latest.payloadJSON)
                    if let itemID = payload["item_id"] {
                        try updateTask(id: itemID, status: "archived", db: db)
                        return "Undid the last assistant capture."
                    }
                case "assistant_project_next_action_confirm":
                    let payload = jsonDictionary(from: latest.payloadJSON)
                    if let itemID = payload["item_id"] {
                        try updateTask(id: itemID, status: "archived", db: db)
                        return "Undid the last assistant project next action."
                    }
                case "assistant_memory_confirm":
                    let payload = jsonDictionary(from: latest.payloadJSON)
                    if let memoryID = payload["memory_id"] {
                        try deleteMemoryRecordInternal(db, id: memoryID)
                        return "Undid the last assistant memory write."
                    }
                default:
                    return nil
                }
                return nil
            }
        }
    }

    func listMemoryRecords(query: String?, includeDisabled: Bool) throws -> [FlowMemoryRecord] {
        try bootstrapDatabaseIfNeeded()
        return try withDatabase { db in
            try fetchMemoryRecords(db, query: query, includeDisabled: includeDisabled)
        }
    }

    func createMemoryRecord(
        kind: String,
        scope: String,
        value: String,
        source: String,
        confidence: Double,
        scopeRef: String?
    ) throws -> FlowMemoryRecord {
        try bootstrapDatabaseIfNeeded()
        return try withDatabase { db in
            try createMemoryRecordInternal(
                db,
                kind: kind,
                scope: scope,
                value: value,
                source: source,
                confidence: confidence,
                scopeRef: scopeRef,
                createdAt: isoTimestamp()
            )
        }
    }

    func updateMemoryRecord(id: String, value: String) throws {
        try bootstrapDatabaseIfNeeded()
        try withDatabase { db in
            try updateMemoryRecordInternal(db, id: id, value: value)
        }
    }

    func setMemoryRecordEnabled(id: String, enabled: Bool) throws {
        try bootstrapDatabaseIfNeeded()
        try withDatabase { db in
            try setMemoryRecordEnabledInternal(db, id: id, enabled: enabled)
        }
    }

    func deleteMemoryRecord(id: String) throws {
        try bootstrapDatabaseIfNeeded()
        try withDatabase { db in
            try deleteMemoryRecordInternal(db, id: id)
        }
    }

    func loadDailyPlanState(planDate: String) throws -> FlowDailyPlanState {
        try bootstrapDatabaseIfNeeded()
        return try withDatabase { db in
            try fetchDailyPlanState(db, planDate: planDate)
        }
    }

    func saveDailyPlan(planDate: String, topItemIDs: [String], bonusItemIDs: [String]) throws {
        try bootstrapDatabaseIfNeeded()
        try withDatabase { db in
            try replaceDailyPlanEntries(db, planDate: planDate, topItemIDs: topItemIDs, bonusItemIDs: bonusItemIDs)
        }
    }

    func loadWeeklyReviewPackage(referenceDate: Date = Date()) throws -> FlowWeeklyReviewPackage {
        try bootstrapDatabaseIfNeeded()
        return try withDatabase { db in
            try buildWeeklyReviewPackage(db, referenceDate: referenceDate)
        }
    }

    func applyWeeklyReviewActions(actionIDs: [String], referenceDate: Date = Date()) throws {
        let requested = Set(actionIDs)
        guard requested.isEmpty == false else { return }

        try bootstrapDatabaseIfNeeded()
        try withDatabase { db in
            let package = try buildWeeklyReviewPackage(db, referenceDate: referenceDate)
            let actions = package.cleanupActions.filter { requested.contains($0.id) }
            guard actions.isEmpty == false else { return }

            let now = isoTimestamp()
            let batchID = try insertMutationBatch(
                db,
                source: "weekly_review",
                requiresConfirmation: false,
                createdAt: now
            )

            for action in actions {
                for targetID in action.targetIDs {
                    if action.kind == "archive_stale_item" {
                        try updateTask(id: targetID, status: "archived", db: db)
                    }
                    try insertMutationRecord(
                        db,
                        batchID: batchID,
                        targetTable: "items",
                        targetID: targetID,
                        action: action.kind == "archive_stale_item" ? "weekly_review_archive" : "weekly_review_accept",
                        payloadJSON: mutationPayloadJSON([
                            "action_id": action.id,
                            "kind": action.kind,
                            "title": action.title
                        ]),
                        createdAt: now
                    )
                }
            }
        }
    }

    func loadNotificationPolicy() throws -> FlowNotificationPolicyState {
        try bootstrapDatabaseIfNeeded()
        return try withDatabase { db in
            try fetchNotificationPolicy(db)
        }
    }

    func updateNotificationPermissionStatus(_ status: String) throws {
        let allowed = ["not_determined", "denied", "authorized", "provisional", "unavailable"]
        guard allowed.contains(status) else {
            throw FlowDataError.message("Unsupported notification permission status.")
        }

        try bootstrapDatabaseIfNeeded()
        try withDatabase { db in
            let sql = """
                INSERT INTO notification_policy (id, permission_status, updated_at)
                VALUES ('flow', ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    permission_status = excluded.permission_status,
                    updated_at = excluded.updated_at
            """
            var statement: OpaquePointer?
            guard sqlite3_prepare_v2(db, sql, -1, &statement, nil) == SQLITE_OK else {
                throw sqliteError(db, fallback: "Unable to prepare notification policy update.")
            }
            defer { sqlite3_finalize(statement) }

            bindText(status, to: statement, index: 1)
            bindText(isoTimestamp(), to: statement, index: 2)

            guard sqlite3_step(statement) == SQLITE_DONE else {
                throw sqliteError(db, fallback: "Unable to update notification policy.")
            }
        }
    }

    private func updateTask(id: String, status: String) throws {
        try bootstrapDatabaseIfNeeded()
        try withDatabase { db in
            try updateTask(id: id, status: status, db: db)
        }
    }

    private func updateTask(id: String, status: String, db: OpaquePointer?) throws {
        let sql = "UPDATE items SET status = ?, updated_at = ? WHERE id = ?"
        var statement: OpaquePointer?
        guard sqlite3_prepare_v2(db, sql, -1, &statement, nil) == SQLITE_OK else {
            throw sqliteError(db, fallback: "Unable to prepare update statement.")
        }
        defer { sqlite3_finalize(statement) }

        bindText(status, to: statement, index: 1)
        bindText(isoTimestamp(), to: statement, index: 2)
        bindText(id, to: statement, index: 3)

        guard sqlite3_step(statement) == SQLITE_DONE else {
            throw sqliteError(db, fallback: "Unable to update task state.")
        }
    }

    private func detectAssistantRoute(prompt: String) -> String {
        let lowered = prompt.lowercased()
        if lowered.hasPrefix("remember") || lowered.contains(" i prefer ") {
            return "memory"
        }
        if lowered.hasPrefix("add ")
            || lowered.hasPrefix("capture ")
            || lowered.hasPrefix("todo ")
            || lowered.hasPrefix("remind me to ")
        {
            return "capture"
        }
        if lowered.contains("plan my day") || lowered.contains("today") {
            return "daily_plan"
        }
        if lowered.contains("review") || lowered.contains("weekly") {
            return "review"
        }
        return "general"
    }

    private func extractAssistantCaptureTitle(_ prompt: String) -> String {
        let lowered = prompt.lowercased()
        if lowered.hasPrefix("remind me to ") {
            return String(prompt.dropFirst("remind me to ".count)).trimmingCharacters(in: .whitespacesAndNewlines)
        }
        for prefix in ["add ", "capture ", "todo "] {
            if lowered.hasPrefix(prefix) {
                return String(prompt.dropFirst(prefix.count)).trimmingCharacters(in: .whitespacesAndNewlines)
            }
        }
        return prompt.trimmingCharacters(in: .whitespacesAndNewlines)
    }

    private func extractAssistantMemoryValue(_ prompt: String) -> String {
        let lowered = prompt.lowercased()
        if lowered.hasPrefix("remember that ") {
            return String(prompt.dropFirst("remember that ".count)).trimmingCharacters(in: .whitespacesAndNewlines)
        }
        if lowered.hasPrefix("remember ") {
            return String(prompt.dropFirst("remember ".count)).trimmingCharacters(in: .whitespacesAndNewlines)
        }
        return prompt.trimmingCharacters(in: .whitespacesAndNewlines)
    }

    private func buildAssistantContextSnapshot(_ db: OpaquePointer?, planDate: String) throws -> [String: Int] {
        let inboxCount = try scalarCount(
            db,
            sql: "SELECT COUNT(*) FROM items WHERE type = 'inbox' AND status = 'active' AND parent_id IS NULL",
            bindings: []
        )
        let activeActionCount = try scalarCount(
            db,
            sql: "SELECT COUNT(*) FROM items WHERE type = 'action' AND status = 'active'",
            bindings: []
        )
        let planCount = try scalarCount(
            db,
            sql: "SELECT COUNT(*) FROM daily_plan_entries WHERE plan_date = ?",
            bindings: [planDate]
        )
        let memoryCount = try scalarCount(
            db,
            sql: "SELECT COUNT(*) FROM memory_entries",
            bindings: []
        )
        return [
            "inbox_count": inboxCount,
            "active_action_count": activeActionCount,
            "plan_count": planCount,
            "memory_count": memoryCount
        ]
    }

    private func buildAssistantFallbackResponse(_ context: [String: Int]) -> String {
        "I can help capture work, summarize today's plan, or save a preference. Right now you have \(context["inbox_count"] ?? 0) inbox items and \(context["memory_count"] ?? 0) saved memories."
    }

    private func buildAssistantDailyPlanResponse(_ db: OpaquePointer?, planDate: String) throws -> String {
        let state = try fetchDailyPlanState(db, planDate: planDate)
        let titles = (state.topItems + state.bonusItems).map(\.title)
        if titles.isEmpty == false {
            return "Your plan for \(planDate) includes: " + titles.joined(separator: "; ")
        }
        return "You do not have a confirmed plan for \(planDate) yet. There are \(state.inbox.count) inbox items ready to review."
    }

    private func buildAssistantReviewResponse(_ db: OpaquePointer?) throws -> String {
        let staleCount = try scalarCount(
            db,
            sql: "SELECT COUNT(*) FROM items WHERE status = 'active' AND updated_at < ?",
            bindings: [isoTimestamp(Calendar.current.date(byAdding: .day, value: -14, to: Date()) ?? Date())]
        )
        let somedayCount = try scalarCount(
            db,
            sql: "SELECT COUNT(*) FROM items WHERE status = 'someday'",
            bindings: []
        )
        return "Weekly review pressure is moderate: \(staleCount) stale items and \(somedayCount) Someday items are currently available."
    }

    private func assistantProposalJSON(proposal: FlowAssistantProposal, payloadJSON: String) -> String {
        let payload = jsonObjectDictionary(from: payloadJSON)
        let object: [String: Any] = [
            "action_type": proposal.actionType,
            "title": proposal.title,
            "detail": proposal.detail,
            "payload": payload,
            "requires_confirmation": proposal.requiresConfirmation
        ]
        guard
            let data = try? JSONSerialization.data(withJSONObject: object, options: [.sortedKeys]),
            let json = String(data: data, encoding: .utf8)
        else {
            return "null"
        }
        return json
    }

    private func makeAssistantAgentContract(
        requestID: String,
        actionType: String,
        targetEntityIDs: [String] = [],
        inputSummary: String,
        proposedChanges: [String],
        fieldDeltas: [String: String],
        previewText: String,
        rationale: String,
        confidence: Double,
        requiresConfirmation: Bool,
        verificationStatus: String
    ) -> [String: Any] {
        [
            "request_id": requestID,
            "action_type": actionType,
            "target_entity_ids": targetEntityIDs,
            "target_entity_versions": [:],
            "input_summary": inputSummary,
            "proposed_changes": proposedChanges,
            "field_deltas": fieldDeltas,
            "preview_text": previewText,
            "rationale": rationale,
            "confidence": confidence,
            "requires_confirmation": requiresConfirmation,
            "verification_status": verificationStatus
        ]
    }

    private func suggestNextActionTitle(for project: FlowProject) -> String {
        if let completedTask = project.tasks.first(where: { $0.status == .done }) {
            return "Define the next step after \(completedTask.title)"
        }
        return "Define the next concrete step for \(project.title)"
    }

    private func assistantPayloadJSON(_ payload: [String: Any]) -> String {
        guard
            let data = try? JSONSerialization.data(withJSONObject: payload, options: [.sortedKeys]),
            let json = String(data: data, encoding: .utf8)
        else {
            return "{}"
        }
        return json
    }

    private func assistantAuditPayloadJSON(_ payload: [String: String]) -> String {
        guard
            let data = try? JSONSerialization.data(withJSONObject: payload, options: [.sortedKeys]),
            let json = String(data: data, encoding: .utf8)
        else {
            return "{}"
        }
        return json
    }

    private func insertAssistantTurn(
        _ db: OpaquePointer?,
        id: String,
        prompt: String,
        response: String,
        route: String,
        proposalJSON: String?,
        proposalStatus: String,
        createdAt: String,
        updatedAt: String
    ) throws {
        let sql = """
            INSERT INTO assistant_turns (
                id, prompt, response, route, proposal_json, proposal_status, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """
        var statement: OpaquePointer?
        guard sqlite3_prepare_v2(db, sql, -1, &statement, nil) == SQLITE_OK else {
            throw sqliteError(db, fallback: "Unable to prepare assistant turn insert.")
        }
        defer { sqlite3_finalize(statement) }

        bindText(id, to: statement, index: 1)
        bindText(prompt, to: statement, index: 2)
        bindText(response, to: statement, index: 3)
        bindText(route, to: statement, index: 4)
        bindNullableText(proposalJSON, to: statement, index: 5)
        bindText(proposalStatus, to: statement, index: 6)
        bindText(createdAt, to: statement, index: 7)
        bindText(updatedAt, to: statement, index: 8)

        guard sqlite3_step(statement) == SQLITE_DONE else {
            throw sqliteError(db, fallback: "Unable to insert assistant turn.")
        }
    }

    private func insertAssistantAuditSteps(
        _ db: OpaquePointer?,
        turnID: String,
        steps: [FlowAssistantAuditStep],
        createdAt: String
    ) throws {
        for step in steps {
            let sql = """
                INSERT INTO assistant_audit_steps (
                    id, turn_id, stage, status, summary, payload_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """
            var statement: OpaquePointer?
            guard sqlite3_prepare_v2(db, sql, -1, &statement, nil) == SQLITE_OK else {
                throw sqliteError(db, fallback: "Unable to prepare assistant audit insert.")
            }
            defer { sqlite3_finalize(statement) }

            bindText(step.id, to: statement, index: 1)
            bindText(turnID, to: statement, index: 2)
            bindText(step.stage, to: statement, index: 3)
            bindText(step.status, to: statement, index: 4)
            bindText(step.summary, to: statement, index: 5)
            bindText(assistantAuditPayloadJSON(step.payload), to: statement, index: 6)
            bindText(createdAt, to: statement, index: 7)

            guard sqlite3_step(statement) == SQLITE_DONE else {
                throw sqliteError(db, fallback: "Unable to insert assistant audit step.")
            }
        }
    }

    private struct AssistantTurnRow {
        let id: String
        let prompt: String
        let response: String
        let route: String
        let proposalPayloadJSON: String?
        let proposal: FlowAssistantProposal?
        let proposalStatus: String
    }

    private func fetchAssistantTurnRow(_ db: OpaquePointer?, turnID: String) throws -> AssistantTurnRow {
        let sql = """
            SELECT id, prompt, response, route, proposal_json, proposal_status
            FROM assistant_turns
            WHERE id = ?
        """
        var statement: OpaquePointer?
        guard sqlite3_prepare_v2(db, sql, -1, &statement, nil) == SQLITE_OK else {
            throw sqliteError(db, fallback: "Unable to prepare assistant turn query.")
        }
        defer { sqlite3_finalize(statement) }

        bindText(turnID, to: statement, index: 1)
        guard sqlite3_step(statement) == SQLITE_ROW else {
            throw FlowDataError.message("Assistant turn does not exist.")
        }

        let proposalJSON = nullableText(statement, column: 4)
        return AssistantTurnRow(
            id: text(statement, column: 0),
            prompt: text(statement, column: 1),
            response: text(statement, column: 2),
            route: text(statement, column: 3),
            proposalPayloadJSON: proposalPayloadJSONString(from: proposalJSON),
            proposal: parseAssistantProposal(from: proposalJSON),
            proposalStatus: text(statement, column: 5)
        )
    }

    private func fetchAssistantTurns(_ db: OpaquePointer?, limit: Int) throws -> [FlowAssistantTurn] {
        let sql = """
            SELECT id, prompt, response, route, proposal_json, proposal_status, created_at
            FROM assistant_turns
            ORDER BY created_at DESC
            LIMIT ?
        """
        var statement: OpaquePointer?
        guard sqlite3_prepare_v2(db, sql, -1, &statement, nil) == SQLITE_OK else {
            throw sqliteError(db, fallback: "Unable to prepare assistant turns query.")
        }
        defer { sqlite3_finalize(statement) }
        sqlite3_bind_int(statement, 1, Int32(limit))

        var turns: [FlowAssistantTurn] = []
        while sqlite3_step(statement) == SQLITE_ROW {
            let turnID = text(statement, column: 0)
            let auditSteps = try fetchAssistantAuditSteps(db, turnID: turnID)
            let provider = providerDetails(from: auditSteps)
            turns.append(
                FlowAssistantTurn(
                    id: turnID,
                    prompt: text(statement, column: 1),
                    response: text(statement, column: 2),
                    route: text(statement, column: 3),
                    proposal: parseAssistantProposal(from: nullableText(statement, column: 4)),
                    proposalStatus: text(statement, column: 5),
                    auditSteps: auditSteps,
                    provider: provider.provider,
                    providerStatus: provider.providerStatus,
                    providerDetail: provider.providerDetail,
                    providerModel: provider.providerModel,
                    createdAtLabel: relativeTimestampLabel(rawValue: nullableText(statement, column: 6)) ?? "Just now"
                )
            )
        }
        return turns
    }

    private func fetchAssistantAuditSteps(_ db: OpaquePointer?, turnID: String) throws -> [FlowAssistantAuditStep] {
        let sql = """
            SELECT id, stage, status, summary, payload_json
            FROM assistant_audit_steps
            WHERE turn_id = ?
            ORDER BY created_at ASC
        """
        var statement: OpaquePointer?
        guard sqlite3_prepare_v2(db, sql, -1, &statement, nil) == SQLITE_OK else {
            throw sqliteError(db, fallback: "Unable to prepare assistant audit query.")
        }
        defer { sqlite3_finalize(statement) }
        bindText(turnID, to: statement, index: 1)

        var steps: [FlowAssistantAuditStep] = []
        while sqlite3_step(statement) == SQLITE_ROW {
            steps.append(
                FlowAssistantAuditStep(
                    id: text(statement, column: 0),
                    stage: text(statement, column: 1),
                    status: text(statement, column: 2),
                    summary: text(statement, column: 3),
                    payload: parseAuditPayload(from: nullableText(statement, column: 4))
                )
            )
        }
        return steps
    }

    private func providerDetails(from steps: [FlowAssistantAuditStep]) -> AssistantProviderDetails {
        guard let providerStep = steps.first(where: { $0.stage == "provider" })
            ?? steps.first(where: { $0.stage == "fallback" }) else {
            return AssistantProviderDetails(
                provider: "unknown",
                providerStatus: "unknown",
                providerDetail: "No provider evidence recorded.",
                providerModel: nil
            )
        }

        return AssistantProviderDetails(
            provider: providerStep.payload["provider"] ?? "unknown",
            providerStatus: providerStep.payload["provider_status"] ?? "unknown",
            providerDetail: providerStep.payload["provider_detail"] ?? providerStep.summary,
            providerModel: providerStep.payload["provider_model"].flatMap { $0.isEmpty ? nil : $0 }
        )
    }

    private func parseAuditPayload(from rawJSON: String?) -> [String: String] {
        guard
            let rawJSON,
            let data = rawJSON.data(using: .utf8),
            let object = try? JSONSerialization.jsonObject(with: data) as? [String: Any]
        else {
            return [:]
        }

        var payload: [String: String] = [:]
        for (key, value) in object {
            payload[key] = String(describing: value)
        }
        return payload
    }

    private func updateAssistantProposalStatus(_ db: OpaquePointer?, turnID: String, status: String, updatedAt: String) throws {
        let sql = "UPDATE assistant_turns SET proposal_status = ?, updated_at = ? WHERE id = ?"
        var statement: OpaquePointer?
        guard sqlite3_prepare_v2(db, sql, -1, &statement, nil) == SQLITE_OK else {
            throw sqliteError(db, fallback: "Unable to prepare assistant status update.")
        }
        defer { sqlite3_finalize(statement) }
        bindText(status, to: statement, index: 1)
        bindText(updatedAt, to: statement, index: 2)
        bindText(turnID, to: statement, index: 3)
        guard sqlite3_step(statement) == SQLITE_DONE else {
            throw sqliteError(db, fallback: "Unable to update assistant status.")
        }
    }

    private func parseAssistantProposal(from rawJSON: String?) -> FlowAssistantProposal? {
        guard
            let rawJSON,
            let data = rawJSON.data(using: .utf8),
            let object = try? JSONSerialization.jsonObject(with: data) as? [String: Any]
        else {
            return nil
        }
        return FlowAssistantProposal(
            actionType: object["action_type"] as? String ?? "",
            title: object["title"] as? String ?? "",
            detail: object["detail"] as? String ?? "",
            requiresConfirmation: object["requires_confirmation"] as? Bool ?? false
        )
    }

    private func proposalPayloadJSONString(from rawJSON: String?) -> String? {
        guard
            let rawJSON,
            let data = rawJSON.data(using: .utf8),
            let object = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
            let payload = object["payload"],
            let payloadData = try? JSONSerialization.data(withJSONObject: payload, options: [.sortedKeys]),
            let payloadJSON = String(data: payloadData, encoding: .utf8)
        else {
            return nil
        }
        return payloadJSON
    }

    private struct MutationRecordRow {
        let action: String
        let payloadJSON: String
    }

    private struct AssistantProviderDetails {
        let provider: String
        let providerStatus: String
        let providerDetail: String
        let providerModel: String?
    }

    private func fetchLatestAssistantMutation(_ db: OpaquePointer?) throws -> MutationRecordRow? {
        let sql = """
            SELECT mr.action, mr.payload_json
            FROM mutation_records mr
            JOIN mutation_batches mb ON mb.id = mr.batch_id
            WHERE mb.source = 'assistant'
            ORDER BY mb.created_at DESC, mr.created_at DESC
            LIMIT 1
        """
        var statement: OpaquePointer?
        guard sqlite3_prepare_v2(db, sql, -1, &statement, nil) == SQLITE_OK else {
            throw sqliteError(db, fallback: "Unable to prepare assistant mutation query.")
        }
        defer { sqlite3_finalize(statement) }
        guard sqlite3_step(statement) == SQLITE_ROW else {
            return nil
        }
        return MutationRecordRow(action: text(statement, column: 0), payloadJSON: text(statement, column: 1))
    }

    private func createMemoryRecordInternal(
        _ db: OpaquePointer?,
        kind: String,
        scope: String,
        value: String,
        source: String,
        confidence: Double,
        scopeRef: String?,
        createdAt: String
    ) throws -> FlowMemoryRecord {
        let id = UUID().uuidString
        let sql = """
            INSERT INTO memory_entries (
                id, kind, scope, scope_ref, value, source, confidence, enabled,
                created_at, updated_at, last_confirmed_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?)
        """
        var statement: OpaquePointer?
        guard sqlite3_prepare_v2(db, sql, -1, &statement, nil) == SQLITE_OK else {
            throw sqliteError(db, fallback: "Unable to prepare memory insert.")
        }
        defer { sqlite3_finalize(statement) }

        bindText(id, to: statement, index: 1)
        bindText(kind, to: statement, index: 2)
        bindText(scope, to: statement, index: 3)
        bindNullableText(scopeRef, to: statement, index: 4)
        bindText(value.trimmingCharacters(in: .whitespacesAndNewlines), to: statement, index: 5)
        bindText(source, to: statement, index: 6)
        sqlite3_bind_double(statement, 7, confidence)
        bindText(createdAt, to: statement, index: 8)
        bindText(createdAt, to: statement, index: 9)
        bindText(createdAt, to: statement, index: 10)

        guard sqlite3_step(statement) == SQLITE_DONE else {
            throw sqliteError(db, fallback: "Unable to insert memory entry.")
        }

        return FlowMemoryRecord(
            id: id,
            kind: kind,
            scope: scope,
            scopeRef: scopeRef,
            value: value,
            source: source,
            confidence: confidence,
            enabled: true,
            updatedAtLabel: relativeTimestampLabel(rawValue: createdAt) ?? "Just now",
            whyItMatters: whyMemoryMatters(kind: kind, scope: scope)
        )
    }

    private func fetchMemoryRecords(_ db: OpaquePointer?, query: String?, includeDisabled: Bool) throws -> [FlowMemoryRecord] {
        var sql = """
            SELECT id, kind, scope, scope_ref, value, source, confidence, enabled, updated_at
            FROM memory_entries
        """
        var bindings: [String] = []
        var clauses: [String] = []
        if includeDisabled == false {
            clauses.append("enabled = 1")
        }
        if let query, query.isEmpty == false {
            clauses.append("LOWER(value) LIKE ?")
            bindings.append("%\(query.lowercased())%")
        }
        if clauses.isEmpty == false {
            sql += " WHERE " + clauses.joined(separator: " AND ")
        }
        sql += " ORDER BY updated_at DESC, created_at DESC"

        var statement: OpaquePointer?
        guard sqlite3_prepare_v2(db, sql, -1, &statement, nil) == SQLITE_OK else {
            throw sqliteError(db, fallback: "Unable to prepare memory list query.")
        }
        defer { sqlite3_finalize(statement) }

        for (index, value) in bindings.enumerated() {
            bindText(value, to: statement, index: Int32(index + 1))
        }

        var records: [FlowMemoryRecord] = []
        while sqlite3_step(statement) == SQLITE_ROW {
            let kind = text(statement, column: 1)
            let scope = text(statement, column: 2)
            records.append(
                FlowMemoryRecord(
                    id: text(statement, column: 0),
                    kind: kind,
                    scope: scope,
                    scopeRef: nullableText(statement, column: 3),
                    value: text(statement, column: 4),
                    source: text(statement, column: 5),
                    confidence: sqlite3_column_double(statement, 6),
                    enabled: sqlite3_column_int(statement, 7) == 1,
                    updatedAtLabel: relativeTimestampLabel(rawValue: nullableText(statement, column: 8)) ?? "Just now",
                    whyItMatters: whyMemoryMatters(kind: kind, scope: scope)
                )
            )
        }
        return records
    }

    private func updateMemoryRecordInternal(_ db: OpaquePointer?, id: String, value: String) throws {
        let sql = "UPDATE memory_entries SET value = ?, updated_at = ? WHERE id = ?"
        var statement: OpaquePointer?
        guard sqlite3_prepare_v2(db, sql, -1, &statement, nil) == SQLITE_OK else {
            throw sqliteError(db, fallback: "Unable to prepare memory update.")
        }
        defer { sqlite3_finalize(statement) }
        bindText(value.trimmingCharacters(in: .whitespacesAndNewlines), to: statement, index: 1)
        bindText(isoTimestamp(), to: statement, index: 2)
        bindText(id, to: statement, index: 3)
        guard sqlite3_step(statement) == SQLITE_DONE else {
            throw sqliteError(db, fallback: "Unable to update memory entry.")
        }
    }

    private func setMemoryRecordEnabledInternal(_ db: OpaquePointer?, id: String, enabled: Bool) throws {
        let sql = "UPDATE memory_entries SET enabled = ?, updated_at = ? WHERE id = ?"
        var statement: OpaquePointer?
        guard sqlite3_prepare_v2(db, sql, -1, &statement, nil) == SQLITE_OK else {
            throw sqliteError(db, fallback: "Unable to prepare memory enabled update.")
        }
        defer { sqlite3_finalize(statement) }
        sqlite3_bind_int(statement, 1, enabled ? 1 : 0)
        bindText(isoTimestamp(), to: statement, index: 2)
        bindText(id, to: statement, index: 3)
        guard sqlite3_step(statement) == SQLITE_DONE else {
            throw sqliteError(db, fallback: "Unable to update memory enabled state.")
        }
    }

    private func deleteMemoryRecordInternal(_ db: OpaquePointer?, id: String) throws {
        let sql = "DELETE FROM memory_entries WHERE id = ?"
        var statement: OpaquePointer?
        guard sqlite3_prepare_v2(db, sql, -1, &statement, nil) == SQLITE_OK else {
            throw sqliteError(db, fallback: "Unable to prepare memory delete.")
        }
        defer { sqlite3_finalize(statement) }
        bindText(id, to: statement, index: 1)
        guard sqlite3_step(statement) == SQLITE_DONE else {
            throw sqliteError(db, fallback: "Unable to delete memory entry.")
        }
    }

    private func whyMemoryMatters(kind: String, scope: String) -> String {
        switch kind {
        case "planning_preference", "explicit_preference":
            return "This can influence planning and assistant suggestions in the \(scope) scope."
        case "project_context":
            return "This keeps project context visible when the assistant or planner reasons about related work."
        default:
            return "This remains inspectable product memory that can shape workflow suggestions."
        }
    }

    private func fetchDailyPlanState(_ db: OpaquePointer?, planDate: String) throws -> FlowDailyPlanState {
        let topItems = try fetchPlanItems(db, planDate: planDate, bucket: "top")
        let bonusItems = try fetchPlanItems(db, planDate: planDate, bucket: "bonus")
        let plannedIDs = Set((topItems + bonusItems).map(\.id))
        let mustAddress = try fetchCandidateTasks(
            db,
            sql: """
                SELECT id, title, status, context_tags, due_date, estimated_duration, updated_at
                FROM items
                WHERE type = 'action' AND status = 'active' AND due_date IS NOT NULL AND date(due_date) <= date(?)
                ORDER BY due_date ASC
            """,
            bindings: [planDate],
            source: .planned
        ).filter { plannedIDs.contains($0.id) == false }
        let mustAddressIDs = Set(mustAddress.map(\.id))
        let inbox = try fetchInboxItems(db).filter { plannedIDs.contains($0.id) == false }
        let readyActions = try fetchCandidateTasks(
            db,
            sql: """
                SELECT id, title, status, context_tags, due_date, estimated_duration, updated_at
                FROM items
                WHERE type = 'action' AND status = 'active' AND parent_id IS NULL
                ORDER BY updated_at DESC
            """,
            source: .planned
        ).filter { plannedIDs.contains($0.id) == false && mustAddressIDs.contains($0.id) == false }
        let projectTasks = try fetchCandidateTasks(
            db,
            sql: """
                SELECT i.id, i.title, i.status, i.context_tags, i.due_date, i.estimated_duration, i.updated_at, i.parent_id, p.title
                FROM items i
                LEFT JOIN items p ON p.id = i.parent_id AND p.type = 'project'
                WHERE i.type = 'action' AND i.status = 'active' AND i.parent_id IS NOT NULL
                ORDER BY i.updated_at DESC
            """,
            source: .project,
            projectIDColumnIndex: 7,
            projectColumnIndex: 8
        ).filter { plannedIDs.contains($0.id) == false && mustAddressIDs.contains($0.id) == false }

        var riskFlags: [String] = []
        if topItems.count > 3 {
            riskFlags.append("Top focus exceeds three items.")
        }
        if bonusItems.count > 2 {
            riskFlags.append("Bonus load may crowd the day.")
        }
        if mustAddress.count > topItems.count && mustAddress.isEmpty == false {
            riskFlags.append("Due-soon work exceeds the current committed focus.")
        }

        return FlowDailyPlanState(
            planDate: planDate,
            topItems: topItems,
            bonusItems: bonusItems,
            mustAddress: mustAddress,
            inbox: inbox,
            readyActions: readyActions,
            projectTasks: projectTasks,
            riskFlags: riskFlags,
            calendarStatus: "Calendar-aware reasoning is currently limited to task due dates. Live calendar integration is not connected yet."
        )
    }

    private func fetchPlanItems(_ db: OpaquePointer?, planDate: String, bucket: String) throws -> [FlowTask] {
        try fetchCandidateTasks(
            db,
            sql: """
                SELECT i.id, i.title, i.status, i.context_tags, i.due_date, i.estimated_duration, i.updated_at, i.parent_id, p.title
                FROM daily_plan_entries d
                JOIN items i ON i.id = d.item_id
                LEFT JOIN items p ON p.id = i.parent_id AND p.type = 'project'
                WHERE d.plan_date = ? AND d.bucket = ? AND i.status = 'active'
                ORDER BY d.position ASC
            """,
            bindings: [planDate, bucket],
            source: .planned,
            projectIDColumnIndex: 7,
            projectColumnIndex: 8
        )
    }

    private func fetchCandidateTasks(
        _ db: OpaquePointer?,
        sql: String,
        bindings: [String] = [],
        source: FlowTaskSource,
        projectIDColumnIndex: Int? = nil,
        projectColumnIndex: Int? = nil
    ) throws -> [FlowTask] {
        try fetchTasks(
            db,
            sql: sql,
            bindings: bindings,
            source: source,
            projectIDColumnIndex: projectIDColumnIndex,
            projectColumnIndex: projectColumnIndex
        )
    }

    private func replaceDailyPlanEntries(_ db: OpaquePointer?, planDate: String, topItemIDs: [String], bonusItemIDs: [String]) throws {
        try executePrepared(db, sql: "DELETE FROM daily_plan_entries WHERE plan_date = ?", bindings: [planDate])
        let now = isoTimestamp()
        var seen: Set<String> = []
        var position = 1
        for itemID in topItemIDs where seen.contains(itemID) == false {
            seen.insert(itemID)
            try insertDailyPlanEntry(db, planDate: planDate, itemID: itemID, bucket: "top", position: position, createdAt: now)
            position += 1
        }
        position = 1
        for itemID in bonusItemIDs where seen.contains(itemID) == false {
            seen.insert(itemID)
            try insertDailyPlanEntry(db, planDate: planDate, itemID: itemID, bucket: "bonus", position: position, createdAt: now)
            position += 1
        }
    }

    private func insertDailyPlanEntry(_ db: OpaquePointer?, planDate: String, itemID: String, bucket: String, position: Int, createdAt: String) throws {
        let sql = """
            INSERT INTO daily_plan_entries (plan_date, item_id, bucket, position, created_at)
            VALUES (?, ?, ?, ?, ?)
        """
        var statement: OpaquePointer?
        guard sqlite3_prepare_v2(db, sql, -1, &statement, nil) == SQLITE_OK else {
            throw sqliteError(db, fallback: "Unable to prepare daily plan insert.")
        }
        defer { sqlite3_finalize(statement) }
        bindText(planDate, to: statement, index: 1)
        bindText(itemID, to: statement, index: 2)
        bindText(bucket, to: statement, index: 3)
        sqlite3_bind_int(statement, 4, Int32(position))
        bindText(createdAt, to: statement, index: 5)
        guard sqlite3_step(statement) == SQLITE_DONE else {
            throw sqliteError(db, fallback: "Unable to insert daily plan entry.")
        }
    }

    private func executePrepared(_ db: OpaquePointer?, sql: String, bindings: [String]) throws {
        var statement: OpaquePointer?
        guard sqlite3_prepare_v2(db, sql, -1, &statement, nil) == SQLITE_OK else {
            throw sqliteError(db, fallback: "Unable to prepare statement.")
        }
        defer { sqlite3_finalize(statement) }
        for (index, value) in bindings.enumerated() {
            bindText(value, to: statement, index: Int32(index + 1))
        }
        guard sqlite3_step(statement) == SQLITE_DONE else {
            throw sqliteError(db, fallback: "Unable to execute statement.")
        }
    }

    private func jsonDictionary(from rawJSON: String?) -> [String: String] {
        guard
            let rawJSON,
            let data = rawJSON.data(using: .utf8),
            let object = try? JSONSerialization.jsonObject(with: data) as? [String: Any]
        else {
            return [:]
        }
        var result: [String: String] = [:]
        for (key, value) in object {
            result[key] = String(describing: value)
        }
        return result
    }

    private func jsonObjectDictionary(from rawJSON: String?) -> [String: Any] {
        guard
            let rawJSON,
            let data = rawJSON.data(using: .utf8),
            let object = try? JSONSerialization.jsonObject(with: data) as? [String: Any]
        else {
            return [:]
        }
        return object
    }

    private func fetchCreatedAt(_ db: OpaquePointer?, id: String) throws -> String? {
        let sql = "SELECT created_at FROM items WHERE id = ?"
        var statement: OpaquePointer?
        guard sqlite3_prepare_v2(db, sql, -1, &statement, nil) == SQLITE_OK else {
            throw sqliteError(db, fallback: "Unable to prepare created_at query.")
        }
        defer { sqlite3_finalize(statement) }

        bindText(id, to: statement, index: 1)
        guard sqlite3_step(statement) == SQLITE_ROW else {
            return nil
        }
        return nullableText(statement, column: 0)
    }

    private func requireActiveProjectTitle(_ db: OpaquePointer?, projectID: String) throws -> String {
        let sql = "SELECT title FROM items WHERE id = ? AND type = 'project' AND status = 'active' LIMIT 1"
        var statement: OpaquePointer?
        guard sqlite3_prepare_v2(db, sql, -1, &statement, nil) == SQLITE_OK else {
            throw sqliteError(db, fallback: "Unable to prepare project lookup.")
        }
        defer { sqlite3_finalize(statement) }

        bindText(projectID, to: statement, index: 1)
        guard sqlite3_step(statement) == SQLITE_ROW else {
            throw FlowDataError.message("Project \(projectID) does not exist.")
        }
        return text(statement, column: 0)
    }

    private func requireAssignableTask(
        _ db: OpaquePointer?,
        taskID: String
    ) throws -> (title: String, status: String, createdAt: String, sourceInboxItemID: String?) {
        let sql = """
            SELECT i.title, i.status, i.created_at, t.source_inbox_item_id
            FROM items i
            LEFT JOIN tasks t ON t.id = i.id
            WHERE i.id = ? AND i.type IN ('inbox', 'action') AND i.status != 'archived'
            LIMIT 1
        """
        var statement: OpaquePointer?
        guard sqlite3_prepare_v2(db, sql, -1, &statement, nil) == SQLITE_OK else {
            throw sqliteError(db, fallback: "Unable to prepare task lookup.")
        }
        defer { sqlite3_finalize(statement) }

        bindText(taskID, to: statement, index: 1)
        guard sqlite3_step(statement) == SQLITE_ROW else {
            throw FlowDataError.message("Task \(taskID) does not exist.")
        }
        return (
            title: text(statement, column: 0),
            status: text(statement, column: 1),
            createdAt: text(statement, column: 2),
            sourceInboxItemID: nullableText(statement, column: 3)
        )
    }

    private func updateLegacyItemForClarifiedTask(
        _ db: OpaquePointer?,
        id: String,
        title: String,
        projectID: String?,
        updatedAt: String
    ) throws {
        let sql = """
            UPDATE items
            SET type = 'action', title = ?, parent_id = ?, status = 'active', updated_at = ?
            WHERE id = ?
        """
        var statement: OpaquePointer?
        guard sqlite3_prepare_v2(db, sql, -1, &statement, nil) == SQLITE_OK else {
            throw sqliteError(db, fallback: "Unable to prepare clarified task update.")
        }
        defer { sqlite3_finalize(statement) }

        bindText(title, to: statement, index: 1)
        if let projectID {
            bindText(projectID, to: statement, index: 2)
        } else {
            sqlite3_bind_null(statement, 2)
        }
        bindText(updatedAt, to: statement, index: 3)
        bindText(id, to: statement, index: 4)

        guard sqlite3_step(statement) == SQLITE_DONE else {
            throw sqliteError(db, fallback: "Unable to update clarified task state.")
        }
    }

    private func updateLegacyItemForClarifiedProject(
        _ db: OpaquePointer?,
        id: String,
        title: String,
        updatedAt: String
    ) throws {
        let sql = """
            UPDATE items
            SET type = 'project', title = ?, parent_id = NULL, status = 'active', updated_at = ?
            WHERE id = ?
        """
        var statement: OpaquePointer?
        guard sqlite3_prepare_v2(db, sql, -1, &statement, nil) == SQLITE_OK else {
            throw sqliteError(db, fallback: "Unable to prepare clarified project update.")
        }
        defer { sqlite3_finalize(statement) }

        bindText(title, to: statement, index: 1)
        bindText(updatedAt, to: statement, index: 2)
        bindText(id, to: statement, index: 3)

        guard sqlite3_step(statement) == SQLITE_DONE else {
            throw sqliteError(db, fallback: "Unable to update clarified project state.")
        }
    }

    private func findOrCreateProject(
        _ db: OpaquePointer?,
        title: String?,
        createdAt: String,
        batchID: String
    ) throws -> String? {
        let trimmed = title?.trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
        guard trimmed.isEmpty == false else {
            return nil
        }

        let lookupSQL = """
            SELECT id
            FROM projects
            WHERE lower(name) = lower(?) AND status != 'archived'
            LIMIT 1
        """
        var lookup: OpaquePointer?
        guard sqlite3_prepare_v2(db, lookupSQL, -1, &lookup, nil) == SQLITE_OK else {
            throw sqliteError(db, fallback: "Unable to prepare project lookup.")
        }
        defer { sqlite3_finalize(lookup) }

        bindText(trimmed, to: lookup, index: 1)
        if sqlite3_step(lookup) == SQLITE_ROW {
            return text(lookup, column: 0)
        }

        let projectID = UUID().uuidString
        try insertLegacyProjectItem(db, id: projectID, title: trimmed, createdAt: createdAt, updatedAt: createdAt)
        try upsertProject(db, id: projectID, name: trimmed, status: "active", createdAt: createdAt, updatedAt: createdAt)
        try insertMutationRecord(
            db,
            batchID: batchID,
            targetTable: "projects",
            targetID: projectID,
            action: "create",
            payloadJSON: mutationPayloadJSON(["title": trimmed]),
            createdAt: createdAt
        )
        return projectID
    }

    private func insertLegacyProjectItem(
        _ db: OpaquePointer?,
        id: String,
        title: String,
        createdAt: String,
        updatedAt: String
    ) throws {
        let sql = """
            INSERT INTO items (
                id, type, title, status, context_tags, parent_id, created_at,
                due_date, meta_payload, original_ek_id, estimated_duration, updated_at
            ) VALUES (?, 'project', ?, 'active', '[]', NULL, ?, NULL, '{}', NULL, NULL, ?)
        """
        var statement: OpaquePointer?
        guard sqlite3_prepare_v2(db, sql, -1, &statement, nil) == SQLITE_OK else {
            throw sqliteError(db, fallback: "Unable to prepare legacy project insert.")
        }
        defer { sqlite3_finalize(statement) }

        bindText(id, to: statement, index: 1)
        bindText(title, to: statement, index: 2)
        bindText(createdAt, to: statement, index: 3)
        bindText(updatedAt, to: statement, index: 4)

        guard sqlite3_step(statement) == SQLITE_DONE else {
            throw sqliteError(db, fallback: "Unable to insert legacy project item.")
        }
    }

    private func createAssistantProjectTask(
        _ db: OpaquePointer?,
        title: String,
        projectID: String,
        createdAt: String
    ) throws -> FlowTask {
        let taskID = UUID().uuidString
        let trimmedTitle = title.trimmingCharacters(in: .whitespacesAndNewlines)
        let sql = """
            INSERT INTO items (
                id, type, title, status, context_tags, parent_id, created_at,
                due_date, meta_payload, original_ek_id, estimated_duration, updated_at
            ) VALUES (?, 'action', ?, 'active', '[]', ?, ?, NULL, '{}', NULL, NULL, ?)
        """
        var statement: OpaquePointer?
        guard sqlite3_prepare_v2(db, sql, -1, &statement, nil) == SQLITE_OK else {
            throw sqliteError(db, fallback: "Unable to prepare assistant project-task insert.")
        }
        defer { sqlite3_finalize(statement) }

        bindText(taskID, to: statement, index: 1)
        bindText(trimmedTitle, to: statement, index: 2)
        bindText(projectID, to: statement, index: 3)
        bindText(createdAt, to: statement, index: 4)
        bindText(createdAt, to: statement, index: 5)

        guard sqlite3_step(statement) == SQLITE_DONE else {
            throw sqliteError(db, fallback: "Unable to insert assistant project task.")
        }

        try upsertTask(
            db,
            id: taskID,
            title: trimmedTitle,
            status: "active",
            projectID: projectID,
            sourceInboxItemID: taskID,
            createdAt: createdAt,
            updatedAt: createdAt
        )

        return FlowTask(
            id: taskID,
            title: trimmedTitle,
            summary: "Assistant-generated project next action awaiting execution.",
            status: .active,
            source: .assistant,
            projectID: projectID,
            projectName: nil,
            dueLabel: nil,
            tags: [],
            estimatedMinutes: nil,
            isFlagged: false,
            lastUpdatedLabel: "Just now"
        )
    }

    private func upsertProject(
        _ db: OpaquePointer?,
        id: String,
        name: String,
        status: String,
        createdAt: String,
        updatedAt: String
    ) throws {
        let sql = """
            INSERT INTO projects (id, name, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                name = excluded.name,
                status = excluded.status,
                updated_at = excluded.updated_at
        """
        var statement: OpaquePointer?
        guard sqlite3_prepare_v2(db, sql, -1, &statement, nil) == SQLITE_OK else {
            throw sqliteError(db, fallback: "Unable to prepare project upsert.")
        }
        defer { sqlite3_finalize(statement) }

        bindText(id, to: statement, index: 1)
        bindText(name, to: statement, index: 2)
        bindText(status, to: statement, index: 3)
        bindText(createdAt, to: statement, index: 4)
        bindText(updatedAt, to: statement, index: 5)

        guard sqlite3_step(statement) == SQLITE_DONE else {
            throw sqliteError(db, fallback: "Unable to upsert project.")
        }
    }

    private func upsertTask(
        _ db: OpaquePointer?,
        id: String,
        title: String,
        status: String,
        projectID: String?,
        sourceInboxItemID: String,
        createdAt: String,
        updatedAt: String
    ) throws {
        let sql = """
            INSERT INTO tasks (
                id, title, status, project_id, source_inbox_item_id, time_sensitivity,
                effort_band, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, 'none', 'medium', ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                title = excluded.title,
                status = excluded.status,
                project_id = excluded.project_id,
                source_inbox_item_id = excluded.source_inbox_item_id,
                updated_at = excluded.updated_at
        """
        var statement: OpaquePointer?
        guard sqlite3_prepare_v2(db, sql, -1, &statement, nil) == SQLITE_OK else {
            throw sqliteError(db, fallback: "Unable to prepare task upsert.")
        }
        defer { sqlite3_finalize(statement) }

        bindText(id, to: statement, index: 1)
        bindText(title, to: statement, index: 2)
        bindText(status, to: statement, index: 3)
        if let projectID {
            bindText(projectID, to: statement, index: 4)
        } else {
            sqlite3_bind_null(statement, 4)
        }
        bindText(sourceInboxItemID, to: statement, index: 5)
        bindText(createdAt, to: statement, index: 6)
        bindText(updatedAt, to: statement, index: 7)

        guard sqlite3_step(statement) == SQLITE_DONE else {
            throw sqliteError(db, fallback: "Unable to upsert task.")
        }
    }

    private func updateInboxClarifyState(
        _ db: OpaquePointer?,
        id: String,
        inboxState: String,
        taskID: String?,
        clarifiedTaskID: String?,
        clarifiedProjectID: String?,
        clarifiedAt: String,
        updatedAt: String
    ) throws {
        let sql = """
            UPDATE inbox_items
            SET inbox_state = ?,
                task_id = ?,
                clarified_task_id = ?,
                clarified_project_id = ?,
                clarified_at = ?,
                updated_at = ?
            WHERE id = ?
        """
        var statement: OpaquePointer?
        guard sqlite3_prepare_v2(db, sql, -1, &statement, nil) == SQLITE_OK else {
            throw sqliteError(db, fallback: "Unable to prepare inbox clarify update.")
        }
        defer { sqlite3_finalize(statement) }

        bindText(inboxState, to: statement, index: 1)
        bindNullableText(taskID, to: statement, index: 2)
        bindNullableText(clarifiedTaskID, to: statement, index: 3)
        bindNullableText(clarifiedProjectID, to: statement, index: 4)
        bindText(clarifiedAt, to: statement, index: 5)
        bindText(updatedAt, to: statement, index: 6)
        bindText(id, to: statement, index: 7)

        guard sqlite3_step(statement) == SQLITE_DONE else {
            throw sqliteError(db, fallback: "Unable to update inbox clarify state.")
        }
    }

    private func deleteTaskRow(_ db: OpaquePointer?, id: String) throws {
        let sql = "DELETE FROM tasks WHERE id = ?"
        var statement: OpaquePointer?
        guard sqlite3_prepare_v2(db, sql, -1, &statement, nil) == SQLITE_OK else {
            throw sqliteError(db, fallback: "Unable to prepare task delete.")
        }
        defer { sqlite3_finalize(statement) }

        bindText(id, to: statement, index: 1)
        guard sqlite3_step(statement) == SQLITE_DONE else {
            throw sqliteError(db, fallback: "Unable to delete task row.")
        }
    }

    private func insertMutationBatch(
        _ db: OpaquePointer?,
        source: String,
        requiresConfirmation: Bool,
        createdAt: String
    ) throws -> String {
        let batchID = UUID().uuidString
        let sql = """
            INSERT INTO mutation_batches (id, source, requires_confirmation, created_at)
            VALUES (?, ?, ?, ?)
        """
        var statement: OpaquePointer?
        guard sqlite3_prepare_v2(db, sql, -1, &statement, nil) == SQLITE_OK else {
            throw sqliteError(db, fallback: "Unable to prepare mutation batch insert.")
        }
        defer { sqlite3_finalize(statement) }

        bindText(batchID, to: statement, index: 1)
        bindText(source, to: statement, index: 2)
        sqlite3_bind_int(statement, 3, requiresConfirmation ? 1 : 0)
        bindText(createdAt, to: statement, index: 4)

        guard sqlite3_step(statement) == SQLITE_DONE else {
            throw sqliteError(db, fallback: "Unable to insert mutation batch.")
        }
        return batchID
    }

    private func insertMutationRecord(
        _ db: OpaquePointer?,
        batchID: String,
        targetTable: String,
        targetID: String,
        action: String,
        payloadJSON: String,
        createdAt: String
    ) throws {
        let sql = """
            INSERT INTO mutation_records (
                id, batch_id, target_table, target_id, action, payload_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """
        var statement: OpaquePointer?
        guard sqlite3_prepare_v2(db, sql, -1, &statement, nil) == SQLITE_OK else {
            throw sqliteError(db, fallback: "Unable to prepare mutation record insert.")
        }
        defer { sqlite3_finalize(statement) }

        bindText(UUID().uuidString, to: statement, index: 1)
        bindText(batchID, to: statement, index: 2)
        bindText(targetTable, to: statement, index: 3)
        bindText(targetID, to: statement, index: 4)
        bindText(action, to: statement, index: 5)
        bindText(payloadJSON, to: statement, index: 6)
        bindText(createdAt, to: statement, index: 7)

        guard sqlite3_step(statement) == SQLITE_DONE else {
            throw sqliteError(db, fallback: "Unable to insert mutation record.")
        }
    }

    private func mutationPayloadJSON(_ payload: [String: String]) -> String {
        guard
            let data = try? JSONSerialization.data(withJSONObject: payload, options: [.sortedKeys]),
            let json = String(data: data, encoding: .utf8)
        else {
            return "{}"
        }
        return json
    }

    private func bootstrapDatabaseIfNeeded() throws {
        try fileManager.createDirectory(
            at: databaseURL.deletingLastPathComponent(),
            withIntermediateDirectories: true,
            attributes: nil
        )

        try withDatabase { db in
            try execute(
                db,
                """
                CREATE TABLE IF NOT EXISTS items (
                    id TEXT PRIMARY KEY,
                    type TEXT,
                    title TEXT,
                    status TEXT,
                    context_tags TEXT,
                    parent_id TEXT,
                    created_at DATETIME,
                    due_date DATETIME,
                    meta_payload TEXT,
                    original_ek_id TEXT,
                    estimated_duration INTEGER,
                    updated_at DATETIME
                )
                """
            )
            try execute(
                db,
                """
                CREATE TABLE IF NOT EXISTS daily_plan_entries (
                    plan_date TEXT NOT NULL,
                    item_id TEXT NOT NULL,
                    bucket TEXT NOT NULL,
                    position INTEGER NOT NULL,
                    created_at DATETIME NOT NULL,
                    PRIMARY KEY (plan_date, item_id)
                )
                """
            )
            try createWorkflowTables(db)

            if try tableHasColumn(db, table: "items", column: "estimated_duration") == false {
                try execute(db, "ALTER TABLE items ADD COLUMN estimated_duration INTEGER")
            }
            if try tableHasColumn(db, table: "items", column: "updated_at") == false {
                try execute(db, "ALTER TABLE items ADD COLUMN updated_at DATETIME")
                try execute(db, "UPDATE items SET updated_at = created_at WHERE updated_at IS NULL")
            }
            try promoteLegacyInboxItems(db)
        }
    }

    private func fetchInboxItems(_ db: OpaquePointer?) throws -> [FlowTask] {
        let sql = """
            SELECT id, title, status, context_tags, due_date, estimated_duration, updated_at
            FROM items
            WHERE type = 'inbox' AND status = 'active' AND parent_id IS NULL
            ORDER BY created_at DESC
            LIMIT 40
        """
        return try fetchTasks(db, sql: sql, source: .capture, projectName: nil)
    }

    private func fetchPlannedItems(_ db: OpaquePointer?) throws -> [FlowTask] {
        let sql = """
            SELECT i.id, i.title, i.status, i.context_tags, i.due_date, i.estimated_duration, i.updated_at, i.parent_id, p.title
            FROM daily_plan_entries d
            JOIN items i ON i.id = d.item_id
            LEFT JOIN items p ON p.id = i.parent_id AND p.type = 'project'
            WHERE i.status = 'active'
            ORDER BY d.plan_date DESC, d.bucket ASC, d.position ASC
        """
        return try fetchTasks(db, sql: sql, source: .planned, projectIDColumnIndex: 7, projectColumnIndex: 8)
    }

    private func fetchLaterItems(_ db: OpaquePointer?, excluding plannedIDs: Set<String>) throws -> [FlowTask] {
        let sql = """
            SELECT i.id, i.title, i.status, i.context_tags, i.due_date, i.estimated_duration, i.updated_at, i.parent_id, p.title
            FROM items i
            LEFT JOIN items p ON p.id = i.parent_id AND p.type = 'project'
            WHERE i.status IN ('active', 'waiting') AND i.type IN ('action', 'inbox')
            ORDER BY i.due_date IS NOT NULL DESC, i.due_date ASC, i.updated_at DESC
        """
        return try fetchTasks(db, sql: sql, source: .project, projectIDColumnIndex: 7, projectColumnIndex: 8)
            .filter { plannedIDs.contains($0.id) == false }
    }

    private func fetchProjects(_ db: OpaquePointer?) throws -> [FlowProject] {
        let sql = """
            SELECT id, title, status
            FROM items
            WHERE type = 'project' AND status = 'active'
            ORDER BY updated_at DESC, created_at DESC
            LIMIT 12
        """

        var statement: OpaquePointer?
        guard sqlite3_prepare_v2(db, sql, -1, &statement, nil) == SQLITE_OK else {
            throw sqliteError(db, fallback: "Unable to prepare projects query.")
        }
        defer { sqlite3_finalize(statement) }

        var projects: [FlowProject] = []
        while sqlite3_step(statement) == SQLITE_ROW {
            let projectID = text(statement, column: 0)
            let title = text(statement, column: 1)
            let tasks = try fetchProjectTasks(db, projectID: projectID, projectTitle: title)
            let nextAction = tasks.first(where: { $0.status == .active || $0.status == .waiting })
            let summary = tasks.isEmpty
                ? "Needs its first clearly defined next action."
                : "Balance execution and planning without widening the day."

            projects.append(
                FlowProject(
                    id: projectID,
                    title: title,
                    summary: summary,
                    nextActionTitle: nextAction?.title,
                    activeCount: tasks.filter { $0.status != .done && $0.status != .archived }.count,
                    completedCount: tasks.filter { $0.status == .done }.count,
                    tasks: tasks
                )
            )
        }

        return projects
    }

    private func fetchProjectTasks(_ db: OpaquePointer?, projectID: String, projectTitle: String) throws -> [FlowTask] {
        let sql = """
            SELECT id, title, status, context_tags, due_date, estimated_duration, updated_at
            FROM items
            WHERE parent_id = ?
            ORDER BY status = 'done' ASC, updated_at DESC, created_at DESC
        """
        return try fetchTasks(
            db,
            sql: sql,
            bindings: [projectID],
            source: .project,
            projectID: projectID,
            projectName: projectTitle
        )
    }

    private func fetchStaleItems(_ db: OpaquePointer?) throws -> [FlowTask] {
        let threshold = Calendar.current.date(byAdding: .day, value: -14, to: Date()) ?? Date()
        let sql = """
            SELECT id, title, status, context_tags, due_date, estimated_duration, updated_at
            FROM items
            WHERE status = 'active' AND updated_at < ?
            ORDER BY updated_at ASC
            LIMIT 10
        """
        return try fetchTasks(
            db,
            sql: sql,
            bindings: [isoTimestamp(threshold)],
            source: .project
        )
    }

    private func buildReviewSummary(_ db: OpaquePointer?, staleCount: Int) throws -> ReviewSummary {
        let completedSQL = "SELECT COUNT(*) FROM items WHERE status = 'done' AND updated_at >= ?"
        let dueSoonSQL = "SELECT COUNT(*) FROM items WHERE status = 'active' AND due_date IS NOT NULL AND due_date <= ?"
        let weekAgo = Calendar.current.date(byAdding: .day, value: -7, to: Date()) ?? Date()
        let soon = Calendar.current.date(byAdding: .day, value: 3, to: Date()) ?? Date()

        let completed = try scalarCount(db, sql: completedSQL, bindings: [isoTimestamp(weekAgo)])
        let dueSoon = try scalarCount(db, sql: dueSoonSQL, bindings: [isoTimestamp(soon)])

        let headline: String
        let prompt: String
        if staleCount == 0 && dueSoon <= 1 {
            headline = "Healthy system, light maintenance"
            prompt = "Keep the inbox moving and preserve space for deep work."
        } else if staleCount >= 5 {
            headline = "Backlog drift is building"
            prompt = "Prune stale commitments before adding more work."
        } else {
            headline = "Strong progress, tighten follow-through"
            prompt = "Resolve stale edges and keep upcoming commitments visible."
        }

        return ReviewSummary(
            completedThisWeek: completed,
            staleCount: staleCount,
            dueSoonCount: dueSoon,
            headline: headline,
            prompt: prompt
        )
    }

    private func buildWeeklyReviewPackage(_ db: OpaquePointer?, referenceDate: Date) throws -> FlowWeeklyReviewPackage {
        let calendar = Calendar(identifier: .gregorian)
        let weekAgo = calendar.date(byAdding: .day, value: -7, to: referenceDate) ?? referenceDate
        let staleThreshold = calendar.date(byAdding: .day, value: -14, to: referenceDate) ?? referenceDate
        let soon = calendar.date(byAdding: .day, value: 7, to: referenceDate) ?? referenceDate

        let completed = try fetchTasks(
            db,
            sql: """
                SELECT id, title, status, context_tags, due_date, estimated_duration, updated_at
                FROM items
                WHERE status = 'done' AND updated_at >= ?
                ORDER BY updated_at DESC
                LIMIT 12
            """,
            bindings: [isoTimestamp(weekAgo)],
            source: .project
        )
        let stale = try fetchTasks(
            db,
            sql: """
                SELECT id, title, status, context_tags, due_date, estimated_duration, updated_at
                FROM items
                WHERE status = 'active' AND updated_at < ?
                ORDER BY updated_at ASC
                LIMIT 12
            """,
            bindings: [isoTimestamp(staleThreshold)],
            source: .project
        )
        let inbox = try fetchInboxItems(db)
        let dueSoon = try fetchTasks(
            db,
            sql: """
                SELECT id, title, status, context_tags, due_date, estimated_duration, updated_at
                FROM items
                WHERE status = 'active' AND due_date IS NOT NULL AND due_date <= ?
                ORDER BY due_date ASC
                LIMIT 12
            """,
            bindings: [isoTimestamp(soon)],
            source: .planned
        )
        let projects = try fetchProjects(db)
        let projectHealth = makeProjectHealth(projects)
        let cleanupActions = makeWeeklyReviewCleanupActions(stale: stale, inbox: inbox, projects: projects, dueSoon: dueSoon)

        return FlowWeeklyReviewPackage(
            generatedAtLabel: shortDateFormatter.string(from: referenceDate),
            completedWork: completed,
            staleItems: stale,
            inboxItems: inbox,
            projectHealth: projectHealth,
            upcomingDeadlines: dueSoon,
            cleanupActions: cleanupActions
        )
    }

    private func makeProjectHealth(_ projects: [FlowProject]) -> [FlowProjectHealth] {
        guard projects.isEmpty == false else {
            return [
                FlowProjectHealth(
                    id: "project-health-empty",
                    title: "Projects",
                    statusLabel: "No active projects",
                    detail: "The weekly review can stay focused on inbox, deadlines, and stale standalone work."
                )
            ]
        }

        return projects.map { project in
            let statusLabel: String
            let detail: String
            if project.activeCount == 0 {
                statusLabel = "Needs next action"
                detail = "Add or clarify a next action before this project can move."
            } else if project.completedCount > 0 {
                statusLabel = "Progressing"
                detail = "Completed work exists; confirm the next visible commitment."
            } else {
                statusLabel = "Active"
                detail = project.nextActionTitle.map { "Next action: \($0)" } ?? project.summary
            }
            return FlowProjectHealth(
                id: project.id,
                title: project.title,
                statusLabel: statusLabel,
                detail: detail
            )
        }
    }

    private func makeWeeklyReviewCleanupActions(
        stale: [FlowTask],
        inbox: [FlowTask],
        projects: [FlowProject],
        dueSoon: [FlowTask]
    ) -> [FlowReviewCleanupAction] {
        var actions = stale.map { task in
            FlowReviewCleanupAction(
                id: "archive-stale-\(task.id)",
                kind: "archive_stale_item",
                title: "Archive stale: \(task.title)",
                detail: "Move this aging active item out of the live system.",
                targetIDs: [task.id],
                destructive: true
            )
        }

        if inbox.isEmpty == false {
            actions.append(
                FlowReviewCleanupAction(
                    id: "clarify-inbox",
                    kind: "clarify_inbox",
                    title: "Clarify \(inbox.count) inbox item\(inbox.count == 1 ? "" : "s")",
                    detail: "Work through the raw captures still waiting for a decision.",
                    targetIDs: inbox.map(\.id),
                    destructive: false
                )
            )
        }

        let projectsNeedingNextAction = projects.filter { $0.activeCount == 0 }
        if projectsNeedingNextAction.isEmpty == false {
            actions.append(
                FlowReviewCleanupAction(
                    id: "project-next-actions",
                    kind: "project_next_action_review",
                    title: "Add missing project next actions",
                    detail: "\(projectsNeedingNextAction.count) active project\(projectsNeedingNextAction.count == 1 ? "" : "s") need a concrete next step.",
                    targetIDs: projectsNeedingNextAction.map(\.id),
                    destructive: false
                )
            )
        }

        if dueSoon.isEmpty == false {
            actions.append(
                FlowReviewCleanupAction(
                    id: "deadline-check",
                    kind: "deadline_review",
                    title: "Check \(dueSoon.count) upcoming deadline\(dueSoon.count == 1 ? "" : "s")",
                    detail: "Confirm these commitments still fit the coming week.",
                    targetIDs: dueSoon.map(\.id),
                    destructive: false
                )
            )
        }

        return actions
    }

    private func fetchNotificationPolicy(_ db: OpaquePointer?) throws -> FlowNotificationPolicyState {
        let permissionStatus = try fetchNotificationPermissionStatus(db)
        let pending = try fetchPendingNotificationCandidates(db)
        let degradedReasons = notificationDegradedReasons(permissionStatus: permissionStatus)
        let deliveryMode = degradedReasons.isEmpty ? "flow_owned_local" : "degraded"

        return FlowNotificationPolicyState(
            permissionStatus: permissionStatus,
            deliveryMode: deliveryMode,
            degradedReasons: degradedReasons,
            pendingNotifications: deliveryMode == "flow_owned_local" ? pending : [],
            offlineDescription: "Flow-owned notifications are local to this Mac; if permission or system services are unavailable, tasks remain visible in Today and Daily Plan."
        )
    }

    private func fetchNotificationPermissionStatus(_ db: OpaquePointer?) throws -> String {
        let sql = "SELECT permission_status FROM notification_policy WHERE id = 'flow' LIMIT 1"
        var statement: OpaquePointer?
        guard sqlite3_prepare_v2(db, sql, -1, &statement, nil) == SQLITE_OK else {
            throw sqliteError(db, fallback: "Unable to prepare notification policy query.")
        }
        defer { sqlite3_finalize(statement) }

        if sqlite3_step(statement) == SQLITE_ROW {
            return text(statement, column: 0)
        }
        return "not_determined"
    }

    private func fetchPendingNotificationCandidates(_ db: OpaquePointer?) throws -> [FlowNotificationCandidate] {
        let sql = """
            SELECT id, title, due_date
            FROM items
            WHERE status = 'active' AND due_date IS NOT NULL
            ORDER BY due_date ASC
            LIMIT 20
        """
        var statement: OpaquePointer?
        guard sqlite3_prepare_v2(db, sql, -1, &statement, nil) == SQLITE_OK else {
            throw sqliteError(db, fallback: "Unable to prepare notification candidates query.")
        }
        defer { sqlite3_finalize(statement) }

        var candidates: [FlowNotificationCandidate] = []
        while sqlite3_step(statement) == SQLITE_ROW {
            let id = text(statement, column: 0)
            let rawDue = nullableText(statement, column: 2)
            candidates.append(
                FlowNotificationCandidate(
                    id: "notification-\(id)",
                    taskID: id,
                    title: text(statement, column: 1),
                    fireAtLabel: formattedDueLabel(rawValue: rawDue) ?? "Scheduled",
                    policyLabel: "Flow-owned local"
                )
            )
        }
        return candidates
    }

    private func notificationDegradedReasons(permissionStatus: String) -> [String] {
        switch permissionStatus {
        case "authorized", "provisional":
            return []
        case "denied":
            return ["Notifications are denied in macOS settings; Flow will keep reminders visible in-app only."]
        case "unavailable":
            return ["macOS notification services are unavailable; Flow is running in degraded local-only mode."]
        default:
            return ["Local notification permission has not been requested; Flow will not schedule alerts yet."]
        }
    }

    private func buildAssistantSuggestions(inbox: [FlowTask], today: [FlowTask], stale: [FlowTask]) -> [AssistantSuggestion] {
        var suggestions: [AssistantSuggestion] = []

        if let firstInbox = inbox.first {
            suggestions.append(
                AssistantSuggestion(
                    id: "assistant-inbox",
                    title: "Clarify your newest capture",
                    detail: "\"\(firstInbox.title)\" still looks like raw intent. Turn it into a concrete next action.",
                    outcomeLabel: "Preview"
                )
            )
        }

        if today.count >= 3 {
            suggestions.append(
                AssistantSuggestion(
                    id: "assistant-plan",
                    title: "Keep the plan constrained",
                    detail: "Three primary items are already active. Push additional work into later, not into today.",
                    outcomeLabel: "Guardrail"
                )
            )
        }

        if let staleItem = stale.first {
            suggestions.append(
                AssistantSuggestion(
                    id: "assistant-stale",
                    title: "Review an aging commitment",
                    detail: "\"\(staleItem.title)\" has gone quiet. Archive it or restate the next move.",
                    outcomeLabel: "Needs decision"
                )
            )
        }

        if suggestions.isEmpty {
            suggestions = SampleWorkspaceFactory.makeSnapshot().assistantSuggestions
        }

        return suggestions
    }

    private func buildMemoryEntries(projects: [FlowProject], inbox: [FlowTask]) -> [MemoryEntry] {
        guard projects.isEmpty == false || inbox.isEmpty == false else {
            return SampleWorkspaceFactory.makeSnapshot().memoryEntries
        }

        var entries: [MemoryEntry] = [
            MemoryEntry(
                id: "memory-plan-shape",
                title: "Prefers a small daily focus set",
                detail: "The current workspace emphasizes a compact set of primary work rather than a broad queue.",
                confidenceLabel: "Working assumption",
                scopeLabel: "Planning"
            )
        ]

        if inbox.isEmpty == false {
            entries.append(
                MemoryEntry(
                    id: "memory-capture",
                    title: "Recent captures need clarification support",
                    detail: "The native shell should continue nudging capture-to-clarify transitions instead of leaving them raw.",
                    confidenceLabel: "Observed",
                    scopeLabel: "Inbox"
                )
            )
        }

        if let project = projects.first {
            entries.append(
                MemoryEntry(
                    id: "memory-project",
                    title: "Active project context: \(project.title)",
                    detail: "Project surfaces should keep the next action visible without flattening project state into a plain list.",
                    confidenceLabel: "Context",
                    scopeLabel: "Project"
                )
            )
        }

        return entries
    }

    private func buildFocusHeadline(todayCount: Int, inboxCount: Int) -> String {
        if todayCount >= 3 {
            return "Deliberate plan in place, protect the next block"
        }
        if inboxCount > 0 {
            return "Clear the freshest ambiguity before widening the day"
        }
        return "Quiet system, ready for a thoughtful start"
    }

    private func fetchTasks(
        _ db: OpaquePointer?,
        sql: String,
        bindings: [String] = [],
        source: FlowTaskSource,
        projectID: String? = nil,
        projectIDColumnIndex: Int? = nil,
        projectName: String? = nil,
        projectColumnIndex: Int? = nil
    ) throws -> [FlowTask] {
        var statement: OpaquePointer?
        guard sqlite3_prepare_v2(db, sql, -1, &statement, nil) == SQLITE_OK else {
            throw sqliteError(db, fallback: "Unable to prepare task query.")
        }
        defer { sqlite3_finalize(statement) }

        for (offset, value) in bindings.enumerated() {
            bindText(value, to: statement, index: Int32(offset + 1))
        }

        var tasks: [FlowTask] = []
        while sqlite3_step(statement) == SQLITE_ROW {
            let resolvedProjectID: String?
            if let projectIDColumnIndex {
                let value = text(statement, column: Int32(projectIDColumnIndex))
                resolvedProjectID = value.isEmpty ? projectID : value
            } else {
                resolvedProjectID = projectID
            }

            let resolvedProjectName: String?
            if let projectColumnIndex {
                let value = text(statement, column: Int32(projectColumnIndex))
                resolvedProjectName = value.isEmpty ? projectName : value
            } else {
                resolvedProjectName = projectName
            }

            tasks.append(
                FlowTask(
                    id: text(statement, column: 0),
                    title: text(statement, column: 1),
                    summary: resolvedProjectName.map { "Linked to \($0)." } ?? sourceSummary(for: source),
                    status: FlowTaskStatus(rawValue: text(statement, column: 2)) ?? .active,
                    source: inferredSource(source: source, projectName: resolvedProjectName),
                    projectID: resolvedProjectID,
                    projectName: resolvedProjectName,
                    dueLabel: formattedDueLabel(rawValue: nullableText(statement, column: 4)),
                    tags: decodedTags(nullableText(statement, column: 3)),
                    estimatedMinutes: nullableInt(statement, column: 5),
                    isFlagged: nullableText(statement, column: 4) != nil,
                    lastUpdatedLabel: relativeTimestampLabel(rawValue: nullableText(statement, column: 6))
                )
            )
        }
        return tasks
    }

    private func inferredSource(source: FlowTaskSource, projectName: String?) -> FlowTaskSource {
        if source == .capture, projectName != nil {
            return .project
        }
        return source
    }

    private func scalarCount(_ db: OpaquePointer?, sql: String, bindings: [String]) throws -> Int {
        var statement: OpaquePointer?
        guard sqlite3_prepare_v2(db, sql, -1, &statement, nil) == SQLITE_OK else {
            throw sqliteError(db, fallback: "Unable to prepare scalar query.")
        }
        defer { sqlite3_finalize(statement) }

        for (offset, value) in bindings.enumerated() {
            bindText(value, to: statement, index: Int32(offset + 1))
        }

        guard sqlite3_step(statement) == SQLITE_ROW else { return 0 }
        return Int(sqlite3_column_int(statement, 0))
    }

    private func sourceSummary(for source: FlowTaskSource) -> String {
        switch source {
        case .capture:
            return "Fresh capture awaiting a confident next step."
        case .planned:
            return "Selected for the active day and ready to move."
        case .project:
            return "Project-linked work kept visible without flooding the plan."
        case .reminders:
            return "Imported from Apple Reminders."
        case .assistant:
            return "Assistant-suggested refinement of your current flow."
        }
    }

    private func createWorkflowTables(_ db: OpaquePointer?) throws {
        for statement in FlowSchema.nativeWorkflowTableStatements {
            try execute(db, statement)
        }
    }

    private func promoteLegacyInboxItems(_ db: OpaquePointer?) throws {
        let sql = """
            SELECT id, type, title, status, parent_id, created_at, updated_at, original_ek_id
            FROM items
        """
        var statement: OpaquePointer?
        guard sqlite3_prepare_v2(db, sql, -1, &statement, nil) == SQLITE_OK else {
            throw sqliteError(db, fallback: "Unable to prepare legacy inbox promotion query.")
        }
        defer { sqlite3_finalize(statement) }

        while sqlite3_step(statement) == SQLITE_ROW {
            let id = text(statement, column: 0)
            let itemType = text(statement, column: 1)
            let title = text(statement, column: 2)
            let status = text(statement, column: 3)
            let parentID = nullableText(statement, column: 4)
            let createdAt = nullableText(statement, column: 5) ?? isoTimestamp()
            let updatedAt = nullableText(statement, column: 6) ?? createdAt
            let originalReminderID = nullableText(statement, column: 7)

            switch itemType {
            case "inbox":
                let originType: NativeCaptureOrigin = originalReminderID == nil ? .manualCapture : .remindersImport
                try insertRawCapture(
                    db,
                    record: RawCaptureRecord(
                        id: id,
                        source: originType,
                        rawText: title,
                        createdAt: createdAt
                    )
                )
                try insertInboxItem(
                    db,
                    record: InboxItemRecord(
                        id: id,
                        rawCaptureID: id,
                        originType: originType,
                        inboxState: "needs_clarification",
                        sourceRef: originalReminderID,
                        importedAt: originalReminderID == nil ? nil : createdAt,
                        createdAt: createdAt,
                        updatedAt: updatedAt
                    )
                )
            case "project":
                try insertProject(
                    db,
                    id: id,
                    name: title,
                    status: status,
                    createdAt: createdAt,
                    updatedAt: updatedAt
                )
            case "action":
                try insertTask(
                    db,
                    id: id,
                    title: title,
                    status: status,
                    projectID: parentID,
                    createdAt: createdAt,
                    updatedAt: updatedAt
                )
            default:
                continue
            }
        }
    }

    private func insertRawCapture(
        _ db: OpaquePointer?,
        record: RawCaptureRecord
    ) throws {
        let sql = """
            INSERT OR IGNORE INTO raw_captures (id, source, raw_text, created_at)
            VALUES (?, ?, ?, ?)
        """
        var statement: OpaquePointer?
        guard sqlite3_prepare_v2(db, sql, -1, &statement, nil) == SQLITE_OK else {
            throw sqliteError(db, fallback: "Unable to prepare raw capture insert.")
        }
        defer { sqlite3_finalize(statement) }

        bindText(record.id, to: statement, index: 1)
        bindText(record.source.rawValue, to: statement, index: 2)
        bindText(record.rawText, to: statement, index: 3)
        bindText(record.createdAt, to: statement, index: 4)

        guard sqlite3_step(statement) == SQLITE_DONE else {
            throw sqliteError(db, fallback: "Unable to insert raw capture.")
        }
    }

    private func insertInboxItem(
        _ db: OpaquePointer?,
        record: InboxItemRecord
    ) throws {
        let sql = """
            INSERT OR IGNORE INTO inbox_items (
                id, raw_capture_id, origin_type, inbox_state, source_ref,
                imported_at, task_id, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, NULL, ?, ?)
        """
        var statement: OpaquePointer?
        guard sqlite3_prepare_v2(db, sql, -1, &statement, nil) == SQLITE_OK else {
            throw sqliteError(db, fallback: "Unable to prepare inbox item insert.")
        }
        defer { sqlite3_finalize(statement) }

        bindText(record.id, to: statement, index: 1)
        bindText(record.rawCaptureID, to: statement, index: 2)
        bindText(record.originType.rawValue, to: statement, index: 3)
        bindText(record.inboxState, to: statement, index: 4)
        if let sourceRef = record.sourceRef {
            bindText(sourceRef, to: statement, index: 5)
        } else {
            sqlite3_bind_null(statement, 5)
        }
        if let importedAt = record.importedAt {
            bindText(importedAt, to: statement, index: 6)
        } else {
            sqlite3_bind_null(statement, 6)
        }
        bindText(record.createdAt, to: statement, index: 7)
        bindText(record.updatedAt, to: statement, index: 8)

        guard sqlite3_step(statement) == SQLITE_DONE else {
            throw sqliteError(db, fallback: "Unable to insert inbox item.")
        }
    }

    private func insertProject(
        _ db: OpaquePointer?,
        id: String,
        name: String,
        status: String,
        createdAt: String,
        updatedAt: String
    ) throws {
        let sql = """
            INSERT OR IGNORE INTO projects (id, name, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
        """
        var statement: OpaquePointer?
        guard sqlite3_prepare_v2(db, sql, -1, &statement, nil) == SQLITE_OK else {
            throw sqliteError(db, fallback: "Unable to prepare project insert.")
        }
        defer { sqlite3_finalize(statement) }

        bindText(id, to: statement, index: 1)
        bindText(name, to: statement, index: 2)
        bindText(status, to: statement, index: 3)
        bindText(createdAt, to: statement, index: 4)
        bindText(updatedAt, to: statement, index: 5)

        guard sqlite3_step(statement) == SQLITE_DONE else {
            throw sqliteError(db, fallback: "Unable to insert project.")
        }
    }

    private func insertTask(
        _ db: OpaquePointer?,
        id: String,
        title: String,
        status: String,
        projectID: String?,
        createdAt: String,
        updatedAt: String
    ) throws {
        let sql = """
            INSERT OR IGNORE INTO tasks (
                id, title, status, project_id, time_sensitivity, effort_band, created_at, updated_at
            ) VALUES (?, ?, ?, ?, 'none', 'medium', ?, ?)
        """
        var statement: OpaquePointer?
        guard sqlite3_prepare_v2(db, sql, -1, &statement, nil) == SQLITE_OK else {
            throw sqliteError(db, fallback: "Unable to prepare task insert.")
        }
        defer { sqlite3_finalize(statement) }

        bindText(id, to: statement, index: 1)
        bindText(title, to: statement, index: 2)
        bindText(status, to: statement, index: 3)
        if let projectID {
            bindText(projectID, to: statement, index: 4)
        } else {
            sqlite3_bind_null(statement, 4)
        }
        bindText(createdAt, to: statement, index: 5)
        bindText(updatedAt, to: statement, index: 6)

        guard sqlite3_step(statement) == SQLITE_DONE else {
            throw sqliteError(db, fallback: "Unable to insert task.")
        }
    }

    private func withDatabase<T>(_ body: (OpaquePointer?) throws -> T) throws -> T {
        var db: OpaquePointer?
        guard sqlite3_open(databaseURL.path, &db) == SQLITE_OK else {
            defer { sqlite3_close(db) }
            throw sqliteError(db, fallback: "Unable to open SQLite database at \(databaseURL.path).")
        }
        defer { sqlite3_close(db) }
        return try body(db)
    }

    private func execute(_ db: OpaquePointer?, _ sql: String) throws {
        var errorPointer: UnsafeMutablePointer<Int8>?
        guard sqlite3_exec(db, sql, nil, nil, &errorPointer) == SQLITE_OK else {
            let fallback = errorPointer.map { String(cString: $0) } ?? "SQLite execution error."
            sqlite3_free(errorPointer)
            throw FlowDataError.message(fallback)
        }
    }

    private func tableHasColumn(_ db: OpaquePointer?, table: String, column: String) throws -> Bool {
        let sql = "PRAGMA table_info(\(table))"
        var statement: OpaquePointer?
        guard sqlite3_prepare_v2(db, sql, -1, &statement, nil) == SQLITE_OK else {
            throw sqliteError(db, fallback: "Unable to inspect database schema.")
        }
        defer { sqlite3_finalize(statement) }

        while sqlite3_step(statement) == SQLITE_ROW {
            if text(statement, column: 1) == column {
                return true
            }
        }
        return false
    }

    private func text(_ statement: OpaquePointer?, column: Int32) -> String {
        guard let pointer = sqlite3_column_text(statement, column) else { return "" }
        return String(cString: pointer)
    }

    private func nullableText(_ statement: OpaquePointer?, column: Int32) -> String? {
        let value = text(statement, column: column)
        return value.isEmpty ? nil : value
    }

    private func bindNullableText(_ value: String?, to statement: OpaquePointer?, index: Int32) {
        if let value {
            bindText(value, to: statement, index: index)
        } else {
            sqlite3_bind_null(statement, index)
        }
    }

    private func nullableInt(_ statement: OpaquePointer?, column: Int32) -> Int? {
        guard sqlite3_column_type(statement, column) != SQLITE_NULL else { return nil }
        return Int(sqlite3_column_int(statement, column))
    }

    private func decodedTags(_ rawValue: String?) -> [String] {
        guard
            let rawValue,
            let data = rawValue.data(using: .utf8),
            let decoded = try? JSONSerialization.jsonObject(with: data) as? [String]
        else {
            return []
        }
        return decoded
    }

    private func formattedDueLabel(rawValue: String?) -> String? {
        guard let rawValue, let date = parseDate(rawValue) else {
            return rawValue
        }
        if Calendar.current.isDateInToday(date) { return "Today" }
        if Calendar.current.isDateInTomorrow(date) { return "Tomorrow" }
        return shortDateFormatter.string(from: date)
    }

    private func relativeTimestampLabel(rawValue: String?) -> String? {
        guard let rawValue, let date = parseDate(rawValue) else {
            return nil
        }
        let formatter = RelativeDateTimeFormatter()
        formatter.unitsStyle = .abbreviated
        return "Updated " + formatter.localizedString(for: date, relativeTo: Date())
    }

    private func bindText(_ value: String, to statement: OpaquePointer?, index: Int32) {
        _ = value.withCString { pointer in
            sqlite3_bind_text(statement, index, pointer, -1, transientDestructor)
        }
    }

    private func sqliteError(_ db: OpaquePointer?, fallback: String) -> FlowDataError {
        guard let db else { return .message(fallback) }
        let message = String(cString: sqlite3_errmsg(db))
        return .message(message.isEmpty ? fallback : message)
    }
}

private let isoDateFormatter: ISO8601DateFormatter = {
    let formatter = ISO8601DateFormatter()
    formatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
    return formatter
}()

private let shortDateFormatter: DateFormatter = {
    let formatter = DateFormatter()
    formatter.dateStyle = .medium
    formatter.timeStyle = .none
    return formatter
}()

private let transientDestructor = unsafeBitCast(-1, to: sqlite3_destructor_type.self)

private func isoTimestamp(_ date: Date = Date()) -> String {
    isoDateFormatter.string(from: date)
}

private func parseDate(_ rawValue: String) -> Date? {
    if let date = isoDateFormatter.date(from: rawValue) {
        return date
    }
    let fallbackFormatter = ISO8601DateFormatter()
    fallbackFormatter.formatOptions = [.withInternetDateTime]
    return fallbackFormatter.date(from: rawValue)
}

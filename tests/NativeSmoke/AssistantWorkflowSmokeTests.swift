import Foundation
import SwiftUI

enum AssistantWorkflowSmokeTests {
    @MainActor
    static func run() throws {
        try smokeTestAssistantSessionMessageBoundaryContract()
        try smokeTestWorkspaceStoreSessionMessageState()
        try smokeTestWorkspaceStoreSessionReloadResumeAndContinuation()
        try smokeTestSidecarWorkspaceStoreSessionReloadResumeAndContinuation()
        try smokeTestAssistantUndoTargetsTheMutatedSession()
        try smokeTestWorkspaceStoreRefreshDoesNotGateOnTurns()
        try smokeTestAssistantViewUsesRenderedChatFirstSurface()
        try smokeTestAssistantSendDoesNotBlockMainActor()
        try smokeTestAssistantProposalActionFailuresSurfaceLocalFeedback()
        try smokeTestAssistantWorkflowServiceDelegatesSessionMessageAPI()
    }

    private static func smokeTestAssistantSessionMessageBoundaryContract() throws {
        let repository = LegacyFlowRepository(databaseURL: temporaryDatabaseURL())

        let session = try repository.createAssistantSession(title: "Plan my day")
        let firstMessage = try repository.sendAssistantMessage(
            sessionID: session.id,
            prompt: "Add review the launch checklist.",
            planDate: "2026-03-08"
        )
        let secondMessage = try repository.sendAssistantMessage(
            sessionID: session.id,
            prompt: "Remember that I prefer maker mornings.",
            planDate: "2026-03-08"
        )

        let sessions = try repository.loadAssistantSessions(limit: 10)
        guard sessions.first?.id == session.id else {
            throw FlowDataError.message("Expected assistant sessions to expose the created conversation.")
        }
        guard sessions.first?.messageCount == 4 else {
            throw FlowDataError.message("Expected assistant session metadata to reflect the user and assistant messages.")
        }

        let messages = try repository.loadAssistantMessages(sessionID: session.id, limit: 10)
        guard messages.map(\.role) == ["user", "assistant", "user", "assistant"] else {
            throw FlowDataError.message("Expected assistant messages to stay ordered oldest-to-newest inside one session.")
        }
        guard messages.compactMap(\.sourceTurnID).count == 2 else {
            throw FlowDataError.message("Expected assistant messages to preserve transitional source turn ids.")
        }

        _ = try repository.confirmAssistantMessageProposal(messageID: firstMessage.id)
        try repository.dismissAssistantMessageProposal(messageID: secondMessage.id)

        let updatedMessages = try repository.loadAssistantMessages(sessionID: session.id, limit: 10)
        guard updatedMessages.first(where: { $0.id == firstMessage.id })?.proposalStatus == "confirmed" else {
            throw FlowDataError.message("Expected confirmation to target the assistant message id.")
        }
        guard updatedMessages.first(where: { $0.id == secondMessage.id })?.proposalStatus == "dismissed" else {
            throw FlowDataError.message("Expected dismissal to target the assistant message id.")
        }

        let undoMessage = try repository.undoLastAssistantMutation()
        guard undoMessage?.localizedCaseInsensitiveContains("undid") == true else {
            throw FlowDataError.message("Expected undo to remain available through the assistant repository boundary.")
        }

        let undoneMessages = try repository.loadAssistantMessages(sessionID: session.id, limit: 10)
        guard undoneMessages.map(\.role) == ["user", "assistant"] else {
            throw FlowDataError.message("Expected undo to roll back the latest assistant message pair.")
        }
    }

    @MainActor
    private static func smokeTestWorkspaceStoreSessionMessageState() throws {
        let repository = LegacyFlowRepository(databaseURL: temporaryDatabaseURL())
        let store = WorkspaceStore(repository: repository)

        store.refresh()
        guard store.assistantSessions.isEmpty else {
            throw FlowDataError.message("Expected assistant sessions to start empty for the fallback repository smoke test.")
        }
        guard store.assistantMessages.isEmpty else {
            throw FlowDataError.message("Expected assistant messages to start empty before the first send.")
        }

        store.assistantComposerText = "Add review the launch checklist."
        store.sendAssistantMessage()
        try waitForAssistantSendCompletion(store)

        guard store.assistantSessions.count == 1 else {
            throw FlowDataError.message("Expected sending from an empty assistant state to lazy-create one session.")
        }
        guard store.selectedAssistantSessionID == store.assistantSessions.first?.id else {
            throw FlowDataError.message("Expected the lazily created assistant session to remain selected.")
        }
        guard store.assistantMessages.map(\.role) == ["user", "assistant"] else {
            throw FlowDataError.message("Expected the selected assistant session to expose the user and assistant messages.")
        }
        guard store.selectedAssistantMessage?.proposalStatus == "pending" else {
            throw FlowDataError.message("Expected the assistant message state to stay proposal-pending after send.")
        }
        guard store.assistantComposerText.isEmpty else {
            throw FlowDataError.message("Expected the assistant composer to clear after send.")
        }

        let messageCount = store.assistantMessages.count
        store.assistantComposerText = "   "
        store.sendAssistantMessage()
        try waitForAssistantSendCompletion(store)
        guard store.assistantSendPending == false else {
            throw FlowDataError.message("Expected an empty assistant prompt to remain disabled and not enter a pending send state.")
        }
        guard store.assistantMessages.count == messageCount else {
            throw FlowDataError.message("Expected an empty assistant prompt send to be a no-op.")
        }

        let firstSessionID = store.assistantSessions.first?.id
        store.createAssistantSession(title: "Second chat")
        guard store.assistantSessions.count == 2 else {
            throw FlowDataError.message("Expected explicit assistant session creation to add another conversation.")
        }
        guard store.assistantMessages.isEmpty else {
            throw FlowDataError.message("Expected a new assistant session to start with no messages.")
        }
        guard store.selectedAssistantSession?.title == "Second chat" else {
            throw FlowDataError.message("Expected explicit assistant session creation to select the new conversation.")
        }

        if let firstSessionID {
            store.selectAssistantSession(id: firstSessionID)
        }
        guard store.assistantMessages.map(\.role) == ["user", "assistant"] else {
            throw FlowDataError.message("Expected selecting the first assistant session to reload its message history.")
        }

        store.confirmSelectedAssistantProposal()
        guard store.selectedAssistantMessage?.proposalStatus == "confirmed" else {
            throw FlowDataError.message("Expected confirming the selected assistant proposal to update message state.")
        }

        store.dismissSelectedAssistantProposal()
        guard store.errorMessage?.localizedCaseInsensitiveContains("pending") == true else {
            throw FlowDataError.message("Expected dismissing a confirmed assistant proposal to fail with the pending-state guard.")
        }
        guard store.selectedAssistantMessage?.proposalStatus == "confirmed" else {
            throw FlowDataError.message("Expected the confirmed assistant message to remain confirmed after the rejected dismissal.")
        }

        store.undoLastAssistantMutation()
        guard store.assistantMessages.isEmpty else {
            throw FlowDataError.message("Expected undo to remove the latest assistant message pair from the selected session.")
        }
        guard store.selectedAssistantSession?.messageCount == 0 else {
            throw FlowDataError.message("Expected undo to clear the selected session message count.")
        }
        guard store.assistantActionFeedback?.localizedCaseInsensitiveContains("undid") == true else {
            throw FlowDataError.message("Expected undo to surface assistant-local feedback from the returned result string.")
        }
    }

    @MainActor
    private static func smokeTestWorkspaceStoreSessionReloadResumeAndContinuation() throws {
        let repository = LegacyFlowRepository(databaseURL: temporaryDatabaseURL())
        let firstStore = WorkspaceStore(repository: repository)

        firstStore.refresh()
        firstStore.assistantComposerText = "Add review the launch checklist."
        firstStore.sendAssistantMessage()
        try waitForAssistantSendCompletion(firstStore)

        guard let firstSessionID = firstStore.selectedAssistantSessionID else {
            throw FlowDataError.message("Expected the first assistant send to lazily create a selected session.")
        }
        guard firstStore.assistantSessions.count == 1 else {
            throw FlowDataError.message("Expected the first assistant send to create one persisted session.")
        }
        guard firstStore.assistantMessages.map(\.role) == ["user", "assistant"] else {
            throw FlowDataError.message("Expected the first assistant send to create a user/assistant message pair.")
        }
        guard firstStore.selectedAssistantMessage?.proposalStatus == "pending" else {
            throw FlowDataError.message("Expected the first assistant reply to remain pending before review.")
        }
        guard firstStore.selectedAssistantMessage?.provider == "deterministic" else {
            throw FlowDataError.message("Expected the assistant reply to preserve provider provenance in storage.")
        }
        guard firstStore.selectedAssistantMessage?.providerStatus == "success" else {
            throw FlowDataError.message("Expected the assistant reply to preserve provider success state in storage.")
        }
        guard firstStore.selectedAssistantMessage?.auditSteps.isEmpty == false else {
            throw FlowDataError.message("Expected the assistant reply to preserve audit evidence in storage.")
        }

        let reloadedStore = WorkspaceStore(repository: repository)
        reloadedStore.refresh()

        guard reloadedStore.assistantSessions.map(\.id) == [firstSessionID] else {
            throw FlowDataError.message("Expected the persisted assistant session to reload into the next store instance.")
        }
        guard reloadedStore.selectedAssistantSessionID == firstSessionID else {
            throw FlowDataError.message("Expected reload to resume the persisted assistant session selection.")
        }
        guard reloadedStore.assistantMessages.map(\.role) == ["user", "assistant"] else {
            throw FlowDataError.message("Expected reload to restore the assistant session message history.")
        }
        guard reloadedStore.assistantMessages.allSatisfy({ $0.sessionID == firstSessionID }) else {
            throw FlowDataError.message("Expected reload to keep the restored assistant messages scoped to the persisted session.")
        }
        guard reloadedStore.selectedAssistantMessage?.provider == "deterministic" else {
            throw FlowDataError.message("Expected reload to preserve assistant message provenance visibility.")
        }
        guard reloadedStore.selectedAssistantMessageDisclosureSummary?.contains("Provider: deterministic") == true else {
            throw FlowDataError.message("Expected reload to expose assistant disclosure state through the WorkspaceStore hook.")
        }

        reloadedStore.assistantComposerText = "Add a follow-up next action."
        reloadedStore.sendAssistantMessage()
        try waitForAssistantSendCompletion(reloadedStore)

        guard reloadedStore.assistantSessions.first(where: { $0.id == firstSessionID })?.messageCount == 4 else {
            throw FlowDataError.message("Expected multi-turn continuation to stay inside the selected assistant session.")
        }
        guard reloadedStore.assistantMessages.map(\.role) == ["user", "assistant", "user", "assistant"] else {
            throw FlowDataError.message("Expected a second send to continue the same assistant session conversation.")
        }
        guard reloadedStore.assistantMessages.allSatisfy({ $0.sessionID == firstSessionID }) else {
            throw FlowDataError.message("Expected the continued conversation to remain scoped to one selected session.")
        }
        guard reloadedStore.selectedAssistantMessage?.proposalStatus == "pending" else {
            throw FlowDataError.message("Expected the most recent assistant response to remain pending before mutation.")
        }
        guard reloadedStore.assistantMessageDisclosureSummaries.last?.contains("Provider: deterministic") == true else {
            throw FlowDataError.message("Expected follow-up disclosure state to remain attached to the selected assistant message state.")
        }

        reloadedStore.createAssistantSession(title: "Second chat")
        guard let secondSessionID = reloadedStore.selectedAssistantSessionID else {
            throw FlowDataError.message("Expected creating a second assistant session to keep that session selected.")
        }
        guard reloadedStore.assistantMessages.isEmpty else {
            throw FlowDataError.message("Expected a new assistant session to start with an empty message history.")
        }

        reloadedStore.assistantComposerText = "Remember the review rhythm."
        reloadedStore.sendAssistantMessage()
        try waitForAssistantSendCompletion(reloadedStore)

        guard reloadedStore.assistantMessages.map(\.role) == ["user", "assistant"] else {
            throw FlowDataError.message("Expected the second assistant session to maintain its own message history.")
        }
        guard reloadedStore.assistantMessages.allSatisfy({ $0.sessionID == secondSessionID }) else {
            throw FlowDataError.message("Expected the second assistant session to keep its messages scoped to itself.")
        }
        guard reloadedStore.assistantMessageDisclosureSummaries.contains(where: { $0.contains("Provider: deterministic") }) else {
            throw FlowDataError.message("Expected assistant disclosure summaries to stay attached to the current session state.")
        }

        reloadedStore.selectAssistantSession(id: firstSessionID)
        guard reloadedStore.assistantMessages.map(\.role) == ["user", "assistant", "user", "assistant"] else {
            throw FlowDataError.message("Expected switching sessions to restore the first session history.")
        }
        guard reloadedStore.selectedAssistantMessage?.proposalStatus == "pending" else {
            throw FlowDataError.message("Expected the first session's latest proposal to still be pending after switching back.")
        }

        reloadedStore.confirmSelectedAssistantProposal()
        guard reloadedStore.selectedAssistantMessage?.proposalStatus == "confirmed" else {
            throw FlowDataError.message("Expected confirmation visibility to update the selected assistant message.")
        }
        guard reloadedStore.selectedAssistantMessageDisclosureSummary?.contains("Provider: deterministic") == true else {
            throw FlowDataError.message("Expected confirmed message disclosure state to remain available after reload and switch back.")
        }

        reloadedStore.selectAssistantSession(id: secondSessionID)
        guard reloadedStore.selectedAssistantMessage?.proposalStatus == "pending" else {
            throw FlowDataError.message("Expected the second session's proposal to remain pending before dismissal.")
        }

        reloadedStore.dismissSelectedAssistantProposal()
        guard reloadedStore.selectedAssistantMessage?.proposalStatus == "dismissed" else {
            throw FlowDataError.message("Expected dismissal visibility to update the second session's assistant message.")
        }
        guard reloadedStore.assistantActionFeedback == "Dismissed assistant proposal." else {
            throw FlowDataError.message("Expected dismissal to leave visible assistant-local feedback.")
        }

        reloadedStore.undoLastAssistantMutation()
        guard reloadedStore.assistantActionFeedback?.localizedCaseInsensitiveContains("undid") == true else {
            throw FlowDataError.message("Expected undo to surface assistant-local feedback from the returned result string.")
        }
        guard reloadedStore.assistantMessages.isEmpty else {
            throw FlowDataError.message("Expected undo to roll back the dismissed assistant conversation in the selected session.")
        }

        reloadedStore.selectAssistantSession(id: firstSessionID)
        guard reloadedStore.assistantMessages.map(\.role) == ["user", "assistant", "user", "assistant"] else {
            throw FlowDataError.message("Expected undo in the second session to leave the first session conversation intact.")
        }
        guard reloadedStore.selectedAssistantMessage?.proposalStatus == "confirmed" else {
            throw FlowDataError.message("Expected the first session confirmation to survive undoing the second session mutation.")
        }
    }

    @MainActor
    private static func smokeTestSidecarWorkspaceStoreSessionReloadResumeAndContinuation() throws {
        let databaseURL = temporaryDatabaseURL()
        let repository = SidecarFlowRepository(
            fallback: LegacyFlowRepository(databaseURL: databaseURL),
            environment: [
                "FLOW_DB_PATH": databaseURL.path,
                "FLOW_AGENT_RUNTIME_PROVIDER": "deterministic"
            ]
        )

        let firstStore = WorkspaceStore(repository: repository)
        firstStore.refresh()
        firstStore.assistantComposerText = "Add review the launch checklist."
        firstStore.sendAssistantMessage()
        try waitForAssistantSendCompletion(firstStore)

        guard let firstSessionID = firstStore.selectedAssistantSessionID else {
            throw FlowDataError.message("Expected the sidecar-backed send to create a selected assistant session.")
        }
        guard firstStore.assistantMessages.map(\.role) == ["user", "assistant"] else {
            throw FlowDataError.message("Expected the sidecar-backed send to create a message pair in the selected session.")
        }
        guard firstStore.selectedAssistantMessageDisclosureSummary?.contains("Provider: deterministic") == true else {
            throw FlowDataError.message("Expected the sidecar-backed message to expose disclosure state through WorkspaceStore.")
        }

        let reloadedStore = WorkspaceStore(repository: SidecarFlowRepository(
            fallback: LegacyFlowRepository(databaseURL: databaseURL),
            environment: [
                "FLOW_DB_PATH": databaseURL.path,
                "FLOW_AGENT_RUNTIME_PROVIDER": "deterministic"
            ]
        ))
        reloadedStore.refresh()

        guard reloadedStore.selectedAssistantSessionID == firstSessionID else {
            throw FlowDataError.message("Expected the sidecar-backed assistant session selection to persist across repository reinstantiation.")
        }
        guard reloadedStore.assistantMessages.map(\.role) == ["user", "assistant"] else {
            throw FlowDataError.message("Expected reload to restore the persisted sidecar assistant history.")
        }
        guard reloadedStore.selectedAssistantMessageDisclosureSummary?.contains("Provider: deterministic") == true else {
            throw FlowDataError.message("Expected reload to preserve disclosure state on the selected assistant message.")
        }

        reloadedStore.assistantComposerText = "Add a follow-up next action."
        reloadedStore.sendAssistantMessage()
        try waitForAssistantSendCompletion(reloadedStore)

        guard reloadedStore.assistantMessages.map(\.role) == ["user", "assistant", "user", "assistant"] else {
            throw FlowDataError.message("Expected follow-up in the sidecar-backed session to remain in the same thread.")
        }
        guard reloadedStore.assistantMessages.allSatisfy({ $0.sessionID == firstSessionID }) else {
            throw FlowDataError.message("Expected follow-up in the sidecar-backed session to stay scoped to the selected session.")
        }
        guard reloadedStore.assistantMessages
            .filter({ $0.role == "assistant" })
            .map({ reloadedStore.assistantMessageDisclosureSummary(for: $0) })
            .allSatisfy({ $0.contains("Provider: deterministic") }) else {
            throw FlowDataError.message("Expected all persisted sidecar assistant messages to keep disclosure content attached.")
        }

        reloadedStore.createAssistantSession(title: "Second chat")
        guard let secondSessionID = reloadedStore.selectedAssistantSessionID else {
            throw FlowDataError.message("Expected a new sidecar-backed assistant session to remain selected.")
        }
        reloadedStore.assistantComposerText = "Remember the review rhythm."
        reloadedStore.sendAssistantMessage()
        try waitForAssistantSendCompletion(reloadedStore)
        guard reloadedStore.assistantMessages.allSatisfy({ $0.sessionID == secondSessionID }) else {
            throw FlowDataError.message("Expected the second sidecar-backed session to keep its own message history.")
        }

        reloadedStore.selectAssistantSession(id: firstSessionID)
        guard reloadedStore.assistantMessages.map(\.role) == ["user", "assistant", "user", "assistant"] else {
            throw FlowDataError.message("Expected switching back to restore the first sidecar-backed session history.")
        }
        guard reloadedStore.assistantMessageDisclosureSummaries.last?.contains("Provider: deterministic") == true else {
            throw FlowDataError.message("Expected the restored assistant message to keep view-state disclosure data attached.")
        }
    }

    private static func smokeTestAssistantUndoTargetsTheMutatedSession() throws {
        let repository = LegacyFlowRepository(databaseURL: temporaryDatabaseURL())

        let firstSession = try repository.createAssistantSession(title: "First chat")
        let firstMessage = try repository.sendAssistantMessage(
            sessionID: firstSession.id,
            prompt: "Add review the launch checklist.",
            planDate: "2026-03-08"
        )
        _ = try repository.confirmAssistantMessageProposal(messageID: firstMessage.id)

        let secondSession = try repository.createAssistantSession(title: "Second chat")
        _ = try repository.sendAssistantMessage(
            sessionID: secondSession.id,
            prompt: "Add review the release checklist.",
            planDate: "2026-03-08"
        )

        let undoMessage = try repository.undoLastAssistantMutation()
        guard undoMessage?.localizedCaseInsensitiveContains("undid") == true else {
            throw FlowDataError.message("Expected undo to return a visible assistant rollback message.")
        }

        let firstSessionMessages = try repository.loadAssistantMessages(sessionID: firstSession.id, limit: 10)
        guard firstSessionMessages.isEmpty else {
            throw FlowDataError.message("Expected undo to remove the conversation from the mutated session, not the latest session.")
        }

        let secondSessionMessages = try repository.loadAssistantMessages(sessionID: secondSession.id, limit: 10)
        guard secondSessionMessages.count == 2 else {
            throw FlowDataError.message("Expected the later session send to remain intact after undoing Session A.")
        }
    }

    @MainActor
    private static func smokeTestWorkspaceStoreRefreshDoesNotGateOnTurns() throws {
        let repository = AssistantWorkflowRepositorySpy(shouldThrowOnLoadTurns: true)
        let session = try repository.createAssistantSession(title: "Refresh test")
        _ = try repository.sendAssistantMessage(
            sessionID: session.id,
            prompt: "Add review the launch checklist.",
            planDate: "2026-03-08"
        )

        let store = WorkspaceStore(repository: repository)
        store.refresh()

        guard store.assistantSessions.map(\.id) == [session.id] else {
            throw FlowDataError.message("Expected session/message refresh to load even when assistant turns are unavailable.")
        }
        guard store.assistantMessages.map(\.role) == ["user", "assistant"] else {
            throw FlowDataError.message("Expected session/message refresh to populate the assistant conversation independently of turns.")
        }
        guard store.assistantTurns.isEmpty else {
            throw FlowDataError.message("Expected turn compatibility to fail open, leaving the primary assistant state lane intact.")
        }
        guard store.selectedAssistantSessionID == session.id else {
            throw FlowDataError.message("Expected the refreshed assistant session to remain selected.")
        }
    }

    @MainActor
    private static func smokeTestAssistantViewUsesRenderedChatFirstSurface() throws {
        let repository = LegacyFlowRepository(databaseURL: temporaryDatabaseURL())
        let store = WorkspaceStore(repository: repository)

        store.refresh()
        store.assistantComposerText = "Add review the launch checklist."
        store.sendAssistantMessage()
        try waitForAssistantSendCompletion(store)

        guard let firstSessionID = store.selectedAssistantSessionID else {
            throw FlowDataError.message("Expected the assistant surface to expose a selected session after send.")
        }

        var surfaceState = AssistantView.renderedSurfaceState(store: store)
        guard surfaceState.keepsOuterWorkspaceShell else {
            throw FlowDataError.message("Expected the Assistant workspace to stay inside the Flow workspace shell.")
        }
        guard surfaceState.usesChatGPTStyleLayout else {
            throw FlowDataError.message("Expected the Assistant internals to present a ChatGPT-style internal layout.")
        }
        guard surfaceState.usesFullHeightChatPane else {
            throw FlowDataError.message("Expected the Assistant chat pane to fill the available workspace height.")
        }
        guard surfaceState.hasConversationRail else {
            throw FlowDataError.message("Expected the Assistant surface to expose a conversation rail.")
        }
        guard surfaceState.hasMainTranscript else {
            throw FlowDataError.message("Expected the Assistant surface to expose a main transcript.")
        }
        guard surfaceState.hasBottomComposer else {
            throw FlowDataError.message("Expected the Assistant surface to expose a bottom composer.")
        }
        let projectRootURL = URL(fileURLWithPath: #filePath)
            .deletingLastPathComponent()
            .deletingLastPathComponent()
            .deletingLastPathComponent()
        let assistantSourceURL = projectRootURL.appendingPathComponent("Sources/FlowMacApp/UI/Assistant/AssistantView.swift")
        let assistantSource = try String(contentsOf: assistantSourceURL)
        let workspaceSourceURL = projectRootURL.appendingPathComponent("Sources/FlowMacApp/UI/Workspace/Workspaces.swift")
        let workspaceSource = try String(contentsOf: workspaceSourceURL)
        guard assistantSource.contains("WorkspaceShell(store: store, scrollsContent: false)") else {
            throw FlowDataError.message("Expected Assistant to opt out of the scrolling workspace shell so the chat surface can fill the viewport.")
        }
        guard workspaceSource.contains("scrollsContent: Bool = true") && workspaceSource.contains("maxHeight: .infinity") else {
            throw FlowDataError.message("Expected WorkspaceShell to support a non-scrolling full-height content mode for Assistant.")
        }
        guard assistantSource.contains(".frame(width: max(0, availableSize.width - 16), height: max(0, availableSize.height - 16), alignment: .topLeading)") else {
            throw FlowDataError.message("Expected the Assistant horizontal layout to receive a concrete full-height proposal so the chat list cannot collapse under its header.")
        }
        guard assistantSource.contains("AssistantConversationRail(store: store, availableHeight: max(0, availableSize.height - 16))") else {
            throw FlowDataError.message("Expected the Assistant conversation rail to receive the full available height before rendering session rows.")
        }
        guard assistantSource.contains("let availableHeight: CGFloat") else {
            throw FlowDataError.message("Expected the Assistant conversation rail to own an explicit height contract.")
        }
        guard assistantSource.contains(".frame(maxWidth: .infinity, minHeight: availableHeight, maxHeight: availableHeight, alignment: .topLeading)") else {
            throw FlowDataError.message("Expected the Assistant conversation rail card to fill its explicit height so the chat list cannot collapse under its header.")
        }
        guard assistantSource.contains(".frame(height: max(140, availableHeight - 78), alignment: .topLeading)") else {
            throw FlowDataError.message("Expected the Assistant conversation rail list to get an explicit visible height below the header.")
        }
        guard assistantSource.contains("expandsEditor: store.assistantMessages.isEmpty") else {
            throw FlowDataError.message("Expected empty chats to expand the composer editor across the main pane instead of showing a short fixed-height input.")
        }
        guard assistantSource.contains("maxHeight: expandsEditor ? .infinity : nil") else {
            throw FlowDataError.message("Expected the assistant composer editor to have an explicit expansion mode for empty chats.")
        }
        guard assistantSource.contains("AssistantTypingIndicatorBubble()") else {
            throw FlowDataError.message("Expected the pending assistant state to render as an iMessage-style animated typing bubble.")
        }
        guard assistantSource.contains("flowUserAccent") && assistantSource.contains("imessageAssistant") else {
            throw FlowDataError.message("Expected assistant message presentations to distinguish Flow-themed user bubbles and assistant bubble styles.")
        }
        guard assistantSource.contains("AssistantThinkingBubble()") == false else {
            throw FlowDataError.message("Expected the pending assistant state to avoid replacing the composer with a large Thinking panel.")
        }
        guard surfaceState.sessionTitles == [store.selectedAssistantSession?.title ?? ""] else {
            throw FlowDataError.message("Expected the rendered assistant surface to show one active chat in the session rail.")
        }
        guard surfaceState.selectedSessionTitle == store.selectedAssistantSession?.title else {
            throw FlowDataError.message("Expected the rendered assistant surface to show the selected chat title in the pane.")
        }
        guard surfaceState.selectedSessionMessageCount == 2 else {
            throw FlowDataError.message("Expected the rendered assistant surface to show the selected session message count.")
        }
        guard surfaceState.messageRoles == ["user", "assistant"] else {
            throw FlowDataError.message("Expected the rendered assistant surface to show the selected chat messages.")
        }
        guard surfaceState.selectedMessageHasProposal else {
            throw FlowDataError.message("Expected the rendered assistant surface to show a proposal card for the selected assistant reply.")
        }
        guard surfaceState.selectedMessageProposalStatus == "pending" else {
            throw FlowDataError.message("Expected the rendered assistant surface to show pending proposal status in the selected chat.")
        }
        guard surfaceState.selectedMessageDisclosureSummary?.contains("Provider: deterministic") == true else {
            throw FlowDataError.message("Expected the rendered assistant surface to show disclosure content for the selected assistant message.")
        }
        guard surfaceState.messagePresentations == [
            AssistantRenderedMessagePresentation(
                role: "user",
                alignment: "trailing",
                bubbleStyle: "flowUserAccent",
                textColorStyle: "light",
                textSelectionEnabled: true,
                showsProposalCard: false,
                showsProvenanceDisclosure: false
            ),
            AssistantRenderedMessagePresentation(
                role: "assistant",
                alignment: "leading",
                bubbleStyle: "imessageAssistant",
                textColorStyle: "primary",
                textSelectionEnabled: true,
                showsProposalCard: true,
                showsProvenanceDisclosure: true
            )
        ] else {
            throw FlowDataError.message("Expected the rendered assistant surface to reflect chat-style role alignment, copyable message text, and assistant-only proposal/provenance attachment.")
        }
        guard assistantSource.contains(".textSelection(.enabled)") else {
            throw FlowDataError.message("Expected assistant message text to enable system text selection so chat messages can be copied.")
        }
        guard assistantSource.contains("FlowTheme.warmAccent") else {
            throw FlowDataError.message("Expected user message bubbles to use the Flow theme accent rather than a hard-coded iMessage blue.")
        }
        guard surfaceState.showsNewChatAction else {
            throw FlowDataError.message("Expected the rendered assistant surface to expose the New Chat action.")
        }
        guard surfaceState.showsUndoAction else {
            throw FlowDataError.message("Expected the rendered assistant surface to expose the undo action.")
        }
        guard surfaceState.showsLegacyTurnDrivenSurface == false else {
            throw FlowDataError.message("Expected the Assistant surface to stop reading like a legacy turn-driven dashboard.")
        }
        guard surfaceState.showsFlowDashboardHeader == false else {
            throw FlowDataError.message("Expected the Assistant surface to stop rendering the Flow dashboard header chrome.")
        }
        guard surfaceState.sessionRailIsDisabled == false else {
            throw FlowDataError.message("Expected the rendered assistant surface to leave the session rail enabled while idle.")
        }
        guard surfaceState.sessionRailLockLabel == nil else {
            throw FlowDataError.message("Expected no rail lock label while the assistant is idle.")
        }
        guard surfaceState.showsStopAction == false else {
            throw FlowDataError.message("Expected the stop action to stay hidden while the assistant is idle.")
        }
        guard surfaceState.primaryComposerActionLabel == "Send" else {
            throw FlowDataError.message("Expected the composer primary action to send messages while idle.")
        }

        store.assistantComposerText = "Thinking about the next step."
        store.assistantSendPending = true
        surfaceState = AssistantView.renderedSurfaceState(store: store)
        guard surfaceState.showsTypingIndicator else {
            throw FlowDataError.message("Expected the rendered assistant surface to expose the iMessage-style typing indicator while the assistant is working.")
        }
        guard surfaceState.typingIndicatorText == "..." else {
            throw FlowDataError.message("Expected the rendered assistant surface to expose three typing dots while the assistant is working.")
        }
        guard surfaceState.typingIndicatorDotCount == 3 else {
            throw FlowDataError.message("Expected the assistant typing indicator to use three animated dots.")
        }
        guard surfaceState.typingIndicatorAnimates else {
            throw FlowDataError.message("Expected the assistant typing indicator dots to animate.")
        }
        guard assistantSource.contains(".animation(.easeInOut(duration: 0.2), value: phase)") else {
            throw FlowDataError.message("Expected the assistant typing indicator to animate dot phase changes.")
        }
        guard surfaceState.composerIsDisabled == false else {
            throw FlowDataError.message("Expected the composer to remain editable while the typing indicator is visible so the user can queue a follow-up.")
        }
        guard surfaceState.showsStopAction else {
            throw FlowDataError.message("Expected the composer primary action to become Stop while the assistant is working.")
        }
        guard surfaceState.primaryComposerActionLabel == "Stop" else {
            throw FlowDataError.message("Expected the pending composer primary action label to read Stop.")
        }
        guard assistantSource.contains("Label(\"Stop\", systemImage: \"stop.fill\")") else {
            throw FlowDataError.message("Expected the pending composer button to render as a stop control.")
        }
        guard assistantSource.contains("store.stopAssistantMessage()") else {
            throw FlowDataError.message("Expected the Assistant composer to call the store stop action while generation is pending.")
        }
        guard surfaceState.showsComposerInInteractionSlot else {
            throw FlowDataError.message("Expected the composer to remain in the same interaction slot while the typing indicator is visible.")
        }
        guard surfaceState.sessionRailIsDisabled else {
            throw FlowDataError.message("Expected the session rail to be disabled while the typing indicator is visible.")
        }
        guard surfaceState.sessionRailLockLabel == nil else {
            throw FlowDataError.message("Expected the Assistant surface to avoid extra pending-lock copy outside the typing indicator slot.")
        }
        guard surfaceState.showsRailPendingCopy == false else {
            throw FlowDataError.message("Expected the Assistant surface to suppress extra rail pending copy while the typing indicator is visible.")
        }
        store.assistantSendPending = false

        store.createAssistantSession(title: "Second chat")
        guard store.selectedAssistantSessionID != nil else {
            throw FlowDataError.message("Expected the rendered assistant surface to keep a selected session after creating a new chat.")
        }

        surfaceState = AssistantView.renderedSurfaceState(store: store)
        guard surfaceState.sessionTitles.contains("Second chat") else {
            throw FlowDataError.message("Expected the rendered assistant session rail to include the new chat row.")
        }
        guard surfaceState.selectedSessionTitle == "Second chat" else {
            throw FlowDataError.message("Expected the rendered assistant pane to switch to the new session.")
        }
        guard surfaceState.messageRoles.isEmpty else {
            throw FlowDataError.message("Expected the new chat surface state to start with an empty message pane.")
        }
        guard surfaceState.selectedMessageDisclosureSummary == nil else {
            throw FlowDataError.message("Expected an empty chat to have no selected disclosure summary.")
        }

        store.selectAssistantSession(id: firstSessionID)
        surfaceState = AssistantView.renderedSurfaceState(store: store)
        guard surfaceState.selectedSessionTitle == store.selectedAssistantSession?.title else {
            throw FlowDataError.message("Expected switching back to restore the first rendered session.")
        }
        guard surfaceState.messageRoles == ["user", "assistant"] else {
            throw FlowDataError.message("Expected switching back to restore the first message pane history.")
        }
        guard surfaceState.selectedMessageDisclosureSummary?.contains("Provider: deterministic") == true else {
            throw FlowDataError.message("Expected switching back to preserve disclosure content in the visible message pane.")
        }

        store.confirmSelectedAssistantProposal()
        surfaceState = AssistantView.renderedSurfaceState(store: store)
        guard surfaceState.selectedMessageProposalStatus == "confirmed" else {
            throw FlowDataError.message("Expected the rendered assistant surface to reflect confirmed proposal state.")
        }
        guard surfaceState.selectedMessageHasProposal else {
            throw FlowDataError.message("Expected the rendered assistant surface to keep the proposal card visible after confirmation.")
        }

        store.undoLastAssistantMutation()
        surfaceState = AssistantView.renderedSurfaceState(store: store)
        guard surfaceState.assistantActionFeedback?.localizedCaseInsensitiveContains("undid") == true else {
            throw FlowDataError.message("Expected the rendered assistant surface to expose undo feedback after rollback.")
        }
    }

    @MainActor
    private static func smokeTestAssistantSendDoesNotBlockMainActor() throws {
        let repository = AssistantWorkflowRepositorySpy(sendDelay: 0.45)
        let store = WorkspaceStore(repository: repository)

        store.refresh()
        store.createAssistantSession(title: "Pending send")
        store.assistantComposerText = "Plan without freezing the app."
        store.sendAssistantMessage()

        let startedAt = Date()
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.05) {
            store.searchText = "main actor stayed responsive"
        }
        RunLoop.current.run(mode: .default, before: Date(timeIntervalSinceNow: 0.2))

        guard store.searchText == "main actor stayed responsive" else {
            throw FlowDataError.message("Expected unrelated app state to update while the assistant send remains pending.")
        }
        guard store.assistantSendPending else {
            throw FlowDataError.message("Expected the assistant send to still be pending while other app components remain operable.")
        }
        guard store.assistantComposerText.isEmpty else {
            throw FlowDataError.message("Expected the composer to clear immediately after the user clicks Send.")
        }
        guard store.assistantMessages.last?.role == "user",
              store.assistantMessages.last?.content == "Plan without freezing the app." else {
            throw FlowDataError.message("Expected the user's sent message to appear in the transcript while assistant generation is still pending.")
        }
        guard Date().timeIntervalSince(startedAt) < 0.35 else {
            throw FlowDataError.message("Expected the main actor to avoid blocking on the assistant sidecar call.")
        }

        store.assistantComposerText = "Queue this follow-up after the current answer."
        guard store.assistantSendPending else {
            throw FlowDataError.message("Expected typing a follow-up to keep the active assistant send pending.")
        }
        guard store.assistantComposerText == "Queue this follow-up after the current answer." else {
            throw FlowDataError.message("Expected typed follow-up text to remain editable while the current assistant turn is still running.")
        }

        try waitForAssistantSendCompletion(store, timeout: 2.0)
        guard repository.sentMessagePrompts == [
            "Plan without freezing the app.",
            "Queue this follow-up after the current answer."
        ] else {
            throw FlowDataError.message("Expected the assistant to continue with queued follow-up messages after the current response finishes.")
        }
        guard store.assistantMessages.map(\.role) == ["user", "assistant", "user", "assistant"] else {
            throw FlowDataError.message("Expected the final transcript to contain both user turns and assistant responses in order.")
        }
        guard store.assistantComposerText.isEmpty else {
            throw FlowDataError.message("Expected the pending follow-up draft to clear once it is picked up for the queued assistant turn.")
        }

        let stoppedRepository = AssistantWorkflowRepositorySpy(sendDelay: 0.45)
        let stoppedStore = WorkspaceStore(repository: stoppedRepository)
        stoppedStore.refresh()
        stoppedStore.createAssistantSession(title: "Stop pending send")
        stoppedStore.assistantComposerText = "Stop this assistant turn."
        stoppedStore.sendAssistantMessage()
        RunLoop.current.run(mode: .default, before: Date(timeIntervalSinceNow: 0.1))
        stoppedStore.assistantComposerText = "Keep this draft after stop."
        stoppedStore.stopAssistantMessage()
        guard stoppedStore.assistantSendPending == false else {
            throw FlowDataError.message("Expected Stop to clear the assistant pending state immediately.")
        }
        guard stoppedStore.assistantComposerText == "Keep this draft after stop." else {
            throw FlowDataError.message("Expected Stop to preserve the editable follow-up draft for the user.")
        }
        guard stoppedStore.assistantActionFeedback?.localizedCaseInsensitiveContains("stopped") == true else {
            throw FlowDataError.message("Expected Stop to surface local stopped feedback.")
        }
        RunLoop.current.run(mode: .default, before: Date(timeIntervalSinceNow: 0.6))
        guard stoppedStore.assistantMessages.map(\.role) == ["user"] else {
            throw FlowDataError.message("Expected a stopped assistant response to ignore stale completion and avoid appending an assistant bubble.")
        }
    }

    @MainActor
    private static func smokeTestAssistantProposalActionFailuresSurfaceLocalFeedback() throws {
        let repository = AssistantWorkflowRepositorySpy(shouldThrowOnConfirmAssistantMessageProposal: true, shouldThrowOnDismissAssistantMessageProposal: true)
        let store = WorkspaceStore(repository: repository)

        store.refresh()
        store.assistantComposerText = "Add review the launch checklist."
        store.sendAssistantMessage()
        try waitForAssistantSendCompletion(store)

        store.confirmSelectedAssistantProposal()
        guard store.assistantActionFeedback?.localizedCaseInsensitiveContains("Could not confirm assistant proposal") == true else {
            throw FlowDataError.message("Expected confirm failures to surface assistant-local feedback.")
        }

        store.assistantActionFeedback = nil
        store.dismissSelectedAssistantProposal()
        guard store.assistantActionFeedback?.localizedCaseInsensitiveContains("Could not dismiss assistant proposal") == true else {
            throw FlowDataError.message("Expected dismiss failures to surface assistant-local feedback.")
        }
    }

    @MainActor
    private static func smokeTestAssistantWorkflowServiceDelegatesSessionMessageAPI() throws {
        let repository = AssistantWorkflowRepositorySpy()
        let service = AssistantWorkflowService(repository: repository, planDateProvider: { "2026-03-08" })

        let session = try service.createSession(title: "Weekly review")
        let message = try service.sendMessage(sessionID: session.id, prompt: "Plan my day")

        guard repository.createdSessionTitles == ["Weekly review"] else {
            throw FlowDataError.message("Expected the service to create sessions through the repository boundary.")
        }
        guard repository.sentMessagePrompts == ["Plan my day"] else {
            throw FlowDataError.message("Expected the service to send assistant messages through the repository boundary.")
        }
        guard repository.sentMessagePlanDates == ["2026-03-08"] else {
            throw FlowDataError.message("Expected the service to use the injected plan date for assistant sends.")
        }

        _ = try service.confirmMessage(messageID: message.id)
        do {
            try service.dismissMessage(messageID: message.id)
            throw FlowDataError.message("Expected a confirmed assistant proposal to reject dismissal.")
        } catch {
            guard String(describing: error).localizedCaseInsensitiveContains("pending") else {
                throw error
            }
        }
        _ = try service.undoLastMutation()

        guard repository.confirmedMessageIDs == [message.id] else {
            throw FlowDataError.message("Expected the service to confirm assistant proposals by message id.")
        }
        guard repository.dismissedMessageIDs.isEmpty else {
            throw FlowDataError.message("Expected the service to block dismissal after confirmation.")
        }
        guard repository.undoCallCount == 1 else {
            throw FlowDataError.message("Expected the service to keep undo discoverable.")
        }
    }

    private static func temporaryDatabaseURL() -> URL {
        URL(fileURLWithPath: NSTemporaryDirectory())
            .appendingPathComponent(UUID().uuidString)
            .appendingPathExtension("sqlite")
    }

    @MainActor
    private static func waitForAssistantSendCompletion(_ store: WorkspaceStore, timeout: TimeInterval = 1.0) throws {
        let deadline = Date().addingTimeInterval(timeout)
        while store.assistantSendPending {
            if Date() >= deadline {
                throw FlowDataError.message("Timed out waiting for the assistant send task to complete.")
            }
            RunLoop.current.run(mode: .default, before: Date(timeIntervalSinceNow: 0.01))
        }
    }

}

private enum AssistantMessageRole {
    case user
    case assistant
}

private enum AssistantProposalStatus {
    case none
    case pending
    case confirmed
    case dismissed
}

private enum AssistantProvider {
    case unknown
    case codex
}

private struct AssistantAuditStepSpec {
    let stage: String
    let summary: String
}

private struct AssistantSessionSpec: Identifiable {
    let id: String
    var title: String
    var createdAt: Int
    var updatedAt: Int
}

private struct AssistantMessageSpec: Identifiable {
    let id: String
    let sessionID: String
    let role: AssistantMessageRole
    var content: String
    var proposalStatus: AssistantProposalStatus
    var proposalTarget: String?
    var provider: AssistantProvider
    var auditSteps: [AssistantAuditStepSpec]
    let createdAt: Int
}

private final class AssistantSessionTimelineHarness {
    private var nextID = 1
    private var clock = 1
    private var sessions: [AssistantSessionSpec] = []
    private var messages: [AssistantMessageSpec] = []
    private(set) var selectedSessionID: String?

    func createSession(title: String) -> String {
        let id = makeID(prefix: "session")
        let timestamp = tick()
        sessions.append(
            AssistantSessionSpec(id: id, title: title, createdAt: timestamp, updatedAt: timestamp)
        )
        selectedSessionID = id
        return id
    }

    @discardableResult
    func sendMessage(
        sessionID: String?,
        role: AssistantMessageRole,
        content: String,
        proposalStatus: AssistantProposalStatus = .none,
        proposalTarget: String? = nil,
        provider: AssistantProvider = .unknown,
        auditSteps: [AssistantAuditStepSpec] = []
    ) -> AssistantMessageSpec {
        let targetSessionID = sessionID ?? selectedSessionID ?? createSession(title: content)
        selectedSessionID = targetSessionID
        touchSession(id: targetSessionID)

        let message = AssistantMessageSpec(
            id: makeID(prefix: "message"),
            sessionID: targetSessionID,
            role: role,
            content: content,
            proposalStatus: proposalStatus,
            proposalTarget: proposalTarget,
            provider: provider,
            auditSteps: auditSteps,
            createdAt: tick()
        )
        messages.append(message)
        return message
    }

    func listSessions() -> [AssistantSessionSpec] {
        sessions.sorted {
            if $0.updatedAt == $1.updatedAt { return $0.createdAt > $1.createdAt }
            return $0.updatedAt > $1.updatedAt
        }
    }

    func loadMessages(sessionID: String) -> [AssistantMessageSpec] {
        messages
            .filter { $0.sessionID == sessionID }
            .sorted { $0.createdAt < $1.createdAt }
    }

    func selectSession(_ sessionID: String) {
        selectedSessionID = sessionID
        touchSession(id: sessionID)
    }

    func message(id: String) -> AssistantMessageSpec? {
        messages.first(where: { $0.id == id })
    }

    func confirmProposal(messageID: String) {
        mutateProposal(messageID: messageID, status: .confirmed)
    }

    func dismissProposal(messageID: String) {
        mutateProposal(messageID: messageID, status: .dismissed)
    }

    private func mutateProposal(messageID: String, status: AssistantProposalStatus) {
        guard let index = messages.firstIndex(where: { $0.id == messageID }) else { return }
        messages[index].proposalStatus = status
        touchSession(id: messages[index].sessionID)
    }

    private func touchSession(id: String) {
        guard let index = sessions.firstIndex(where: { $0.id == id }) else { return }
        sessions[index].updatedAt = tick()
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

private final class AssistantWorkflowRepositorySpy: FlowRepository {
    private var nextTurnIndex = 1
    private var turns: [FlowAssistantTurn] = []
    private let assistantBridge = AssistantSessionMessageBridge()
    private let shouldThrowOnLoadTurns: Bool
    private let shouldThrowOnConfirmAssistantMessageProposal: Bool
    private let shouldThrowOnDismissAssistantMessageProposal: Bool
    private let sendDelay: TimeInterval
    private(set) var sentPrompts: [String] = []
    private(set) var createdSessionTitles: [String] = []
    private(set) var sentMessagePrompts: [String] = []
    private(set) var sentMessagePlanDates: [String] = []
    private(set) var confirmedMessageIDs: [String] = []
    private(set) var dismissedMessageIDs: [String] = []
    private(set) var confirmedTurnIDs: [String] = []
    private(set) var dismissedTurnIDs: [String] = []
    private(set) var undoCallCount = 0
    private var assistantMessageStatuses: [String: AssistantProposalStatus] = [:]

    init(
        shouldThrowOnLoadTurns: Bool = false,
        shouldThrowOnConfirmAssistantMessageProposal: Bool = false,
        shouldThrowOnDismissAssistantMessageProposal: Bool = false,
        sendDelay: TimeInterval = 0
    ) {
        self.shouldThrowOnLoadTurns = shouldThrowOnLoadTurns
        self.shouldThrowOnConfirmAssistantMessageProposal = shouldThrowOnConfirmAssistantMessageProposal
        self.shouldThrowOnDismissAssistantMessageProposal = shouldThrowOnDismissAssistantMessageProposal
        self.sendDelay = sendDelay
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
        assistantBridge.loadSessions(limit: limit)
    }

    func loadAssistantMessages(sessionID: String, limit: Int) throws -> [FlowAssistantMessage] {
        assistantBridge.loadMessages(sessionID: sessionID, limit: limit)
    }

    func createAssistantSession(title: String) throws -> FlowAssistantSession {
        createdSessionTitles.append(title)
        return assistantBridge.createSession(title: title)
    }

    func sendAssistantMessage(sessionID: String, prompt: String, planDate: String) throws -> FlowAssistantMessage {
        if sendDelay > 0 {
            Thread.sleep(forTimeInterval: sendDelay)
        }
        sentMessagePrompts.append(prompt)
        sentMessagePlanDates.append(planDate)
        let message = try assistantBridge.sendMessage(
            sessionID: sessionID,
            prompt: prompt,
            planDate: planDate,
            routeTurn: sendAssistantPrompt(_:planDate:)
        )
        assistantMessageStatuses[message.id] = proposalStatus(from: message.proposalStatus)
        return message
    }

    func confirmAssistantMessageProposal(messageID: String) throws -> String {
        if shouldThrowOnConfirmAssistantMessageProposal {
            throw FlowDataError.message("Assistant proposal confirmation failed.")
        }
        confirmedMessageIDs.append(messageID)
        assistantMessageStatuses[messageID] = .confirmed
        return try assistantBridge.confirm(messageID: messageID, backingTurn: confirmAssistantProposal(turnID:))
    }

    func dismissAssistantMessageProposal(messageID: String) throws {
        if shouldThrowOnDismissAssistantMessageProposal {
            throw FlowDataError.message("Assistant proposal dismissal failed.")
        }
        if assistantMessageStatuses[messageID] == .confirmed {
            throw FlowDataError.message("Assistant message proposal is not pending.")
        }
        dismissedMessageIDs.append(messageID)
        assistantMessageStatuses[messageID] = .dismissed
        try assistantBridge.dismiss(messageID: messageID, backingTurn: dismissAssistantProposal(turnID:))
    }

    func sendAssistantPrompt(_ prompt: String, planDate: String) throws -> FlowAssistantTurn {
        sentPrompts.append(prompt)
        let turn = makeTurn(prompt: prompt)
        turns.insert(turn, at: 0)
        return turn
    }

    func proposeProjectNextActionReview(projectID: String) throws -> FlowAssistantTurn {
        let turn = makeTurn(prompt: "Review project \(projectID)")
        turns.insert(turn, at: 0)
        return turn
    }

    func loadAssistantTurns(limit: Int) throws -> [FlowAssistantTurn] {
        if shouldThrowOnLoadTurns {
            throw FlowDataError.message("Legacy turn compatibility is unavailable.")
        }
        return Array(turns.prefix(limit))
    }

    func confirmAssistantProposal(turnID: String) throws -> String {
        confirmedTurnIDs.append(turnID)
        return "Confirmed \(turnID)"
    }

    func dismissAssistantProposal(turnID: String) throws {
        dismissedTurnIDs.append(turnID)
    }

    func undoLastAssistantMutation() throws -> String? {
        undoCallCount += 1
        return "Undid assistant write"
    }

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
            updatedAtLabel: "Now",
            whyItMatters: "Stub"
        )
    }

    func updateMemoryRecord(id: String, value: String) throws {}

    func setMemoryRecordEnabled(id: String, enabled: Bool) throws {}

    func deleteMemoryRecord(id: String) throws {}

    func loadDailyPlanState(planDate: String) throws -> FlowDailyPlanState { .empty(planDate: planDate) }

    func saveDailyPlan(planDate: String, topItemIDs: [String], bonusItemIDs: [String]) throws {}

    func loadWeeklyReviewPackage(referenceDate: Date) throws -> FlowWeeklyReviewPackage { .empty }

    func applyWeeklyReviewActions(actionIDs: [String], referenceDate: Date) throws {}

    func loadNotificationPolicy() throws -> FlowNotificationPolicyState { .empty }

    func updateNotificationPermissionStatus(_ status: String) throws {}

    func markTaskDone(id: String) throws {}

    func archiveTask(id: String) throws {}

    private func proposalStatus(from value: String) -> AssistantProposalStatus {
        switch value {
        case "pending":
            return .pending
        case "confirmed":
            return .confirmed
        case "dismissed":
            return .dismissed
        default:
            return .none
        }
    }

    private func makeTurn(prompt: String) -> FlowAssistantTurn {
        let turnID = "turn-\(nextTurnIndex)"
        nextTurnIndex += 1
        return FlowAssistantTurn(
            id: turnID,
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
                .init(id: "\(turnID)-provider", stage: "provider", status: "ok", summary: "Provider completed the request.", payload: ["provider": "deterministic"]),
                .init(id: "\(turnID)-validation", stage: "validation", status: "ok", summary: "Proposal is ready for confirmation.", payload: [:])
            ],
            provider: "deterministic",
            providerStatus: "success",
            providerDetail: "Deterministic provider completed the request.",
            providerModel: nil,
            createdAtLabel: "Now"
        )
    }
}

private final class AssistantViewStubRepository: FlowRepository {
    func loadWorkspaceSnapshot() throws -> WorkspaceSnapshot { SampleWorkspaceFactory.makeSnapshot() }
    func capture(title: String) throws -> FlowTask { SampleWorkspaceFactory.makeSnapshot().inboxItems.first! }
    func clarifyCapture(id: String, title: String, destination: ClarifyDestination, projectTitle: String?) throws {}
    func rejectCapture(id: String) throws {}
    func loadAssistantSessions(limit: Int) throws -> [FlowAssistantSession] { [] }
    func loadAssistantMessages(sessionID: String, limit: Int) throws -> [FlowAssistantMessage] { [] }
    func createAssistantSession(title: String) throws -> FlowAssistantSession {
        FlowAssistantSession(id: "stub-session", title: title, latestPreview: "", messageCount: 0, createdAtLabel: "Now", updatedAtLabel: "Now")
    }
    func sendAssistantMessage(sessionID: String, prompt: String, planDate: String) throws -> FlowAssistantMessage {
        FlowAssistantMessage(
            id: "stub-message",
            sessionID: sessionID,
            role: "assistant",
            content: prompt,
            route: "general",
            proposal: nil,
            proposalStatus: "none",
            auditSteps: [],
            provider: "unknown",
            providerStatus: "success",
            providerDetail: "Stub",
            providerModel: nil,
            sourceTurnID: nil,
            createdAtLabel: "Now",
            updatedAtLabel: "Now"
        )
    }
    func confirmAssistantMessageProposal(messageID: String) throws -> String { "Confirmed" }
    func dismissAssistantMessageProposal(messageID: String) throws {}
    func sendAssistantPrompt(_ prompt: String, planDate: String) throws -> FlowAssistantTurn { SampleWorkspaceFactory.makeSnapshot().assistantSuggestions.isEmpty ? FlowAssistantTurn(id: "stub", prompt: prompt, response: "Stub", route: "general", proposal: nil, proposalStatus: "none", auditSteps: [], createdAtLabel: "Now") : FlowAssistantTurn(id: "stub", prompt: prompt, response: "Stub", route: "general", proposal: nil, proposalStatus: "none", auditSteps: [], createdAtLabel: "Now") }
    func proposeProjectNextActionReview(projectID: String) throws -> FlowAssistantTurn { FlowAssistantTurn(id: "stub-review", prompt: "Review", response: "Stub", route: "project_health", proposal: nil, proposalStatus: "none", auditSteps: [], createdAtLabel: "Now") }
    func loadAssistantTurns(limit: Int) throws -> [FlowAssistantTurn] { [] }
    func confirmAssistantProposal(turnID: String) throws -> String { "Confirmed" }
    func dismissAssistantProposal(turnID: String) throws {}
    func undoLastAssistantMutation() throws -> String? { nil }
    func listMemoryRecords(query: String?, includeDisabled: Bool) throws -> [FlowMemoryRecord] { [] }
    func createMemoryRecord(kind: String, scope: String, value: String, source: String, confidence: Double, scopeRef: String?) throws -> FlowMemoryRecord {
        FlowMemoryRecord(id: "stub-memory", kind: kind, scope: scope, scopeRef: scopeRef, value: value, source: source, confidence: confidence, enabled: true, updatedAtLabel: "Now", whyItMatters: "Stub")
    }
    func updateMemoryRecord(id: String, value: String) throws {}
    func setMemoryRecordEnabled(id: String, enabled: Bool) throws {}
    func deleteMemoryRecord(id: String) throws {}
    func loadDailyPlanState(planDate: String) throws -> FlowDailyPlanState { .empty(planDate: planDate) }
    func saveDailyPlan(planDate: String, topItemIDs: [String], bonusItemIDs: [String]) throws {}
    func loadWeeklyReviewPackage(referenceDate: Date) throws -> FlowWeeklyReviewPackage { .empty }
    func applyWeeklyReviewActions(actionIDs: [String], referenceDate: Date) throws {}
    func loadNotificationPolicy() throws -> FlowNotificationPolicyState { .empty }
    func updateNotificationPermissionStatus(_ status: String) throws {}
    func markTaskDone(id: String) throws {}
    func archiveTask(id: String) throws {}
}

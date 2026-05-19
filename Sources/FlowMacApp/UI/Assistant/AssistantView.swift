import SwiftUI

struct AssistantView: View {
    @ObservedObject var store: WorkspaceStore

    var body: some View {
        WorkspaceShell(store: store, scrollsContent: false) {
            GeometryReader { geometry in
                AssistantChatShell(store: store, availableSize: geometry.size)
                    .frame(width: geometry.size.width, height: geometry.size.height, alignment: .topLeading)
            }
        }
    }

    private func sessionRail(maxHeight: CGFloat) -> some View {
        SurfaceCard(
            title: "Chats",
            subtitle: store.assistantSendPending ? "Assistant is typing. Session switching is locked." : "Switch sessions or start a new conversation",
            accent: FlowTheme.coolAccent
        ) {
            VStack(alignment: .leading, spacing: 12) {
                HStack {
                    Text("Session Rail")
                        .font(.system(size: 11, weight: .semibold))
                        .foregroundStyle(FlowTheme.textSecondary)

                    Spacer()

                    Button {
                        store.createAssistantSession()
                    } label: {
                        Label("New Chat", systemImage: "plus")
                    }
                    .buttonStyle(.borderedProminent)
                    .tint(FlowTheme.coolAccent)
                    .disabled(store.assistantSendPending)
                }

                ScrollView(.vertical) {
                    VStack(spacing: 10) {
                        if store.assistantSessions.isEmpty {
                            EmptyStateCard(
                                title: "No chats yet",
                                detail: "Start a new assistant session or use one of the example prompts in the composer."
                            )
                        } else {
                            VStack(spacing: 10) {
                                ForEach(store.assistantSessions) { session in
                                    Button {
                                        store.selectAssistantSession(id: session.id)
                                    } label: {
                                        VStack(alignment: .leading, spacing: 8) {
                                            HStack(alignment: .firstTextBaseline, spacing: 8) {
                                                Text(session.title)
                                                    .font(.system(size: 13, weight: .semibold))
                                                    .foregroundStyle(FlowTheme.textPrimary)
                                                    .multilineTextAlignment(.leading)
                                                Spacer(minLength: 8)
                                                StatusPill(
                                                    title: session.messageCount == 0 ? "Empty" : "\(session.messageCount) msg",
                                                    accent: session.id == store.selectedAssistantSession?.id ? FlowTheme.coolAccent : FlowTheme.surfaceRaised
                                                )
                                            }

                                            Text(session.latestPreview.isEmpty ? "No preview yet" : session.latestPreview)
                                                .font(.system(size: 12, weight: .medium))
                                                .foregroundStyle(FlowTheme.textSecondary)
                                                .lineLimit(2)

                                            HStack {
                                                Text(session.updatedAtLabel)
                                                    .font(.system(size: 11, weight: .medium))
                                                    .foregroundStyle(FlowTheme.textMuted)
                                                Spacer()
                                                Text(session.createdAtLabel)
                                                    .font(.system(size: 11, weight: .medium))
                                                    .foregroundStyle(FlowTheme.textMuted)
                                            }
                                        }
                                        .frame(maxWidth: .infinity, alignment: .leading)
                                        .padding(14)
                                        .background(
                                            RoundedRectangle(cornerRadius: 18, style: .continuous)
                                                .fill(sessionBackground(for: session))
                                                .overlay(
                                                    RoundedRectangle(cornerRadius: 18, style: .continuous)
                                                        .stroke(session.id == store.selectedAssistantSession?.id ? FlowTheme.coolAccent.opacity(0.5) : FlowTheme.strokeStrong, lineWidth: 1)
                                                )
                                        )
                                    }
                                    .buttonStyle(.plain)
                                    .disabled(store.assistantSendPending)
                                    .opacity(store.assistantSendPending ? 0.72 : 1)
                                }
                            }
                        }
                    }
                    .padding(.trailing, 2)
                }
                .frame(maxHeight: maxHeight, alignment: .top)
            }
        }
    }

    private func conversationPane(messageScrollHeight: CGFloat) -> some View {
        SurfaceCard(
            title: selectedSessionTitle,
            subtitle: selectedSessionSubtitle,
            accent: FlowTheme.warmAccent
        ) {
            VStack(alignment: .leading, spacing: 16) {
                if let feedback = store.assistantActionFeedback, feedback.isEmpty == false {
                    HStack(alignment: .top, spacing: 8) {
                        Image(systemName: "info.circle.fill")
                            .font(.system(size: 13, weight: .semibold))
                            .foregroundStyle(FlowTheme.tealAccent)
                        Text(feedback)
                            .font(.system(size: 12, weight: .medium))
                            .foregroundStyle(FlowTheme.textSecondary)
                            .fixedSize(horizontal: false, vertical: true)
                    }
                    .padding(12)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .background(
                        RoundedRectangle(cornerRadius: 16, style: .continuous)
                            .fill(FlowTheme.sidebar.opacity(0.78))
                            .overlay(
                                RoundedRectangle(cornerRadius: 16, style: .continuous)
                                    .stroke(FlowTheme.strokeStrong, lineWidth: 1)
                            )
                    )
                }

                ScrollView(.vertical) {
                    VStack(spacing: 12) {
                        if store.assistantMessages.isEmpty {
                            EmptyStateCard(
                                title: "Start a chat",
                                detail: "Pick a session or begin with an example prompt. The assistant stays on the session/message lane, not the legacy turn inspector."
                            )

                            AssistantExamplePromptGrid(
                                prompts: assistantEmptyStateExamples,
                                onPick: { store.assistantComposerText = $0 }
                            )
                        } else {
                            VStack(spacing: 12) {
                                ForEach(store.assistantMessages) { message in
                                    AssistantMessageBubble(
                                        message: message,
                                        isSelected: store.selectedAssistantMessage?.id == message.id,
                                        isActionPending: store.assistantProposalActionPending,
                                        onSelect: {
                                            store.selectAssistantMessage(id: message.id)
                                        },
                                        onConfirm: message.role == "assistant" && message.proposalStatus == "pending" ? {
                                            store.selectAssistantMessage(id: message.id)
                                            store.confirmSelectedAssistantProposal()
                                        } : nil,
                                        onDismiss: message.role == "assistant" && message.proposalStatus == "pending" ? {
                                            store.selectAssistantMessage(id: message.id)
                                            store.dismissSelectedAssistantProposal()
                                        } : nil
                                    )
                                }
                            }
                        }
                    }
                    .padding(.trailing, 2)
                }
                .frame(maxHeight: messageScrollHeight, alignment: .top)

                AssistantComposerCard(
                    composerText: $store.assistantComposerText,
                    isSending: store.assistantSendPending,
                    statusMessage: store.assistantActionFeedback,
                    onNewChat: {
                        store.createAssistantSession()
                    },
                    onUndo: {
                        store.undoLastAssistantMutation()
                    },
                    onSend: {
                        store.sendAssistantMessage()
                    },
                    onStop: {
                        store.stopAssistantMessage()
                    }
                )
            }
        }
    }

    private var selectedSessionTitle: String {
        store.selectedAssistantSession?.title ?? "Chat"
    }

    private var selectedSessionSubtitle: String {
        if let session = store.selectedAssistantSession {
            let preview = session.latestPreview.isEmpty ? "No preview yet" : session.latestPreview
            return "\(session.messageCount) messages - \(preview)"
        }

        return "Chat-first assistant workspace"
    }

    private var pendingProposalCount: Int {
        store.assistantMessages.filter { $0.role == "assistant" && $0.proposalStatus == "pending" }.count
    }

    private func sessionBackground(for session: FlowAssistantSession) -> some ShapeStyle {
        session.id == store.selectedAssistantSession?.id
            ? AnyShapeStyle(FlowTheme.surfaceRaised.opacity(0.92))
            : AnyShapeStyle(FlowTheme.sidebar.opacity(0.8))
    }

    private func railScrollHeight(for availableHeight: CGFloat) -> CGFloat {
        max(220, availableHeight * 0.34)
    }

    private func messageScrollHeight(for availableHeight: CGFloat) -> CGFloat {
        max(280, availableHeight * 0.44)
    }

    static func renderedSurfaceState(store: WorkspaceStore) -> AssistantRenderedSurfaceState {
        AssistantRenderedSurfaceState(
            keepsOuterWorkspaceShell: true,
            usesChatGPTStyleLayout: true,
            usesFullHeightChatPane: true,
            hasConversationRail: true,
            hasMainTranscript: true,
            hasBottomComposer: true,
            sessionTitles: store.assistantSessions.map(\.title),
            selectedSessionTitle: store.selectedAssistantSession?.title ?? "Chat",
            selectedSessionMessageCount: store.selectedAssistantSession?.messageCount ?? 0,
            selectedSessionPreview: store.selectedAssistantSession?.latestPreview ?? "",
            messageRoles: store.assistantMessages.map(\.role),
            messagePresentations: store.assistantMessages.map {
                AssistantRenderedMessagePresentation(
                    role: $0.role,
                    alignment: $0.role == "assistant" ? "leading" : "trailing",
                    bubbleStyle: $0.role == "assistant" ? "imessageAssistant" : "flowUserAccent",
                    textColorStyle: $0.role == "assistant" ? "primary" : "light",
                    textSelectionEnabled: true,
                    showsProposalCard: $0.role == "assistant" && $0.proposal != nil,
                    showsProvenanceDisclosure: $0.role == "assistant"
                )
            },
            selectedMessageHasProposal: store.selectedAssistantMessage?.proposal != nil,
            selectedMessageProposalStatus: store.selectedAssistantMessage?.proposalStatus,
            selectedMessageDisclosureSummary: store.selectedAssistantMessage.map(store.assistantMessageDisclosureSummary(for:)),
            assistantActionFeedback: store.assistantActionFeedback,
            showsTypingIndicator: store.assistantSendPending,
            typingIndicatorText: store.assistantSendPending ? "..." : "",
            typingIndicatorDotCount: store.assistantSendPending ? 3 : 0,
            typingIndicatorAnimates: store.assistantSendPending,
            composerIsDisabled: false,
            showsComposerInInteractionSlot: true,
            showsStopAction: store.assistantSendPending,
            primaryComposerActionLabel: store.assistantSendPending ? "Stop" : "Send",
            sessionRailIsDisabled: store.assistantSendPending,
            sessionRailLockLabel: nil,
            showsRailPendingCopy: false,
            showsNewChatAction: true,
            showsUndoAction: true,
            showsProposalActions: store.selectedAssistantMessage?.role == "assistant" && store.selectedAssistantMessage?.proposalStatus == "pending",
            showsLegacyTurnDrivenSurface: false,
            showsFlowDashboardHeader: false
        )
    }
}

private let assistantEmptyStateExamples = [
    "Capture the three tasks that matter most today.",
    "Save a memory about how I prefer assistant responses.",
    "Summarize the open work that still needs confirmation."
]

struct AssistantRenderedSurfaceState: Equatable {
    let keepsOuterWorkspaceShell: Bool
    let usesChatGPTStyleLayout: Bool
    let usesFullHeightChatPane: Bool
    let hasConversationRail: Bool
    let hasMainTranscript: Bool
    let hasBottomComposer: Bool
    let sessionTitles: [String]
    let selectedSessionTitle: String
    let selectedSessionMessageCount: Int
    let selectedSessionPreview: String
    let messageRoles: [String]
    let messagePresentations: [AssistantRenderedMessagePresentation]
    let selectedMessageHasProposal: Bool
    let selectedMessageProposalStatus: String?
    let selectedMessageDisclosureSummary: String?
    let assistantActionFeedback: String?
    let showsTypingIndicator: Bool
    let typingIndicatorText: String
    let typingIndicatorDotCount: Int
    let typingIndicatorAnimates: Bool
    let composerIsDisabled: Bool
    let showsComposerInInteractionSlot: Bool
    let showsStopAction: Bool
    let primaryComposerActionLabel: String
    let sessionRailIsDisabled: Bool
    let sessionRailLockLabel: String?
    let showsRailPendingCopy: Bool
    let showsNewChatAction: Bool
    let showsUndoAction: Bool
    let showsProposalActions: Bool
    let showsLegacyTurnDrivenSurface: Bool
    let showsFlowDashboardHeader: Bool
}

struct AssistantRenderedMessagePresentation: Equatable {
    let role: String
    let alignment: String
    let bubbleStyle: String
    let textColorStyle: String
    let textSelectionEnabled: Bool
    let showsProposalCard: Bool
    let showsProvenanceDisclosure: Bool
}

private struct AssistantChatShell: View {
    @ObservedObject var store: WorkspaceStore
    let availableSize: CGSize

    var body: some View {
        ViewThatFits(in: .horizontal) {
            HStack(alignment: .top, spacing: 16) {
                AssistantConversationRail(store: store, availableHeight: max(0, availableSize.height - 16))
                    .frame(width: 320, alignment: .top)

                AssistantTranscript(store: store)
                    .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topLeading)
            }
            .frame(width: max(0, availableSize.width - 16), height: max(0, availableSize.height - 16), alignment: .topLeading)

            VStack(spacing: 16) {
                AssistantConversationRail(store: store, availableHeight: max(220, availableSize.height * 0.34))
                AssistantTranscript(store: store)
            }
        }
        .padding(8)
        .frame(minHeight: availableSize.height, maxHeight: .infinity, alignment: .topLeading)
        .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topLeading)
        .background(FlowTheme.canvas)
    }
}

private struct AssistantConversationRail: View {
    @ObservedObject var store: WorkspaceStore
    let availableHeight: CGFloat

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            HStack(alignment: .firstTextBaseline, spacing: 12) {
                VStack(alignment: .leading, spacing: 4) {
                    Text("Chats")
                        .font(.system(size: 16, weight: .semibold))
                        .foregroundStyle(FlowTheme.textPrimary)
                    Text("\(store.assistantSessions.count) conversations")
                        .font(.system(size: 12, weight: .medium))
                        .foregroundStyle(FlowTheme.textMuted)
                }

                Spacer(minLength: 0)

                Button {
                    store.createAssistantSession()
                } label: {
                    Label("New Chat", systemImage: "plus")
                }
                .buttonStyle(.bordered)
                .disabled(store.assistantSendPending)
            }

            ScrollView(.vertical) {
                sessionRows
                .padding(.vertical, 2)
            }
            .frame(height: max(140, availableHeight - 78), alignment: .topLeading)
            .frame(maxWidth: .infinity, alignment: .topLeading)
            .layoutPriority(1)
        }
        .padding(16)
        .frame(maxWidth: .infinity, minHeight: availableHeight, maxHeight: availableHeight, alignment: .topLeading)
        .background(
            RoundedRectangle(cornerRadius: 24, style: .continuous)
                .fill(FlowTheme.surface.opacity(0.92))
                .overlay(
                    RoundedRectangle(cornerRadius: 24, style: .continuous)
                        .stroke(FlowTheme.strokeStrong, lineWidth: 1)
                )
        )
    }

    private var sessionRows: some View {
        VStack(alignment: .leading, spacing: 10) {
            if store.assistantSessions.isEmpty {
                AssistantEmptyRailState()
            } else {
                ForEach(store.assistantSessions) { session in
                    sessionRow(for: session)
                }
            }
        }
    }

    private func sessionRow(for session: FlowAssistantSession) -> some View {
        AssistantConversationRailRow(
            session: session,
            isSelected: session.id == store.selectedAssistantSessionID,
            isDisabled: store.assistantSendPending,
            onSelect: {
                store.selectAssistantSession(id: session.id)
            }
        )
    }
}

private struct AssistantConversationRailRow: View {
    let session: FlowAssistantSession
    let isSelected: Bool
    let isDisabled: Bool
    let onSelect: () -> Void

    var body: some View {
        Button(action: onSelect) {
            VStack(alignment: .leading, spacing: 8) {
                HStack(alignment: .firstTextBaseline, spacing: 8) {
                    Text(session.title)
                        .font(.system(size: 13, weight: .semibold))
                        .foregroundStyle(FlowTheme.textPrimary)
                        .lineLimit(1)
                    Spacer(minLength: 0)
                    Text(session.updatedAtLabel)
                        .font(.system(size: 11, weight: .medium))
                        .foregroundStyle(FlowTheme.textMuted)
                }

                Text(session.latestPreview.isEmpty ? "Start a new conversation" : session.latestPreview)
                    .font(.system(size: 12, weight: .medium))
                    .foregroundStyle(FlowTheme.textSecondary)
                    .lineLimit(2)
            }
            .frame(maxWidth: .infinity, alignment: .leading)
            .padding(14)
            .background(
                RoundedRectangle(cornerRadius: 18, style: .continuous)
                    .fill(isSelected ? FlowTheme.surfaceRaised.opacity(0.95) : FlowTheme.surfaceMuted.opacity(0.72))
                    .overlay(
                        RoundedRectangle(cornerRadius: 18, style: .continuous)
                            .stroke(isSelected ? FlowTheme.tealAccent.opacity(0.45) : FlowTheme.strokeStrong, lineWidth: 1)
                    )
            )
        }
        .buttonStyle(.plain)
        .disabled(isDisabled)
        .opacity(isDisabled ? 0.72 : 1)
    }
}

private struct AssistantEmptyRailState: View {
    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("No conversations yet")
                .font(.system(size: 13, weight: .semibold))
                .foregroundStyle(FlowTheme.textPrimary)
            Text("Start a chat from the composer to build a new conversation.")
                .font(.system(size: 12, weight: .medium))
                .foregroundStyle(FlowTheme.textSecondary)
                .fixedSize(horizontal: false, vertical: true)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(14)
        .background(
            RoundedRectangle(cornerRadius: 18, style: .continuous)
                .fill(FlowTheme.surfaceMuted.opacity(0.72))
                .overlay(
                    RoundedRectangle(cornerRadius: 18, style: .continuous)
                        .stroke(FlowTheme.strokeStrong, lineWidth: 1)
                )
        )
    }
}

private struct AssistantTranscript: View {
    @ObservedObject var store: WorkspaceStore

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            transcriptHeader

            if let feedback = store.assistantActionFeedback, feedback.isEmpty == false {
                AssistantStatusBanner(text: feedback)
            }

            if store.assistantMessages.isEmpty == false || store.assistantSendPending {
                ScrollView(.vertical) {
                    VStack(alignment: .leading, spacing: 12) {
                        ForEach(store.assistantMessages) { message in
                            AssistantMessageBubble(
                                message: message,
                                isSelected: store.selectedAssistantMessage?.id == message.id,
                                isActionPending: store.assistantProposalActionPending,
                                onSelect: {
                                    store.selectAssistantMessage(id: message.id)
                                },
                                onConfirm: message.role == "assistant" && message.proposalStatus == "pending" ? {
                                    store.selectAssistantMessage(id: message.id)
                                    store.confirmSelectedAssistantProposal()
                                } : nil,
                                onDismiss: message.role == "assistant" && message.proposalStatus == "pending" ? {
                                    store.selectAssistantMessage(id: message.id)
                                    store.dismissSelectedAssistantProposal()
                                } : nil
                            )
                        }

                        if store.assistantSendPending {
                            AssistantTypingIndicatorBubble()
                        }
                    }
                    .padding(.vertical, 2)
                    .padding(.horizontal, 2)
                }
                .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topLeading)
            }

            AssistantComposer(
                composerText: $store.assistantComposerText,
                isSending: store.assistantSendPending,
                expandsEditor: store.assistantMessages.isEmpty,
                onNewChat: {
                    store.createAssistantSession()
                },
                onSend: {
                    store.sendAssistantMessage()
                },
                onStop: {
                    store.stopAssistantMessage()
                }
            )
            .frame(maxWidth: .infinity, maxHeight: store.assistantMessages.isEmpty ? .infinity : nil, alignment: .topLeading)
        }
        .padding(16)
        .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topLeading)
        .background(
            RoundedRectangle(cornerRadius: 24, style: .continuous)
                .fill(FlowTheme.surface.opacity(0.82))
                .overlay(
                    RoundedRectangle(cornerRadius: 24, style: .continuous)
                        .stroke(FlowTheme.strokeStrong, lineWidth: 1)
                )
        )
    }

    private var transcriptHeader: some View {
        HStack(alignment: .firstTextBaseline, spacing: 12) {
            VStack(alignment: .leading, spacing: 4) {
                Text(store.selectedAssistantSession?.title ?? "Chat")
                    .font(.system(size: 17, weight: .semibold))
                    .foregroundStyle(FlowTheme.textPrimary)
                Text(transcriptSubtitle)
                    .font(.system(size: 12, weight: .medium))
                    .foregroundStyle(FlowTheme.textMuted)
            }

            Spacer(minLength: 0)

            Button {
                store.undoLastAssistantMutation()
            } label: {
                Label("Undo", systemImage: "arrow.uturn.backward")
            }
            .buttonStyle(.plain)
            .font(.system(size: 12, weight: .semibold))
            .foregroundStyle(FlowTheme.textSecondary)
            .disabled(isSendingLocked)
        }
    }

    private var transcriptSubtitle: String {
        if let session = store.selectedAssistantSession {
            let preview = session.latestPreview.isEmpty ? "No preview yet" : session.latestPreview
            return "\(session.messageCount) messages · \(preview)"
        }
        return "Chat-first assistant workspace"
    }

    private var isSendingLocked: Bool {
        store.assistantSendPending
    }
}

private struct AssistantStatusBanner: View {
    let text: String

    var body: some View {
        HStack(alignment: .top, spacing: 8) {
            Image(systemName: "info.circle.fill")
                .font(.system(size: 13, weight: .semibold))
                .foregroundStyle(FlowTheme.tealAccent)
            Text(text)
                .font(.system(size: 12, weight: .medium))
                .foregroundStyle(FlowTheme.textSecondary)
                .fixedSize(horizontal: false, vertical: true)
        }
        .padding(12)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(
            RoundedRectangle(cornerRadius: 16, style: .continuous)
                .fill(FlowTheme.surfaceRaised.opacity(0.74))
                .overlay(
                    RoundedRectangle(cornerRadius: 16, style: .continuous)
                        .stroke(FlowTheme.strokeStrong, lineWidth: 1)
                )
        )
    }
}

private struct AssistantEmptyTranscriptState: View {
    let prompts: [String]
    let onPick: (String) -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            VStack(alignment: .leading, spacing: 6) {
                Text("Start a conversation")
                    .font(.system(size: 18, weight: .semibold))
                    .foregroundStyle(FlowTheme.textPrimary)
                Text("Choose a prompt or start typing to create the first turn.")
                    .font(.system(size: 12, weight: .medium))
                    .foregroundStyle(FlowTheme.textMuted)
            }

            VStack(alignment: .leading, spacing: 8) {
                ForEach(prompts, id: \.self) { prompt in
                    Button {
                        onPick(prompt)
                    } label: {
                        HStack(alignment: .top, spacing: 10) {
                            Image(systemName: "sparkles")
                                .font(.system(size: 11, weight: .semibold))
                                .foregroundStyle(FlowTheme.warmAccent)
                                .padding(.top, 1)

                            Text(prompt)
                                .font(.system(size: 13, weight: .medium))
                                .foregroundStyle(FlowTheme.textPrimary)
                                .multilineTextAlignment(.leading)

                            Spacer(minLength: 0)
                        }
                        .padding(12)
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .background(
                            RoundedRectangle(cornerRadius: 16, style: .continuous)
                                .fill(FlowTheme.surfaceRaised.opacity(0.72))
                                .overlay(
                                    RoundedRectangle(cornerRadius: 16, style: .continuous)
                                        .stroke(FlowTheme.strokeStrong, lineWidth: 1)
                                )
                        )
                    }
                    .buttonStyle(.plain)
                }
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }
}

private struct AssistantComposer: View {
    @Binding var composerText: String
    let isSending: Bool
    let expandsEditor: Bool
    let onNewChat: () -> Void
    let onSend: () -> Void
    let onStop: () -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            ZStack(alignment: .topLeading) {
                TextEditor(text: $composerText)
                    .font(.system(size: 14, weight: .medium))
                    .frame(minHeight: expandsEditor ? 240 : 112, maxHeight: expandsEditor ? .infinity : nil)
                    .scrollContentBackground(.hidden)
                    .padding(10)
                    .background(
                        RoundedRectangle(cornerRadius: 18, style: .continuous)
                            .fill(FlowTheme.surfaceRaised.opacity(0.84))
                            .overlay(
                                RoundedRectangle(cornerRadius: 18, style: .continuous)
                                    .stroke(FlowTheme.strokeStrong, lineWidth: 1)
                            )
                    )

                if composerText.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
                    Text("Ask Flow to capture work, save a memory, or summarize a chat.")
                        .font(.system(size: 13, weight: .medium))
                        .foregroundStyle(FlowTheme.textMuted)
                        .padding(.horizontal, 18)
                        .padding(.vertical, 18)
                }
            }

            HStack(spacing: 10) {
                Button {
                    onNewChat()
                } label: {
                    Label("New Chat", systemImage: "plus")
                }
                .buttonStyle(.bordered)
                .disabled(isSending)

                Spacer()

                if isSending {
                    Button {
                        onStop()
                    } label: {
                        Label("Stop", systemImage: "stop.fill")
                    }
                    .buttonStyle(.borderedProminent)
                    .tint(FlowTheme.danger)
                } else {
                    Button {
                        onSend()
                    } label: {
                        Label("Send", systemImage: "paperplane.fill")
                    }
                    .buttonStyle(.borderedProminent)
                    .tint(FlowTheme.warmAccent)
                    .disabled(composerText.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
                }
            }
        }
        .frame(maxWidth: .infinity, maxHeight: expandsEditor ? .infinity : nil, alignment: .topLeading)
    }
}

private struct AssistantTypingIndicatorBubble: View {
    var body: some View {
        HStack(alignment: .top, spacing: 0) {
            typingBubble
                .frame(maxWidth: 520, alignment: .leading)

            Spacer(minLength: 40)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }

    private var typingBubble: some View {
        TimelineView(.periodic(from: .now, by: 0.32)) { context in
            let phase = Int(context.date.timeIntervalSinceReferenceDate / 0.32) % 3

            HStack(spacing: 5) {
                ForEach(0..<3, id: \.self) { index in
                    Circle()
                        .fill(FlowTheme.textSecondary.opacity(index == phase ? 0.95 : 0.42))
                        .frame(width: 6, height: 6)
                        .offset(y: index == phase ? -2 : 0)
                }
            }
            .animation(.easeInOut(duration: 0.2), value: phase)
            .padding(.horizontal, 16)
            .padding(.vertical, 12)
            .background(
                RoundedRectangle(cornerRadius: 21, style: .continuous)
                    .fill(FlowTheme.surfaceRaised.opacity(0.9))
                    .overlay(
                        RoundedRectangle(cornerRadius: 21, style: .continuous)
                            .stroke(FlowTheme.strokeStrong, lineWidth: 1)
                    )
            )
            .accessibilityLabel("Assistant typing")
        }
    }
}

private struct AssistantMessageBubble: View {
    let message: FlowAssistantMessage
    let isSelected: Bool
    let isActionPending: Bool
    let onSelect: () -> Void
    let onConfirm: (() -> Void)?
    let onDismiss: (() -> Void)?

    var body: some View {
        HStack(alignment: .top, spacing: 0) {
            if isAssistantBubble {
                bubble
                    .frame(maxWidth: 520, alignment: .leading)
                Spacer(minLength: 40)
            } else {
                Spacer(minLength: 40)
                bubble
                    .frame(maxWidth: 520, alignment: .leading)
            }
        }
        .frame(maxWidth: .infinity, alignment: isAssistantBubble ? .leading : .trailing)
    }

    private var bubble: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text(message.content)
                .font(.system(size: 13, weight: .medium))
                .foregroundStyle(messageTextColor)
                .multilineTextAlignment(.leading)
                .fixedSize(horizontal: false, vertical: true)
                .textSelection(.enabled)

            if let proposal = message.proposal, isAssistantBubble {
                AssistantProposalCard(
                    message: message,
                    proposal: proposal,
                    onConfirm: onConfirm,
                    onDismiss: onDismiss,
                    isActionPending: isActionPending
                )
            }

            if isAssistantBubble {
                AssistantProvenanceDisclosure(message: message)
            }
        }
        .padding(16)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(
            RoundedRectangle(cornerRadius: 21, style: .continuous)
                .fill(bubbleBackground)
                .overlay(
                    RoundedRectangle(cornerRadius: 21, style: .continuous)
                        .stroke(isSelected ? bubbleAccent.opacity(0.5) : FlowTheme.strokeStrong, lineWidth: 1)
                )
        )
        .contentShape(RoundedRectangle(cornerRadius: 21, style: .continuous))
        .onTapGesture(perform: onSelect)
    }

    private var isAssistantBubble: Bool {
        message.role == "assistant"
    }

    private var bubbleBackground: some ShapeStyle {
        isAssistantBubble
            ? AnyShapeStyle(FlowTheme.surfaceRaised.opacity(0.9))
            : AnyShapeStyle(FlowTheme.warmAccent.opacity(0.92))
    }

    private var bubbleAccent: Color {
        isAssistantBubble ? FlowTheme.tealAccent : FlowTheme.warmAccent
    }

    private var messageTextColor: Color {
        isAssistantBubble ? FlowTheme.textPrimary : .white
    }
}

private struct AssistantProposalCard: View {
    let message: FlowAssistantMessage
    let proposal: FlowAssistantProposal
    let onConfirm: (() -> Void)?
    let onDismiss: (() -> Void)?
    let isActionPending: Bool

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack(alignment: .firstTextBaseline, spacing: 10) {
                Text(proposal.title)
                    .font(.system(size: 13, weight: .semibold))
                    .foregroundStyle(FlowTheme.textPrimary)
                Spacer(minLength: 8)
                StatusPill(title: message.proposalStatus.capitalized, accent: proposalAccent)
            }

            Text(proposal.detail)
                .font(.system(size: 12, weight: .medium))
                .foregroundStyle(FlowTheme.textSecondary)
                .fixedSize(horizontal: false, vertical: true)

            if message.proposalStatus == "pending" {
                HStack(spacing: 10) {
                    Button("Dismiss") {
                        onDismiss?()
                    }
                    .buttonStyle(.bordered)
                    .disabled(isActionPending)

                    Spacer()

                    Button("Confirm") {
                        onConfirm?()
                    }
                    .buttonStyle(.borderedProminent)
                    .tint(FlowTheme.tealAccent)
                    .disabled(isActionPending)
                }
            }
        }
        .padding(14)
        .background(
            RoundedRectangle(cornerRadius: 18, style: .continuous)
                .fill(FlowTheme.surface.opacity(0.72))
                .overlay(
                    RoundedRectangle(cornerRadius: 18, style: .continuous)
                        .stroke(FlowTheme.strokeStrong, lineWidth: 1)
                )
        )
    }

    private var proposalAccent: Color {
        switch message.proposalStatus {
        case "pending":
            return FlowTheme.warmAccent
        case "confirmed":
            return FlowTheme.tealAccent
        case "dismissed":
            return FlowTheme.roseAccent
        default:
            return FlowTheme.surfaceRaised
        }
    }

}

private struct AssistantProvenanceDisclosure: View {
    let message: FlowAssistantMessage

    var body: some View {
        DisclosureGroup {
            VStack(alignment: .leading, spacing: 8) {
                DetailTile(label: "Provider", value: providerLabel, accent: providerAccent)
                DetailTile(label: "Provider Detail", value: message.providerDetail, accent: providerAccent)

                if let providerModel = message.providerModel, providerModel.isEmpty == false {
                    DetailTile(label: "Model", value: providerModel, accent: FlowTheme.coolAccent)
                }

                if let sourceTurnID = message.sourceTurnID {
                    DetailTile(label: "Source Turn", value: sourceTurnID, accent: FlowTheme.coolAccent)
                } else {
                    DetailTile(
                        label: "Source Turn",
                        value: "No legacy turn source attached to this message.",
                        accent: FlowTheme.textMuted
                    )
                }

                if message.auditSteps.isEmpty == false {
                    VStack(alignment: .leading, spacing: 8) {
                        ForEach(message.auditSteps) { step in
                            DetailTile(
                                label: step.stage.capitalized,
                                value: step.summary,
                                accent: stepAccent(for: step.status)
                            )
                        }
                    }
                } else {
                    DetailTile(
                        label: "Audit",
                        value: "No additional audit steps were recorded for this message.",
                        accent: FlowTheme.textMuted
                    )
                }
            }
            .padding(.top, 4)
        } label: {
            Text("Provider & audit details")
                .font(.system(size: 12, weight: .semibold))
                .foregroundStyle(FlowTheme.textSecondary)
        }
    }

    private var providerLabel: String {
        var parts = [message.provider.capitalized, message.providerStatus.capitalized]
        if let providerModel = message.providerModel, providerModel.isEmpty == false {
            parts.append(providerModel)
        }
        return parts.joined(separator: " | ")
    }

    private var providerAccent: Color {
        switch message.providerStatus {
        case "success":
            return FlowTheme.tealAccent
        case "degraded", "failed", "unavailable":
            return FlowTheme.warmAccent
        default:
            return FlowTheme.coolAccent
        }
    }

    private func stepAccent(for status: String) -> Color {
        switch status {
        case "ok":
            return FlowTheme.tealAccent
        case "warn":
            return FlowTheme.warmAccent
        case "error":
            return FlowTheme.roseAccent
        default:
            return FlowTheme.coolAccent
        }
    }
}

private struct AssistantComposerCard: View {
    @Binding var composerText: String
    let isSending: Bool
    let statusMessage: String?
    let onNewChat: () -> Void
    let onUndo: () -> Void
    let onSend: () -> Void
    let onStop: () -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Text("Composer")
                    .font(.system(size: 11, weight: .semibold))
                    .foregroundStyle(FlowTheme.textSecondary)

                Spacer()

                Button("Undo Last Safe Write") {
                    onUndo()
                }
                .buttonStyle(.bordered)
            }

            if let interactionStatus = interactionStatusText, interactionStatus.isEmpty == false {
                HStack(alignment: .top, spacing: 8) {
                    Image(systemName: "info.circle.fill")
                        .font(.system(size: 13, weight: .semibold))
                        .foregroundStyle(FlowTheme.tealAccent)
                    Text(interactionStatus)
                        .font(.system(size: 12, weight: .medium))
                        .foregroundStyle(FlowTheme.textSecondary)
                        .fixedSize(horizontal: false, vertical: true)
                }
                .padding(12)
                .frame(maxWidth: .infinity, alignment: .leading)
                .background(
                    RoundedRectangle(cornerRadius: 16, style: .continuous)
                        .fill(FlowTheme.sidebar.opacity(0.78))
                        .overlay(
                            RoundedRectangle(cornerRadius: 16, style: .continuous)
                                .stroke(FlowTheme.strokeStrong, lineWidth: 1)
                        )
                )
            }

            ZStack(alignment: .topLeading) {
                TextEditor(text: $composerText)
                    .font(.system(size: 14, weight: .medium))
                    .frame(minHeight: 110)
                    .scrollContentBackground(.hidden)
                    .padding(10)
                    .background(
                        RoundedRectangle(cornerRadius: 18, style: .continuous)
                            .fill(FlowTheme.surfaceRaised.opacity(0.84))
                            .overlay(
                                RoundedRectangle(cornerRadius: 18, style: .continuous)
                                    .stroke(FlowTheme.strokeStrong, lineWidth: 1)
                            )
                    )

                if composerText.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty && isSending == false {
                    Text("Ask Flow to capture work, save a memory, or summarize a chat.")
                        .font(.system(size: 13, weight: .medium))
                        .foregroundStyle(FlowTheme.textMuted)
                        .padding(.horizontal, 18)
                        .padding(.vertical, 18)
                }
            }

            HStack(spacing: 10) {
                Button {
                    onNewChat()
                } label: {
                    Label("New Chat", systemImage: "plus")
                }
                .buttonStyle(.bordered)
                .disabled(isSending)

                Spacer()

                if isSending {
                    Button {
                        onStop()
                    } label: {
                        Label("Stop", systemImage: "stop.fill")
                    }
                    .buttonStyle(.borderedProminent)
                    .tint(FlowTheme.danger)
                } else {
                    Button {
                        onSend()
                    } label: {
                        Label("Send", systemImage: "paperplane.fill")
                    }
                    .buttonStyle(.borderedProminent)
                    .tint(FlowTheme.warmAccent)
                    .disabled(composerText.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
                }
            }
        }
    }

    private var interactionStatusText: String? {
        if isSending {
            return nil
        }
        return statusMessage
    }
}

private struct AssistantExamplePromptGrid: View {
    let prompts: [String]
    let onPick: (String) -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text("Examples")
                .font(.system(size: 11, weight: .semibold))
                .foregroundStyle(FlowTheme.textSecondary)

            VStack(alignment: .leading, spacing: 8) {
                ForEach(prompts, id: \.self) { prompt in
                    Button {
                        onPick(prompt)
                    } label: {
                        HStack(alignment: .top, spacing: 10) {
                            Image(systemName: "sparkles")
                                .font(.system(size: 11, weight: .semibold))
                                .foregroundStyle(FlowTheme.warmAccent)
                                .padding(.top, 1)

                            Text(prompt)
                                .font(.system(size: 12, weight: .medium))
                                .foregroundStyle(FlowTheme.textPrimary)
                                .multilineTextAlignment(.leading)

                            Spacer(minLength: 0)
                        }
                        .padding(12)
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .background(
                            RoundedRectangle(cornerRadius: 16, style: .continuous)
                                .fill(FlowTheme.sidebar.opacity(0.78))
                                .overlay(
                                    RoundedRectangle(cornerRadius: 16, style: .continuous)
                                        .stroke(FlowTheme.strokeStrong, lineWidth: 1)
                                )
                        )
                    }
                    .buttonStyle(.plain)
                }
            }
        }
    }
}

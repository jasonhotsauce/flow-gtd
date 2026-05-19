import SwiftUI

struct RootSplitView: View {
    @ObservedObject var store: WorkspaceStore
    @ObservedObject var sidecarRuntime: SidecarRuntimeModel

    var body: some View {
        NavigationSplitView {
            SidebarView(store: store)
                .navigationSplitViewColumnWidth(min: 270, ideal: 292)
        } detail: {
            ZStack {
                FlowBackdrop()
                workspaceView
                    .id(store.selectedSection)
                    .transition(.asymmetric(insertion: .opacity.combined(with: .move(edge: .trailing)), removal: .opacity))
            }
        }
        .navigationSplitViewStyle(.balanced)
        .sheet(isPresented: $store.isCapturePresented) {
            CaptureSheet(store: store)
        }
        .sheet(
            isPresented: Binding(
                get: { store.clarifyDraft != nil },
                set: { isPresented in
                    if isPresented == false {
                        store.cancelClarify()
                    }
                }
            )
        ) {
            ClarifyEditor(store: store)
        }
        .searchable(text: $store.searchText, placement: .toolbar, prompt: "Search tasks, projects, or memory")
        .toolbar {
            ToolbarItem(placement: .principal) {
                ToolbarHeadlineChip(section: store.selectedSection, headline: store.snapshot.focusHeadline)
            }

            ToolbarItemGroup(placement: .primaryAction) {
                ControlGroup {
                    Button {
                        store.toggleInspector()
                    } label: {
                        Label(
                            store.isInspectorPresented ? "Hide Inspector" : "Show Inspector",
                            systemImage: store.isInspectorPresented ? "sidebar.right" : "sidebar.right"
                        )
                    }

                    Button {
                        store.refresh()
                    } label: {
                        Label("Refresh", systemImage: "arrow.clockwise")
                    }

                    Button {
                        store.isCapturePresented = true
                    } label: {
                        Label("Capture", systemImage: "plus")
                    }
                    .keyboardShortcut("n", modifiers: [.command])
                }
            }
        }
        .onMoveCommand(perform: handleMoveCommand(_:))
        .alert(
            "Flow encountered an issue",
            isPresented: Binding(
                get: { store.errorMessage != nil },
                set: { newValue in
                    if newValue == false {
                        store.clearError()
                    }
                }
            ),
            actions: {
                Button("Dismiss", role: .cancel) {
                    store.clearError()
                }
            },
            message: {
                Text(store.errorMessage ?? "Unknown error")
            }
        )
        .background(FlowBackdrop())
        .safeAreaInset(edge: .top, spacing: 0) {
            switch sidecarRuntime.status {
            case .starting(let attempt):
                SidecarStartingBanner(attempt: attempt)
                    .padding(.horizontal, 18)
                    .padding(.top, 10)
            case .degraded(let degradedState):
                SidecarDegradedBanner(
                    degradedState: degradedState,
                    onRetry: {
                        Task {
                            await sidecarRuntime.retry()
                        }
                    }
                )
                .padding(.horizontal, 18)
                .padding(.top, 10)
            default:
                EmptyView()
            }
        }
        .animation(.spring(response: 0.34, dampingFraction: 0.88), value: store.selectedSection)
        .animation(.easeOut(duration: 0.18), value: store.selectedTaskID)
        .task {
            await sidecarRuntime.startIfNeeded()
        }
    }

    @ViewBuilder
    private var workspaceView: some View {
        switch store.selectedSection {
        case .today:
            TodayWorkspaceView(store: store)
        case .inbox:
            InboxWorkspaceView(store: store)
        case .projects:
            ProjectsWorkspaceView(store: store)
        case .review:
            ReviewWorkspaceView(store: store)
        case .assistant:
            AssistantView(store: store)
        case .memory:
            MemoryView(store: store)
        }
    }

    private func handleMoveCommand(_ direction: MoveCommandDirection) {
        switch direction {
        case .up:
            store.moveSelection(.previous)
        case .down:
            store.moveSelection(.next)
        default:
            break
        }
    }
}

private struct SidecarStartingBanner: View {
    let attempt: Int

    var body: some View {
        HStack(alignment: .center, spacing: 14) {
            ProgressView()
                .controlSize(.small)
                .tint(FlowTheme.coolAccent)

            VStack(alignment: .leading, spacing: 6) {
                Text(attempt > 1 ? "Retrying Flow services" : "Starting Flow services")
                    .font(.system(size: 14, weight: .semibold))
                    .foregroundStyle(FlowTheme.textPrimary)

                Text("Assistant suggestions, planning, and other smart features may take a moment while Flow reconnects to its background services.")
                    .font(.system(size: 12, weight: .medium))
                    .foregroundStyle(FlowTheme.textSecondary)
                    .fixedSize(horizontal: false, vertical: true)
            }

            Spacer(minLength: 16)

            Button(attempt > 1 ? "Retrying…" : "Starting…") {}
                .buttonStyle(.bordered)
                .disabled(true)
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 14)
        .background(
            RoundedRectangle(cornerRadius: 20, style: .continuous)
                .fill(FlowTheme.surface.opacity(0.96))
                .overlay(
                    RoundedRectangle(cornerRadius: 20, style: .continuous)
                        .stroke(FlowTheme.coolAccent.opacity(0.28), lineWidth: 1)
                )
        )
        .shadow(color: .black.opacity(0.18), radius: 14, y: 8)
    }
}

private struct SidecarDegradedBanner: View {
    let degradedState: SidecarDegradedState
    let onRetry: () -> Void

    var body: some View {
        HStack(alignment: .top, spacing: 14) {
            Image(systemName: "exclamationmark.triangle.fill")
                .font(.system(size: 15, weight: .bold))
                .foregroundStyle(FlowTheme.warmAccent)
                .padding(.top, 2)

            VStack(alignment: .leading, spacing: 6) {
                Text("Flow is running in degraded mode")
                    .font(.system(size: 14, weight: .semibold))
                    .foregroundStyle(FlowTheme.textPrimary)

                Text("Assistant suggestions, planning, and other smart features are temporarily unavailable until Flow reconnects to its background services.")
                    .font(.system(size: 12, weight: .medium))
                    .foregroundStyle(FlowTheme.textSecondary)
                    .fixedSize(horizontal: false, vertical: true)

                Text(degradedState.failureReasons.last ?? "The sidecar did not report ready state.")
                    .font(.system(size: 12, weight: .medium))
                    .foregroundStyle(FlowTheme.textMuted)
                    .fixedSize(horizontal: false, vertical: true)

                Text("Try again in a moment. If this keeps happening, reopen Flow to restart its background services.")
                    .font(.system(size: 12, weight: .medium))
                    .foregroundStyle(FlowTheme.textMuted)
                    .fixedSize(horizontal: false, vertical: true)
            }

            Spacer(minLength: 16)

            VStack(alignment: .trailing, spacing: 8) {
                Text("Auto-restarts: \(degradedState.restartCount)")
                    .font(.system(size: 11, weight: .semibold))
                    .foregroundStyle(FlowTheme.textSecondary)

                Button("Retry Sidecar", action: onRetry)
                    .buttonStyle(.borderedProminent)
                    .tint(FlowTheme.warmAccent)
            }
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 14)
        .background(
            RoundedRectangle(cornerRadius: 20, style: .continuous)
                .fill(FlowTheme.surface.opacity(0.96))
                .overlay(
                    RoundedRectangle(cornerRadius: 20, style: .continuous)
                        .stroke(FlowTheme.warmAccent.opacity(0.36), lineWidth: 1)
                )
        )
        .shadow(color: .black.opacity(0.24), radius: 18, y: 10)
    }
}

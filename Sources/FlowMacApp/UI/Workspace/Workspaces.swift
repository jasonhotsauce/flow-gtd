import SwiftUI

enum TodayWorkspaceLayoutMetrics {
    static let heroMinimumHeight: CGFloat = 168
    static let metricRailWidth: CGFloat = 208
    static let supportRailWidth: CGFloat = 268
    static let compactCardSpacing: CGFloat = 16
}

enum ProjectsWorkspaceLayoutMetrics {
    static let projectCardSpacing: CGFloat = 18
}

enum WorkspaceInspectorMetrics {
    static let collapsedByDefault = true
    static let inspectorWidth: CGFloat = 360
}

let workspaceColumns = [
    GridItem(.adaptive(minimum: 320, maximum: 440), spacing: 18, alignment: .top)
]

struct TodayWorkspaceView: View {
    @ObservedObject var store: WorkspaceStore

    var body: some View {
        WorkspaceShell(store: store) {
            VStack(alignment: .leading, spacing: TodayWorkspaceLayoutMetrics.compactCardSpacing) {
                TodayActionHeader(store: store)
                DailyPlanView(store: store)

                ViewThatFits(in: .horizontal) {
                    HStack(alignment: .top, spacing: TodayWorkspaceLayoutMetrics.compactCardSpacing) {
                        taskColumnCard(
                            title: "Focus Now",
                            subtitle: "Current block",
                            accent: FlowTheme.coolAccent,
                            tasks: store.filteredTodayItems,
                            emptyTitle: "No focused work yet",
                            emptyDetail: "Choose the few items that deserve the next block."
                        )
                        .frame(maxWidth: .infinity)

                        taskColumnCard(
                            title: "Later Today",
                            subtitle: "Visible queue",
                            accent: FlowTheme.warmAccent,
                            tasks: store.filteredLaterItems,
                            emptyTitle: "Breathing room preserved",
                            emptyDetail: "You have not overloaded the rest of the day."
                        )
                        .frame(maxWidth: .infinity)
                    }

                    VStack(spacing: TodayWorkspaceLayoutMetrics.compactCardSpacing) {
                        taskColumnCard(
                            title: "Focus Now",
                            subtitle: "Current block",
                            accent: FlowTheme.coolAccent,
                            tasks: store.filteredTodayItems,
                            emptyTitle: "No focused work yet",
                            emptyDetail: "Choose the few items that deserve the next block."
                        )

                        taskColumnCard(
                            title: "Later Today",
                            subtitle: "Visible queue",
                            accent: FlowTheme.warmAccent,
                            tasks: store.filteredLaterItems,
                            emptyTitle: "Breathing room preserved",
                            emptyDetail: "You have not overloaded the rest of the day."
                        )
                    }
                }
            }
        }
    }

    private func taskColumnCard(
        title: String,
        subtitle: String,
        accent: Color,
        tasks: [FlowTask],
        emptyTitle: String,
        emptyDetail: String
    ) -> some View {
        SurfaceCard(title: title, subtitle: subtitle, accent: accent) {
            if tasks.isEmpty {
                EmptyStateCard(title: emptyTitle, detail: emptyDetail)
            } else {
                VStack(spacing: 10) {
                    ForEach(tasks) { task in
                        TaskRow(
                            task: task,
                            isSelected: store.selectedTaskID == task.id,
                            onSelect: {
                                store.select(task: task)
                            },
                            onComplete: {
                                store.markDone(task)
                            },
                            onArchive: {
                                store.archive(task)
                            }
                        )
                    }
                }
            }
        }
        .frame(maxWidth: .infinity)
    }
}

private struct TodayActionHeader: View {
    @ObservedObject var store: WorkspaceStore

    var body: some View {
        HStack(alignment: .firstTextBaseline, spacing: 14) {
            VStack(alignment: .leading, spacing: 4) {
                Text("Today")
                    .font(.system(size: 24, weight: .semibold))
                    .foregroundStyle(FlowTheme.textPrimary)
                Text(actionLine)
                    .font(.system(size: 13, weight: .medium))
                    .foregroundStyle(FlowTheme.textSecondary)
                    .lineLimit(2)
            }

            Spacer(minLength: 12)

            StatusPill(
                title: store.filteredTodayItems.isEmpty ? "Open day" : "\(store.filteredTodayItems.count) in focus",
                accent: FlowTheme.coolAccent
            )
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(.vertical, 4)
    }

    private var actionLine: String {
        if store.dailyPlanDraftTopItemIDs.isEmpty == false {
            return "Primary tasks are set. Keep the rest of the day narrow."
        }

        if store.snapshot.inboxItems.isEmpty == false {
            return "\(store.snapshot.inboxItems.count) captures are waiting, but choose today's work before widening scope."
        }

        return "Choose up to three primary tasks and two secondary tasks."
    }
}

private struct TodayHeroCard: View {
    @ObservedObject var store: WorkspaceStore

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            ViewThatFits(in: .horizontal) {
                HStack(alignment: .top, spacing: TodayWorkspaceLayoutMetrics.compactCardSpacing) {
                    heroCopy
                        .frame(maxWidth: .infinity, alignment: .leading)

                    TodayMetricCluster(metrics: store.focusMetrics)
                        .frame(width: TodayWorkspaceLayoutMetrics.metricRailWidth)
                }

                VStack(alignment: .leading, spacing: TodayWorkspaceLayoutMetrics.compactCardSpacing) {
                    heroCopy
                    TodayMetricCluster(metrics: store.focusMetrics)
                }
            }
        }
        .padding(20)
        .frame(maxWidth: .infinity, alignment: .leading)
        .frame(minHeight: TodayWorkspaceLayoutMetrics.heroMinimumHeight, alignment: .topLeading)
        .background(backgroundChrome)
        .overlay(alignment: .topTrailing) {
            RoundedRectangle(cornerRadius: 30, style: .continuous)
                .fill(FlowTheme.coolAccent.opacity(0.14))
                .frame(width: 176, height: 112)
                .blur(radius: 44)
                .offset(x: 12, y: -4)
        }
    }

    private var heroCopy: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack(alignment: .center, spacing: 14) {
                SectionBadge(section: .today, size: 48)

                VStack(alignment: .leading, spacing: 6) {
                    HStack(alignment: .center, spacing: 10) {
                        Text(FlowSection.today.title)
                            .font(.system(size: 26, weight: .semibold, design: .rounded))
                            .foregroundStyle(FlowTheme.textPrimary)
                        StatusPill(
                            title: store.filteredTodayItems.isEmpty ? "Open day" : "\(store.filteredTodayItems.count) in focus",
                            accent: FlowTheme.coolAccent
                        )
                    }

                    Text(FlowSection.today.subtitle)
                        .font(.system(size: 12, weight: .semibold))
                        .foregroundStyle(FlowTheme.textSecondary)
                }

                Spacer(minLength: 0)
            }

            Text(store.snapshot.focusHeadline)
                .font(.system(size: 16, weight: .semibold))
                .foregroundStyle(FlowTheme.coolAccent)
                .fixedSize(horizontal: false, vertical: true)

            Text(supportingLine)
                .font(.system(size: 12, weight: .medium))
                .foregroundStyle(FlowTheme.textSecondary)
                .lineLimit(2)
        }
    }

    private var supportingLine: String {
        if let selectedTask = store.selectedTask, store.selectedSection == .today {
            return "Current focus: \(selectedTask.title)"
        }

        if store.snapshot.inboxItems.isEmpty {
            return "Inbox is calm enough to keep the day narrow."
        }

        return "\(store.snapshot.inboxItems.count) fresh captures are still waiting for clarification."
    }

    private var backgroundChrome: some View {
        RoundedRectangle(cornerRadius: 28, style: .continuous)
            .fill(
                LinearGradient(
                    colors: [FlowTheme.surface.opacity(0.98), FlowTheme.surfaceMuted.opacity(0.92)],
                    startPoint: .topLeading,
                    endPoint: .bottomTrailing
                )
            )
            .overlay(
                RoundedRectangle(cornerRadius: 28, style: .continuous)
                    .stroke(FlowTheme.strokeStrong, lineWidth: 1)
            )
            .shadow(color: .black.opacity(0.28), radius: 30, y: 18)
    }
}

private struct TodayMetricCluster: View {
    let metrics: [(String, String)]

    private let columns = [
        GridItem(.flexible(minimum: 88), spacing: 10),
        GridItem(.flexible(minimum: 88), spacing: 10)
    ]

    var body: some View {
        LazyVGrid(columns: columns, spacing: 10) {
            ForEach(metrics, id: \.0) { metric in
                CompactMetricTile(
                    label: metric.0,
                    value: metric.1,
                    accent: accent(for: metric.0)
                )
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }

    private func accent(for label: String) -> Color {
        switch label.lowercased() {
        case "inbox":
            return FlowTheme.warmAccent
        case "projects":
            return FlowTheme.tealAccent
        case "stale":
            return FlowTheme.roseAccent
        default:
            return FlowTheme.coolAccent
        }
    }
}

private struct CompactMetricTile: View {
    let label: String
    let value: String
    let accent: Color

    var body: some View {
        VStack(alignment: .leading, spacing: 5) {
            Text(label.uppercased())
                .font(.system(size: 9, weight: .bold, design: .rounded))
                .kerning(1.1)
                .foregroundStyle(FlowTheme.textMuted)
                .lineLimit(1)

            Text(value)
                .font(.system(size: 18, weight: .semibold, design: .rounded))
                .foregroundStyle(FlowTheme.textPrimary)
                .lineLimit(1)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(.horizontal, 12)
        .padding(.vertical, 10)
        .background(
            RoundedRectangle(cornerRadius: 18, style: .continuous)
                .fill(FlowTheme.surfaceRaised.opacity(0.88))
                .overlay(
                    RoundedRectangle(cornerRadius: 18, style: .continuous)
                        .stroke(accent.opacity(0.24), lineWidth: 1)
                )
        )
    }
}

private struct TodaySupportRail: View {
    @ObservedObject var store: WorkspaceStore

    var body: some View {
        SurfaceCard(
            title: "Daily Rhythm",
            subtitle: "Pressure and review signals",
            accent: FlowTheme.warmAccent
        ) {
            VStack(alignment: .leading, spacing: 14) {
                LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible())], spacing: 10) {
                    DetailTile(label: "Search", value: store.searchText.isEmpty ? "Off" : "Active", accent: FlowTheme.coolAccent)
                    DetailTile(label: "Selected", value: store.selectedTask != nil ? "Focused" : "None", accent: FlowTheme.warmAccent)
                    DetailTile(label: "Inbox", value: "\(store.snapshot.inboxItems.count) fresh", accent: FlowTheme.warmAccent)
                    DetailTile(label: "Review", value: "\(store.snapshot.review.staleCount) stale", accent: FlowTheme.roseAccent)
                }

                GuidanceList(items: [
                    store.snapshot.review.prompt,
                    store.searchText.isEmpty
                        ? "Keep the visible day narrow and let the inspector hold the extra context."
                        : "Search is filtering the visible day, so finish the current decision before widening scope."
                ])
            }
        }
    }
}

struct InboxWorkspaceView: View {
    @ObservedObject var store: WorkspaceStore

    var body: some View {
        WorkspaceShell(store: store) {
            VStack(alignment: .leading, spacing: 20) {
                WorkspaceHeader(
                    section: .inbox,
                    headline: "Capture fast, clarify calmly, and avoid mixing raw intent with committed work",
                    metrics: [
                        ("Items", "\(store.snapshot.inboxItems.count)"),
                        ("Search", store.searchText.isEmpty ? "Off" : "On"),
                        ("Hints", "\(store.snapshot.assistantSuggestions.count)")
                    ]
                )

                LazyVGrid(columns: workspaceColumns, spacing: 18) {
                    SurfaceCard(
                        title: "Captured Items",
                        subtitle: "Fresh intent waiting to become action",
                        accent: FlowTheme.warmAccent
                    ) {
                        if store.filteredInboxItems.isEmpty {
                            EmptyStateCard(
                                title: "Inbox is clear",
                                detail: "Use Quick Capture from the toolbar or sidebar when something new lands."
                            )
                        } else {
                            VStack(spacing: 12) {
                                ForEach(store.filteredInboxItems) { task in
                                    TaskRow(
                                        task: task,
                                        isSelected: store.selectedTaskID == task.id,
                                        onSelect: {
                                            store.select(task: task)
                                        },
                                        onArchive: {
                                            store.archive(task)
                                        }
                                    )
                                }
                            }
                        }
                    }

                    SurfaceCard(
                        title: "Clarify Rhythm",
                        subtitle: "Stay deliberate instead of bulk-processing every item",
                        accent: FlowTheme.coolAccent
                    ) {
                        VStack(alignment: .leading, spacing: 16) {
                            GuidanceList(items: [
                                "Clarify the newest capture first while the context is still fresh.",
                                "Turn project-shaped captures into visible outcomes rather than anonymous tasks.",
                                store.selectedTask == nil
                                    ? "Select an inbox item to inspect tags, timing, and likely next-step framing."
                                    : "Current focus: \(store.selectedTask?.title ?? "")"
                            ])

                            Button {
                                store.beginClarify()
                            } label: {
                                Label("Clarify Selected Capture", systemImage: "wand.and.stars")
                                    .frame(maxWidth: .infinity)
                            }
                            .buttonStyle(.borderedProminent)
                            .tint(FlowTheme.coolAccent)
                            .disabled(store.selectedTask == nil)
                        }
                    }
                }
            }
        }
    }
}

struct ProjectsWorkspaceView: View {
    @ObservedObject var store: WorkspaceStore

    var body: some View {
        WorkspaceShell(store: store) {
            VStack(alignment: .leading, spacing: 20) {
                WorkspaceHeader(
                    section: .projects,
                    headline: "Project state stays visible without crowding the day",
                    metrics: [
                        ("Active", "\(store.snapshot.projects.count)"),
                        ("Tracked", "\(store.filteredProjectTasks.count)"),
                        ("Visible", store.searchText.isEmpty ? "All" : "Filtered")
                    ]
                )

                if store.filteredProjects.isEmpty {
                    SurfaceCard(title: "No active projects", subtitle: "Turn clusters of work into visible outcomes", accent: FlowTheme.tealAccent) {
                        EmptyStateCard(
                            title: "Projects will appear here",
                            detail: "As project-shaped work emerges, this area can keep next actions visible without flooding Today."
                        )
                    }
                    .frame(maxWidth: .infinity, alignment: .leading)
                } else {
                    LazyVStack(alignment: .leading, spacing: ProjectsWorkspaceLayoutMetrics.projectCardSpacing) {
                        ForEach(store.filteredProjects) { project in
                            SurfaceCard(title: project.title, subtitle: project.summary, accent: FlowTheme.tealAccent) {
                                VStack(alignment: .leading, spacing: 14) {
                                    HStack(spacing: 10) {
                                        MetricBadge(label: "Active", value: "\(project.activeCount)", accent: FlowTheme.tealAccent)
                                        MetricBadge(label: "Done", value: "\(project.completedCount)", accent: FlowTheme.success)
                                    }

                                    if let nextActionTitle = project.nextActionTitle {
                                        DetailTile(label: "Next Action", value: nextActionTitle, accent: FlowTheme.coolAccent)
                                    }

                                    VStack(spacing: 12) {
                                        ForEach(project.tasks) { task in
                                            TaskRow(
                                                task: task,
                                                isSelected: store.selectedTaskID == task.id,
                                                onSelect: {
                                                    store.select(task: task)
                                                },
                                                onComplete: {
                                                    store.markDone(task)
                                                },
                                                onArchive: {
                                                    store.archive(task)
                                                }
                                            )
                                        }
                                    }
                                }
                            }
                            .frame(maxWidth: .infinity, alignment: .leading)
                        }
                    }
                    .frame(maxWidth: .infinity, alignment: .leading)
                }
            }
        }
    }
}

struct ReviewWorkspaceView: View {
    @ObservedObject var store: WorkspaceStore

    var body: some View {
        WorkspaceShell(store: store) {
            VStack(alignment: .leading, spacing: 20) {
                WorkspaceHeader(
                    section: .review,
                    headline: store.snapshot.review.headline,
                    metrics: [
                        ("Wins", "\(store.snapshot.review.completedThisWeek)"),
                        ("Stale", "\(store.snapshot.review.staleCount)"),
                        ("Due Soon", "\(store.snapshot.review.dueSoonCount)")
                    ]
                )

                SurfaceCard(title: "Review Focus", subtitle: store.snapshot.review.prompt, accent: FlowTheme.roseAccent) {
                    VStack(alignment: .leading, spacing: 14) {
                        Text("Work from left to right: clear stale commitments that should leave the system, then jump into the workspace that resolves the rest.")
                            .font(.system(size: 13, weight: .medium))
                            .foregroundStyle(FlowTheme.textSecondary)

                        LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible())], spacing: 10) {
                            DetailTile(label: "Wins", value: "\(store.weeklyReviewPackage.completedWork.count)", accent: FlowTheme.success)
                            DetailTile(label: "Stale", value: "\(store.reviewArchiveActions.count)", accent: FlowTheme.roseAccent)
                            DetailTile(label: "Guided", value: "\(store.reviewGuidedActions.count)", accent: FlowTheme.coolAccent)
                            DetailTile(label: "Generated", value: store.weeklyReviewPackage.generatedAtLabel, accent: FlowTheme.tealAccent)
                        }

                        if let reviewLastActionFeedback = store.reviewLastActionFeedback {
                            Text(reviewLastActionFeedback)
                                .font(.system(size: 12, weight: .semibold))
                                .foregroundStyle(FlowTheme.coolAccent)
                                .frame(maxWidth: .infinity, alignment: .leading)
                                .padding(.horizontal, 14)
                                .padding(.vertical, 12)
                                .background(
                                    RoundedRectangle(cornerRadius: 18, style: .continuous)
                                        .fill(FlowTheme.sidebar.opacity(0.88))
                                        .overlay(
                                            RoundedRectangle(cornerRadius: 18, style: .continuous)
                                                .stroke(FlowTheme.coolAccent.opacity(0.3), lineWidth: 1)
                                        )
                                )
                        }
                    }
                }

                LazyVGrid(columns: workspaceColumns, spacing: 18) {
                    SurfaceCard(title: "Archive Stale Items", subtitle: store.reviewArchiveSelectionSummary, accent: FlowTheme.roseAccent) {
                        VStack(alignment: .leading, spacing: 12) {
                            if store.reviewArchiveActions.isEmpty {
                                EmptyStateCard(
                                    title: "No stale cleanup is queued",
                                    detail: "Review can move straight into inbox, projects, or deadline checks."
                                )
                            } else {
                                ForEach(store.reviewArchiveActions) { action in
                                    Toggle(isOn: Binding(
                                        get: { store.selectedReviewActionIDs.contains(action.id) },
                                        set: { _ in store.toggleReviewAction(id: action.id) }
                                    )) {
                                        VStack(alignment: .leading, spacing: 4) {
                                            HStack {
                                                Text(action.title)
                                                    .font(.system(size: 13, weight: .semibold))
                                                    .foregroundStyle(FlowTheme.textPrimary)
                                                Spacer()
                                                StatusPill(title: "Archives now", accent: FlowTheme.roseAccent)
                                            }
                                            Text(action.detail)
                                                .font(.system(size: 12, weight: .medium))
                                                .foregroundStyle(FlowTheme.textSecondary)
                                        }
                                    }
                                    .toggleStyle(.checkbox)
                                }

                                Button(store.reviewApplyButtonTitle) {
                                    store.applySelectedReviewActions()
                                }
                                .disabled(store.selectedReviewActionIDs.isEmpty)
                                .buttonStyle(.borderedProminent)
                                .tint(FlowTheme.roseAccent)
                            }
                        }
                    }

                    SurfaceCard(title: "Guided Follow-Up", subtitle: "These actions do not mutate state here. Open the right workspace and finish the decision there.", accent: FlowTheme.coolAccent) {
                        VStack(spacing: 12) {
                            if store.reviewGuidedActions.isEmpty {
                                EmptyStateCard(
                                    title: "No guided follow-up is pending",
                                    detail: "Inbox, projects, and deadlines are already in a clean enough state."
                                )
                            } else {
                                ForEach(store.reviewGuidedActions) { action in
                                    VStack(alignment: .leading, spacing: 10) {
                                        Text(action.title)
                                            .font(.system(size: 13, weight: .semibold))
                                            .foregroundStyle(FlowTheme.textPrimary)
                                        Text(action.detail)
                                            .font(.system(size: 12, weight: .medium))
                                            .foregroundStyle(FlowTheme.textSecondary)

                                        switch action.kind {
                                        case "clarify_inbox":
                                            Button("Open Inbox") {
                                                store.openReviewGuidance(for: action)
                                            }
                                            .buttonStyle(.bordered)
                                        case "project_next_action_review":
                                            Button("Draft Next Action") {
                                                store.triggerReviewGuidedAction(action)
                                            }
                                            .buttonStyle(.bordered)
                                        case "deadline_review":
                                            Button("Open Today") {
                                                store.openReviewGuidance(for: action)
                                            }
                                            .buttonStyle(.bordered)
                                        default:
                                            Button(store.reviewGuidanceButtonTitle(for: action)) {
                                                store.triggerReviewGuidedAction(action)
                                            }
                                            .buttonStyle(.bordered)
                                        }
                                    }
                                    .frame(maxWidth: .infinity, alignment: .leading)
                                    .padding(14)
                                    .background(
                                        RoundedRectangle(cornerRadius: 20, style: .continuous)
                                            .fill(FlowTheme.sidebar.opacity(0.84))
                                            .overlay(
                                                RoundedRectangle(cornerRadius: 20, style: .continuous)
                                                    .stroke(FlowTheme.stroke, lineWidth: 1)
                                            )
                                    )
                                }
                            }
                        }
                    }

                    SurfaceCard(title: "Aging Items", subtitle: "Inspect the commitments that are candidates for archiving or reframing.", accent: FlowTheme.warmAccent) {
                        if store.filteredStaleItems.isEmpty {
                            EmptyStateCard(
                                title: "No stale work is surfacing",
                                detail: "The system is relatively current. Maintain the discipline rather than widening scope."
                            )
                        } else {
                            VStack(spacing: 12) {
                                ForEach(store.filteredStaleItems) { task in
                                    TaskRow(
                                        task: task,
                                        isSelected: store.selectedTaskID == task.id,
                                        onSelect: {
                                            store.select(task: task)
                                        },
                                        onComplete: {
                                            store.markDone(task)
                                        },
                                        onArchive: {
                                            store.archive(task)
                                        }
                                    )
                                }
                            }
                        }
                    }

                    SurfaceCard(title: "Project Health", subtitle: "Projects that need a next action or confirmation", accent: FlowTheme.tealAccent) {
                        VStack(spacing: 12) {
                            ForEach(store.weeklyReviewPackage.projectHealth) { health in
                                VStack(alignment: .leading, spacing: 8) {
                                    HStack {
                                        Text(health.title)
                                            .font(.system(size: 14, weight: .semibold))
                                            .foregroundStyle(FlowTheme.textPrimary)
                                        Spacer()
                                        StatusPill(title: health.statusLabel, accent: FlowTheme.tealAccent)
                                    }
                                    Text(health.detail)
                                        .font(.system(size: 12, weight: .medium))
                                        .foregroundStyle(FlowTheme.textSecondary)
                                }
                                .frame(maxWidth: .infinity, alignment: .leading)
                                .padding(14)
                                .background(
                                    RoundedRectangle(cornerRadius: 20, style: .continuous)
                                        .fill(FlowTheme.sidebar.opacity(0.84))
                                        .overlay(
                                            RoundedRectangle(cornerRadius: 20, style: .continuous)
                                                .stroke(FlowTheme.stroke, lineWidth: 1)
                                        )
                                )
                            }
                        }
                    }
                }
            }
        }
    }
}

struct AssistantWorkspaceView: View {
    @ObservedObject var store: WorkspaceStore

    var body: some View {
        WorkspaceShell(store: store) {
            VStack(alignment: .leading, spacing: 20) {
                WorkspaceHeader(
                    section: .assistant,
                    headline: "Assistant previews should feel bounded, legible, and recoverable",
                    metrics: [
                        ("Suggestions", "\(store.snapshot.assistantSuggestions.count)"),
                        ("Selected", store.selectedTask != nil ? "1" : "0"),
                        ("Writes", "Previewed")
                    ]
                )

                LazyVGrid(columns: workspaceColumns, spacing: 18) {
                    SurfaceCard(title: "Action Previews", subtitle: "High-trust assistant behavior starts with explicit previews", accent: FlowTheme.warmAccent) {
                        VStack(spacing: 14) {
                            ForEach(store.snapshot.assistantSuggestions) { suggestion in
                                VStack(alignment: .leading, spacing: 8) {
                                    HStack {
                                        Text(suggestion.title)
                                            .font(.system(size: 14, weight: .semibold))
                                            .foregroundStyle(FlowTheme.textPrimary)
                                        Spacer()
                                        StatusPill(title: suggestion.outcomeLabel, accent: FlowTheme.warmAccent)
                                    }
                                    Text(suggestion.detail)
                                        .font(.system(size: 12, weight: .medium))
                                        .foregroundStyle(FlowTheme.textSecondary)
                                }
                                .frame(maxWidth: .infinity, alignment: .leading)
                                .padding(14)
                                .background(
                                    RoundedRectangle(cornerRadius: 20, style: .continuous)
                                        .fill(FlowTheme.sidebar.opacity(0.84))
                                        .overlay(
                                            RoundedRectangle(cornerRadius: 20, style: .continuous)
                                                .stroke(FlowTheme.stroke, lineWidth: 1)
                                        )
                                )
                            }
                        }
                    }

                    SurfaceCard(title: "Trust Contract", subtitle: "Preview, explain, and keep every destructive action explicit", accent: FlowTheme.coolAccent) {
                        GuidanceList(items: [
                            "Do not silently move tasks between inbox, plan, and archive states.",
                            "Show the selected task context next to any proposed write.",
                            "Keep verifier language concrete enough that the user can say yes or no quickly."
                        ])
                    }
                }
            }
        }
    }
}

struct MemoryWorkspaceView: View {
    @ObservedObject var store: WorkspaceStore

    var body: some View {
        WorkspaceShell(store: store) {
            VStack(alignment: .leading, spacing: 20) {
                WorkspaceHeader(
                    section: .memory,
                    headline: "Remembered behavior must stay inspectable and editable",
                    metrics: [
                        ("Entries", "\(store.snapshot.memoryEntries.count)"),
                        ("Scope", "Mixed"),
                        ("Bias", "Visible")
                    ]
                )

                LazyVGrid(columns: workspaceColumns, spacing: 18) {
                    SurfaceCard(title: "Behavior Signals", subtitle: "Visible product memory, not hidden adaptation", accent: FlowTheme.coolAccent) {
                        VStack(spacing: 14) {
                            ForEach(store.snapshot.memoryEntries) { entry in
                                VStack(alignment: .leading, spacing: 8) {
                                    HStack {
                                        Text(entry.title)
                                            .font(.system(size: 14, weight: .semibold))
                                            .foregroundStyle(FlowTheme.textPrimary)
                                        Spacer()
                                        StatusPill(title: entry.scopeLabel, accent: FlowTheme.coolAccent)
                                    }
                                    Text(entry.detail)
                                        .font(.system(size: 12, weight: .medium))
                                        .foregroundStyle(FlowTheme.textSecondary)
                                    Text(entry.confidenceLabel)
                                        .font(.system(size: 11, weight: .semibold))
                                        .foregroundStyle(FlowTheme.warmAccent)
                                }
                                .frame(maxWidth: .infinity, alignment: .leading)
                                .padding(14)
                                .background(
                                    RoundedRectangle(cornerRadius: 20, style: .continuous)
                                        .fill(FlowTheme.sidebar.opacity(0.84))
                                        .overlay(
                                            RoundedRectangle(cornerRadius: 20, style: .continuous)
                                                .stroke(FlowTheme.stroke, lineWidth: 1)
                                        )
                                )
                            }
                        }
                    }

                    SurfaceCard(title: "Memory Guardrails", subtitle: "Preferences should stay editable, scoped, and easy to contest", accent: FlowTheme.tealAccent) {
                        GuidanceList(items: [
                            "Explain why a remembered pattern is affecting this workspace.",
                            "Prefer small, readable memory entries over opaque aggregate profiles.",
                            "Treat memory as editable product state, not hidden model tuning."
                        ])
                    }
                }
            }
        }
    }
}

struct WorkspaceShell<Content: View>: View {
    @ObservedObject var store: WorkspaceStore
    private let scrollsContent: Bool
    private let content: Content

    init(store: WorkspaceStore, scrollsContent: Bool = true, @ViewBuilder content: () -> Content) {
        self.store = store
        self.scrollsContent = scrollsContent
        self.content = content()
    }

    var body: some View {
        HStack(spacing: 0) {
            if scrollsContent {
                ScrollView {
                    paddedContent
                        .frame(maxWidth: .infinity, alignment: .leading)
                }
                .background(Color.clear)
            } else {
                paddedContent
                    .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topLeading)
                    .background(Color.clear)
            }

            if store.isInspectorPresented {
                Divider()
                    .overlay(FlowTheme.strokeStrong)

                InspectorPanel(store: store)
                    .frame(width: WorkspaceInspectorMetrics.inspectorWidth)
                    .transition(.move(edge: .trailing).combined(with: .opacity))
            }
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topLeading)
    }

    private var paddedContent: some View {
        content
            .padding(24)
            .padding(.top, WindowChromeMetrics.contentTopPadding)
    }
}

struct GuidanceList: View {
    let items: [String]

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            ForEach(Array(items.enumerated()), id: \.offset) { entry in
                HStack(alignment: .top, spacing: 10) {
                    Circle()
                        .fill(FlowTheme.textMuted)
                        .frame(width: 5, height: 5)
                        .padding(.top, 6)
                    Text(entry.element)
                        .font(.system(size: 12, weight: .medium))
                        .foregroundStyle(FlowTheme.textSecondary)
                        .fixedSize(horizontal: false, vertical: true)
                }
            }
        }
    }
}

private struct InspectorPanel: View {
    @ObservedObject var store: WorkspaceStore

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 16) {
                SurfaceCard(
                    title: "Selection",
                    subtitle: store.selectedTask?.projectName ?? "Current focus",
                    accent: selectedAccent
                ) {
                    if let task = store.selectedTask {
                        VStack(alignment: .leading, spacing: 14) {
                            Text(task.title)
                                .font(.system(size: 19, weight: .semibold))
                                .foregroundStyle(FlowTheme.textPrimary)
                            Text(task.summary)
                                .font(.system(size: 13, weight: .medium))
                                .foregroundStyle(FlowTheme.textSecondary)

                            LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible())], spacing: 10) {
                                DetailTile(label: "Status", value: task.status.label, accent: FlowTheme.taskAccent(for: task.status))
                                DetailTile(label: "Source", value: task.source.rawValue.capitalized, accent: FlowTheme.coolAccent)
                                if let dueLabel = task.dueLabel {
                                    DetailTile(label: "Due", value: dueLabel, accent: FlowTheme.warmAccent)
                                }
                                if let estimatedMinutes = task.estimatedMinutes {
                                    DetailTile(label: "Estimate", value: "\(estimatedMinutes) min", accent: FlowTheme.tealAccent)
                                }
                                if let updated = task.lastUpdatedLabel {
                                    DetailTile(label: "Updated", value: updated, accent: FlowTheme.roseAccent)
                                }
                                if let projectName = task.projectName {
                                    DetailTile(label: "Project", value: projectName, accent: FlowTheme.coolAccent)
                                }
                            }

                            if task.tags.isEmpty == false {
                                WrappingPillRow(tags: task.tags)
                            }

                            HStack(spacing: 10) {
                                Button {
                                    store.markDone(task)
                                } label: {
                                    Label("Complete", systemImage: "checkmark.circle.fill")
                                }
                                .buttonStyle(.borderedProminent)
                                .tint(FlowTheme.success)

                                Button {
                                    store.archive(task)
                                } label: {
                                    Label("Archive", systemImage: "archivebox")
                                }
                                .buttonStyle(.bordered)
                            }
                        }
                    } else {
                        EmptyStateCard(
                            title: "Nothing selected",
                            detail: "Use the arrow keys or click any task card to bring its context and actions into the inspector."
                        )
                    }
                }

                if let task = store.selectedTask, task.source == .assistant {
                    SurfaceCard(title: "Assistant Basis", subtitle: "Why this task is here", accent: FlowTheme.warmAccent) {
                        GuidanceList(items: store.snapshot.assistantSuggestions.prefix(2).map(\.title))
                    }
                }
            }
            .padding(20)
            .padding(.top, WindowChromeMetrics.contentTopPadding)
        }
        .background(RailBackdrop())
    }

    private var selectedAccent: Color {
        guard let task = store.selectedTask else {
            return FlowTheme.accent(for: store.selectedSection)
        }
        return FlowTheme.taskAccent(for: task.status)
    }
}

private struct WrappingPillRow: View {
    let tags: [String]

    var body: some View {
        HStack(spacing: 8) {
            ForEach(tags.prefix(4), id: \.self) { tag in
                StatusPill(title: tag, accent: FlowTheme.surfaceRaised)
            }
            Spacer(minLength: 0)
        }
    }
}

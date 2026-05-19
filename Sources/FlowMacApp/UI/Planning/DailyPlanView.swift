import SwiftUI

enum DailyPlanLayoutMetrics {
    static let primaryTaskLimit = 3
    static let secondaryTaskLimit = 2
}

struct DailyPlanView: View {
    @ObservedObject var store: WorkspaceStore
    @State private var isReasoningExpanded = false

    private let primaryLimit = DailyPlanLayoutMetrics.primaryTaskLimit
    private let secondaryLimit = DailyPlanLayoutMetrics.secondaryTaskLimit

    var body: some View {
        SurfaceCard(title: "Daily Plan", subtitle: "Pick up to 3 primary tasks and 2 secondary tasks.", accent: FlowTheme.coolAccent) {
            VStack(alignment: .leading, spacing: 16) {
                reasoningDisclosure

                planBucket(
                    title: "Primary Tasks",
                    limit: primaryLimit,
                    taskIDs: store.dailyPlanDraftTopItemIDs,
                    emptyText: "Commit the few tasks that deserve the day."
                )
                planBucket(
                    title: "Secondary Tasks",
                    limit: secondaryLimit,
                    taskIDs: store.dailyPlanDraftBonusItemIDs,
                    emptyText: "Keep bonus work optional so it cannot crowd focus."
                )

                candidateSection(title: "Must Address", tasks: store.dailyPlanState.mustAddress)
                candidateSection(title: "Inbox", tasks: store.dailyPlanState.inbox)
                candidateSection(title: "Ready Actions", tasks: store.dailyPlanState.readyActions)
                candidateSection(title: "Project Tasks", tasks: store.dailyPlanState.projectTasks)

                HStack {
                    Spacer()
                    Button("Confirm Daily Plan") {
                        store.saveDailyPlan()
                    }
                    .buttonStyle(.borderedProminent)
                    .tint(FlowTheme.coolAccent)
                }
            }
        }
    }

    private var reasoningDisclosure: some View {
        DisclosureGroup(isExpanded: $isReasoningExpanded) {
            VStack(alignment: .leading, spacing: 10) {
                if store.dailyPlanState.riskFlags.isEmpty == false {
                    GuidanceList(items: store.dailyPlanState.riskFlags)
                }

                Text(store.dailyPlanState.calendarStatus)
                    .font(.system(size: 12, weight: .medium))
                    .foregroundStyle(FlowTheme.textSecondary)

                if store.notificationPolicy.degradedReasons.isEmpty == false {
                    GuidanceList(items: store.notificationPolicy.degradedReasons)
                }
            }
            .padding(.top, 8)
        } label: {
            Label("View planning reasons", systemImage: "info.circle")
                .font(.system(size: 12, weight: .semibold))
                .foregroundStyle(FlowTheme.textSecondary)
        }
    }

    private func planBucket(title: String, limit: Int, taskIDs: [String], emptyText: String) -> some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack {
                Text(title)
                    .font(.system(size: 12, weight: .bold))
                    .foregroundStyle(FlowTheme.textMuted)
                Spacer()
                Text("\(min(taskIDs.count, limit))/\(limit)")
                    .font(.system(size: 11, weight: .semibold))
                    .foregroundStyle(FlowTheme.textMuted)
            }

            if taskIDs.isEmpty {
                Text(emptyText)
                    .font(.system(size: 12, weight: .medium))
                    .foregroundStyle(FlowTheme.textSecondary)
            } else {
                ForEach(taskIDs, id: \.self) { id in
                    HStack {
                        Text(taskTitle(for: id))
                            .font(.system(size: 13, weight: .semibold))
                            .foregroundStyle(FlowTheme.textPrimary)
                        Spacer()
                        Button {
                            store.removeDailyPlanItem(id: id)
                        } label: {
                            Label("Remove", systemImage: "minus.circle")
                        }
                        .labelStyle(.iconOnly)
                    }
                }
            }
        }
    }

    private func candidateSection(title: String, tasks: [FlowTask]) -> some View {
        VStack(alignment: .leading, spacing: 10) {
            Text(title)
                .font(.system(size: 12, weight: .bold))
                .foregroundStyle(FlowTheme.textMuted)

            if tasks.isEmpty {
                Text("No items in this planning bucket.")
                    .font(.system(size: 12, weight: .medium))
                    .foregroundStyle(FlowTheme.textSecondary)
            } else {
                ForEach(tasks) { task in
                    HStack(alignment: .top, spacing: 10) {
                        VStack(alignment: .leading, spacing: 4) {
                            Text(task.title)
                                .font(.system(size: 13, weight: .semibold))
                                .foregroundStyle(FlowTheme.textPrimary)
                            Text(task.summary)
                                .font(.system(size: 11, weight: .medium))
                                .foregroundStyle(FlowTheme.textSecondary)
                        }
                        Spacer()
                        Button {
                            store.addDailyPlanTopItem(id: task.id)
                        } label: {
                            Label("Primary", systemImage: "1.circle")
                        }
                        .disabled(store.dailyPlanDraftTopItemIDs.count >= primaryLimit)

                        Button {
                            store.addDailyPlanBonusItem(id: task.id)
                        } label: {
                            Label("Secondary", systemImage: "2.circle")
                        }
                        .disabled(store.dailyPlanDraftBonusItemIDs.count >= secondaryLimit)
                    }
                }
            }
        }
    }

    private func taskTitle(for id: String) -> String {
        let all = store.dailyPlanState.topItems
            + store.dailyPlanState.bonusItems
            + store.dailyPlanState.mustAddress
            + store.dailyPlanState.inbox
            + store.dailyPlanState.readyActions
            + store.dailyPlanState.projectTasks
        return all.first(where: { $0.id == id })?.title ?? id
    }
}

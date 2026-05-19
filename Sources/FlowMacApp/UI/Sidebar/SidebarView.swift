import SwiftUI

struct SidebarView: View {
    @ObservedObject var store: WorkspaceStore

    @Namespace private var selectionAnimation
    @State private var hoveredSection: FlowSection?

    var body: some View {
        VStack(alignment: .leading, spacing: 18) {
            brandCard

            Text("Workspace")
                .font(.system(size: 11, weight: .bold))
                .kerning(1.3)
                .foregroundStyle(FlowTheme.textMuted)
                .padding(.horizontal, 18)

            ScrollView {
                VStack(spacing: 8) {
                    ForEach(FlowSection.allCases) { section in
                        sidebarRow(for: section)
                    }
                }
                .padding(.horizontal, 12)
                .padding(.bottom, 12)
            }

            quickCaptureCard
        }
        .padding(.top, WindowChromeMetrics.sidebarTopPadding)
        .padding(.bottom, 14)
        .background(SidebarBackdrop())
    }

    private var brandCard: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("At A Glance")
                .font(.system(size: 11, weight: .bold))
                .kerning(1.2)
                .foregroundStyle(FlowTheme.textMuted)

            HStack(spacing: 10) {
                MetricBadge(
                    label: "Focus",
                    value: "\(store.snapshot.todayItems.count)",
                    accent: FlowTheme.coolAccent
                )
                MetricBadge(
                    label: "Inbox",
                    value: "\(store.snapshot.inboxItems.count)",
                    accent: FlowTheme.warmAccent
                )
            }

            Text("Capture lightly and keep the visible day narrow.")
                .font(.system(size: 11, weight: .medium))
                .foregroundStyle(FlowTheme.textSecondary)
                .fixedSize(horizontal: false, vertical: true)
        }
        .padding(18)
        .background(
            RoundedRectangle(cornerRadius: 24, style: .continuous)
                .fill(FlowTheme.surface.opacity(0.86))
                .overlay(
                    RoundedRectangle(cornerRadius: 24, style: .continuous)
                        .stroke(FlowTheme.strokeStrong, lineWidth: 1)
                )
        )
        .padding(.horizontal, 12)
    }

    private func sidebarRow(for section: FlowSection) -> some View {
        let isSelected = store.selectedSection == section
        let isHovered = hoveredSection == section
        let accent = FlowTheme.accent(for: section)

        return Button {
            withAnimation(.spring(response: 0.32, dampingFraction: 0.86)) {
                store.select(section: section)
            }
        } label: {
            HStack(spacing: 12) {
                SectionBadge(section: section, size: 36)

                VStack(alignment: .leading, spacing: 3) {
                    Text(section.title)
                        .font(.system(size: 14, weight: .semibold))
                        .foregroundStyle(FlowTheme.textPrimary)
                    Text(section.subtitle)
                        .font(.system(size: 11, weight: .medium))
                        .foregroundStyle(FlowTheme.textSecondary)
                }

                Spacer(minLength: 12)

                if badgeValue(for: section) > 0 {
                    Text("\(badgeValue(for: section))")
                        .font(.system(size: 11, weight: .bold))
                        .foregroundStyle(FlowTheme.textPrimary)
                        .padding(.horizontal, 9)
                        .padding(.vertical, 6)
                        .background(
                            Capsule(style: .continuous)
                                .fill(isSelected ? accent.opacity(0.22) : FlowTheme.surfaceRaised.opacity(0.82))
                                .overlay(
                                    Capsule(style: .continuous)
                                        .stroke(isSelected ? accent.opacity(0.28) : Color.clear, lineWidth: 1)
                                )
                        )
                }
            }
            .padding(.horizontal, 12)
            .padding(.vertical, 11)
            .background(rowBackground(isSelected: isSelected, isHovered: isHovered, accent: accent))
        }
        .buttonStyle(.plain)
        .onHover { hovering in
            withAnimation(.easeOut(duration: 0.14)) {
                hoveredSection = hovering ? section : nil
            }
        }
    }

    private func rowBackground(isSelected: Bool, isHovered: Bool, accent: Color) -> some View {
        ZStack {
            if isSelected {
                RoundedRectangle(cornerRadius: 20, style: .continuous)
                    .fill(
                        LinearGradient(
                            colors: [FlowTheme.surfacePressed.opacity(0.92), FlowTheme.surfaceRaised.opacity(0.82)],
                            startPoint: .topLeading,
                            endPoint: .bottomTrailing
                        )
                    )
                    .matchedGeometryEffect(id: "sidebar-selection", in: selectionAnimation)
            } else if isHovered {
                RoundedRectangle(cornerRadius: 20, style: .continuous)
                    .fill(FlowTheme.surfaceRaised.opacity(0.34))
            }

            RoundedRectangle(cornerRadius: 20, style: .continuous)
                .stroke(isSelected ? accent.opacity(0.34) : Color.clear, lineWidth: 1)
        }
    }

    private var quickCaptureCard: some View {
        Button {
            store.isCapturePresented = true
        } label: {
            HStack(spacing: 12) {
                Image(systemName: "plus.circle.fill")
                    .font(.system(size: 20, weight: .semibold))
                    .foregroundStyle(FlowTheme.warmAccent)

                VStack(alignment: .leading, spacing: 3) {
                    Text("Quick Capture")
                        .font(.system(size: 14, weight: .semibold))
                        .foregroundStyle(FlowTheme.textPrimary)
                    Text("Store it now, clarify it later.")
                        .font(.system(size: 11, weight: .medium))
                        .foregroundStyle(FlowTheme.textSecondary)
                }
                Spacer()
                Text("⌘N")
                    .font(.system(size: 11, weight: .bold, design: .rounded))
                    .foregroundStyle(FlowTheme.textMuted)
                    .padding(.horizontal, 8)
                    .padding(.vertical, 5)
                    .background(
                        Capsule(style: .continuous)
                            .fill(FlowTheme.surfaceRaised.opacity(0.84))
                    )
            }
            .padding(14)
            .background(
                RoundedRectangle(cornerRadius: 22, style: .continuous)
                    .fill(FlowTheme.surface.opacity(0.88))
                    .overlay(
                        RoundedRectangle(cornerRadius: 22, style: .continuous)
                            .stroke(FlowTheme.strokeStrong, lineWidth: 1)
                    )
            )
            .padding(.horizontal, 12)
        }
        .buttonStyle(.plain)
    }

    private func badgeValue(for section: FlowSection) -> Int {
        switch section {
        case .today:
            return store.snapshot.todayItems.count
        case .inbox:
            return store.snapshot.inboxItems.count
        case .projects:
            return store.snapshot.projects.count
        case .review:
            return store.snapshot.review.staleCount
        case .assistant:
            return store.assistantSessions.count
        case .memory:
            return store.memoryRecords.count
        }
    }
}

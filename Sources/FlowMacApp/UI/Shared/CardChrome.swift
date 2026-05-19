import SwiftUI

enum WindowChromeMetrics {
    static let contentTopPadding: CGFloat = 0
    static let sidebarTopPadding: CGFloat = 16
}

enum FlowTheme {
    static let canvas = Color(red: 0.047, green: 0.063, blue: 0.086)
    static let canvasTop = Color(red: 0.088, green: 0.112, blue: 0.161)
    static let canvasBottom = Color(red: 0.036, green: 0.047, blue: 0.067)

    static let sidebar = Color(red: 0.079, green: 0.098, blue: 0.133)
    static let rail = Color(red: 0.084, green: 0.094, blue: 0.129)

    static let surface = Color(red: 0.106, green: 0.129, blue: 0.169)
    static let surfaceRaised = Color(red: 0.138, green: 0.164, blue: 0.216)
    static let surfacePressed = Color(red: 0.17, green: 0.194, blue: 0.247)
    static let surfaceMuted = Color(red: 0.124, green: 0.145, blue: 0.188)

    static let stroke = Color.white.opacity(0.08)
    static let strokeStrong = Color.white.opacity(0.16)
    static let textPrimary = Color(red: 0.965, green: 0.972, blue: 0.988)
    static let textSecondary = Color.white.opacity(0.68)
    static let textMuted = Color.white.opacity(0.46)

    static let coolAccent = Color(red: 0.40, green: 0.70, blue: 0.97)
    static let warmAccent = Color(red: 0.95, green: 0.65, blue: 0.39)
    static let roseAccent = Color(red: 0.90, green: 0.49, blue: 0.58)
    static let tealAccent = Color(red: 0.42, green: 0.78, blue: 0.73)
    static let success = Color(red: 0.45, green: 0.80, blue: 0.60)
    static let danger = Color(red: 0.84, green: 0.41, blue: 0.44)

    static func accent(for section: FlowSection) -> Color {
        switch section {
        case .today: return coolAccent
        case .inbox: return warmAccent
        case .projects: return tealAccent
        case .review: return roseAccent
        case .assistant: return warmAccent
        case .memory: return coolAccent
        }
    }

    static func taskAccent(for status: FlowTaskStatus) -> Color {
        switch status {
        case .active: return coolAccent
        case .done: return success
        case .waiting: return warmAccent
        case .someday: return textSecondary
        case .archived: return textMuted
        }
    }
}

struct FlowBackdrop: View {
    var body: some View {
        ZStack {
            FlowTheme.canvas.ignoresSafeArea()
            LinearGradient(
                colors: [FlowTheme.canvasTop.opacity(0.42), FlowTheme.canvasBottom],
                startPoint: .topLeading,
                endPoint: .bottomTrailing
            )
            .ignoresSafeArea()
        }
    }
}

struct SidebarBackdrop: View {
    var body: some View {
        Rectangle()
            .fill(.regularMaterial)
            .overlay(FlowTheme.sidebar.opacity(0.56))
    }
}

struct RailBackdrop: View {
    var body: some View {
        LinearGradient(
            colors: [FlowTheme.rail.opacity(0.96), FlowTheme.surface.opacity(0.9)],
            startPoint: .top,
            endPoint: .bottom
        )
    }
}

struct SurfaceCard<Content: View>: View {
    let title: String
    let subtitle: String?
    let accent: Color
    private let content: Content

    @State private var isHovered = false

    init(
        title: String,
        subtitle: String? = nil,
        accent: Color = FlowTheme.coolAccent,
        @ViewBuilder content: () -> Content
    ) {
        self.title = title
        self.subtitle = subtitle
        self.accent = accent
        self.content = content()
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 18) {
            VStack(alignment: .leading, spacing: 6) {
                Text(title)
                    .font(.system(size: 15, weight: .semibold))
                    .foregroundStyle(FlowTheme.textPrimary)
                if let subtitle {
                    Text(subtitle)
                        .font(.system(size: 12, weight: .medium))
                        .foregroundStyle(FlowTheme.textSecondary)
                        .fixedSize(horizontal: false, vertical: true)
                }
            }
            content
        }
        .padding(20)
        .background(cardBackground)
        .scaleEffect(isHovered ? 1.006 : 1)
        .animation(.easeOut(duration: 0.18), value: isHovered)
        .onHover { hovering in
            isHovered = hovering
        }
    }

    private var cardBackground: some View {
        RoundedRectangle(cornerRadius: 24, style: .continuous)
            .fill(
                LinearGradient(
                    colors: [FlowTheme.surface.opacity(0.97), FlowTheme.surfaceMuted.opacity(0.92)],
                    startPoint: .topLeading,
                    endPoint: .bottomTrailing
                )
            )
            .overlay(
                RoundedRectangle(cornerRadius: 24, style: .continuous)
                    .strokeBorder(
                        LinearGradient(
                            colors: [FlowTheme.strokeStrong, FlowTheme.stroke.opacity(0.5)],
                            startPoint: .topLeading,
                            endPoint: .bottomTrailing
                        ),
                        lineWidth: 1
                    )
            )
            .shadow(color: .black.opacity(0.28), radius: 28, y: 16)
    }
}

struct SectionBadge: View {
    let section: FlowSection
    let size: CGFloat

    init(section: FlowSection, size: CGFloat = 42) {
        self.section = section
        self.size = size
    }

    var body: some View {
        ZStack {
            RoundedRectangle(cornerRadius: size * 0.32, style: .continuous)
                .fill(
                    LinearGradient(
                        colors: [FlowTheme.accent(for: section).opacity(0.34), FlowTheme.accent(for: section).opacity(0.12)],
                        startPoint: .topLeading,
                        endPoint: .bottomTrailing
                    )
                )
                .overlay(
                    RoundedRectangle(cornerRadius: size * 0.32, style: .continuous)
                        .stroke(FlowTheme.accent(for: section).opacity(0.35), lineWidth: 1)
                )
            Image(systemName: section.symbolName)
                .font(.system(size: size * 0.36, weight: .semibold))
                .foregroundStyle(FlowTheme.textPrimary)
        }
        .frame(width: size, height: size)
    }
}

struct ToolbarHeadlineChip: View {
    let section: FlowSection
    let headline: String

    var body: some View {
        HStack(spacing: 10) {
            Image(systemName: section.symbolName)
                .font(.system(size: 11, weight: .semibold))
                .foregroundStyle(FlowTheme.accent(for: section))
            Text(headline)
                .font(.system(size: 11, weight: .semibold))
                .lineLimit(1)
                .foregroundStyle(FlowTheme.textSecondary)
        }
        .padding(.horizontal, 10)
        .padding(.vertical, 5)
        .background(
            RoundedRectangle(cornerRadius: 12, style: .continuous)
                .fill(FlowTheme.surface.opacity(0.54))
                .overlay(
                    RoundedRectangle(cornerRadius: 12, style: .continuous)
                        .stroke(FlowTheme.stroke.opacity(0.8), lineWidth: 1)
                )
        )
    }
}

struct MetricBadge: View {
    let label: String
    let value: String
    var accent: Color = FlowTheme.coolAccent

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text(label.uppercased())
                .font(.system(size: 10, weight: .bold, design: .rounded))
                .kerning(1.2)
                .foregroundStyle(FlowTheme.textSecondary)
                .lineLimit(1)
            Text(value)
                .font(.system(size: 21, weight: .semibold, design: .rounded))
                .foregroundStyle(FlowTheme.textPrimary)
                .lineLimit(1)
        }
        .frame(minWidth: 92, alignment: .leading)
        .padding(.horizontal, 14)
        .padding(.vertical, 12)
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

struct TaskRow: View {
    let task: FlowTask
    let isSelected: Bool
    let onSelect: () -> Void
    var onComplete: (() -> Void)? = nil
    var onArchive: (() -> Void)? = nil

    @State private var isHovered = false

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack(alignment: .top, spacing: 12) {
                RoundedRectangle(cornerRadius: 3, style: .continuous)
                    .fill(taskAccent.opacity(isSelected ? 0.94 : 0.64))
                    .frame(width: 4, height: 52)

                VStack(alignment: .leading, spacing: 8) {
                    HStack(alignment: .top, spacing: 10) {
                        VStack(alignment: .leading, spacing: 6) {
                            Text(task.title)
                                .font(.system(size: 14, weight: .semibold))
                                .foregroundStyle(FlowTheme.textPrimary)
                                .multilineTextAlignment(.leading)
                            Text(task.summary)
                                .font(.system(size: 12, weight: .medium))
                                .foregroundStyle(FlowTheme.textSecondary)
                                .lineLimit(2)
                        }
                        Spacer(minLength: 10)
                        if let dueLabel = task.dueLabel {
                            StatusPill(
                                title: dueLabel,
                                accent: task.isFlagged ? FlowTheme.warmAccent : FlowTheme.surfaceRaised
                            )
                        }
                    }

                    HStack(spacing: 8) {
                        StatusPill(title: task.status.label, accent: taskAccent)
                        if let projectName = task.projectName {
                            StatusPill(title: projectName, accent: FlowTheme.coolAccent)
                        }
                        if let estimatedMinutes = task.estimatedMinutes {
                            StatusPill(title: "\(estimatedMinutes)m", accent: FlowTheme.surfaceRaised)
                        }
                        Spacer(minLength: 10)
                        if let lastUpdatedLabel = task.lastUpdatedLabel {
                            Text(lastUpdatedLabel)
                                .font(.system(size: 11, weight: .medium))
                                .foregroundStyle(FlowTheme.textMuted)
                        }
                    }
                }
            }

            if isHovered || isSelected {
                HStack(spacing: 8) {
                    if let onComplete {
                        IconActionButton(
                            systemName: "checkmark",
                            title: "Complete",
                            tint: FlowTheme.success,
                            action: onComplete
                        )
                    }
                    if let onArchive {
                        IconActionButton(
                            systemName: "archivebox",
                            title: "Archive",
                            tint: FlowTheme.textSecondary,
                            action: onArchive
                        )
                    }
                    Spacer()
                    if task.tags.isEmpty == false {
                        Text(task.tags.prefix(3).joined(separator: "  •  "))
                            .font(.system(size: 11, weight: .medium))
                            .foregroundStyle(FlowTheme.textMuted)
                            .lineLimit(1)
                    }
                }
                .transition(.move(edge: .top).combined(with: .opacity))
            }
        }
        .padding(16)
        .background(backgroundChrome)
        .overlay(alignment: .topTrailing) {
            if task.isFlagged {
                Image(systemName: "pin.fill")
                    .font(.system(size: 10, weight: .bold))
                    .foregroundStyle(FlowTheme.warmAccent)
                    .padding(12)
            }
        }
        .contentShape(RoundedRectangle(cornerRadius: 22, style: .continuous))
        .onTapGesture(perform: onSelect)
        .onHover { hovering in
            withAnimation(.easeOut(duration: 0.16)) {
                isHovered = hovering
            }
        }
        .animation(.easeOut(duration: 0.16), value: isSelected)
    }

    private var taskAccent: Color {
        FlowTheme.taskAccent(for: task.status)
    }

    private var backgroundChrome: some View {
        RoundedRectangle(cornerRadius: 22, style: .continuous)
            .fill(
                LinearGradient(
                    colors: [
                        isSelected ? FlowTheme.surfacePressed : FlowTheme.surfaceRaised.opacity(0.78),
                        isSelected ? FlowTheme.surfaceRaised : FlowTheme.sidebar.opacity(0.82)
                    ],
                    startPoint: .topLeading,
                    endPoint: .bottomTrailing
                )
            )
            .overlay(
                RoundedRectangle(cornerRadius: 22, style: .continuous)
                    .stroke(
                        isSelected ? taskAccent.opacity(0.58) : FlowTheme.stroke,
                        lineWidth: 1
                    )
            )
            .shadow(color: .black.opacity(isSelected ? 0.22 : 0.14), radius: isSelected ? 18 : 8, y: 8)
    }
}

struct StatusPill: View {
    let title: String
    let accent: Color

    var body: some View {
        Text(title)
            .font(.system(size: 11, weight: .semibold))
            .foregroundStyle(FlowTheme.textPrimary)
            .padding(.horizontal, 10)
            .padding(.vertical, 6)
            .background(
                Capsule(style: .continuous)
                    .fill(accent.opacity(0.18))
                    .overlay(Capsule(style: .continuous).stroke(accent.opacity(0.34), lineWidth: 1))
            )
    }
}

struct WorkspaceHeader: View {
    let section: FlowSection
    let headline: String
    let metrics: [(String, String)]

    var body: some View {
        VStack(alignment: .leading, spacing: 20) {
            HStack(alignment: .top, spacing: 16) {
                SectionBadge(section: section, size: 52)
                VStack(alignment: .leading, spacing: 8) {
                    Text(section.title)
                        .font(.system(size: 30, weight: .semibold, design: .rounded))
                        .foregroundStyle(FlowTheme.textPrimary)
                    Text(section.subtitle)
                        .font(.system(size: 13, weight: .semibold))
                        .foregroundStyle(FlowTheme.textSecondary)
                }
                Spacer()
            }

            Text(headline)
                .font(.system(size: 18, weight: .semibold))
                .foregroundStyle(FlowTheme.accent(for: section))
                .fixedSize(horizontal: false, vertical: true)

            ViewThatFits(in: .horizontal) {
                HStack(spacing: 10) {
                    ForEach(metrics, id: \.0) { metric in
                        MetricBadge(label: metric.0, value: metric.1, accent: FlowTheme.accent(for: section))
                    }
                }
                VStack(alignment: .leading, spacing: 10) {
                    ForEach(metrics, id: \.0) { metric in
                        MetricBadge(label: metric.0, value: metric.1, accent: FlowTheme.accent(for: section))
                    }
                }
            }
        }
        .padding(24)
        .background(
            RoundedRectangle(cornerRadius: 28, style: .continuous)
                .fill(
                    LinearGradient(
                        colors: [FlowTheme.surface.opacity(0.98), FlowTheme.surfaceMuted.opacity(0.9)],
                        startPoint: .topLeading,
                        endPoint: .bottomTrailing
                    )
                )
                .overlay(
                    RoundedRectangle(cornerRadius: 28, style: .continuous)
                        .stroke(FlowTheme.strokeStrong, lineWidth: 1)
                )
                .shadow(color: .black.opacity(0.28), radius: 34, y: 18)
        )
    }
}

struct EmptyStateCard: View {
    let title: String
    let detail: String

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text(title)
                .font(.system(size: 14, weight: .semibold))
                .foregroundStyle(FlowTheme.textPrimary)
            Text(detail)
                .font(.system(size: 12, weight: .medium))
                .foregroundStyle(FlowTheme.textSecondary)
                .fixedSize(horizontal: false, vertical: true)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(18)
        .background(
            RoundedRectangle(cornerRadius: 22, style: .continuous)
                .fill(FlowTheme.sidebar.opacity(0.82))
                .overlay(
                    RoundedRectangle(cornerRadius: 22, style: .continuous)
                        .stroke(FlowTheme.stroke, lineWidth: 1)
                )
        )
    }
}

struct IconActionButton: View {
    let systemName: String
    let title: String
    let tint: Color
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            Label(title, systemImage: systemName)
                .font(.system(size: 11, weight: .semibold))
                .foregroundStyle(FlowTheme.textPrimary)
                .padding(.horizontal, 10)
                .padding(.vertical, 7)
                .background(
                    Capsule(style: .continuous)
                        .fill(tint.opacity(0.16))
                        .overlay(Capsule(style: .continuous).stroke(tint.opacity(0.3), lineWidth: 1))
                )
        }
        .buttonStyle(.plain)
    }
}

struct DetailTile: View {
    let label: String
    let value: String
    var accent: Color = FlowTheme.coolAccent

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text(label.uppercased())
                .font(.system(size: 10, weight: .bold, design: .rounded))
                .kerning(1.1)
                .foregroundStyle(FlowTheme.textMuted)
            Text(value)
                .font(.system(size: 13, weight: .semibold))
                .foregroundStyle(FlowTheme.textPrimary)
                .fixedSize(horizontal: false, vertical: true)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(12)
        .background(
            RoundedRectangle(cornerRadius: 18, style: .continuous)
                .fill(FlowTheme.surfaceRaised.opacity(0.8))
                .overlay(
                    RoundedRectangle(cornerRadius: 18, style: .continuous)
                        .stroke(accent.opacity(0.22), lineWidth: 1)
                )
        )
    }
}

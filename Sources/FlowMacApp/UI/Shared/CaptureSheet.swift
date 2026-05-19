import SwiftUI

struct CaptureSheet: View {
    @ObservedObject var store: WorkspaceStore

    var body: some View {
        ZStack {
            FlowBackdrop()

            VStack(alignment: .leading, spacing: 18) {
                HStack(alignment: .top) {
                    VStack(alignment: .leading, spacing: 8) {
                        Text("Quick Capture")
                            .font(.system(size: 26, weight: .semibold, design: .rounded))
                            .foregroundStyle(FlowTheme.textPrimary)

                        Text("Store the raw thought first. Clarification can happen after it is safely inside Flow.")
                            .font(.system(size: 13, weight: .medium))
                            .foregroundStyle(FlowTheme.textSecondary)
                            .fixedSize(horizontal: false, vertical: true)
                    }

                    Spacer()

                    MetricBadge(
                        label: "Length",
                        value: "\(store.captureDraft.count)",
                        accent: FlowTheme.warmAccent
                    )
                }

                TextEditor(text: $store.captureDraft)
                    .font(.system(size: 15, weight: .medium))
                    .padding(14)
                    .frame(minHeight: 180)
                    .scrollContentBackground(.hidden)
                    .background(
                        RoundedRectangle(cornerRadius: 24, style: .continuous)
                            .fill(FlowTheme.sidebar.opacity(0.88))
                            .overlay(
                                RoundedRectangle(cornerRadius: 24, style: .continuous)
                                    .stroke(FlowTheme.strokeStrong, lineWidth: 1)
                            )
                    )

                VStack(alignment: .leading, spacing: 10) {
                    bullet("Captures can stay rough. Use natural language rather than forcing structure too early.")
                    bullet("If it turns into a project, let review or assistant workflows shape it later.")
                }

                HStack {
                    Button("Cancel") {
                        store.isCapturePresented = false
                        store.captureDraft = ""
                    }
                    .keyboardShortcut(.cancelAction)

                    Spacer()

                    Button {
                        store.capture()
                    } label: {
                        Label("Capture", systemImage: "plus.circle.fill")
                    }
                    .keyboardShortcut(.defaultAction)
                    .buttonStyle(.borderedProminent)
                    .tint(FlowTheme.warmAccent)
                }
            }
            .padding(26)
            .frame(width: 620)
            .background(
                RoundedRectangle(cornerRadius: 28, style: .continuous)
                    .fill(FlowTheme.surface.opacity(0.96))
                    .overlay(
                        RoundedRectangle(cornerRadius: 28, style: .continuous)
                            .stroke(FlowTheme.strokeStrong, lineWidth: 1)
                    )
                    .shadow(color: .black.opacity(0.32), radius: 28, y: 18)
            )
            .padding(24)
        }
    }

    private func bullet(_ text: String) -> some View {
        HStack(alignment: .top, spacing: 10) {
            Circle()
                .fill(FlowTheme.textMuted)
                .frame(width: 5, height: 5)
                .padding(.top, 6)
            Text(text)
                .font(.system(size: 12, weight: .medium))
                .foregroundStyle(FlowTheme.textSecondary)
                .fixedSize(horizontal: false, vertical: true)
        }
    }
}

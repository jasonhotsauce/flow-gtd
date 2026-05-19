import SwiftUI

struct ClarifyEditor: View {
    @ObservedObject var store: WorkspaceStore

    var body: some View {
        let binding = Binding<ClarifyDraft>(
            get: {
                store.clarifyDraft ?? ClarifyDraft(
                    inboxItemID: "missing",
                    rawText: "",
                    title: ""
                )
            },
            set: { store.clarifyDraft = $0 }
        )

        ZStack {
            FlowBackdrop()

            VStack(alignment: .leading, spacing: 18) {
                Text("Clarify Capture")
                    .font(.system(size: 26, weight: .semibold, design: .rounded))
                    .foregroundStyle(FlowTheme.textPrimary)

                Text("Shape the raw capture into either a task or a project before it joins the rest of the system.")
                    .font(.system(size: 13, weight: .medium))
                    .foregroundStyle(FlowTheme.textSecondary)
                    .fixedSize(horizontal: false, vertical: true)

                VStack(alignment: .leading, spacing: 8) {
                    Text("Raw Capture")
                        .font(.system(size: 12, weight: .bold))
                        .foregroundStyle(FlowTheme.textMuted)

                    Text(binding.wrappedValue.rawText)
                        .font(.system(size: 14, weight: .medium))
                        .foregroundStyle(FlowTheme.textPrimary)
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .padding(14)
                        .background(
                            RoundedRectangle(cornerRadius: 20, style: .continuous)
                                .fill(FlowTheme.sidebar.opacity(0.84))
                                .overlay(
                                    RoundedRectangle(cornerRadius: 20, style: .continuous)
                                        .stroke(FlowTheme.strokeStrong, lineWidth: 1)
                                )
                        )
                }

                VStack(alignment: .leading, spacing: 12) {
                    Text("Clarified Title")
                        .font(.system(size: 12, weight: .bold))
                        .foregroundStyle(FlowTheme.textMuted)

                    TextField("Describe the concrete outcome", text: binding.title)
                        .textFieldStyle(.plain)
                        .padding(14)
                        .background(
                            RoundedRectangle(cornerRadius: 18, style: .continuous)
                                .fill(FlowTheme.surfaceRaised.opacity(0.84))
                                .overlay(
                                    RoundedRectangle(cornerRadius: 18, style: .continuous)
                                        .stroke(FlowTheme.strokeStrong, lineWidth: 1)
                                )
                        )
                }

                VStack(alignment: .leading, spacing: 12) {
                    Text("Destination")
                        .font(.system(size: 12, weight: .bold))
                        .foregroundStyle(FlowTheme.textMuted)

                    Picker("Destination", selection: binding.destination) {
                        ForEach(ClarifyDestination.allCases) { destination in
                            Text(destination.title).tag(destination)
                        }
                    }
                    .pickerStyle(.segmented)
                }

                if binding.wrappedValue.destination == .task {
                    VStack(alignment: .leading, spacing: 12) {
                        Text("Project")
                            .font(.system(size: 12, weight: .bold))
                            .foregroundStyle(FlowTheme.textMuted)

                        TextField("Optional project name", text: binding.projectTitle)
                            .textFieldStyle(.plain)
                            .padding(14)
                            .background(
                                RoundedRectangle(cornerRadius: 18, style: .continuous)
                                    .fill(FlowTheme.surfaceRaised.opacity(0.84))
                                    .overlay(
                                        RoundedRectangle(cornerRadius: 18, style: .continuous)
                                            .stroke(FlowTheme.strokeStrong, lineWidth: 1)
                                    )
                            )
                    }
                }

                HStack {
                    Button("Cancel") {
                        store.cancelClarify()
                    }
                    .keyboardShortcut(.cancelAction)

                    Button("Reject") {
                        store.rejectClarify()
                    }

                    Spacer()

                    Button {
                        store.confirmClarify()
                    } label: {
                        Label("Apply", systemImage: "checkmark.circle.fill")
                    }
                    .buttonStyle(.borderedProminent)
                    .keyboardShortcut(.defaultAction)
                    .tint(FlowTheme.coolAccent)
                }
            }
            .padding(26)
            .frame(width: 640)
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
}

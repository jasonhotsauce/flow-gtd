import SwiftUI

struct MemoryView: View {
    @ObservedObject var store: WorkspaceStore

    var body: some View {
        WorkspaceShell(store: store) {
            VStack(alignment: .leading, spacing: 20) {
                WorkspaceHeader(
                    section: .memory,
                    headline: "Memory stays editable, scoped, and easy to challenge",
                    metrics: [
                        ("Entries", "\(store.memoryRecords.count)"),
                        ("Visible", "\(store.filteredMemoryRecords.count)"),
                        ("Disabled", "\(store.memoryRecords.filter { $0.enabled == false }.count)")
                    ]
                )

                LazyVGrid(columns: workspaceColumns, spacing: 18) {
                    SurfaceCard(title: "Memory Records", subtitle: "Searchable, inspectable product memory", accent: FlowTheme.coolAccent) {
                        if store.filteredMemoryRecords.isEmpty {
                            EmptyStateCard(title: "No memory records are visible", detail: "Use the assistant to save a preference or clear the search filter.")
                        } else {
                            VStack(spacing: 12) {
                                ForEach(store.filteredMemoryRecords) { record in
                                    Button {
                                        store.selectMemory(id: record.id)
                                    } label: {
                                        VStack(alignment: .leading, spacing: 8) {
                                            HStack {
                                                Text(record.value)
                                                    .font(.system(size: 13, weight: .semibold))
                                                    .foregroundStyle(FlowTheme.textPrimary)
                                                    .multilineTextAlignment(.leading)
                                                Spacer()
                                                StatusPill(title: record.enabled ? "Enabled" : "Disabled", accent: record.enabled ? FlowTheme.tealAccent : FlowTheme.roseAccent)
                                            }
                                            Text(record.whyItMatters)
                                                .font(.system(size: 12, weight: .medium))
                                                .foregroundStyle(FlowTheme.textSecondary)
                                        }
                                        .frame(maxWidth: .infinity, alignment: .leading)
                                        .padding(14)
                                        .background(
                                            RoundedRectangle(cornerRadius: 18, style: .continuous)
                                                .fill(store.selectedMemoryID == record.id ? FlowTheme.surfaceRaised.opacity(0.92) : FlowTheme.sidebar.opacity(0.8))
                                                .overlay(
                                                    RoundedRectangle(cornerRadius: 18, style: .continuous)
                                                        .stroke(FlowTheme.strokeStrong, lineWidth: 1)
                                                )
                                        )
                                    }
                                    .buttonStyle(.plain)
                                }
                            }
                        }
                    }

                    SurfaceCard(title: "Inspector", subtitle: "Edit, disable, or remove a memory entry", accent: FlowTheme.tealAccent) {
                        if let record = store.selectedMemoryRecord {
                            VStack(alignment: .leading, spacing: 14) {
                                DetailTile(label: "Scope", value: record.scope.capitalized, accent: FlowTheme.coolAccent)
                                DetailTile(label: "Why It Matters", value: record.whyItMatters, accent: FlowTheme.warmAccent)

                                TextEditor(text: $store.memoryEditorText)
                                    .font(.system(size: 14, weight: .medium))
                                    .frame(minHeight: 160)
                                    .padding(10)
                                    .scrollContentBackground(.hidden)
                                    .background(
                                        RoundedRectangle(cornerRadius: 18, style: .continuous)
                                            .fill(FlowTheme.surfaceRaised.opacity(0.84))
                                            .overlay(
                                                RoundedRectangle(cornerRadius: 18, style: .continuous)
                                                    .stroke(FlowTheme.strokeStrong, lineWidth: 1)
                                            )
                                    )

                                HStack {
                                    Button(record.enabled ? "Disable" : "Enable") {
                                        store.toggleSelectedMemoryEnabled()
                                    }

                                    Button("Delete") {
                                        store.deleteSelectedMemory()
                                    }

                                    Spacer()

                                    Button("Save") {
                                        store.saveSelectedMemoryEdit()
                                    }
                                    .buttonStyle(.borderedProminent)
                                    .tint(FlowTheme.tealAccent)
                                }
                            }
                        } else {
                            EmptyStateCard(title: "Select a memory", detail: "Choose a visible memory entry to inspect why it affects behavior.")
                        }
                    }
                }
            }
        }
    }
}

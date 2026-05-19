import Foundation

enum MemoryWorkflowSmokeTests {
    static func run() throws {
        try smokeTestMemoryCRUDAndFiltering()
    }

    private static func smokeTestMemoryCRUDAndFiltering() throws {
        let databaseURL = temporaryDatabaseURL()
        let repository = LegacyFlowRepository(databaseURL: databaseURL)

        let created = try repository.createMemoryRecord(
            kind: "explicit_preference",
            scope: "global",
            value: "Protect mornings for focused work.",
            source: "manual",
            confidence: 1.0,
            scopeRef: nil
        )

        var memories = try repository.listMemoryRecords(query: "mornings", includeDisabled: true)
        guard memories.count == 1 else {
            throw FlowDataError.message("Expected memory query to find the created entry.")
        }
        guard memories[0].whyItMatters.localizedCaseInsensitiveContains("planning") else {
            throw FlowDataError.message("Expected native memory record to explain why it affects behavior.")
        }

        try repository.updateMemoryRecord(id: created.id, value: "Protect afternoons for meetings.")
        try repository.setMemoryRecordEnabled(id: created.id, enabled: false)

        memories = try repository.listMemoryRecords(query: "afternoons", includeDisabled: true)
        guard memories.first?.enabled == false else {
            throw FlowDataError.message("Expected memory enable/disable state to persist.")
        }

        try repository.deleteMemoryRecord(id: created.id)
        guard try repository.listMemoryRecords(query: nil, includeDisabled: true).isEmpty else {
            throw FlowDataError.message("Expected deleting a memory entry to remove it from the native list.")
        }
    }

    private static func temporaryDatabaseURL() -> URL {
        URL(fileURLWithPath: NSTemporaryDirectory())
            .appendingPathComponent(UUID().uuidString)
            .appendingPathExtension("sqlite")
    }
}

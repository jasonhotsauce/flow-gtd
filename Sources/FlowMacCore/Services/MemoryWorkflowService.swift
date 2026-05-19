import Foundation

@MainActor
final class MemoryWorkflowService {
    private let repository: FlowRepository

    init(repository: FlowRepository) {
        self.repository = repository
    }

    func load(query: String?, includeDisabled: Bool = true) throws -> [FlowMemoryRecord] {
        try repository.listMemoryRecords(query: query, includeDisabled: includeDisabled)
    }

    func update(id: String, value: String) throws {
        try repository.updateMemoryRecord(id: id, value: value)
    }

    func setEnabled(id: String, enabled: Bool) throws {
        try repository.setMemoryRecordEnabled(id: id, enabled: enabled)
    }

    func delete(id: String) throws {
        try repository.deleteMemoryRecord(id: id)
    }
}

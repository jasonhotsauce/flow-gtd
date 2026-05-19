import Foundation

@MainActor
final class DailyPlanWorkflowService {
    private let repository: FlowRepository

    init(repository: FlowRepository) {
        self.repository = repository
    }

    func planDateString(for date: Date = Date(), timeZone: TimeZone = .autoupdatingCurrent) -> String {
        let formatter = DateFormatter()
        formatter.calendar = Calendar(identifier: .gregorian)
        formatter.locale = Locale(identifier: "en_US_POSIX")
        formatter.timeZone = timeZone
        formatter.dateFormat = "yyyy-MM-dd"
        return formatter.string(from: date)
    }

    func load(planDate: String) throws -> FlowDailyPlanState {
        try repository.loadDailyPlanState(planDate: planDate)
    }

    func save(planDate: String, topItemIDs: [String], bonusItemIDs: [String]) throws {
        try repository.saveDailyPlan(planDate: planDate, topItemIDs: topItemIDs, bonusItemIDs: bonusItemIDs)
    }
}

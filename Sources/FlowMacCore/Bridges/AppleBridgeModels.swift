import Foundation

enum AppleBridgeMethod: String, Codable, CaseIterable, Equatable {
    case permissionsStatus = "apple.permissions.status"
    case remindersStatus = "apple.reminders.status"
    case calendarStatus = "apple.calendar.status"
    case notificationCapability = "apple.notifications.capability"
}

enum AppleBridgeDomain: String, Codable, Equatable {
    case reminders
    case calendar
    case notifications
}

enum AppleBridgePermissionStatus: String, Codable, Equatable {
    case notDetermined = "not_determined"
    case denied
    case authorized
    case restricted
    case writeOnly = "write_only"
    case unsupported
}

struct AppleBridgePermissionRecord: Codable, Equatable {
    let domain: AppleBridgeDomain
    let status: AppleBridgePermissionStatus
    let canPrompt: Bool
    let detail: String
}

struct ApplePermissionsStatusParams: Codable, Equatable {
    let domains: [AppleBridgeDomain]
}

struct ApplePermissionsStatusResult: Codable, Equatable {
    let permissions: [AppleBridgePermissionRecord]
}

struct AppleRemindersStatusParams: Codable, Equatable {
    let taskIDs: [String]
    let writeBack: Bool

    enum CodingKeys: String, CodingKey {
        case taskIDs = "taskIds"
        case writeBack
    }
}

struct AppleRemindersStatusResult: Codable, Equatable {
    let status: String
    let importedCount: Int
    let updatedCount: Int
    let conflictsCount: Int
    let detail: String
}

struct AppleCalendarStatusParams: Codable, Equatable {
    let taskIDs: [String]

    enum CodingKeys: String, CodingKey {
        case taskIDs = "taskIds"
    }
}

struct AppleCalendarStatusResult: Codable, Equatable {
    let status: String
    let syncedCount: Int
    let conflictsCount: Int
    let detail: String
}

struct AppleNotificationCapabilityParams: Codable, Equatable {
    let includePendingCandidates: Bool
}

struct AppleNotificationCapabilityResult: Codable, Equatable {
    let status: String
    let permissionStatus: AppleBridgePermissionStatus
    let deliveryMode: String
    let available: Bool
    let pendingCandidateCount: Int
    let detail: String
}

struct AppleBridgeErrorData: Codable, Equatable {
    let kind: String
    let retryable: Bool
    let supportedMethods: [String]?
}

typealias ApplePermissionsStatusRequest = SidecarRequestEnvelope<ApplePermissionsStatusParams>
typealias ApplePermissionsStatusResponse = SidecarSuccessResponseEnvelope<ApplePermissionsStatusResult>
typealias AppleRemindersStatusRequest = SidecarRequestEnvelope<AppleRemindersStatusParams>
typealias AppleRemindersStatusResponse = SidecarSuccessResponseEnvelope<AppleRemindersStatusResult>
typealias AppleCalendarStatusRequest = SidecarRequestEnvelope<AppleCalendarStatusParams>
typealias AppleCalendarStatusResponse = SidecarSuccessResponseEnvelope<AppleCalendarStatusResult>
typealias AppleNotificationCapabilityRequest = SidecarRequestEnvelope<AppleNotificationCapabilityParams>
typealias AppleNotificationCapabilityResponse = SidecarSuccessResponseEnvelope<AppleNotificationCapabilityResult>
typealias AppleBridgeErrorResponse = SidecarErrorResponseEnvelope<AppleBridgeErrorData>

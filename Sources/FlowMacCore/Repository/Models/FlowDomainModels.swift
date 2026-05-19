import Foundation

enum NativeCaptureOrigin: String {
    case manualCapture = "manual_capture"
    case remindersImport = "reminders_import"
}

struct RawCaptureRecord: Hashable {
    let id: String
    let source: NativeCaptureOrigin
    let rawText: String
    let createdAt: String
}

struct InboxItemRecord: Hashable {
    let id: String
    let rawCaptureID: String
    let originType: NativeCaptureOrigin
    let inboxState: String
    let sourceRef: String?
    let importedAt: String?
    let createdAt: String
    let updatedAt: String
}

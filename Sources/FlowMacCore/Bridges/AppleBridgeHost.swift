import Foundation
import EventKit
import UserNotifications

protocol AppleBridgeHost {
    func handlePermissionsStatus(_ request: ApplePermissionsStatusRequest) -> ApplePermissionsStatusResponse
    func handleRemindersStatus(_ request: AppleRemindersStatusRequest) -> AppleRemindersStatusResponse
    func handleCalendarStatus(_ request: AppleCalendarStatusRequest) -> AppleCalendarStatusResponse
    func handleNotificationCapability(_ request: AppleNotificationCapabilityRequest) -> AppleNotificationCapabilityResponse
    func bridgeUnavailableResponse(id: String) -> AppleBridgeErrorResponse
}

struct StubAppleBridgeHost: AppleBridgeHost {
    func handlePermissionsStatus(_ request: ApplePermissionsStatusRequest) -> ApplePermissionsStatusResponse {
        ApplePermissionsStatusResponse(
            jsonrpc: SidecarProtocol.jsonrpcVersion,
            id: request.id,
            result: ApplePermissionsStatusResult(
                permissions: request.params.domains.map(defaultPermissionRecord(for:))
            )
        )
    }

    func handleRemindersStatus(_ request: AppleRemindersStatusRequest) -> AppleRemindersStatusResponse {
        AppleRemindersStatusResponse(
            jsonrpc: SidecarProtocol.jsonrpcVersion,
            id: request.id,
            result: AppleRemindersStatusResult(
                status: "stubbed",
                importedCount: 0,
                updatedCount: 0,
                conflictsCount: 0,
                detail: request.params.taskIDs.isEmpty
                    ? "Reminders bridge stub acknowledged capability probe."
                    : "Reminders bridge stub accepted the task scope but did not contact EventKit."
            )
        )
    }

    func handleCalendarStatus(_ request: AppleCalendarStatusRequest) -> AppleCalendarStatusResponse {
        AppleCalendarStatusResponse(
            jsonrpc: SidecarProtocol.jsonrpcVersion,
            id: request.id,
            result: AppleCalendarStatusResult(
                status: "stubbed",
                syncedCount: 0,
                conflictsCount: 0,
                detail: request.params.taskIDs.isEmpty
                    ? "Calendar bridge stub acknowledged capability probe."
                    : "Calendar bridge stub accepted the task scope but did not contact EventKit."
            )
        )
    }

    func handleNotificationCapability(_ request: AppleNotificationCapabilityRequest) -> AppleNotificationCapabilityResponse {
        AppleNotificationCapabilityResponse(
            jsonrpc: SidecarProtocol.jsonrpcVersion,
            id: request.id,
            result: AppleNotificationCapabilityResult(
                status: "stubbed",
                permissionStatus: .notDetermined,
                deliveryMode: "degraded",
                available: false,
                pendingCandidateCount: request.params.includePendingCandidates ? 0 : 0,
                detail: "Notification capability is stubbed; Flow should remain in degraded local-delivery mode until the Swift bridge is wired."
            )
        )
    }

    func bridgeUnavailableResponse(id: String) -> AppleBridgeErrorResponse {
        AppleBridgeErrorResponse(
            jsonrpc: SidecarProtocol.jsonrpcVersion,
            id: id,
            error: SidecarErrorEnvelope(
                code: SidecarProtocol.bridgeUnavailableCode,
                message: "Apple bridge host unavailable.",
                data: AppleBridgeErrorData(
                    kind: "bridge_unavailable",
                    retryable: true,
                    supportedMethods: AppleBridgeMethod.allCases.map(\.rawValue)
                )
            )
        )
    }

    private func defaultPermissionRecord(for domain: AppleBridgeDomain) -> AppleBridgePermissionRecord {
        switch domain {
        case .notifications:
            return AppleBridgePermissionRecord(
                domain: domain,
                status: .notDetermined,
                canPrompt: true,
                detail: "Notification permission has not been requested yet; Flow should remain in degraded local-delivery mode."
            )
        case .reminders, .calendar:
            return AppleBridgePermissionRecord(
                domain: domain,
                status: .notDetermined,
                canPrompt: true,
                detail: "\(domain.rawValue) bridge is stubbed until native Apple integration is wired through IPC."
            )
        }
    }
}

struct LiveAppleBridgeHost: AppleBridgeHost {
    func handlePermissionsStatus(_ request: ApplePermissionsStatusRequest) -> ApplePermissionsStatusResponse {
        ApplePermissionsStatusResponse(
            jsonrpc: SidecarProtocol.jsonrpcVersion,
            id: request.id,
            result: ApplePermissionsStatusResult(
                permissions: request.params.domains.map(permissionRecord(for:))
            )
        )
    }

    func handleRemindersStatus(_ request: AppleRemindersStatusRequest) -> AppleRemindersStatusResponse {
        let permission = permissionRecord(for: .reminders)
        let available = permission.status == .authorized || permission.status == .writeOnly
        return AppleRemindersStatusResponse(
            jsonrpc: SidecarProtocol.jsonrpcVersion,
            id: request.id,
            result: AppleRemindersStatusResult(
                status: available ? "available" : "unavailable",
                importedCount: 0,
                updatedCount: 0,
                conflictsCount: 0,
                detail: available
                    ? "Reminders bridge is available for scoped native operations."
                    : permission.detail
            )
        )
    }

    func handleCalendarStatus(_ request: AppleCalendarStatusRequest) -> AppleCalendarStatusResponse {
        let permission = permissionRecord(for: .calendar)
        let available = permission.status == .authorized || permission.status == .writeOnly
        return AppleCalendarStatusResponse(
            jsonrpc: SidecarProtocol.jsonrpcVersion,
            id: request.id,
            result: AppleCalendarStatusResult(
                status: available ? "available" : "unavailable",
                syncedCount: 0,
                conflictsCount: 0,
                detail: available
                    ? "Calendar bridge is available for scoped native operations."
                    : permission.detail
            )
        )
    }

    func handleNotificationCapability(_ request: AppleNotificationCapabilityRequest) -> AppleNotificationCapabilityResponse {
        let permissionStatus = notificationPermissionStatus()
        let available = permissionStatus == .authorized || permissionStatus == .writeOnly
        return AppleNotificationCapabilityResponse(
            jsonrpc: SidecarProtocol.jsonrpcVersion,
            id: request.id,
            result: AppleNotificationCapabilityResult(
                status: available ? "available" : "degraded",
                permissionStatus: permissionStatus,
                deliveryMode: available ? "flow_owned_local" : "degraded",
                available: available,
                pendingCandidateCount: request.params.includePendingCandidates ? 0 : 0,
                detail: notificationDetail(for: permissionStatus)
            )
        )
    }

    func bridgeUnavailableResponse(id: String) -> AppleBridgeErrorResponse {
        StubAppleBridgeHost().bridgeUnavailableResponse(id: id)
    }

    private func permissionRecord(for domain: AppleBridgeDomain) -> AppleBridgePermissionRecord {
        switch domain {
        case .reminders:
            let status = mapEventKitStatus(EKEventStore.authorizationStatus(for: .reminder))
            return AppleBridgePermissionRecord(
                domain: domain,
                status: status,
                canPrompt: status == .notDetermined,
                detail: eventKitDetail(for: status, domain: domain)
            )
        case .calendar:
            let status = mapEventKitStatus(EKEventStore.authorizationStatus(for: .event))
            return AppleBridgePermissionRecord(
                domain: domain,
                status: status,
                canPrompt: status == .notDetermined,
                detail: eventKitDetail(for: status, domain: domain)
            )
        case .notifications:
            let status = notificationPermissionStatus()
            return AppleBridgePermissionRecord(
                domain: domain,
                status: status,
                canPrompt: status == .notDetermined,
                detail: notificationDetail(for: status)
            )
        }
    }

    private func mapEventKitStatus(_ status: EKAuthorizationStatus) -> AppleBridgePermissionStatus {
        switch status {
        case .fullAccess:
            return .authorized
        case .writeOnly:
            return .writeOnly
        case .denied:
            return .denied
        case .restricted:
            return .restricted
        case .notDetermined:
            return .notDetermined
        @unknown default:
            return .unsupported
        }
    }

    private func mapNotificationStatus(_ status: UNAuthorizationStatus) -> AppleBridgePermissionStatus {
        switch status {
        case .authorized, .provisional, .ephemeral:
            return .authorized
        case .denied:
            return .denied
        case .notDetermined:
            return .notDetermined
        @unknown default:
            return .unsupported
        }
    }

    private func eventKitDetail(for status: AppleBridgePermissionStatus, domain: AppleBridgeDomain) -> String {
        switch status {
        case .authorized, .writeOnly:
            return "\(domain.rawValue.capitalized) access is available to the native Apple bridge."
        case .denied:
            return "\(domain.rawValue.capitalized) access is denied in System Settings."
        case .restricted:
            return "\(domain.rawValue.capitalized) access is restricted on this Mac."
        case .notDetermined:
            return "\(domain.rawValue.capitalized) access has not been requested yet."
        case .unsupported:
            return "\(domain.rawValue.capitalized) access is unavailable on this system."
        }
    }

    private func notificationDetail(for status: AppleBridgePermissionStatus) -> String {
        switch status {
        case .authorized, .writeOnly:
            return "Notification permission is available for Flow-owned local delivery."
        case .denied:
            return "Notifications are denied in System Settings; Flow should stay in degraded local-only mode."
        case .restricted:
            return "Notifications are restricted on this Mac."
        case .notDetermined:
            return "Notification permission has not been requested yet; Flow should remain in degraded local-delivery mode."
        case .unsupported:
            return "Notification capability is unavailable on this system."
        }
    }

    private func notificationPermissionStatus() -> AppleBridgePermissionStatus {
        guard Bundle.main.bundleURL.pathExtension == "app" else {
            return .unsupported
        }
        let semaphore = DispatchSemaphore(value: 0)
        var capturedStatus: UNAuthorizationStatus?
        UNUserNotificationCenter.current().getNotificationSettings { settings in
            capturedStatus = settings.authorizationStatus
            semaphore.signal()
        }
        _ = semaphore.wait(timeout: .now() + 2.0)
        return mapNotificationStatus(capturedStatus ?? .notDetermined)
    }
}

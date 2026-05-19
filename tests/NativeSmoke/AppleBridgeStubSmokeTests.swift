import Foundation

enum AppleBridgeStubSmokeTests {
    static func run() throws {
        try smokeTestStubPermissionsResponse()
        try smokeTestStubBridgeUnavailableError()
        try smokeTestNotificationCapabilityStub()
        try smokeTestLiveNotificationCapabilityReturnsRealStatus()
    }

    private static func smokeTestStubPermissionsResponse() throws {
        let host = StubAppleBridgeHost()
        let response = host.handlePermissionsStatus(
            ApplePermissionsStatusRequest(
                jsonrpc: SidecarProtocol.jsonrpcVersion,
                id: "apple-bridge-1",
                method: AppleBridgeMethod.permissionsStatus.rawValue,
                params: ApplePermissionsStatusParams(
                    domains: [.reminders, .calendar, .notifications]
                )
            )
        )

        guard response.result.permissions.count == 3 else {
            throw TestFailure("Expected stub permissions response to preserve all requested Apple bridge domains.")
        }
        guard response.result.permissions.last?.status == .notDetermined else {
            throw TestFailure("Expected notification bridge stub to default to not_determined permission status.")
        }
    }

    private static func smokeTestStubBridgeUnavailableError() throws {
        let errorResponse = StubAppleBridgeHost().bridgeUnavailableResponse(id: "apple-bridge-2")

        guard errorResponse.error.code == SidecarProtocol.bridgeUnavailableCode else {
            throw TestFailure("Expected unavailable bridge response to use the shared bridge-unavailable error code.")
        }
        guard errorResponse.error.data?.supportedMethods?.contains(AppleBridgeMethod.remindersStatus.rawValue) == true else {
            throw TestFailure("Expected unavailable bridge response to advertise supported Apple bridge methods.")
        }
    }

    private static func smokeTestNotificationCapabilityStub() throws {
        let host = StubAppleBridgeHost()
        let response = host.handleNotificationCapability(
            AppleNotificationCapabilityRequest(
                jsonrpc: SidecarProtocol.jsonrpcVersion,
                id: "apple-bridge-3",
                method: AppleBridgeMethod.notificationCapability.rawValue,
                params: AppleNotificationCapabilityParams(includePendingCandidates: true)
            )
        )

        guard response.result.status == "stubbed" else {
            throw TestFailure("Expected notification capability bridge to remain stubbed in TASK-006.")
        }
        guard response.result.available == false else {
            throw TestFailure("Expected notification capability bridge to remain unavailable before real native wiring.")
        }
    }

    private static func smokeTestLiveNotificationCapabilityReturnsRealStatus() throws {
        let host = LiveAppleBridgeHost()
        let response = host.handleNotificationCapability(
            AppleNotificationCapabilityRequest(
                jsonrpc: SidecarProtocol.jsonrpcVersion,
                id: "apple-bridge-4",
                method: AppleBridgeMethod.notificationCapability.rawValue,
                params: AppleNotificationCapabilityParams(includePendingCandidates: false)
            )
        )

        guard response.result.status != "stubbed" else {
            throw TestFailure("Expected live notification capability host to stop reporting stubbed status.")
        }
        guard response.result.detail.isEmpty == false else {
            throw TestFailure("Expected live notification capability host to return explanatory detail.")
        }
    }
}

private struct TestFailure: LocalizedError {
    let errorDescription: String?

    init(_ message: String) {
        self.errorDescription = message
    }
}

import Foundation

enum SidecarHealthCheckSmokeTests {
    static func run() async throws {
        try await smokeTestSwiftHealthCheckCallerReadsSuccessEnvelope()
        try await smokeTestSwiftHealthCheckCallerReadsProtocolMismatchEnvelope()
    }

    private static func smokeTestSwiftHealthCheckCallerReadsSuccessEnvelope() async throws {
        let client = ProcessSidecarProbeClient()
        let response = try await client.healthCheck(
            configuration: SidecarLaunchConfiguration.runtimeHealthCheck(),
            timeout: 2.0
        )

        guard case let .success(success) = response else {
            throw TestFailure("Expected Swift health.check caller to decode a success envelope.")
        }
        guard success.result.protocolVersion == SidecarProtocol.protocolVersion else {
            throw TestFailure("Expected Swift health.check caller to preserve the current protocol version.")
        }
    }

    private static func smokeTestSwiftHealthCheckCallerReadsProtocolMismatchEnvelope() async throws {
        let client = ProcessSidecarProbeClient()
        let response = try await client.healthCheck(
            configuration: SidecarLaunchConfiguration.runtimeHealthCheck(protocolVersion: "1999-01-01"),
            timeout: 2.0
        )

        guard case let .failure(error) = response else {
            throw TestFailure("Expected Swift health.check caller to decode the mismatch envelope.")
        }
        guard error.error.code == SidecarProtocol.incompatibleProtocolCode else {
            throw TestFailure("Expected Swift health.check caller to preserve the incompatible protocol code.")
        }
        guard error.error.data?.supportedProtocolVersion == SidecarProtocol.protocolVersion else {
            throw TestFailure("Expected Swift health.check caller to expose the supported protocol version.")
        }
    }
}

private struct TestFailure: LocalizedError {
    let errorDescription: String?

    init(_ message: String) {
        self.errorDescription = message
    }
}

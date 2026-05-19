import Foundation

enum SidecarSupervisorSmokeTests {
    static func run() async throws {
        try await smokeTestRuntimeLaunchConfigurationProbesCompiledSidecar()
        try await smokeTestSuccessfulProbeLeavesSupervisorReady()
        try await smokeTestSupervisorReportsEachStartupAttempt()
        try await smokeTestFailedProbeRestartsOnceThenDegrades()
        try smokeTestRootSplitViewContainsDegradedModeBanner()
    }

    private static func smokeTestRuntimeLaunchConfigurationProbesCompiledSidecar() async throws {
        let readyEvent = try await ProcessSidecarProbeClient().probeReadiness(
            configuration: .runtimeDefault(),
            timeout: 2.0
        )

        guard readyEvent.event == "sidecar.ready" else {
            throw FlowDataError.message("Expected the compiled sidecar probe to emit a ready event.")
        }
        guard readyEvent.transport == .stdio else {
            throw FlowDataError.message("Expected the compiled sidecar probe to use stdio transport.")
        }
        guard readyEvent.mode == "once" else {
            throw FlowDataError.message("Expected the compiled sidecar probe to run in once mode.")
        }
    }

    private static func smokeTestSuccessfulProbeLeavesSupervisorReady() async throws {
        let readyEvent = SidecarReadyEvent(
            event: "sidecar.ready",
            mode: "once",
            transport: .stdio,
            version: "0.1.0"
        )
        let client = StubSidecarProbeClient(results: [.success(readyEvent)])
        let supervisor = SidecarSupervisor(
            client: client,
            configuration: SidecarLaunchConfiguration(
                executableURL: URL(fileURLWithPath: "/usr/bin/env"),
                arguments: ["true"]
            ),
            policy: SidecarSupervisorPolicy(readinessTimeout: 0.1, maxAutomaticRestarts: 1)
        )

        let status = await supervisor.start()

        guard status == .ready(readyEvent) else {
            throw FlowDataError.message("Expected successful readiness probe to leave the supervisor ready.")
        }
        guard await client.recordedAttemptCount == 1 else {
            throw FlowDataError.message("Expected a successful readiness probe to complete in one attempt.")
        }
    }

    private static func smokeTestFailedProbeRestartsOnceThenDegrades() async throws {
        let client = StubSidecarProbeClient(
            results: [
                .failure(SidecarProbeError.invalidReadyEvent("missing ready payload")),
                .failure(SidecarProbeError.timedOut(seconds: 0.1))
            ]
        )
        let supervisor = SidecarSupervisor(
            client: client,
            configuration: SidecarLaunchConfiguration(
                executableURL: URL(fileURLWithPath: "/usr/bin/env"),
                arguments: ["false"]
            ),
            policy: SidecarSupervisorPolicy(readinessTimeout: 0.1, maxAutomaticRestarts: 1)
        )

        let status = await supervisor.start()

        guard case let .degraded(degradedState) = status else {
            throw FlowDataError.message("Expected repeated readiness failures to degrade the supervisor.")
        }
        guard degradedState.restartCount == 1 else {
            throw FlowDataError.message("Expected the degraded state to report one automatic restart.")
        }
        guard degradedState.failureReasons.count == 2 else {
            throw FlowDataError.message("Expected degraded mode to preserve each readiness failure reason.")
        }
        guard degradedState.failureReasons.last?.localizedCaseInsensitiveContains("timed out") == true else {
            throw FlowDataError.message("Expected degraded mode to surface the last readiness timeout.")
        }
        guard degradedState.recoverySuggestion.localizedCaseInsensitiveContains("Retry") else {
            throw FlowDataError.message("Expected degraded mode to instruct the user to retry sidecar launch.")
        }
        guard await client.recordedAttemptCount == 2 else {
            throw FlowDataError.message("Expected the supervisor to probe twice before degrading.")
        }

        await supervisor.shutdown()
        guard await supervisor.currentStatus() == .idle else {
            throw FlowDataError.message("Expected shutdown to reset the supervisor back to idle state.")
        }
    }

    private static func smokeTestSupervisorReportsEachStartupAttempt() async throws {
        let recorder = SidecarStatusRecorder()
        let client = StubSidecarProbeClient(
            results: [
                .failure(SidecarProbeError.invalidReadyEvent("missing ready payload")),
                .success(
                    SidecarReadyEvent(
                        event: "sidecar.ready",
                        mode: "once",
                        transport: .stdio,
                        version: "0.1.0"
                    )
                )
            ]
        )
        let supervisor = SidecarSupervisor(
            client: client,
            configuration: SidecarLaunchConfiguration(
                executableURL: URL(fileURLWithPath: "/usr/bin/env"),
                arguments: ["true"]
            ),
            policy: SidecarSupervisorPolicy(readinessTimeout: 0.1, maxAutomaticRestarts: 1)
        )

        let status = await supervisor.start { updatedStatus in
            await recorder.record(updatedStatus)
        }

        guard case .ready = status else {
            throw FlowDataError.message("Expected second-attempt startup to eventually reach ready state.")
        }

        let updates = await recorder.statuses
        guard updates.contains(.starting(attempt: 1)) else {
            throw FlowDataError.message("Expected startup status updates to include the initial sidecar launch attempt.")
        }
        guard updates.contains(.starting(attempt: 2)) else {
            throw FlowDataError.message("Expected startup status updates to include the automatic restart attempt.")
        }
    }

    private static func smokeTestRootSplitViewContainsDegradedModeBanner() throws {
        let rootSplitViewURL = URL(fileURLWithPath: #filePath)
            .deletingLastPathComponent()
            .deletingLastPathComponent()
            .deletingLastPathComponent()
            .appendingPathComponent("Sources/FlowMacApp/UI/Root/RootSplitView.swift")
        let source = try String(contentsOf: rootSplitViewURL)

        guard source.contains("Flow is running in degraded mode") else {
            throw FlowDataError.message("Expected RootSplitView to include degraded-mode banner copy.")
        }
        guard source.contains("Starting Flow services") else {
            throw FlowDataError.message("Expected RootSplitView to show sidecar startup progress while Flow services are starting.")
        }
        guard source.contains("Retrying Flow services") else {
            throw FlowDataError.message("Expected RootSplitView to show retry-in-progress copy during sidecar restart attempts.")
        }
        guard source.contains("Retry Sidecar") else {
            throw FlowDataError.message("Expected RootSplitView to expose a retry affordance for degraded sidecar state.")
        }
        guard source.contains("Assistant suggestions, planning, and other smart features are temporarily unavailable") else {
            throw FlowDataError.message("Expected degraded banner copy to explain which product capabilities are unavailable.")
        }
        guard source.contains("Try again in a moment. If this keeps happening, reopen Flow to restart its background services.") else {
            throw FlowDataError.message("Expected degraded banner copy to explain the next user action in plain language.")
        }
    }
}

private actor SidecarStatusRecorder {
    private(set) var statuses: [SidecarSupervisorStatus] = []

    func record(_ status: SidecarSupervisorStatus) {
        statuses.append(status)
    }
}

private actor StubSidecarProbeClient: SidecarProbeClient {
    private var remainingResults: [Result<SidecarReadyEvent, Error>]
    private(set) var recordedAttemptCount = 0

    init(results: [Result<SidecarReadyEvent, Error>]) {
        self.remainingResults = results
    }

    func probeReadiness(
        configuration: SidecarLaunchConfiguration,
        timeout: TimeInterval
    ) async throws -> SidecarReadyEvent {
        recordedAttemptCount += 1

        guard remainingResults.isEmpty == false else {
            throw FlowDataError.message("Expected another stubbed readiness probe result.")
        }

        let result = remainingResults.removeFirst()
        return try result.get()
    }
}

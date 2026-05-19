import Combine
import Foundation

actor SidecarSupervisor {
    private let client: any SidecarProbeClient
    private let configuration: SidecarLaunchConfiguration
    private let policy: SidecarSupervisorPolicy
    private var status: SidecarSupervisorStatus = .idle

    init(
        client: any SidecarProbeClient,
        configuration: SidecarLaunchConfiguration,
        policy: SidecarSupervisorPolicy
    ) {
        self.client = client
        self.configuration = configuration
        self.policy = policy
    }

    func start(
        statusHandler: (@Sendable (SidecarSupervisorStatus) async -> Void)? = nil
    ) async -> SidecarSupervisorStatus {
        var failureReasons: [String] = []
        let totalAttempts = max(1, policy.maxAutomaticRestarts + 1)

        for attempt in 1...totalAttempts {
            status = .starting(attempt: attempt)
            if let statusHandler {
                await statusHandler(status)
            }

            do {
                let readyEvent = try await client.probeReadiness(
                    configuration: configuration,
                    timeout: policy.readinessTimeout
                )
                status = .ready(readyEvent)
                if let statusHandler {
                    await statusHandler(status)
                }
                return status
            } catch {
                failureReasons.append(error.localizedDescription)
            }
        }

        let degradedState = SidecarDegradedState(
            restartCount: min(policy.maxAutomaticRestarts, max(0, totalAttempts - 1)),
            failureReasons: failureReasons,
            recoverySuggestion: "Retry Sidecar after the local runtime becomes available."
        )
        status = .degraded(degradedState)
        if let statusHandler {
            await statusHandler(status)
        }
        return status
    }

    func shutdown() {
        status = .idle
    }

    func currentStatus() -> SidecarSupervisorStatus {
        status
    }
}

@MainActor
final class SidecarRuntimeModel: ObservableObject {
    @Published private(set) var status: SidecarSupervisorStatus = .idle

    private let supervisor: SidecarSupervisor

    init(supervisor: SidecarSupervisor) {
        self.supervisor = supervisor
    }

    var degradedState: SidecarDegradedState? {
        guard case let .degraded(state) = status else { return nil }
        return state
    }

    var startingAttempt: Int? {
        guard case let .starting(attempt) = status else { return nil }
        return attempt
    }

    func startIfNeeded() async {
        guard case .idle = status else { return }
        await runStartup()
    }

    func retry() async {
        guard startingAttempt == nil else { return }
        await runStartup()
    }

    func shutdown() async {
        await supervisor.shutdown()
        status = .idle
    }

    private func runStartup() async {
        status = .starting(attempt: 1)
        status = await supervisor.start { [self] updatedStatus in
            await MainActor.run {
                self.status = updatedStatus
            }
        }
    }
}

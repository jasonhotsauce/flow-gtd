import Foundation

struct AppBootstrapContext {
    let store: WorkspaceStore
    let sidecarRuntime: SidecarRuntimeModel
}

enum AppBootstrap {
    private static func codexBinaryPath() -> String? {
        let environment = ProcessInfo.processInfo.environment
        if let configured = environment["FLOW_CODEX_BIN"], configured.isEmpty == false {
            return configured
        }

        let candidates = [
            "/opt/homebrew/bin/codex",
            "/usr/local/bin/codex"
        ]
        return candidates.first(where: { FileManager.default.isExecutableFile(atPath: $0) })
    }

    @MainActor
    static func makeContext() -> AppBootstrapContext {
        let legacyRepository = LegacyFlowRepository()
        var sidecarEnvironment = [
            "FLOW_DB_PATH": legacyRepository.databaseURL.path,
            "FLOW_AGENT_RUNTIME_PROVIDER": "codex"
        ]
        if let codexBinaryPath = codexBinaryPath() {
            sidecarEnvironment["FLOW_CODEX_BIN"] = codexBinaryPath
        }
        let repository: FlowRepository = SidecarFlowRepository(
            fallback: legacyRepository,
            environment: sidecarEnvironment
        )

        let store = WorkspaceStore(repository: repository)
        store.refresh()
        let sidecarRuntime = SidecarRuntimeModel(
            supervisor: SidecarSupervisor(
                client: ProcessSidecarProbeClient(),
                configuration: .runtimeDefault(),
                policy: SidecarSupervisorPolicy(
                    readinessTimeout: 2.0,
                    maxAutomaticRestarts: 1
                )
            )
        )
        return AppBootstrapContext(store: store, sidecarRuntime: sidecarRuntime)
    }
}

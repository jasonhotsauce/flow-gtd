import Foundation

protocol SidecarProbeClient {
    func probeReadiness(
        configuration: SidecarLaunchConfiguration,
        timeout: TimeInterval
    ) async throws -> SidecarReadyEvent
}

protocol SidecarReadClient {
    func readPayload<Payload: Decodable>(
        configuration: SidecarLaunchConfiguration,
        timeout: TimeInterval,
        as type: Payload.Type
    ) throws -> Payload
}

protocol SidecarMutationClient {
    func mutatePayload<Payload: Decodable>(
        configuration: SidecarLaunchConfiguration,
        timeout: TimeInterval,
        as type: Payload.Type
    ) throws -> Payload
}

enum SidecarHealthCheckOutcome: Equatable {
    case success(SidecarHealthCheckSuccessResponse)
    case failure(SidecarHealthCheckErrorResponse)
}

enum SidecarProbeError: LocalizedError, Equatable {
    case launchFailed(String)
    case invalidReadyEvent(String)
    case invalidHealthCheckResponse(String)
    case nonZeroExit(code: Int32, stderr: String)
    case timedOut(seconds: TimeInterval)

    var errorDescription: String? {
        switch self {
        case .launchFailed(let message):
            return "Sidecar launch failed: \(message)"
        case .invalidReadyEvent(let message):
            return "Sidecar emitted an invalid ready event: \(message)"
        case .invalidHealthCheckResponse(let message):
            return "Sidecar emitted an invalid health.check response: \(message)"
        case .nonZeroExit(let code, let stderr):
            let trimmed = stderr.trimmingCharacters(in: .whitespacesAndNewlines)
            return trimmed.isEmpty
                ? "Sidecar exited with status \(code)."
                : "Sidecar exited with status \(code): \(trimmed)"
        case .timedOut(let seconds):
            return String(format: "Sidecar readiness timed out after %.1f seconds.", seconds)
        }
    }
}

struct ProcessSidecarProbeClient: SidecarProbeClient, SidecarReadClient, SidecarMutationClient {
    func healthCheck(
        configuration: SidecarLaunchConfiguration,
        timeout: TimeInterval
    ) async throws -> SidecarHealthCheckOutcome {
        let output = try await runProcess(
            configuration: configuration,
            timeout: timeout
        )

        guard output.exitCode == 0 else {
            let stderr = output.stderr.isEmpty ? output.stdout : output.stderr
            throw SidecarProbeError.nonZeroExit(code: output.exitCode, stderr: stderr)
        }

        return try decodeHealthCheckResponse(from: output.stdout)
    }

    func probeReadiness(
        configuration: SidecarLaunchConfiguration,
        timeout: TimeInterval
    ) async throws -> SidecarReadyEvent {
        let output = try await runProcess(
            configuration: configuration,
            timeout: timeout
        )

        guard output.exitCode == 0 else {
            let stderr = output.stderr.isEmpty ? output.stdout : output.stderr
            throw SidecarProbeError.nonZeroExit(code: output.exitCode, stderr: stderr)
        }

        return try decodeReadyEvent(from: output.stdout)
    }

    func readPayload<Payload: Decodable>(
        configuration: SidecarLaunchConfiguration,
        timeout: TimeInterval,
        as type: Payload.Type
    ) throws -> Payload {
        let output = try runProcessSync(
            configuration: configuration,
            timeout: timeout
        )

        guard output.exitCode == 0 else {
            let stderr = output.stderr.isEmpty ? output.stdout : output.stderr
            throw SidecarProbeError.nonZeroExit(code: output.exitCode, stderr: stderr)
        }

        let lines = output.stdout
            .split(whereSeparator: \.isNewline)
            .map(String.init)
            .filter { $0.isEmpty == false }

        guard let payload = lines.last else {
            throw SidecarProbeError.invalidHealthCheckResponse("missing read payload")
        }

        do {
            return try JSONDecoder().decode(Payload.self, from: Data(payload.utf8))
        } catch {
            throw SidecarProbeError.invalidHealthCheckResponse(payload)
        }
    }

    func mutatePayload<Payload: Decodable>(
        configuration: SidecarLaunchConfiguration,
        timeout: TimeInterval,
        as type: Payload.Type
    ) throws -> Payload {
        try readPayload(configuration: configuration, timeout: timeout, as: type)
    }

    private func decodeReadyEvent(from stdout: String) throws -> SidecarReadyEvent {
        let lines = stdout
            .split(whereSeparator: \.isNewline)
            .map(String.init)
            .filter { $0.isEmpty == false }

        guard let payload = lines.last else {
            throw SidecarProbeError.invalidReadyEvent("missing ready payload")
        }

        do {
            let readyEvent = try JSONDecoder().decode(
                SidecarReadyEvent.self,
                from: Data(payload.utf8)
            )
            guard readyEvent.event == "sidecar.ready" else {
                throw SidecarProbeError.invalidReadyEvent("unexpected event \(readyEvent.event)")
            }
            return readyEvent
        } catch let error as SidecarProbeError {
            throw error
        } catch {
            throw SidecarProbeError.invalidReadyEvent(payload)
        }
    }

    private func decodeHealthCheckResponse(from stdout: String) throws -> SidecarHealthCheckOutcome {
        let lines = stdout
            .split(whereSeparator: \.isNewline)
            .map(String.init)
            .filter { $0.isEmpty == false }

        guard let payload = lines.last else {
            throw SidecarProbeError.invalidHealthCheckResponse("missing health.check payload")
        }

        let payloadData = Data(payload.utf8)
        let decoder = JSONDecoder()

        if let success = try? decoder.decode(
            SidecarHealthCheckSuccessResponse.self,
            from: payloadData
        ) {
            return .success(success)
        }

        if let failure = try? decoder.decode(
            SidecarHealthCheckErrorResponse.self,
            from: payloadData
        ) {
            return .failure(failure)
        }

        throw SidecarProbeError.invalidHealthCheckResponse(payload)
    }

    private func runProcess(
        configuration: SidecarLaunchConfiguration,
        timeout: TimeInterval
    ) async throws -> ProcessOutput {
        let process = Process()
        let stdoutPipe = Pipe()
        let stderrPipe = Pipe()

        process.executableURL = configuration.executableURL
        process.arguments = configuration.arguments
        process.currentDirectoryURL = configuration.workingDirectoryURL
        process.environment = ProcessInfo.processInfo.environment.merging(configuration.environment) { _, new in new }
        process.standardOutput = stdoutPipe
        process.standardError = stderrPipe

        do {
            try process.run()
        } catch {
            throw SidecarProbeError.launchFailed(error.localizedDescription)
        }

        return try await withThrowingTaskGroup(of: ProcessOutput.self) { group in
            group.addTask {
                process.waitUntilExit()
                let stdoutData = stdoutPipe.fileHandleForReading.readDataToEndOfFile()
                let stderrData = stderrPipe.fileHandleForReading.readDataToEndOfFile()

                return ProcessOutput(
                    exitCode: process.terminationStatus,
                    stdout: String(decoding: stdoutData, as: UTF8.self),
                    stderr: String(decoding: stderrData, as: UTF8.self)
                )
            }

            group.addTask {
                try await Task.sleep(nanoseconds: UInt64(timeout * 1_000_000_000))
                if process.isRunning {
                    process.terminate()
                }
                throw SidecarProbeError.timedOut(seconds: timeout)
            }

            let output = try await group.next() ?? ProcessOutput(exitCode: 1, stdout: "", stderr: "")
            group.cancelAll()
            return output
        }
    }

    private func runProcessSync(
        configuration: SidecarLaunchConfiguration,
        timeout: TimeInterval
    ) throws -> ProcessOutput {
        let process = Process()
        let stdoutPipe = Pipe()
        let stderrPipe = Pipe()

        process.executableURL = configuration.executableURL
        process.arguments = configuration.arguments
        process.currentDirectoryURL = configuration.workingDirectoryURL
        process.environment = ProcessInfo.processInfo.environment.merging(configuration.environment) { _, new in new }
        process.standardOutput = stdoutPipe
        process.standardError = stderrPipe

        do {
            try process.run()
        } catch {
            throw SidecarProbeError.launchFailed(error.localizedDescription)
        }

        let deadline = Date().addingTimeInterval(timeout)
        while process.isRunning {
            if Date() >= deadline {
                process.terminate()
                throw SidecarProbeError.timedOut(seconds: timeout)
            }
            Thread.sleep(forTimeInterval: 0.01)
        }

        let stdoutData = stdoutPipe.fileHandleForReading.readDataToEndOfFile()
        let stderrData = stderrPipe.fileHandleForReading.readDataToEndOfFile()
        return ProcessOutput(
            exitCode: process.terminationStatus,
            stdout: String(decoding: stdoutData, as: UTF8.self),
            stderr: String(decoding: stderrData, as: UTF8.self)
        )
    }
}

extension SidecarLaunchConfiguration {
    private static func developmentEntrypoint() -> (projectRootURL: URL, entrypointURL: URL) {
        let projectRootURL = URL(fileURLWithPath: #filePath)
            .deletingLastPathComponent()
            .deletingLastPathComponent()
            .deletingLastPathComponent()
            .deletingLastPathComponent()
        let entrypointURL = projectRootURL
            .appendingPathComponent("sidecar")
            .appendingPathComponent("dist")
            .appendingPathComponent("main.js")
        return (projectRootURL, entrypointURL)
    }

    private static func bundledRuntime() -> (nodeURL: URL, entrypointURL: URL, workingDirectoryURL: URL)? {
        guard let resourceURL = Bundle.main.resourceURL else { return nil }
        let nodeURL = resourceURL
            .appendingPathComponent("sidecar-runtime")
            .appendingPathComponent("node")
            .appendingPathComponent("bin")
            .appendingPathComponent("node")
        let entrypointURL = resourceURL
            .appendingPathComponent("sidecar-runtime")
            .appendingPathComponent("dist")
            .appendingPathComponent("main.js")
        let fileManager = FileManager.default
        guard fileManager.isExecutableFile(atPath: nodeURL.path), fileManager.fileExists(atPath: entrypointURL.path) else {
            return nil
        }
        return (nodeURL, entrypointURL, resourceURL)
    }

    static func runtimeDefault() -> SidecarLaunchConfiguration {
        if let bundled = bundledRuntime() {
            return SidecarLaunchConfiguration(
                executableURL: bundled.nodeURL,
                arguments: [bundled.entrypointURL.path, "--once"],
                workingDirectoryURL: bundled.workingDirectoryURL
            )
        }

        let paths = developmentEntrypoint()

        return SidecarLaunchConfiguration(
            executableURL: URL(fileURLWithPath: "/usr/bin/env"),
            arguments: ["node", paths.entrypointURL.path, "--once"],
            workingDirectoryURL: paths.projectRootURL
        )
    }

    static func runtimeHealthCheck(
        protocolVersion: String = SidecarProtocol.protocolVersion
    ) -> SidecarLaunchConfiguration {
        if let bundled = bundledRuntime() {
            return SidecarLaunchConfiguration(
                executableURL: bundled.nodeURL,
                arguments: [
                    bundled.entrypointURL.path,
                    "--health-check",
                    "--protocol-version",
                    protocolVersion
                ],
                workingDirectoryURL: bundled.workingDirectoryURL
            )
        }

        let paths = developmentEntrypoint()

        return SidecarLaunchConfiguration(
            executableURL: URL(fileURLWithPath: "/usr/bin/env"),
            arguments: [
                "node",
                paths.entrypointURL.path,
                "--health-check",
                "--protocol-version",
                protocolVersion
            ],
            workingDirectoryURL: paths.projectRootURL
        )
    }

    static func runtimeRead(
        kind: String,
        planDate: String? = nil,
        limit: Int? = nil,
        sessionID: String? = nil,
        query: String? = nil,
        includeDisabled: Bool? = nil,
        referenceDate: String? = nil,
        environment: [String: String] = [:]
    ) -> SidecarLaunchConfiguration {
        let useBundled = bundledRuntime()
        let paths = developmentEntrypoint()
        var arguments = useBundled == nil
            ? ["node", paths.entrypointURL.path, "--read", kind]
            : [useBundled!.entrypointURL.path, "--read", kind]

        if let planDate {
            arguments.append(contentsOf: ["--plan-date", planDate])
        }
        if let limit {
            arguments.append(contentsOf: ["--limit", String(limit)])
        }
        if let sessionID {
            arguments.append(contentsOf: ["--session-id", sessionID])
        }
        if let query {
            arguments.append(contentsOf: ["--query", query])
        }
        if let includeDisabled {
            arguments.append(contentsOf: ["--include-disabled", includeDisabled ? "true" : "false"])
        }
        if let referenceDate {
            arguments.append(contentsOf: ["--reference-date", referenceDate])
        }

        return SidecarLaunchConfiguration(
            executableURL: useBundled?.nodeURL ?? URL(fileURLWithPath: "/usr/bin/env"),
            arguments: arguments,
            workingDirectoryURL: useBundled?.workingDirectoryURL ?? paths.projectRootURL,
            environment: environment
        )
    }

    static func runtimeWrite(
        kind: String,
        payloadData: Data,
        environment: [String: String] = [:]
    ) -> SidecarLaunchConfiguration {
        let useBundled = bundledRuntime()
        let paths = developmentEntrypoint()
        let arguments = useBundled == nil
            ? ["node", paths.entrypointURL.path, "--write", kind, "--payload-base64", payloadData.base64EncodedString()]
            : [useBundled!.entrypointURL.path, "--write", kind, "--payload-base64", payloadData.base64EncodedString()]

        return SidecarLaunchConfiguration(
            executableURL: useBundled?.nodeURL ?? URL(fileURLWithPath: "/usr/bin/env"),
            arguments: arguments,
            workingDirectoryURL: useBundled?.workingDirectoryURL ?? paths.projectRootURL,
            environment: environment
        )
    }

    static func runtimeAssistant(
        mode: String,
        payloadData: Data,
        environment: [String: String] = [:]
    ) -> SidecarLaunchConfiguration {
        let useBundled = bundledRuntime()
        let paths = developmentEntrypoint()
        let arguments = useBundled == nil
            ? ["node", paths.entrypointURL.path, "--assistant-mode", mode, "--payload-base64", payloadData.base64EncodedString()]
            : [useBundled!.entrypointURL.path, "--assistant-mode", mode, "--payload-base64", payloadData.base64EncodedString()]

        return SidecarLaunchConfiguration(
            executableURL: useBundled?.nodeURL ?? URL(fileURLWithPath: "/usr/bin/env"),
            arguments: arguments,
            workingDirectoryURL: useBundled?.workingDirectoryURL ?? paths.projectRootURL,
            environment: environment
        )
    }
}

private struct ProcessOutput {
    let exitCode: Int32
    let stdout: String
    let stderr: String
}

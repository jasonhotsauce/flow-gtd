import Foundation

enum SidecarProtocol {
    static let jsonrpcVersion = "2.0"
    static let protocolVersion = "2026-05-02"
    static let healthCheckMethod = "health.check"
    static let incompatibleProtocolCode = -32001
    static let methodNotFoundCode = -32601
    static let bridgeUnavailableCode = -32010
}

enum SidecarTransport: String, Codable, Equatable {
    case stdio
}

struct SidecarRequestEnvelope<Params: Codable & Equatable>: Codable, Equatable {
    let jsonrpc: String
    let id: String
    let method: String
    let params: Params
}

struct SidecarSuccessResponseEnvelope<ResultPayload: Codable & Equatable>: Codable, Equatable {
    let jsonrpc: String
    let id: String
    let result: ResultPayload
}

struct SidecarErrorEnvelope<ErrorData: Codable & Equatable>: Codable, Equatable {
    let code: Int
    let message: String
    let data: ErrorData?
}

struct SidecarErrorResponseEnvelope<ErrorData: Codable & Equatable>: Codable, Equatable {
    let jsonrpc: String
    let id: String
    let error: SidecarErrorEnvelope<ErrorData>
}

struct SidecarProtocolVersionMismatchData: Codable, Equatable {
    let supportedProtocolVersion: String
}

struct SidecarHealthCheckParams: Codable, Equatable {
    let protocolVersion: String
}

struct SidecarHealthCheckResult: Codable, Equatable {
    let protocolVersion: String
    let sidecarVersion: String
    let transport: SidecarTransport
    let status: String
    let capabilities: [String]
}

typealias SidecarHealthCheckRequest = SidecarRequestEnvelope<SidecarHealthCheckParams>
typealias SidecarHealthCheckSuccessResponse = SidecarSuccessResponseEnvelope<SidecarHealthCheckResult>
typealias SidecarHealthCheckErrorResponse = SidecarErrorResponseEnvelope<SidecarProtocolVersionMismatchData>

struct SidecarReadyEvent: Codable, Equatable {
    let event: String
    let mode: String
    let transport: SidecarTransport
    let version: String
}

struct SidecarLaunchConfiguration: Equatable {
    let executableURL: URL
    let arguments: [String]
    var workingDirectoryURL: URL? = nil
    var environment: [String: String] = [:]
}

struct SidecarSupervisorPolicy: Equatable {
    let readinessTimeout: TimeInterval
    let maxAutomaticRestarts: Int
}

struct SidecarDegradedState: Equatable {
    let restartCount: Int
    let failureReasons: [String]
    let recoverySuggestion: String
}

enum SidecarSupervisorStatus: Equatable {
    case idle
    case starting(attempt: Int)
    case ready(SidecarReadyEvent)
    case degraded(SidecarDegradedState)
}

import {
  createErrorResponse,
  createSuccessResponse,
  HEALTH_CHECK_METHOD,
  INCOMPATIBLE_PROTOCOL_CODE,
  METHOD_NOT_FOUND_CODE,
  PROTOCOL_VERSION,
  type HealthCheckRequest,
  type HealthCheckResponse
} from "../protocol.js";

export interface HealthCheckHandlerOptions {
  sidecarVersion: string;
}

export function createHealthCheckRequest(options: {
  id: string;
  protocolVersion: string;
}): HealthCheckRequest {
  return {
    jsonrpc: "2.0",
    id: options.id,
    method: HEALTH_CHECK_METHOD,
    params: {
      protocolVersion: options.protocolVersion
    }
  };
}

export function handleHealthCheck(
  request: HealthCheckRequest,
  options: HealthCheckHandlerOptions
): HealthCheckResponse {
  if (request.method !== HEALTH_CHECK_METHOD) {
    return createErrorResponse(
      request.id,
      METHOD_NOT_FOUND_CODE,
      `Unsupported method ${request.method}.`
    );
  }

  if (request.params.protocolVersion !== PROTOCOL_VERSION) {
    return createErrorResponse(
      request.id,
      INCOMPATIBLE_PROTOCOL_CODE,
      "Unsupported protocol version.",
      {
        supportedProtocolVersion: PROTOCOL_VERSION
      }
    );
  }

  return createSuccessResponse(request.id, {
    protocolVersion: PROTOCOL_VERSION,
    sidecarVersion: options.sidecarVersion,
    transport: "stdio",
    status: "ok",
    capabilities: [HEALTH_CHECK_METHOD]
  });
}

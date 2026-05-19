export const JSONRPC_VERSION = "2.0" as const;
export const PROTOCOL_VERSION = "2026-05-02" as const;
export const HEALTH_CHECK_METHOD = "health.check" as const;
export const APPLE_PERMISSIONS_STATUS_METHOD = "apple.permissions.status" as const;
export const APPLE_REMINDERS_STATUS_METHOD = "apple.reminders.status" as const;
export const APPLE_CALENDAR_STATUS_METHOD = "apple.calendar.status" as const;
export const APPLE_NOTIFICATION_CAPABILITY_METHOD =
  "apple.notifications.capability" as const;
export const INCOMPATIBLE_PROTOCOL_CODE = -32001 as const;
export const METHOD_NOT_FOUND_CODE = -32601 as const;
export const BRIDGE_UNAVAILABLE_CODE = -32010 as const;

export type JSONRPCVersion = typeof JSONRPC_VERSION;
export type ProtocolVersion = typeof PROTOCOL_VERSION;
export type SidecarMethod =
  | typeof HEALTH_CHECK_METHOD
  | typeof APPLE_PERMISSIONS_STATUS_METHOD
  | typeof APPLE_REMINDERS_STATUS_METHOD
  | typeof APPLE_CALENDAR_STATUS_METHOD
  | typeof APPLE_NOTIFICATION_CAPABILITY_METHOD;

export interface SidecarRequestEnvelope<
  TMethod extends string,
  TParams extends object
> {
  jsonrpc: JSONRPCVersion;
  id: string;
  method: TMethod;
  params: TParams;
}

export interface SidecarSuccessResponseEnvelope<TResult> {
  jsonrpc: JSONRPCVersion;
  id: string;
  result: TResult;
}

export interface SidecarErrorResponseEnvelope<TData = undefined> {
  jsonrpc: JSONRPCVersion;
  id: string;
  error: {
    code: number;
    message: string;
    data?: TData;
  };
}

export interface HealthCheckParams {
  protocolVersion: string;
}

export interface HealthCheckResult {
  protocolVersion: ProtocolVersion;
  sidecarVersion: string;
  transport: "stdio";
  status: "ok";
  capabilities: [typeof HEALTH_CHECK_METHOD];
}

export interface ProtocolVersionMismatchData {
  supportedProtocolVersion: ProtocolVersion;
}

export type HealthCheckRequest = SidecarRequestEnvelope<
  typeof HEALTH_CHECK_METHOD,
  HealthCheckParams
>;

export type HealthCheckSuccessResponse = SidecarSuccessResponseEnvelope<HealthCheckResult>;
export type HealthCheckErrorResponse = SidecarErrorResponseEnvelope<ProtocolVersionMismatchData>;
export type HealthCheckResponse =
  | HealthCheckSuccessResponse
  | HealthCheckErrorResponse;

export function createSuccessResponse<TResult>(
  id: string,
  result: TResult
): SidecarSuccessResponseEnvelope<TResult> {
  return {
    jsonrpc: JSONRPC_VERSION,
    id,
    result
  };
}

export function createErrorResponse<TData>(
  id: string,
  code: number,
  message: string,
  data?: TData
): SidecarErrorResponseEnvelope<TData> {
  return {
    jsonrpc: JSONRPC_VERSION,
    id,
    error: data === undefined
      ? { code, message }
      : { code, message, data }
  };
}

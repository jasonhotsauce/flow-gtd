import {
  APPLE_CALENDAR_STATUS_METHOD,
  APPLE_NOTIFICATION_CAPABILITY_METHOD,
  APPLE_PERMISSIONS_STATUS_METHOD,
  APPLE_REMINDERS_STATUS_METHOD,
  BRIDGE_UNAVAILABLE_CODE,
  METHOD_NOT_FOUND_CODE,
  createErrorResponse,
  createSuccessResponse
} from "../protocol.js";
import type {
  AppleBridgeErrorResponse,
  AppleBridgeRequest,
  AppleBridgeResponse,
  AppleCalendarStatusParams,
  AppleNotificationCapabilityParams,
  ApplePermissionsStatusParams,
  AppleRemindersStatusParams
} from "../../bridges/apple/protocol.js";
import { APPLE_BRIDGE_METHODS } from "../../bridges/apple/protocol.js";
import type { AppleBridgeHost } from "../../bridges/apple/stub-host.js";

export function createPermissionsStatusRequest(options: {
  id: string;
  domains: ApplePermissionsStatusParams["domains"];
}): AppleBridgeRequest {
  return {
    jsonrpc: "2.0",
    id: options.id,
    method: APPLE_PERMISSIONS_STATUS_METHOD,
    params: {
      domains: options.domains
    }
  };
}

export function createRemindersStatusRequest(options: {
  id: string;
  taskIds?: string[];
  writeBack?: boolean;
}): AppleBridgeRequest {
  return {
    jsonrpc: "2.0",
    id: options.id,
    method: APPLE_REMINDERS_STATUS_METHOD,
    params: {
      taskIds: options.taskIds ?? [],
      writeBack: options.writeBack ?? false
    } satisfies AppleRemindersStatusParams
  };
}

export function createCalendarStatusRequest(options: {
  id: string;
  taskIds?: string[];
}): AppleBridgeRequest {
  return {
    jsonrpc: "2.0",
    id: options.id,
    method: APPLE_CALENDAR_STATUS_METHOD,
    params: {
      taskIds: options.taskIds ?? []
    } satisfies AppleCalendarStatusParams
  };
}

export function createNotificationCapabilityRequest(options: {
  id: string;
  includePendingCandidates?: boolean;
}): AppleBridgeRequest {
  return {
    jsonrpc: "2.0",
    id: options.id,
    method: APPLE_NOTIFICATION_CAPABILITY_METHOD,
    params: {
      includePendingCandidates: options.includePendingCandidates ?? false
    } satisfies AppleNotificationCapabilityParams
  };
}

export function createBridgeUnavailableResponse(id: string): AppleBridgeErrorResponse {
  return createErrorResponse(
    id,
    BRIDGE_UNAVAILABLE_CODE,
    "Apple bridge host unavailable.",
    {
      kind: "bridge_unavailable",
      retryable: true,
      supportedMethods: [...APPLE_BRIDGE_METHODS]
    }
  );
}

export function handleAppleBridgeRequest(
  request: AppleBridgeRequest,
  host?: AppleBridgeHost
): AppleBridgeResponse {
  if (!APPLE_BRIDGE_METHODS.includes(request.method as typeof APPLE_BRIDGE_METHODS[number])) {
    return createErrorResponse(
      request.id,
      METHOD_NOT_FOUND_CODE,
      `Unsupported method ${request.method}.`,
      {
        kind: "unsupported_operation",
        retryable: false,
        supportedMethods: [...APPLE_BRIDGE_METHODS]
      }
    );
  }

  if (!host) {
    return createBridgeUnavailableResponse(request.id);
  }

  switch (request.method) {
    case APPLE_PERMISSIONS_STATUS_METHOD:
      return createSuccessResponse(
        request.id,
        host.permissionsStatus(request.params)
      );
    case APPLE_REMINDERS_STATUS_METHOD:
      return createSuccessResponse(
        request.id,
        host.remindersStatus(request.params)
      );
    case APPLE_CALENDAR_STATUS_METHOD:
      return createSuccessResponse(
        request.id,
        host.calendarStatus(request.params)
      );
    case APPLE_NOTIFICATION_CAPABILITY_METHOD:
      return createSuccessResponse(
        request.id,
        host.notificationCapability(request.params)
      );
  }
}

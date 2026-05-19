import type {
  SidecarErrorResponseEnvelope,
  SidecarRequestEnvelope,
  SidecarSuccessResponseEnvelope
} from "../../ipc/protocol.js";
import {
  APPLE_CALENDAR_STATUS_METHOD,
  APPLE_NOTIFICATION_CAPABILITY_METHOD,
  APPLE_PERMISSIONS_STATUS_METHOD,
  APPLE_REMINDERS_STATUS_METHOD
} from "../../ipc/protocol.js";

export type AppleBridgeDomain = "reminders" | "calendar" | "notifications";
export type ApplePermissionStatus =
  | "not_determined"
  | "denied"
  | "authorized"
  | "restricted"
  | "write_only"
  | "unsupported";

export type AppleBridgeStubStatus = "stubbed";

export interface ApplePermissionRecord {
  domain: AppleBridgeDomain;
  status: ApplePermissionStatus;
  canPrompt: boolean;
  detail: string;
}

export interface ApplePermissionsStatusParams {
  domains: AppleBridgeDomain[];
}

export interface ApplePermissionsStatusResult {
  permissions: ApplePermissionRecord[];
}

export interface AppleRemindersStatusParams {
  taskIds: string[];
  writeBack: boolean;
}

export interface AppleRemindersStatusResult {
  status: AppleBridgeStubStatus;
  importedCount: number;
  updatedCount: number;
  conflictsCount: number;
  detail: string;
}

export interface AppleCalendarStatusParams {
  taskIds: string[];
}

export interface AppleCalendarStatusResult {
  status: AppleBridgeStubStatus;
  syncedCount: number;
  conflictsCount: number;
  detail: string;
}

export interface AppleNotificationCapabilityParams {
  includePendingCandidates: boolean;
}

export interface AppleNotificationCapabilityResult {
  status: AppleBridgeStubStatus;
  permissionStatus: ApplePermissionStatus;
  deliveryMode: "degraded" | "flow_owned_local";
  available: boolean;
  pendingCandidateCount: number;
  detail: string;
}

export interface AppleBridgeErrorData {
  kind: "bridge_unavailable" | "unsupported_operation";
  retryable: boolean;
  supportedMethods?: string[];
}

export type ApplePermissionsStatusRequest = SidecarRequestEnvelope<
  typeof APPLE_PERMISSIONS_STATUS_METHOD,
  ApplePermissionsStatusParams
>;
export type ApplePermissionsStatusResponse =
  SidecarSuccessResponseEnvelope<ApplePermissionsStatusResult>;

export type AppleRemindersStatusRequest = SidecarRequestEnvelope<
  typeof APPLE_REMINDERS_STATUS_METHOD,
  AppleRemindersStatusParams
>;
export type AppleRemindersStatusResponse =
  SidecarSuccessResponseEnvelope<AppleRemindersStatusResult>;

export type AppleCalendarStatusRequest = SidecarRequestEnvelope<
  typeof APPLE_CALENDAR_STATUS_METHOD,
  AppleCalendarStatusParams
>;
export type AppleCalendarStatusResponse =
  SidecarSuccessResponseEnvelope<AppleCalendarStatusResult>;

export type AppleNotificationCapabilityRequest = SidecarRequestEnvelope<
  typeof APPLE_NOTIFICATION_CAPABILITY_METHOD,
  AppleNotificationCapabilityParams
>;
export type AppleNotificationCapabilityResponse =
  SidecarSuccessResponseEnvelope<AppleNotificationCapabilityResult>;

export type AppleBridgeErrorResponse =
  SidecarErrorResponseEnvelope<AppleBridgeErrorData>;

export type AppleBridgeRequest =
  | ApplePermissionsStatusRequest
  | AppleRemindersStatusRequest
  | AppleCalendarStatusRequest
  | AppleNotificationCapabilityRequest;

export type AppleBridgeResponse =
  | ApplePermissionsStatusResponse
  | AppleRemindersStatusResponse
  | AppleCalendarStatusResponse
  | AppleNotificationCapabilityResponse
  | AppleBridgeErrorResponse;

export const APPLE_BRIDGE_METHODS = [
  APPLE_PERMISSIONS_STATUS_METHOD,
  APPLE_REMINDERS_STATUS_METHOD,
  APPLE_CALENDAR_STATUS_METHOD,
  APPLE_NOTIFICATION_CAPABILITY_METHOD
] as const;

import type {
  AppleBridgeDomain,
  AppleCalendarStatusParams,
  AppleCalendarStatusResult,
  AppleNotificationCapabilityParams,
  AppleNotificationCapabilityResult,
  ApplePermissionRecord,
  ApplePermissionsStatusParams,
  ApplePermissionsStatusResult,
  AppleRemindersStatusParams,
  AppleRemindersStatusResult
} from "./protocol.js";

export interface AppleBridgeHost {
  permissionsStatus(
    params: ApplePermissionsStatusParams
  ): ApplePermissionsStatusResult;
  remindersStatus(
    params: AppleRemindersStatusParams
  ): AppleRemindersStatusResult;
  calendarStatus(params: AppleCalendarStatusParams): AppleCalendarStatusResult;
  notificationCapability(
    params: AppleNotificationCapabilityParams
  ): AppleNotificationCapabilityResult;
}

function defaultPermissionRecord(domain: AppleBridgeDomain): ApplePermissionRecord {
  if (domain === "notifications") {
    return {
      domain,
      status: "not_determined",
      canPrompt: true,
      detail:
        "Notification permission has not been requested yet; Flow should remain in degraded local-delivery mode."
    };
  }

  return {
    domain,
    status: "not_determined",
    canPrompt: true,
    detail: `${domain} bridge is stubbed until native Apple integration is wired through IPC.`
  };
}

export function createStubAppleBridgeHost(): AppleBridgeHost {
  return {
    permissionsStatus(params) {
      return {
        permissions: params.domains.map(defaultPermissionRecord)
      };
    },
    remindersStatus(params) {
      return {
        status: "stubbed",
        importedCount: 0,
        updatedCount: params.writeBack ? 0 : 0,
        conflictsCount: 0,
        detail:
          params.taskIds.length === 0
            ? "Reminders bridge stub acknowledged capability probe."
            : "Reminders bridge stub accepted the task scope but did not contact EventKit."
      };
    },
    calendarStatus(params) {
      return {
        status: "stubbed",
        syncedCount: 0,
        conflictsCount: 0,
        detail:
          params.taskIds.length === 0
            ? "Calendar bridge stub acknowledged capability probe."
            : "Calendar bridge stub accepted the task scope but did not contact EventKit."
      };
    },
    notificationCapability(params) {
      return {
        status: "stubbed",
        permissionStatus: "not_determined",
        deliveryMode: "degraded",
        available: false,
        pendingCandidateCount: params.includePendingCandidates ? 0 : 0,
        detail:
          "Notification capability is stubbed; Flow should treat delivery as degraded until the Swift bridge is wired."
      };
    }
  };
}

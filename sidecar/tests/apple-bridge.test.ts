import { describe, expect, it } from "vitest";
import { createStubAppleBridgeHost } from "../src/bridges/apple/stub-host.js";
import {
  APPLE_NOTIFICATION_CAPABILITY_METHOD,
  APPLE_PERMISSIONS_STATUS_METHOD,
  BRIDGE_UNAVAILABLE_CODE,
  METHOD_NOT_FOUND_CODE
} from "../src/ipc/protocol.js";
import {
  createCalendarStatusRequest,
  createNotificationCapabilityRequest,
  createPermissionsStatusRequest,
  createRemindersStatusRequest,
  handleAppleBridgeRequest
} from "../src/ipc/messages/apple-bridge.js";

describe("apple bridge stubs", () => {
  it("returns typed permission records from the stub host", () => {
    const response = handleAppleBridgeRequest(
      createPermissionsStatusRequest({
        id: "bridge-1",
        domains: ["reminders", "calendar", "notifications"]
      }),
      createStubAppleBridgeHost()
    );

    expect("result" in response).toBe(true);
    if ("result" in response) {
      expect(response.result.permissions).toHaveLength(3);
      expect(response.result.permissions[0]?.domain).toBe("reminders");
      expect(response.result.permissions[2]?.status).toBe("not_determined");
    }
  });

  it("returns typed reminders and calendar stub results", () => {
    const host = createStubAppleBridgeHost();
    const reminders = handleAppleBridgeRequest(
      createRemindersStatusRequest({
        id: "bridge-2",
        taskIds: ["task-1"],
        writeBack: true
      }),
      host
    );
    const calendar = handleAppleBridgeRequest(
      createCalendarStatusRequest({
        id: "bridge-3",
        taskIds: ["task-1", "task-2"]
      }),
      host
    );

    expect("result" in reminders && reminders.result.status).toBe("stubbed");
    expect("result" in calendar && calendar.result.status).toBe("stubbed");
  });

  it("returns a typed notification capability stub", () => {
    const response = handleAppleBridgeRequest(
      createNotificationCapabilityRequest({
        id: "bridge-4",
        includePendingCandidates: true
      }),
      createStubAppleBridgeHost()
    );

    expect("result" in response).toBe(true);
    if ("result" in response) {
      expect(response.result.status).toBe("stubbed");
      expect(response.result.deliveryMode).toBe("degraded");
      expect(response.result.available).toBe(false);
    }
  });

  it("maps missing host into the shared bridge-unavailable error model", () => {
    const response = handleAppleBridgeRequest(
      createPermissionsStatusRequest({
        id: "bridge-5",
        domains: ["reminders"]
      })
    );

    expect("error" in response).toBe(true);
    if ("error" in response) {
      expect(response.error.code).toBe(BRIDGE_UNAVAILABLE_CODE);
      expect(response.error.data?.kind).toBe("bridge_unavailable");
      expect(response.error.data?.supportedMethods).toContain(
        APPLE_PERMISSIONS_STATUS_METHOD
      );
      expect(response.error.data?.supportedMethods).toContain(
        APPLE_NOTIFICATION_CAPABILITY_METHOD
      );
    }
  });

  it("maps unsupported methods into the shared method-not-found error", () => {
    const response = handleAppleBridgeRequest(
      {
        jsonrpc: "2.0",
        id: "bridge-6",
        method: "apple.unsupported.method",
        params: {}
      } as never,
      createStubAppleBridgeHost()
    );

    expect("error" in response).toBe(true);
    if ("error" in response) {
      expect(response.error.code).toBe(METHOD_NOT_FOUND_CODE);
      expect(response.error.data?.kind).toBe("unsupported_operation");
    }
  });
});

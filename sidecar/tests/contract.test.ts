import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";
import { runSidecar } from "../src/main.js";
import {
  PROTOCOL_VERSION,
  type HealthCheckResponse
} from "../src/ipc/protocol.js";
import {
  createHealthCheckRequest,
  handleHealthCheck
} from "../src/ipc/messages/health.js";

function readFixture(name: string): HealthCheckResponse {
  return JSON.parse(
    readFileSync(resolve("tests", "fixtures", name), "utf8")
  ) as HealthCheckResponse;
}

describe("health.check contract", () => {
  it("returns the versioned success envelope for health.check", () => {
    const request = createHealthCheckRequest({
      id: "health-check-1",
      protocolVersion: PROTOCOL_VERSION
    });

    const response = handleHealthCheck(request, {
      sidecarVersion: "0.1.0"
    });

    expect(response).toEqual(readFixture("health-check-success.json"));
  });

  it("fails fast on protocol version mismatch", () => {
    const request = createHealthCheckRequest({
      id: "health-check-2",
      protocolVersion: "1999-01-01"
    });

    const response = handleHealthCheck(request, {
      sidecarVersion: "0.1.0"
    });

    expect(response).toEqual(
      readFixture("health-check-version-mismatch.json")
    );
  });

  it("emits the health.check response envelope in health-check mode", async () => {
    const writes: string[] = [];

    const exitCode = await runSidecar({
      args: ["--health-check"],
      stdout: {
        write(chunk) {
          writes.push(String(chunk));
          return true;
        }
      }
    });

    expect(exitCode).toBe(0);
    expect(JSON.parse(writes[0]) as HealthCheckResponse).toEqual(
      readFixture("health-check-success.json")
    );
  });

  it("emits the protocol mismatch envelope in health-check mode when requested", async () => {
    const writes: string[] = [];

    const exitCode = await runSidecar({
      args: ["--health-check", "--protocol-version", "1999-01-01"],
      stdout: {
        write(chunk) {
          writes.push(String(chunk));
          return true;
        }
      }
    });

    expect(exitCode).toBe(0);
    expect(JSON.parse(writes[0]) as HealthCheckResponse).toEqual(
      readFixture("health-check-version-mismatch.json")
    );
  });
});

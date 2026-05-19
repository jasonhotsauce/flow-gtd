import { describe, expect, it } from "vitest";
import { runSidecar } from "../src/main.js";

describe("runSidecar", () => {
  it("emits a deterministic ready payload and exits cleanly in once mode", async () => {
    const writes: string[] = [];

    const exitCode = await runSidecar({
      args: ["--once"],
      stdout: {
        write(chunk) {
          writes.push(String(chunk));
          return true;
        }
      }
    });

    expect(exitCode).toBe(0);
    expect(writes).toEqual([
      JSON.stringify({
        event: "sidecar.ready",
        mode: "once",
        transport: "stdio",
        version: "0.1.0"
      }) + "\n"
    ]);
  });
});

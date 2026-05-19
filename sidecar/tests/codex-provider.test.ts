import { readFileSync, writeFileSync } from "node:fs";
import { describe, expect, it, vi } from "vitest";
import { createCodexProvider } from "../src/agents/codex-provider.js";
import type { ProviderRunRequest } from "../src/agents/contracts.js";

function createRequest(overrides: Partial<ProviderRunRequest> = {}): ProviderRunRequest {
  return {
    requestID: "req-1",
    prompt: "Plan my day",
    specialist: "daily_planner",
    capabilities: ["read_gtd_context", "propose_planning_change"],
    outputMode: "json",
    context: {
      dailyPlanState: {
        planDate: "2026-05-03",
        topItems: [],
        bonusItems: [],
        mustAddress: [],
        inbox: [],
        readyActions: [],
        projectTasks: [],
        riskFlags: [],
        calendarStatus: "Unavailable"
      }
    },
    metadata: {},
    ...overrides
  };
}

function assertStrictResponseSchema(schema: unknown): void {
  if (!schema || typeof schema !== "object" || Array.isArray(schema)) {
    throw new Error("schema must be an object");
  }
  assertStrictObjectSchema(schema as Record<string, unknown>, "schema");
}

function assertStrictObjectSchema(
  schema: Record<string, unknown>,
  path: string
): void {
  if (schema.type === "object") {
    expect(schema.additionalProperties, `${path}.additionalProperties`).toBe(false);
    const properties = schema.properties as Record<string, unknown> | undefined;
    const required = schema.required as string[] | undefined;
    expect(Array.isArray(required), `${path}.required`).toBe(true);
    expect(new Set(required), `${path}.required`).toEqual(
      new Set(Object.keys(properties ?? {}))
    );
    for (const [key, value] of Object.entries(properties ?? {})) {
      assertStrictSchema(value, `${path}.properties.${key}`);
    }
    return;
  }
  assertStrictSchema(schema, path);
}

function assertStrictSchema(schema: unknown, path: string): void {
  if (!schema || typeof schema !== "object" || Array.isArray(schema)) {
    return;
  }
  const record = schema as Record<string, unknown>;
  if (record.type === "object") {
    assertStrictObjectSchema(record, path);
  }
  if (record.type === "array" && record.items) {
    assertStrictSchema(record.items, `${path}.items`);
  }
}

describe("Codex provider adapter", () => {
  it("parses a successful codex response and records Codex evidence", async () => {
    const commandRunner = vi.fn((command: string, args: string[]) => {
      const outputFile = args[args.indexOf("--output-last-message") + 1];
      const schemaFile = args[args.indexOf("--output-schema") + 1];
      assertStrictResponseSchema(JSON.parse(readFileSync(schemaFile, "utf8")));
      writeFileSync(
        outputFile,
        JSON.stringify({
          responseText: "Codex-backed daily plan.",
          structuredOutput: {
            kind: "daily_planner",
            summary: "Codex selected the top focus items.",
            rationale: ["The day needs a tighter commitment set."],
            focusItems: [
              {
                title: "Finish the cutover",
                energy: "high",
                reason: "It unblocks the branch."
              }
            ],
            risks: [],
            writeProposals: []
          },
          model: "codex-test-model",
          usage: {
            inputTokens: 10
          }
        })
      );
      return {
        pid: 1234,
        output: ["", ""],
        stdout: "",
        stderr: "",
        status: 0,
        signal: null
      };
    });

    const provider = createCodexProvider({
      codexBinary: "/opt/homebrew/bin/codex",
      commandRunner
    });

    const result = await provider.run(createRequest());

    expect(commandRunner).toHaveBeenCalled();
    expect(commandRunner.mock.calls[0]?.[1]).toEqual(
      expect.arrayContaining([
        "exec",
        "--skip-git-repo-check",
        "--ephemeral",
        "--ignore-user-config",
        "--ignore-rules",
        "--disable",
        "codex_hooks",
        "--sandbox",
        "read-only",
        "--output-schema",
        "--output-last-message",
        "-"
      ])
    );
    expect(result.responseText).toBe("Codex-backed daily plan.");
    expect(result.model).toBe("codex-test-model");
    expect(result.providerEvidence?.provider).toBe("codex");
    expect(result.providerEvidence?.status).toBe("success");
    expect(result.traceEvents?.[0]?.payload?.provider).toBe("codex");
  });

  it("throws a typed error when codex exits unsuccessfully", async () => {
    const provider = createCodexProvider({
      codexBinary: "/opt/homebrew/bin/codex",
      commandRunner: vi.fn(() => ({
        pid: 1234,
        output: ["", ""],
        stdout: "",
        stderr: "codex auth failed",
        status: 1,
        signal: null
      }))
    });

    await expect(provider.run(createRequest())).rejects.toMatchObject({
      name: "CodexProviderError",
      code: "runtime_failure"
    });
  });

  it("throws a typed error when the codex output is malformed", async () => {
    const commandRunner = vi.fn((command: string, args: string[]) => {
      const outputFile = args[args.indexOf("--output-last-message") + 1];
      writeFileSync(outputFile, "not-json");
      return {
        pid: 1234,
        output: ["", ""],
        stdout: "",
        stderr: "",
        status: 0,
        signal: null
      };
    });

    const provider = createCodexProvider({
      codexBinary: "/opt/homebrew/bin/codex",
      commandRunner
    });

    await expect(provider.run(createRequest())).rejects.toMatchObject({
      name: "CodexProviderError",
      code: "invalid_output"
    });
  });
});

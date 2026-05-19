import { describe, expect, it, vi } from "vitest";
import { runSidecar } from "../src/main.js";
import {
  AssistantOrchestrator
} from "../src/agents/orchestrator.js";
import {
  type AssistantProviderAdapter,
  createProviderRegistry
} from "../src/agents/providers.js";
import { createDefaultSpecialistRegistry } from "../src/agents/specialists.js";
import type {
  AssistantRequest,
  ProviderRunRequest,
  ProviderRunResult
} from "../src/agents/contracts.js";

function createRequest(
  overrides: Partial<AssistantRequest> = {}
): AssistantRequest {
  return {
    requestID: "req-1",
    prompt: "Plan my day",
    routeHint: "daily_plan",
    capabilities: ["read_gtd_context", "propose_planning_change"],
    provider: "openai",
    context: {
      today: "2026-05-03"
    },
    metadata: {},
    ...overrides
  };
}

function createProvider(
  implementation: (
    request: ProviderRunRequest
  ) => Promise<ProviderRunResult> | ProviderRunResult
): AssistantProviderAdapter {
  return {
    name: "openai",
    run: implementation
  };
}

describe("AssistantOrchestrator", () => {
  it("routes a typed request through the mapped specialist and returns validated structured output", async () => {
    const provider = createProvider(async (request) => ({
      responseText: "Daily plan ready.",
      structuredOutput: {
        kind: request.specialist,
        summary: "Focus on two high-leverage tasks.",
        rationale: ["One deadline is approaching."],
        focusItems: [
          {
            title: "Finish migration",
            energy: "high",
            reason: "Unblocks the next phase."
          }
        ],
        risks: ["Calendar slots are fragmented."]
      },
      traceEvents: [
        {
          stage: "provider",
          summary: "Provider returned daily plan payload.",
          provider: "openai",
          payload: {
            specialist: request.specialist
          }
        }
      ]
    }));
    const orchestrator = new AssistantOrchestrator({
      specialists: createDefaultSpecialistRegistry(),
      providers: createProviderRegistry([provider])
    });

    const result = await orchestrator.handle(createRequest());

    expect(result.failed).toBe(false);
    expect(result.specialist).toBe("daily_planner");
    expect(result.structuredOutput?.kind).toBe("daily_planner");
    expect(result.fallbackReason).toBeUndefined();
    expect(result.traceEvents.map((event) => event.stage)).toEqual([
      "route",
      "provider"
    ]);
  });

  it("returns a deterministic capability-denied fallback without calling the provider", async () => {
    const provider = {
      name: "openai",
      run: vi.fn(async () => ({
        responseText: "should not execute",
        structuredOutput: {}
      }))
    } satisfies AssistantProviderAdapter;
    const orchestrator = new AssistantOrchestrator({
      specialists: createDefaultSpecialistRegistry(),
      providers: createProviderRegistry([provider])
    });

    const result = await orchestrator.handle(
      createRequest({
        capabilities: ["read_gtd_context"]
      })
    );

    expect(result.failed).toBe(true);
    expect(result.fallbackReason).toBe("capability_denied");
    expect(result.responseText).toContain("propose_planning_change");
    expect(provider.run).not.toHaveBeenCalled();
  });

  it("returns a deterministic provider-failure fallback when the provider throws", async () => {
    const orchestrator = new AssistantOrchestrator({
      specialists: createDefaultSpecialistRegistry(),
      providers: createProviderRegistry([
        createProvider(async () => {
          throw new Error("provider offline");
        })
      ])
    });

    const result = await orchestrator.handle(createRequest());

    expect(result.failed).toBe(true);
    expect(result.fallbackReason).toBe("provider_failed");
    expect(result.responseText).toContain("daily_planner");
    expect(result.traceEvents.at(-1)?.stage).toBe("fallback");
  });

  it("falls back deterministically when structured output fails specialist validation", async () => {
    const orchestrator = new AssistantOrchestrator({
      specialists: createDefaultSpecialistRegistry(),
      providers: createProviderRegistry([
        createProvider(async () => ({
          responseText: "invalid payload",
          structuredOutput: {
            kind: "daily_planner",
            summary: "Missing focus items",
            rationale: []
          }
        }))
      ])
    });

    const result = await orchestrator.handle(createRequest());

    expect(result.failed).toBe(true);
    expect(result.fallbackReason).toBe("validation_failed");
    expect(result.responseText).toContain("deterministic fallback");
  });

  it("falls back when a write proposal carries invalid verification status", async () => {
    const orchestrator = new AssistantOrchestrator({
      specialists: createDefaultSpecialistRegistry(),
      providers: createProviderRegistry([
        createProvider(async () => ({
          responseText: "proposal ready",
          structuredOutput: {
            kind: "daily_planner",
            summary: "Try one change.",
            rationale: ["A bounded proposal is available."],
            focusItems: [
              {
                title: "Refine the task title",
                energy: "medium",
                reason: "Keeps the proposal scoped."
              }
            ],
            writeProposals: [
              {
                actionType: "edit_task",
                targetTable: "tasks",
                targetID: "task-1",
                previewText: "Rename task",
                rationale: "Tighten the scope.",
                confidence: 0.9,
                requiresConfirmation: true,
                verificationStatus: "unsafe",
                payload: {
                  title: "Renamed task"
                }
              }
            ]
          }
        }))
      ])
    });

    const result = await orchestrator.handle(createRequest());

    expect(result.failed).toBe(true);
    expect(result.fallbackReason).toBe("validation_failed");
  });

  it("accepts confirmation-gated daily planner tool proposals", async () => {
    const orchestrator = new AssistantOrchestrator({
      specialists: createDefaultSpecialistRegistry(),
      providers: createProviderRegistry([
        createProvider(async () => ({
          responseText: "I can save this plan after confirmation.",
          structuredOutput: {
            kind: "daily_planner",
            summary: "Prepared a bounded plan update.",
            rationale: ["The user asked for planning help."],
            focusItems: [
              {
                title: "Draft launch checklist",
                energy: "medium",
                reason: "Project task is ready."
              }
            ],
            risks: [],
            writeProposals: [
              {
                actionType: "save_daily_plan",
                targetTable: "daily_plan_entries",
                targetID: "2026-05-03",
                previewText: "Save Draft launch checklist to today's plan.",
                rationale: "User asked the assistant to plan the day.",
                confidence: 0.9,
                requiresConfirmation: true,
                verificationStatus: "validated",
                payload: {
                  planDate: "2026-05-03",
                  topItemIDs: "project-task-1",
                  bonusItemIDs: ""
                }
              }
            ]
          }
        }))
      ])
    });

    const result = await orchestrator.handle(createRequest());

    expect(result.failed).toBe(false);
    expect(result.writeProposals[0]?.actionType).toBe("save_daily_plan");
  });

  it("accepts an assistant request in sidecar CLI mode", async () => {
    const writes: string[] = [];

    const exitCode = await runSidecar({
      args: [
        "--assistant-request",
        JSON.stringify(
          createRequest({
            provider: "openai"
          })
        )
      ],
      stdout: {
        write(chunk) {
          writes.push(String(chunk));
          return true;
        }
      },
      providerAdapters: [
        createProvider(async (request) => ({
          responseText: "Daily plan ready.",
          structuredOutput: {
            kind: request.specialist,
            summary: "Two tasks deserve focus today.",
            rationale: ["The release cutover is near."],
            focusItems: [
              {
                title: "Finish TASK-012",
                energy: "high",
                reason: "Unblocks assistant migration."
              }
            ]
          }
        }))
      ]
    });

    expect(exitCode).toBe(0);
    expect(JSON.parse(writes[0]) as { failed: boolean; specialist: string }).toMatchObject({
      failed: false,
      specialist: "daily_planner"
    });
  });
});

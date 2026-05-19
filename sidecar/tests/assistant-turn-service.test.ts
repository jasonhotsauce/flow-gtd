import type { DatabaseSync } from "node:sqlite";
import { mkdtempSync, rmSync } from "node:fs";
import { join } from "node:path";
import { tmpdir } from "node:os";
import { describe, expect, it } from "vitest";
import { createDeterministicProvider } from "../src/agents/deterministic-provider.js";
import { createProviderRegistry } from "../src/agents/providers.js";
import { bootstrapFlowDatabase } from "../src/db/database.js";
import { FlowReadRepository } from "../src/db/repositories/read-repository.js";
import { AssistantSessionMessageService } from "../src/services/assistant-session-message-service.js";
import { AssistantTurnService } from "../src/services/assistant-turn-service.js";

function seedProject(connection: DatabaseSync, projectID = "project-1"): void {
  connection.prepare(
    `
      INSERT INTO items (
        id, type, title, status, context_tags, parent_id, created_at,
        due_date, meta_payload, original_ek_id, estimated_duration, updated_at
      ) VALUES (?, 'project', 'Launch prep', 'active', '[]', NULL, ?, NULL, '{}', NULL, NULL, ?)
    `
  ).run(projectID, "2026-05-03T08:00:00.000Z", "2026-05-03T08:00:00.000Z");
}

function seedProjectTask(
  connection: DatabaseSync,
  projectID = "project-1",
  taskID = "project-task-1"
): void {
  seedProject(connection, projectID);
  connection.prepare(
    `
      INSERT INTO items (
        id, type, title, status, context_tags, parent_id, created_at,
        due_date, meta_payload, original_ek_id, estimated_duration, updated_at
      ) VALUES (?, 'action', 'Draft launch checklist', 'active', '[]', ?, ?, NULL, '{}', NULL, NULL, ?)
    `
  ).run(taskID, projectID, "2026-05-03T09:00:00.000Z", "2026-05-03T09:00:00.000Z");
  connection.prepare(
    `
      INSERT INTO tasks (
        id, title, status, project_id, source_inbox_item_id,
        time_sensitivity, effort_band, created_at, updated_at
      ) VALUES (?, 'Draft launch checklist', 'active', ?, NULL, 'flexible', 'medium', ?, ?)
    `
  ).run(taskID, projectID, "2026-05-03T09:00:00.000Z", "2026-05-03T09:00:00.000Z");
}

async function withAssistantService(
  test: (
    service: AssistantTurnService,
    readRepository: FlowReadRepository,
    connection: DatabaseSync
  ) => Promise<void>
): Promise<void> {
  const directory = mkdtempSync(join(tmpdir(), "flow-sidecar-assistant-"));
  const owner = bootstrapFlowDatabase(join(directory, "flow.sqlite"));
  const service = new AssistantTurnService(owner.connection(), {
    assistantProvider: "deterministic",
    providerRegistry: createProviderRegistry([createDeterministicProvider()])
  });
  const readRepository = new FlowReadRepository(owner.connection());
  try {
    await test(service, readRepository, owner.connection());
  } finally {
    owner.close();
    rmSync(directory, { recursive: true, force: true });
  }
}

describe("AssistantSessionMessageService", () => {
  it("grounds day planning in project-linked tasks when no inbox or confirmed plan exists", async () => {
    const directory = mkdtempSync(join(tmpdir(), "flow-sidecar-session-message-"));
    const owner = bootstrapFlowDatabase(join(directory, "flow.sqlite"));
    const service = new AssistantSessionMessageService(owner.connection(), {
      assistantProvider: "deterministic",
      providerRegistry: createProviderRegistry([createDeterministicProvider()])
    });
    const readRepository = new FlowReadRepository(owner.connection());
    try {
      seedProjectTask(owner.connection());
      const session = service.createSession("Plan my day");

      const message = await service.sendMessage(
        session.id,
        "Plan my day",
        "2026-05-03"
      );

      expect(message.content).toContain("Draft launch checklist");
      expect(message.content).not.toContain("0 inbox items");
      expect(readRepository.loadAssistantMessages(session.id)[1]?.content).toContain(
        "Draft launch checklist"
      );
    } finally {
      owner.close();
      rmSync(directory, { recursive: true, force: true });
    }
  });

  it("passes CRUD tool contracts for plans projects and tasks to the day-planning provider", async () => {
    const directory = mkdtempSync(join(tmpdir(), "flow-sidecar-session-message-"));
    const owner = bootstrapFlowDatabase(join(directory, "flow.sqlite"));
    let capturedContext: Record<string, unknown> | undefined;
    const provider = {
      name: "codex" as const,
      run: async (request: { context: Record<string, unknown>; specialist: string }) => {
        capturedContext = request.context;
        return {
          responseText: "Daily plan ready.",
          structuredOutput: {
            kind: "daily_planner",
            summary: "Prepared a grounded plan.",
            rationale: ["Used available planning tools."],
            focusItems: [
              {
                title: "Draft launch checklist",
                energy: "medium",
                reason: "Project task is available for planning."
              }
            ],
            risks: []
          }
        };
      }
    };
    const service = new AssistantSessionMessageService(owner.connection(), {
      assistantProvider: "codex",
      providerRegistry: createProviderRegistry([provider])
    });
    try {
      seedProjectTask(owner.connection());
      const session = service.createSession("Plan my day");

      await service.sendMessage(session.id, "Plan my day", "2026-05-03");

      expect(capturedContext?.agentTools).toEqual(
        expect.arrayContaining([
          expect.objectContaining({ entity: "plan", operation: "create" }),
          expect.objectContaining({ entity: "plan", operation: "read" }),
          expect.objectContaining({ entity: "plan", operation: "update" }),
          expect.objectContaining({ entity: "plan", operation: "delete" }),
          expect.objectContaining({ entity: "project", operation: "create" }),
          expect.objectContaining({ entity: "project", operation: "read" }),
          expect.objectContaining({ entity: "project", operation: "update" }),
          expect.objectContaining({ entity: "project", operation: "delete" }),
          expect.objectContaining({ entity: "task", operation: "create" }),
          expect.objectContaining({ entity: "task", operation: "read" }),
          expect.objectContaining({ entity: "task", operation: "update" }),
          expect.objectContaining({ entity: "task", operation: "delete" })
        ])
      );
    } finally {
      owner.close();
      rmSync(directory, { recursive: true, force: true });
    }
  });

  it("confirms assistant daily-plan proposals into saved plan entries", async () => {
    const directory = mkdtempSync(join(tmpdir(), "flow-sidecar-session-message-"));
    const owner = bootstrapFlowDatabase(join(directory, "flow.sqlite"));
    const provider = {
      name: "codex" as const,
      run: async () => ({
        responseText: "I can save Draft launch checklist as today's top focus.",
        structuredOutput: {
          kind: "daily_planner",
          summary: "Prepared a saved plan proposal.",
          rationale: ["The project task is ready for today."],
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
              previewText: "Save Draft launch checklist as today's top focus.",
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
      })
    };
    const service = new AssistantSessionMessageService(owner.connection(), {
      assistantProvider: "codex",
      providerRegistry: createProviderRegistry([provider])
    });
    const readRepository = new FlowReadRepository(owner.connection());
    try {
      seedProjectTask(owner.connection());
      const session = service.createSession("Plan my day");
      const message = await service.sendMessage(session.id, "Plan my day", "2026-05-03");

      const confirmation = service.confirmMessage(message.id);

      expect(confirmation).toContain("Saved daily plan");
      expect(readRepository.loadDailyPlanState("2026-05-03").topItems.map((item) => item.id)).toEqual([
        "project-task-1"
      ]);
    } finally {
      owner.close();
      rmSync(directory, { recursive: true, force: true });
    }
  });

  it("persists session messages and targets confirmation by message id", async () => {
    const directory = mkdtempSync(join(tmpdir(), "flow-sidecar-session-message-"));
    const owner = bootstrapFlowDatabase(join(directory, "flow.sqlite"));
    const service = new AssistantSessionMessageService(owner.connection(), {
      assistantProvider: "deterministic",
      providerRegistry: createProviderRegistry([createDeterministicProvider()])
    });
    const readRepository = new FlowReadRepository(owner.connection());
    try {
      const session = service.createSession("Plan my day");
      const message = await service.sendMessage(
        session.id,
        "Add review the launch checklist",
        "2026-05-03"
      );

      expect(readRepository.loadAssistantSessions()[0]?.id).toBe(session.id);
      expect(readRepository.loadAssistantMessages(session.id).map((entry) => entry.role)).toEqual([
        "user",
        "assistant"
      ]);
      expect(readRepository.loadAssistantMessages(session.id)[1]?.proposalStatus).toBe("pending");

      service.confirmMessage(message.id);
      expect(() => service.dismissMessage(message.id)).toThrow(/pending/);
      expect(readRepository.loadAssistantMessages(session.id)[1]?.proposalStatus).toBe("confirmed");

      const undoMessage = service.undoLastMutation();
      expect(undoMessage?.toLowerCase()).toContain("undid");
      expect(readRepository.loadWorkspaceSnapshot().inboxItems).toHaveLength(0);
    } finally {
      owner.close();
      rmSync(directory, { recursive: true, force: true });
    }
  });

  it("reopens persisted assistant sessions and keeps follow-up messages scoped to the selected session", async () => {
    const directory = mkdtempSync(join(tmpdir(), "flow-sidecar-session-message-"));
    const dbPath = join(directory, "flow.sqlite");
    let owner = bootstrapFlowDatabase(dbPath);
    let service = new AssistantSessionMessageService(owner.connection(), {
      assistantProvider: "deterministic",
      providerRegistry: createProviderRegistry([createDeterministicProvider()])
    });
    let readRepository = new FlowReadRepository(owner.connection());

    try {
      const session = service.createSession("Plan my day");
      const firstMessage = await service.sendMessage(
        session.id,
        "Add review the launch checklist",
        "2026-05-03"
      );
      await service.sendMessage(
        session.id,
        "Add a follow-up next action",
        "2026-05-03"
      );

      expect(
        readRepository
          .loadAssistantSessions()
          .find((entry) => entry.id === session.id)?.messageCount
      ).toBe(4);
      expect(
        readRepository.loadAssistantMessages(session.id).map((entry) => entry.role)
      ).toEqual(["user", "assistant", "user", "assistant"]);
      expect(
        readRepository
          .loadAssistantMessages(session.id)
          .every((entry) => entry.sessionID === session.id)
      ).toBe(true);
      expect(readRepository.loadAssistantMessages(session.id)[1]?.provider).toBe(
        "deterministic"
      );
      expect(
        readRepository
          .loadAssistantMessages(session.id)[1]
          ?.auditSteps.some((step) => step.stage === "provider")
      ).toBe(true);

      service.confirmMessage(firstMessage.id);
      expect(readRepository.loadAssistantMessages(session.id)[1]?.proposalStatus).toBe(
        "confirmed"
      );

      const secondSession = service.createSession("Second chat");
      const secondMessage = await service.sendMessage(
        secondSession.id,
        "Remember the review rhythm",
        "2026-05-03"
      );
      expect(
        readRepository.loadAssistantMessages(secondSession.id).map((entry) => entry.role)
      ).toEqual(["user", "assistant"]);
      expect(readRepository.loadAssistantMessages(secondSession.id)[1]?.proposalStatus).toBe(
        "pending"
      );

      service.dismissMessage(secondMessage.id);
      expect(readRepository.loadAssistantMessages(secondSession.id)[1]?.proposalStatus).toBe(
        "dismissed"
      );

      owner.close();
      owner = bootstrapFlowDatabase(dbPath);
      service = new AssistantSessionMessageService(owner.connection(), {
        assistantProvider: "deterministic",
        providerRegistry: createProviderRegistry([createDeterministicProvider()])
      });
      readRepository = new FlowReadRepository(owner.connection());

      expect(
        readRepository
          .loadAssistantSessions()
          .map((entry) => entry.id)
          .sort()
      ).toEqual([session.id, secondSession.id].sort());
      expect(
        readRepository.loadAssistantMessages(session.id).map((entry) => entry.role)
      ).toEqual(["user", "assistant", "user", "assistant"]);
      expect(
        readRepository
          .loadAssistantMessages(session.id)
          .every((entry) => entry.sessionID === session.id)
      ).toBe(true);
      expect(
        readRepository.loadAssistantMessages(secondSession.id).map((entry) => entry.role)
      ).toEqual(["user", "assistant"]);
      expect(readRepository.loadAssistantMessages(secondSession.id)[1]?.proposalStatus).toBe(
        "dismissed"
      );
      expect(readRepository.loadAssistantMessages(secondSession.id)[1]?.provider).toBe(
        "deterministic"
      );
    } finally {
      owner.close();
      rmSync(directory, { recursive: true, force: true });
    }
  });
});

describe("AssistantTurnService", () => {
  it("models session history, scoped messages, and prior-session selection", () => {
    const harness = new AssistantSessionTimelineHarness();

    const firstSessionID = harness.createSession("Plan my day");
    harness.sendMessage(firstSessionID, "user", "Plan my day");
    harness.sendMessage(firstSessionID, "assistant", "Use the top three tasks.");

    const secondSessionID = harness.createSession("Review my system");
    harness.sendMessage(secondSessionID, "user", "Review my system");

    expect(harness.listSessions().map((session) => session.id)).toEqual([secondSessionID, firstSessionID]);
    expect(harness.loadMessages(firstSessionID).map((message) => message.content)).toEqual([
      "Plan my day",
      "Use the top three tasks."
    ]);
    expect(harness.loadMessages(secondSessionID).map((message) => message.content)).toEqual(["Review my system"]);

    harness.selectSession(firstSessionID);
    expect(harness.selectedSessionID).toBe(firstSessionID);
  });

  it("targets proposal confirmation and dismissal by message id", () => {
    const harness = new AssistantSessionTimelineHarness();
    const sessionID = harness.createSession("Capture and remember");
    const firstMessage = harness.sendMessage(sessionID, "assistant", "Add this to memory.", {
      proposalStatus: "pending",
      proposalTarget: "memory-1",
      provider: "codex",
      auditSteps: [
        { stage: "provider", summary: "Codex completed the request." },
        { stage: "validation", summary: "Proposal is ready for confirmation." }
      ]
    });
    const secondMessage = harness.sendMessage(sessionID, "assistant", "Archive the old note.", {
      proposalStatus: "pending",
      proposalTarget: "memory-2"
    });

    harness.confirmProposal(firstMessage.id);
    expect(harness.message(firstMessage.id)?.proposalStatus).toBe("confirmed");
    expect(harness.message(secondMessage.id)?.proposalStatus).toBe("pending");

    harness.dismissProposal(secondMessage.id);
    expect(harness.message(secondMessage.id)?.proposalStatus).toBe("dismissed");
    expect(harness.message(firstMessage.id)?.provider).toBe("codex");
    expect(harness.message(firstMessage.id)?.auditSteps).toHaveLength(2);
  });

  it("preserves provider evidence and audit disclosures on assistant messages", () => {
    const harness = new AssistantSessionTimelineHarness();
    const sessionID = harness.createSession("Plan my day");
    const message = harness.sendMessage(sessionID, "assistant", "Plan the day.", {
      proposalStatus: "pending",
      provider: "codex",
      auditSteps: [
        { stage: "provider", summary: "Codex completed the request." },
        { stage: "validation", summary: "The message is ready for review." }
      ]
    });

    expect(message.provider).toBe("codex");
    expect(message.auditSteps.map((step) => step.stage)).toEqual(["provider", "validation"]);
    expect(harness.loadMessages(sessionID)[0]?.proposalStatus).toBe("pending");
  });

  it("creates pending capture proposals and confirms them into inbox items", async () => {
    await withAssistantService(async (service, readRepository) => {
      const turn = await service.sendPrompt(
        "Add review the launch checklist",
        "2026-03-08"
      );

      expect(turn.route).toBe("capture");
      expect(turn.proposalStatus).toBe("pending");
      expect(turn.proposal?.actionType).toBe("create_task");
      expect(turn.provider).toBe("deterministic");
      expect(turn.providerStatus).toBe("success");
      expect(turn.auditSteps.find((step) => step.stage === "provider")?.payload.provider).toBe("deterministic");

      service.confirmProposal(turn.id);
      const snapshot = readRepository.loadWorkspaceSnapshot();
      expect(
        snapshot.inboxItems.some((task) =>
          task.title.toLowerCase().includes("review the launch checklist")
        )
      ).toBe(true);
    });
  });

  it("uses the configured Codex provider for the normal assistant path", async () => {
    const codexProvider = {
      name: "codex" as const,
      run: async () => ({
        responseText: "Codex-backed plan.",
        structuredOutput: {
          kind: "daily_planner",
          summary: "Codex selected the plan.",
          rationale: ["The assistant path should default to Codex."],
          focusItems: [
            {
              title: "Ship the cutover",
              energy: "high",
              reason: "This verifies the shipped path."
            }
          ],
          risks: []
        },
        traceEvents: [
          {
            stage: "provider",
            summary: "Codex completed the request.",
            provider: "codex",
            payload: {
              provider: "codex",
              provider_status: "success",
              provider_runtime: "codex exec",
              provider_detail: "Codex completed the request."
            }
          }
        ],
        providerEvidence: {
          provider: "codex",
          status: "success",
          runtime: "codex exec",
          detail: "Codex completed the request."
        }
      })
    };
    const deterministicProvider = {
      name: "deterministic" as const,
      run: async () => {
        throw new Error("deterministic provider should not be used");
      }
    };

    await withAssistantService(async (_service, readRepository, connection) => {
      const codexAwareService = new AssistantTurnService(connection, {
        assistantProvider: "codex",
        providerRegistry: createProviderRegistry([codexProvider, deterministicProvider])
      });
      const turn = await codexAwareService.sendPrompt("Plan my day", "2026-05-03");

      expect(turn.provider).toBe("codex");
      expect(turn.providerStatus).toBe("success");
      expect(turn.auditSteps.find((step) => step.stage === "provider")?.payload.provider).toBe("codex");
      expect(readRepository.loadAssistantTurns()[0]?.provider).toBe("codex");
    });
  });

  it("can still use deterministic execution when explicitly selected", async () => {
    await withAssistantService(async (_service, readRepository, connection) => {
      const deterministicService = new AssistantTurnService(connection, {
        assistantProvider: "deterministic"
      });

      const turn = await deterministicService.sendPrompt("Plan my day", "2026-05-03");

      expect(turn.provider).toBe("deterministic");
      expect(turn.providerStatus).toBe("success");
      expect(readRepository.loadAssistantTurns()[0]?.provider).toBe("deterministic");
    });
  });

  it("records explicit degraded evidence when codex is unavailable on the selected route", async () => {
    const unavailableCodexProvider = {
      name: "codex" as const,
      run: async () => {
        throw new Error("codex runtime unavailable");
      }
    };

    await withAssistantService(async (_service, readRepository, connection) => {
      const codexAwareService = new AssistantTurnService(connection, {
        assistantProvider: "codex",
        providerRegistry: createProviderRegistry([unavailableCodexProvider])
      });

      const turn = await codexAwareService.sendPrompt("Plan my day", "2026-05-03");

      expect(turn.provider).toBe("codex");
      expect(turn.providerStatus).toBe("failed");
      expect(turn.response).toContain("Returning deterministic fallback");
      expect(readRepository.loadAssistantTurns()[0]?.providerStatus).toBe("failed");
    });
  });

  it("uses the configured Codex provider for project next-action review when selected", async () => {
    const codexProvider = {
      name: "codex" as const,
      run: async () => ({
        responseText: "Codex drafted a bounded next action.",
        structuredOutput: {
          kind: "project_health_analyst",
          summary: "Prepared one bounded project next action.",
          rationale: ["The project needs a visible next action."],
          projects: [
            {
              id: "project-1",
              title: "Launch prep",
              suggestedTitle: "Draft the launch checklist"
            }
          ],
          writeProposals: [
            {
              actionType: "create_task",
              targetTable: "items",
              targetID: "project-1",
              previewText: "Create next action in Launch prep: Draft the launch checklist",
              rationale: "The project needs a next action.",
              confidence: 0.9,
              requiresConfirmation: true,
              verificationStatus: "validated",
              payload: {
                title: "Draft the launch checklist",
                project_id: "project-1",
                project_title: "Launch prep"
              }
            }
          ]
        },
        traceEvents: [
          {
            stage: "provider",
            summary: "Codex completed the request.",
            provider: "codex",
            payload: {
              provider: "codex",
              provider_status: "success",
              provider_runtime: "codex exec",
              provider_detail: "Codex completed the request."
            }
          }
        ],
        providerEvidence: {
          provider: "codex",
          status: "success",
          runtime: "codex exec",
          detail: "Codex completed the request."
        }
      })
    };

    await withAssistantService(async (_service, readRepository, connection) => {
      seedProject(connection);
      const codexAwareService = new AssistantTurnService(connection, {
        assistantProvider: "codex",
        providerRegistry: createProviderRegistry([codexProvider])
      });

      const turn = await codexAwareService.proposeProjectNextActionReview("project-1");

      expect(turn.provider).toBe("codex");
      expect(turn.proposalStatus).toBe("pending");
      expect(turn.proposal?.actionType).toBe("create_task");
      expect(readRepository.loadAssistantTurns()[0]?.provider).toBe("codex");
    });
  });

  it("dismisses memory proposals and can undo confirmed assistant memory writes", async () => {
    await withAssistantService(async (service, readRepository) => {
      const dismissed = await service.sendPrompt(
        "Remember that I prefer deep work before lunch.",
        "2026-03-08"
      );
      service.dismissProposal(dismissed.id);

      const confirmed = await service.sendPrompt(
        "Remember that I prefer maker mornings.",
        "2026-03-08"
      );
      service.confirmProposal(confirmed.id);
      expect(readRepository.loadMemoryRecords("maker mornings", true)).toHaveLength(1);

      expect(service.undoLastMutation()?.toLowerCase()).toContain("undid");
      expect(readRepository.loadMemoryRecords("maker mornings", true)).toHaveLength(0);
    });
  });
});

type AssistantRole = "user" | "assistant";
type ProposalStatus = "none" | "pending" | "confirmed" | "dismissed";

interface AssistantAuditStepSpec {
  stage: string;
  summary: string;
}

interface AssistantSessionSpec {
  id: string;
  title: string;
  createdAt: number;
  updatedAt: number;
}

interface AssistantMessageSpec {
  id: string;
  sessionID: string;
  role: AssistantRole;
  content: string;
  proposalStatus: ProposalStatus;
  proposalTarget?: string;
  provider?: string;
  auditSteps: AssistantAuditStepSpec[];
  createdAt: number;
}

class AssistantSessionTimelineHarness {
  private nextID = 1;
  private clock = 1;
  private sessions: AssistantSessionSpec[] = [];
  private messages: AssistantMessageSpec[] = [];
  public selectedSessionID?: string;

  createSession(title: string): string {
    const id = this.makeID("session");
    const timestamp = this.tick();
    this.sessions.push({ id, title, createdAt: timestamp, updatedAt: timestamp });
    this.selectedSessionID = id;
    return id;
  }

  sendMessage(
    sessionID: string,
    role: AssistantRole,
    content: string,
    options: Partial<Pick<AssistantMessageSpec, "proposalStatus" | "proposalTarget" | "provider" | "auditSteps">> = {}
  ): AssistantMessageSpec {
    this.touchSession(sessionID);
    const message: AssistantMessageSpec = {
      id: this.makeID("message"),
      sessionID,
      role,
      content,
      proposalStatus: options.proposalStatus ?? "none",
      proposalTarget: options.proposalTarget,
      provider: options.provider,
      auditSteps: options.auditSteps ?? [],
      createdAt: this.tick()
    };
    this.messages.push(message);
    this.selectedSessionID = sessionID;
    return message;
  }

  listSessions(): AssistantSessionSpec[] {
    return [...this.sessions].sort((left, right) => {
      if (left.updatedAt === right.updatedAt) {
        return right.createdAt - left.createdAt;
      }
      return right.updatedAt - left.updatedAt;
    });
  }

  loadMessages(sessionID: string): AssistantMessageSpec[] {
    return this.messages
      .filter((message) => message.sessionID === sessionID)
      .sort((left, right) => left.createdAt - right.createdAt);
  }

  selectSession(sessionID: string): void {
    this.selectedSessionID = sessionID;
    this.touchSession(sessionID);
  }

  message(id: string): AssistantMessageSpec | undefined {
    return this.messages.find((message) => message.id === id);
  }

  confirmProposal(messageID: string): void {
    this.mutateProposal(messageID, "confirmed");
  }

  dismissProposal(messageID: string): void {
    this.mutateProposal(messageID, "dismissed");
  }

  private mutateProposal(messageID: string, proposalStatus: ProposalStatus): void {
    const message = this.message(messageID);
    if (!message) {
      return;
    }

    message.proposalStatus = proposalStatus;
    this.touchSession(message.sessionID);
  }

  private touchSession(sessionID: string): void {
    const session = this.sessions.find((candidate) => candidate.id === sessionID);
    if (!session) {
      return;
    }

    session.updatedAt = this.tick();
  }

  private tick(): number {
    const current = this.clock;
    this.clock += 1;
    return current;
  }

  private makeID(prefix: string): string {
    const current = this.nextID;
    this.nextID += 1;
    return `${prefix}-${current}`;
  }
}

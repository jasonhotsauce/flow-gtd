import type { DatabaseSync } from "node:sqlite";
import type {
  AssistantRequest,
  AssistantResponse,
  ProviderName,
  ProviderEvidence
} from "../agents/contracts.js";
import { AssistantOrchestrator } from "../agents/orchestrator.js";
import { createDefaultProviderRegistry, type ProviderRegistry } from "../agents/providers.js";
import { createDefaultSpecialistRegistry } from "../agents/specialists.js";
import { createAssistantToolContracts } from "../agents/tools.js";
import { FlowReadRepository } from "../db/repositories/read-repository.js";
import type {
  FlowAssistantAuditStep,
  FlowAssistantProposal,
  FlowAssistantTurn,
  FlowProject
} from "../domain/read-models.js";
import { MutationService } from "./mutations/service.js";

interface AssistantTurnRow {
  id: string;
  prompt: string;
  response: string;
  route: string;
  proposal_json: string | null;
  proposal_status: string;
  created_at: string | null;
}

interface AssistantMutationRow {
  action: string;
  payload_json: string;
}

export interface AssistantTurnServiceOptions {
  providerRegistry?: ProviderRegistry;
  assistantProvider?: ProviderName;
}

function nowIso(): string {
  return new Date().toISOString();
}

function relativeUpdatedLabel(value: string | null | undefined): string {
  return value ? `Updated ${value}` : "Just now";
}

function resolveAssistantProviderName(
  explicitProvider?: ProviderName
): ProviderName {
  const configuredProvider = process.env.FLOW_AGENT_RUNTIME_PROVIDER?.trim().toLowerCase();
  if (configuredProvider === "deterministic") {
    return "deterministic";
  }
  if (configuredProvider === "codex" || configuredProvider === "codex-cli") {
    return "codex";
  }
  return explicitProvider ?? "deterministic";
}

function providerForRoute(
  route: string,
  configuredProvider: ProviderName
): ProviderName {
  switch (route) {
    case "capture":
    case "memory":
      return "deterministic";
    default:
      return configuredProvider;
  }
}

function providerEvidenceFromResponse(
  response: AssistantResponse
): ProviderEvidence {
  return response.providerEvidence;
}

function detectAssistantRoute(prompt: string): string {
  const lowered = prompt.toLowerCase();
  if (lowered.startsWith("remember") || lowered.includes(" i prefer ")) {
    return "memory";
  }
  if (
    lowered.startsWith("add ") ||
    lowered.startsWith("capture ") ||
    lowered.startsWith("todo ") ||
    lowered.startsWith("remind me to ")
  ) {
    return "capture";
  }
  if (lowered.includes("plan my day") || lowered.includes("today")) {
    return "daily_plan";
  }
  if (lowered.includes("review") || lowered.includes("weekly")) {
    return "review";
  }
  return "general";
}

function routeSpecialist(route: string): AssistantRequest["specialist"] {
  switch (route) {
    case "capture":
      return "capture_clarifier";
    case "memory":
      return "memory_curator";
    case "daily_plan":
      return "daily_planner";
    case "review":
      return "weekly_reviewer";
    default:
      return "assistant_orchestrator";
  }
}

function routeCapabilities(route: string): AssistantRequest["capabilities"] {
  switch (route) {
    case "capture":
      return ["read_gtd_context", "propose_inbox_write"];
    case "memory":
      return ["read_gtd_context", "propose_memory_write"];
    case "daily_plan":
      return ["read_gtd_context", "propose_planning_change"];
    case "review":
      return ["read_gtd_context", "propose_review_cleanup"];
    default:
      return ["read_gtd_context"];
  }
}

function parseProposal(rawJSON: string | null): FlowAssistantProposal | undefined {
  if (!rawJSON) {
    return undefined;
  }
  try {
    const object = JSON.parse(rawJSON) as Record<string, unknown>;
    return {
      actionType: String(object.action_type ?? ""),
      title: String(object.title ?? ""),
      detail: String(object.detail ?? ""),
      requiresConfirmation: Boolean(object.requires_confirmation)
    };
  } catch {
    return undefined;
  }
}

function proposalPayload(rawJSON: string | null): Record<string, unknown> {
  if (!rawJSON) {
    return {};
  }
  try {
    const object = JSON.parse(rawJSON) as Record<string, unknown>;
    const payload = object.payload;
    return payload && typeof payload === "object" && !Array.isArray(payload)
      ? (payload as Record<string, unknown>)
      : {};
  } catch {
    return {};
  }
}

function jsonDictionary(rawJSON: string | null): Record<string, unknown> {
  if (!rawJSON) {
    return {};
  }
  try {
    const object = JSON.parse(rawJSON) as Record<string, unknown>;
    return object && typeof object === "object" && !Array.isArray(object)
      ? object
      : {};
  } catch {
    return {};
  }
}

function auditStepsFromResponse(response: AssistantResponse): FlowAssistantAuditStep[] {
  const status = response.failed ? "warning" : "ok";
  return [
    ...response.traceEvents.map((event) => ({
      id: crypto.randomUUID(),
      stage: event.stage,
      status,
      summary: event.summary,
      payload: event.payload ?? {}
    })),
    {
      id: crypto.randomUUID(),
      stage: "verifier",
      status: "ok",
      summary: response.writeProposals.length > 0
        ? "Checked that the proposal is bounded and requires confirmation before writes."
        : "Checked that the response is read-only and bounded.",
      payload: {}
    }
  ];
}

function storedProposalJSON(
  proposal: FlowAssistantProposal,
  payload: Record<string, string>
): string {
  return JSON.stringify({
    action_type: proposal.actionType,
    title: proposal.title,
    detail: proposal.detail,
    requires_confirmation: proposal.requiresConfirmation,
    payload
  });
}

export class AssistantTurnService {
  private readonly readRepository: FlowReadRepository;
  private readonly mutationService: MutationService;
  private readonly orchestrator: AssistantOrchestrator;
  private readonly assistantProvider: ProviderName;

  constructor(
    private readonly db: DatabaseSync,
    options: AssistantTurnServiceOptions = {}
  ) {
    this.readRepository = new FlowReadRepository(db);
    this.mutationService = new MutationService(db);
    this.assistantProvider = resolveAssistantProviderName(options.assistantProvider);
    this.orchestrator = new AssistantOrchestrator({
      specialists: createDefaultSpecialistRegistry(),
      providers: options.providerRegistry ?? createDefaultProviderRegistry()
    });
  }

  async sendPrompt(prompt: string, planDate: string): Promise<FlowAssistantTurn> {
    const normalizedPrompt = prompt.trim();
    if (!normalizedPrompt) {
      throw new Error("Prompt must not be empty.");
    }

    const route = detectAssistantRoute(normalizedPrompt);
    const turnID = crypto.randomUUID();
    const response = await this.orchestrator.handle({
      requestID: turnID,
      prompt: normalizedPrompt,
      routeHint: route,
      specialist: routeSpecialist(route),
      capabilities: routeCapabilities(route),
      provider: providerForRoute(route, this.assistantProvider),
      outputMode: "json",
      context: this.assistantContext(planDate),
      metadata: {}
    });

    return this.persistTurn(turnID, normalizedPrompt, route, response);
  }

  async proposeProjectNextActionReview(projectID: string): Promise<FlowAssistantTurn> {
    const project = this.readRepository
      .loadWorkspaceSnapshot()
      .projects.find((entry) => entry.id === projectID);
    if (!project) {
      throw new Error("Project no longer exists for review.");
    }

    const turnID = crypto.randomUUID();
    const response = await this.orchestrator.handle({
      requestID: turnID,
      prompt: `Review project next action: ${project.title}`,
      routeHint: "project_health",
      specialist: "project_health_analyst",
      capabilities: ["read_gtd_context", "propose_planning_change"],
      provider: providerForRoute("project_health", this.assistantProvider),
      outputMode: "json",
      context: {
        ...this.assistantContext(nowIso().slice(0, 10)),
        project,
        suggestedTitle: this.suggestNextActionTitle(project)
      },
      metadata: {}
    });

    return this.persistTurn(
      turnID,
      `Review project next action: ${project.title}`,
      "project_health",
      response
    );
  }

  confirmProposal(turnID: string): string {
    const row = this.fetchTurnRow(turnID);
    if (row.proposal_status != "pending") {
      throw new Error("Assistant proposal is not pending.");
    }
    const proposal = parseProposal(row.proposal_json);
    if (!proposal) {
      throw new Error("Assistant turn has no proposal.");
    }

    const payload = proposalPayload(row.proposal_json);
    const timestamp = nowIso();
    const targetID =
      proposal.actionType === "save_memory"
        ? crypto.randomUUID()
        : proposal.actionType === "create_task"
          ? crypto.randomUUID()
          : turnID;
    const assistantPayload =
      proposal.actionType === "save_memory"
        ? {
            memory_id: targetID,
            kind: "save_memory"
          }
        : typeof payload.project_id === "string" && payload.project_id
          ? {
              item_id: targetID,
              project_id: payload.project_id,
              kind: proposal.actionType
            }
          : {
              item_id: targetID,
              kind: proposal.actionType
            };
    let message = "Proposal confirmed.";

    this.mutationService.executeProposal(
      "assistant",
      {
        actionType: proposal.actionType === "save_memory"
          ? "assistant_memory_confirm"
          : payload.project_id
            ? "assistant_project_next_action_confirm"
            : "assistant_capture_confirm",
        targetTable: proposal.actionType === "save_memory" ? "memory_entries" : "items",
        targetID,
        previewText: proposal.detail,
        rationale: "User confirmed the assistant proposal.",
        confidence: 1,
        requiresConfirmation: false,
        verificationStatus: "validated",
        idempotencyKey: `assistant-confirm:${turnID}`,
        payload: Object.fromEntries(
          Object.entries(assistantPayload).map(([key, value]) => [key, String(value)])
        )
      },
      () => {
        switch (proposal.actionType) {
          case "create_task": {
            const title = String(payload.title ?? "").trim();
            if (!title) {
              throw new Error("Assistant proposal is missing a task title.");
            }
            if (typeof payload.project_id === "string" && payload.project_id) {
              this.insertProjectTask(targetID, title, payload.project_id, timestamp);
              message = `Added next action to ${String(payload.project_title ?? "the project")}: ${title}`;
            } else {
              this.insertInboxCapture(targetID, title, timestamp);
              message = `Added to Inbox: ${title}`;
            }
            break;
          }
          case "save_memory": {
            this.insertMemoryEntry(
              targetID,
              {
                kind: String(payload.kind ?? "explicit_preference"),
                scope: String(payload.scope ?? "global"),
                value: String(payload.value ?? ""),
                source: String(payload.source ?? "assistant-chat"),
                confidence: Number(payload.confidence ?? 1),
                scopeRef: typeof payload.scopeRef === "string" ? payload.scopeRef : undefined
              },
              timestamp
            );
            message = "Saved preference to Memory.";
            break;
          }
          default:
            break;
        }
      }
    );

    this.updateProposalStatus(turnID, "confirmed", timestamp);
    return message;
  }

  dismissProposal(turnID: string): void {
    this.updateProposalStatus(turnID, "dismissed", nowIso());
  }

  undoLastMutation(): string | undefined {
    const latest = this.fetchLatestAssistantMutation();
    if (!latest) {
      return undefined;
    }
    const payload = jsonDictionary(latest.payload_json);
    switch (latest.action) {
      case "assistant_capture_confirm":
        if (typeof payload.item_id === "string") {
          this.archiveAssistantItem(payload.item_id);
          return "Undid the last assistant capture.";
        }
        return undefined;
      case "assistant_project_next_action_confirm":
        if (typeof payload.item_id === "string") {
          this.archiveAssistantItem(payload.item_id);
          return "Undid the last assistant project next action.";
        }
        return undefined;
      case "assistant_memory_confirm":
        if (typeof payload.memory_id === "string") {
          this.db.prepare("DELETE FROM memory_entries WHERE id = ?").run(payload.memory_id);
          return "Undid the last assistant memory write.";
        }
        return undefined;
      default:
        return undefined;
    }
  }

  private assistantContext(planDate: string): Record<string, unknown> {
    const workspace = this.readRepository.loadWorkspaceSnapshot();
    return {
      inboxCount: workspace.inboxItems.length,
      memoryCount: workspace.memoryEntries.length,
      agentTools: createAssistantToolContracts(),
      dailyPlanState: this.readRepository.loadDailyPlanState(planDate),
      weeklyReviewPackage: this.readRepository.loadWeeklyReviewPackage(new Date())
    };
  }

  private persistTurn(
    turnID: string,
    prompt: string,
    route: string,
    response: AssistantResponse
  ): FlowAssistantTurn {
    const timestamp = nowIso();
    const auditSteps = auditStepsFromResponse(response);
    const providerEvidence = providerEvidenceFromResponse(response);
    const firstProposal = response.writeProposals[0];
    let proposal: FlowAssistantProposal | undefined;
    let proposalStatus = "none";
    let proposalJSON: string | null = null;

    if (firstProposal) {
      proposalStatus = "pending";
      proposal = {
        actionType: firstProposal.actionType,
        title: firstProposal.actionType === "save_memory"
          ? "Save Memory"
          : firstProposal.payload.project_id
            ? "Create Project Next Action"
            : "Add to Inbox",
        detail: firstProposal.previewText,
        requiresConfirmation: firstProposal.requiresConfirmation
      }
      proposalJSON = storedProposalJSON(proposal, firstProposal.payload);
    }

    this.db.prepare(
      `
        INSERT INTO assistant_turns (
          id, prompt, response, route, proposal_json, proposal_status, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
      `
    ).run(turnID, prompt, response.responseText, route, proposalJSON, proposalStatus, timestamp, timestamp);

    const insertAudit = this.db.prepare(
      `
      INSERT INTO assistant_audit_steps (
          id, turn_id, stage, status, summary, payload_json, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
      `
    );
    for (const step of auditSteps) {
      insertAudit.run(
        step.id,
        turnID,
        step.stage,
        step.status,
        step.summary,
        JSON.stringify(step.payload ?? {}),
        timestamp
      );
    }

    return {
      id: turnID,
      prompt,
      response: response.responseText,
      route,
      proposal,
      proposalStatus,
      auditSteps,
      provider: providerEvidence.provider,
      providerStatus: providerEvidence.status,
      providerDetail: providerEvidence.detail,
      providerModel: providerEvidence.model,
      createdAtLabel: relativeUpdatedLabel(timestamp)
    };
  }

  private fetchTurnRow(turnID: string): AssistantTurnRow {
    const row = this.db.prepare(
      `
        SELECT id, prompt, response, route, proposal_json, proposal_status, created_at
        FROM assistant_turns
        WHERE id = ?
        LIMIT 1
      `
    ).get(turnID) as AssistantTurnRow | undefined;
    if (!row) {
      throw new Error("Assistant turn was not found.");
    }
    return row;
  }

  private fetchLatestAssistantMutation(): AssistantMutationRow | undefined {
    return this.db.prepare(
      `
        SELECT mr.action, mr.payload_json
        FROM mutation_records mr
        JOIN mutation_batches mb ON mb.id = mr.batch_id
        WHERE mb.source = 'assistant'
        ORDER BY mb.created_at DESC, mr.created_at DESC
        LIMIT 1
      `
    ).get() as AssistantMutationRow | undefined;
  }

  private updateProposalStatus(turnID: string, status: string, updatedAt: string): void {
    this.db.prepare(
      "UPDATE assistant_turns SET proposal_status = ?, updated_at = ? WHERE id = ?"
    ).run(status, updatedAt, turnID);
  }

  private insertInboxCapture(taskID: string, title: string, timestamp: string): string {
    this.db.prepare(
      `
        INSERT INTO items (
          id, type, title, status, context_tags, parent_id, created_at,
          due_date, meta_payload, original_ek_id, estimated_duration, updated_at
        ) VALUES (?, 'inbox', ?, 'active', '[]', NULL, ?, NULL, '{}', NULL, NULL, ?)
      `
    ).run(taskID, title, timestamp, timestamp);
    this.db.prepare(
      `
        INSERT INTO raw_captures (id, source, raw_text, created_at)
        VALUES (?, 'assistant_capture', ?, ?)
      `
    ).run(taskID, title, timestamp);
    this.db.prepare(
      `
        INSERT INTO inbox_items (
          id, raw_capture_id, origin_type, inbox_state, source_ref, imported_at,
          task_id, clarified_task_id, clarified_project_id, clarified_at, created_at, updated_at
        ) VALUES (?, ?, 'assistant_capture', 'needs_clarification', NULL, NULL, NULL, NULL, NULL, NULL, ?, ?)
      `
    ).run(taskID, taskID, timestamp, timestamp);
    return taskID;
  }

  private insertProjectTask(taskID: string, title: string, projectID: string, timestamp: string): string {
    this.db.prepare(
      `
        INSERT INTO items (
          id, type, title, status, context_tags, parent_id, created_at,
          due_date, meta_payload, original_ek_id, estimated_duration, updated_at
        ) VALUES (?, 'action', ?, 'active', '[]', ?, ?, NULL, '{}', NULL, NULL, ?)
      `
    ).run(taskID, title, projectID, timestamp, timestamp);
    this.db.prepare(
      `
        INSERT INTO tasks (
          id, title, status, project_id, source_inbox_item_id,
          time_sensitivity, effort_band, created_at, updated_at
        ) VALUES (?, ?, 'active', ?, ?, 'flexible', 'medium', ?, ?)
      `
    ).run(taskID, title, projectID, taskID, timestamp, timestamp);
    return taskID;
  }

  private insertMemoryEntry(
    memoryID: string,
    input: {
      kind: string;
      scope: string;
      value: string;
      source: string;
      confidence: number;
      scopeRef?: string;
    },
    timestamp: string
  ): string {
    this.db.prepare(
      `
        INSERT INTO memory_entries (
          id, kind, scope, scope_ref, value, source, confidence, enabled,
          created_at, updated_at, last_confirmed_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?)
      `
    ).run(
      memoryID,
      input.kind,
      input.scope,
      input.scopeRef ?? null,
      input.value,
      input.source,
      input.confidence,
      timestamp,
      timestamp,
      timestamp
    );
    return memoryID;
  }

  private archiveAssistantItem(itemID: string): void {
    const timestamp = nowIso();
    this.db.prepare(
      "UPDATE items SET status = 'archived', updated_at = ? WHERE id = ?"
    ).run(timestamp, itemID);
    this.db.prepare(
      "UPDATE tasks SET status = 'archived', updated_at = ? WHERE id = ?"
    ).run(timestamp, itemID);
  }

  private suggestNextActionTitle(project: FlowProject): string {
    const completedTask = project.tasks.find((task) => task.status === "done");
    if (completedTask) {
      return `Define the next step after ${completedTask.title}`;
    }
    return `Define the next concrete step for ${project.title}`;
  }
}

import type { DatabaseSync } from "node:sqlite";
import type {
  AssistantRequest,
  AssistantResponse,
  ProviderEvidence,
  ProviderName
} from "../agents/contracts.js";
import { AssistantOrchestrator } from "../agents/orchestrator.js";
import {
  createDefaultProviderRegistry,
  type ProviderRegistry
} from "../agents/providers.js";
import { createDefaultSpecialistRegistry } from "../agents/specialists.js";
import { createAssistantToolContracts } from "../agents/tools.js";
import { FlowReadRepository } from "../db/repositories/read-repository.js";
import { MutationService } from "./mutations/service.js";
import type {
  FlowAssistantAuditStep,
  FlowAssistantMessage,
  FlowAssistantProposal,
  FlowAssistantSession
} from "../domain/read-models.js";

interface AssistantSessionRow {
  id: string;
  title: string;
  latest_preview: string;
  message_count: number;
  created_at: string | null;
  updated_at: string | null;
}

interface AssistantMessageRow {
  id: string;
  session_id: string;
  role: string;
  content: string;
  route: string;
  proposal_json: string | null;
  proposal_status: string;
  provider: string;
  provider_status: string;
  provider_detail: string;
  provider_model: string | null;
  source_turn_id: string | null;
  created_at: string | null;
  updated_at: string | null;
}

interface AssistantMutationRow {
  action: string;
  payload_json: string;
}

export interface AssistantSessionMessageServiceOptions {
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

function stringList(value: unknown): string[] {
  if (Array.isArray(value)) {
    return value.map(String).filter((entry) => entry.trim().length > 0);
  }
  if (typeof value !== "string") {
    return [];
  }
  const trimmed = value.trim();
  if (!trimmed) {
    return [];
  }
  try {
    const parsed = JSON.parse(trimmed) as unknown;
    if (Array.isArray(parsed)) {
      return parsed.map(String).filter((entry) => entry.trim().length > 0);
    }
  } catch {
    // Fall through to comma-separated parsing.
  }
  return trimmed
    .split(",")
    .map((entry) => entry.trim())
    .filter((entry) => entry.length > 0);
}

export class AssistantSessionMessageService {
  private readonly readRepository: FlowReadRepository;
  private readonly mutationService: MutationService;
  private readonly orchestrator: AssistantOrchestrator;
  private readonly assistantProvider: ProviderName;

  constructor(
    private readonly db: DatabaseSync,
    options: AssistantSessionMessageServiceOptions = {}
  ) {
    this.readRepository = new FlowReadRepository(db);
    this.mutationService = new MutationService(db);
    this.assistantProvider = resolveAssistantProviderName(options.assistantProvider);
    this.orchestrator = new AssistantOrchestrator({
      specialists: createDefaultSpecialistRegistry(),
      providers: options.providerRegistry ?? createDefaultProviderRegistry()
    });
  }

  loadSessions(limit = 30): FlowAssistantSession[] {
    const rows = this.db
      .prepare(
        `
          SELECT id, title, latest_preview, message_count, created_at, updated_at
          FROM assistant_sessions
          ORDER BY updated_at DESC, created_at DESC
          LIMIT ?
        `
      )
      .all(limit) as unknown as AssistantSessionRow[];

    return rows.map((row) => this.sessionFromRow(row));
  }

  loadMessages(sessionID: string, limit = 30): FlowAssistantMessage[] {
    const rows = this.db
      .prepare(
        `
          SELECT id, session_id, role, content, route, proposal_json, proposal_status,
                 provider, provider_status, provider_detail, provider_model, source_turn_id,
                 created_at, updated_at
          FROM assistant_messages
          WHERE session_id = ?
          ORDER BY created_at DESC
          LIMIT ?
        `
      )
      .all(sessionID, limit) as unknown as AssistantMessageRow[];

    return rows.reverse().map((row) => this.messageFromRow(row));
  }

  createSession(title: string): FlowAssistantSession {
    const trimmedTitle = title.trim();
    const sessionID = crypto.randomUUID();
    const timestamp = nowIso();
    const sessionTitle = trimmedTitle || "New Chat";

    this.db.prepare(
      `
        INSERT INTO assistant_sessions (
          id, title, latest_preview, message_count, created_at, updated_at
        ) VALUES (?, ?, '', 0, ?, ?)
      `
    ).run(sessionID, sessionTitle, timestamp, timestamp);

    return {
      id: sessionID,
      title: sessionTitle,
      latestPreview: "",
      messageCount: 0,
      createdAtLabel: relativeUpdatedLabel(timestamp),
      updatedAtLabel: relativeUpdatedLabel(timestamp)
    };
  }

  async sendMessage(
    sessionID: string,
    prompt: string,
    planDate: string
  ): Promise<FlowAssistantMessage> {
    const normalizedPrompt = prompt.trim();
    if (!normalizedPrompt) {
      throw new Error("Prompt must not be empty.");
    }

    const route = detectAssistantRoute(normalizedPrompt);
    const messageID = crypto.randomUUID();
    const response = await this.orchestrator.handle({
      requestID: messageID,
      prompt: normalizedPrompt,
      routeHint: route,
      specialist: routeSpecialist(route),
      capabilities: routeCapabilities(route),
      provider: providerForRoute(route, this.assistantProvider),
      outputMode: "json",
      context: this.assistantContext(planDate),
      metadata: {}
    });

    return this.persistMessage(
      sessionID,
      messageID,
      normalizedPrompt,
      route,
      response
    );
  }

  confirmMessage(messageID: string): string {
    const row = this.fetchMessageRow(messageID);
    if (row.proposal_status !== "pending") {
      throw new Error("Assistant message proposal is not pending.");
    }

    const proposal = parseProposal(row.proposal_json);
    if (!proposal) {
      throw new Error("Assistant message has no proposal.");
    }

    const payload = proposalPayload(row.proposal_json);
    const timestamp = nowIso();
    const targetID =
      proposal.actionType === "save_memory"
        ? crypto.randomUUID()
        : messageID;
    let message = "Proposal confirmed.";
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

    this.mutationService.executeProposal(
      "assistant",
      {
        actionType: this.assistantMutationAction(proposal.actionType, payload),
        targetTable: this.assistantMutationTargetTable(proposal.actionType),
        targetID,
        previewText: proposal.detail,
        rationale: "User confirmed the assistant proposal.",
        confidence: 1,
        requiresConfirmation: false,
        verificationStatus: "validated",
        idempotencyKey: `assistant-confirm:${messageID}`,
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
          case "save_daily_plan": {
            const planDate = String(payload.planDate ?? "").trim();
            if (!planDate) {
              throw new Error("Assistant proposal is missing a plan date.");
            }
            this.replaceDailyPlanEntries(
              planDate,
              stringList(payload.topItemIDs),
              stringList(payload.bonusItemIDs),
              timestamp
            );
            message = `Saved daily plan for ${planDate}.`;
            break;
          }
          case "delete_daily_plan": {
            const planDate = String(payload.planDate ?? "").trim();
            if (!planDate) {
              throw new Error("Assistant proposal is missing a plan date.");
            }
            this.db.prepare("DELETE FROM daily_plan_entries WHERE plan_date = ?").run(planDate);
            message = `Deleted daily plan for ${planDate}.`;
            break;
          }
          default:
            break;
        }
      }
    );

    this.updateMessageProposalStatus(messageID, "confirmed", timestamp);
    return message;
  }

  dismissMessage(messageID: string): void {
    const row = this.fetchMessageRow(messageID);
    if (row.proposal_status !== "pending") {
      throw new Error("Assistant message proposal is not pending.");
    }
    this.updateMessageProposalStatus(messageID, "dismissed", nowIso());
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

  private persistMessage(
    sessionID: string,
    messageID: string,
    prompt: string,
    route: string,
    response: AssistantResponse
  ): FlowAssistantMessage {
    const timestamp = this.nextMessageTimestamp(sessionID);
    const assistantTimestamp = new Date(Date.parse(timestamp) + 1000).toISOString();
    const auditSteps = auditStepsFromResponse(response);
    const providerEvidence = response.providerEvidence;
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
      };
      proposalJSON = storedProposalJSON(proposal, firstProposal.payload);
    }

    this.db.exec("BEGIN");
    try {
      this.ensureSession(sessionID, prompt, timestamp);
      this.insertMessage(
        {
          id: `${messageID}-user`,
          sessionID,
          role: "user",
          content: prompt,
          route: "user",
          proposalJSON: null,
          proposalStatus: "none",
          provider: "user",
          providerStatus: "success",
          providerDetail: "",
          providerModel: null,
          sourceTurnID: null,
          createdAt: timestamp,
          updatedAt: timestamp
        }
      );
      this.insertMessage(
        {
          id: messageID,
          sessionID,
          role: "assistant",
          content: response.responseText,
          route,
          proposalJSON,
          proposalStatus,
          provider: providerEvidence.provider,
          providerStatus: providerEvidence.status,
          providerDetail: providerEvidence.detail,
          providerModel: providerEvidence.model ?? null,
          sourceTurnID: messageID,
          createdAt: assistantTimestamp,
          updatedAt: assistantTimestamp
        }
      );
      this.insertAuditSteps(messageID, auditSteps, assistantTimestamp);
      this.updateSession(sessionID, response.responseText, 2, assistantTimestamp);
      this.db.exec("COMMIT");
    } catch (error) {
      this.db.exec("ROLLBACK");
      throw error;
    }

    return this.loadMessage(messageID);
  }

  private ensureSession(sessionID: string, title: string, timestamp: string): void {
    const existing = this.db
      .prepare("SELECT id FROM assistant_sessions WHERE id = ? LIMIT 1")
      .get(sessionID) as { id?: string } | undefined;
    if (existing?.id) {
      return;
    }

    this.db.prepare(
      `
        INSERT INTO assistant_sessions (
          id, title, latest_preview, message_count, created_at, updated_at
        ) VALUES (?, ?, '', 0, ?, ?)
      `
    ).run(sessionID, title.trim() || "New Chat", timestamp, timestamp);
  }

  private insertMessage(row: {
    id: string;
    sessionID: string;
    role: string;
    content: string;
    route: string;
    proposalJSON: string | null;
    proposalStatus: string;
    provider: string;
    providerStatus: string;
    providerDetail: string;
    providerModel: string | null;
    sourceTurnID: string | null;
    createdAt: string;
    updatedAt: string;
  }): void {
    this.db.prepare(
      `
        INSERT INTO assistant_messages (
          id, session_id, role, content, route, proposal_json, proposal_status,
          provider, provider_status, provider_detail, provider_model, source_turn_id,
          created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
      `
    ).run(
      row.id,
      row.sessionID,
      row.role,
      row.content,
      row.route,
      row.proposalJSON,
      row.proposalStatus,
      row.provider,
      row.providerStatus,
      row.providerDetail,
      row.providerModel,
      row.sourceTurnID,
      row.createdAt,
      row.updatedAt
    );
  }

  private insertAuditSteps(messageID: string, auditSteps: FlowAssistantAuditStep[], timestamp: string): void {
    const insertAudit = this.db.prepare(
      `
        INSERT INTO assistant_message_audit_steps (
          id, message_id, stage, status, summary, payload_json, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
      `
    );
    for (const step of auditSteps) {
      insertAudit.run(
        step.id,
        messageID,
        step.stage,
        step.status,
        step.summary,
        JSON.stringify(step.payload ?? {}),
        timestamp
      );
    }
  }

  private updateSession(sessionID: string, latestPreview: string, messageCountDelta: number, timestamp: string): void {
    const row = this.db
      .prepare(
        `
          SELECT message_count
          FROM assistant_sessions
          WHERE id = ?
          LIMIT 1
        `
      )
      .get(sessionID) as { message_count?: number } | undefined;
    const nextCount = Number(row?.message_count ?? 0) + messageCountDelta;
    this.db.prepare(
      `
        UPDATE assistant_sessions
        SET latest_preview = ?, message_count = ?, updated_at = ?
        WHERE id = ?
      `
    ).run(latestPreview, nextCount, timestamp, sessionID);
  }

  private updateMessageProposalStatus(messageID: string, status: string, updatedAt: string): void {
    this.db.prepare(
      "UPDATE assistant_messages SET proposal_status = ?, updated_at = ? WHERE id = ?"
    ).run(status, updatedAt, messageID);
    const sessionID = this.db
      .prepare(
        `
          SELECT session_id
          FROM assistant_messages
          WHERE id = ?
          LIMIT 1
        `
      )
      .get(messageID) as { session_id?: string } | undefined;
    if (sessionID?.session_id) {
      this.db.prepare(
        "UPDATE assistant_sessions SET updated_at = ? WHERE id = ?"
      ).run(updatedAt, sessionID.session_id);
    }
  }

  private fetchMessageRow(messageID: string): AssistantMessageRow {
    const row = this.db.prepare(
      `
        SELECT id, session_id, role, content, route, proposal_json, proposal_status,
               provider, provider_status, provider_detail, provider_model, source_turn_id,
               created_at, updated_at
        FROM assistant_messages
        WHERE id = ?
        LIMIT 1
      `
    ).get(messageID) as AssistantMessageRow | undefined;
    if (!row) {
      throw new Error("Assistant message was not found.");
    }
    return row;
  }

  private loadMessage(messageID: string): FlowAssistantMessage {
    const row = this.fetchMessageRow(messageID);
    return this.messageFromRow(row);
  }

  private sessionFromRow(row: AssistantSessionRow): FlowAssistantSession {
    return {
      id: row.id,
      title: row.title,
      latestPreview: row.latest_preview,
      messageCount: Number(row.message_count ?? 0),
      createdAtLabel: relativeUpdatedLabel(row.created_at),
      updatedAtLabel: relativeUpdatedLabel(row.updated_at)
    };
  }

  private messageFromRow(row: AssistantMessageRow): FlowAssistantMessage {
    const auditSteps = this.fetchAuditSteps(row.id);
    const proposal = parseProposal(row.proposal_json);
    return {
      id: row.id,
      sessionID: row.session_id,
      role: row.role,
      content: row.content,
      route: row.route,
      proposal,
      proposalStatus: row.proposal_status,
      auditSteps,
      provider: row.provider,
      providerStatus: row.provider_status,
      providerDetail: row.provider_detail,
      providerModel: row.provider_model ?? undefined,
      sourceTurnID: row.source_turn_id ?? undefined,
      createdAtLabel: relativeUpdatedLabel(row.created_at),
      updatedAtLabel: relativeUpdatedLabel(row.updated_at)
    };
  }

  private fetchAuditSteps(messageID: string): FlowAssistantAuditStep[] {
    const rows = this.db
      .prepare(
        `
          SELECT id, stage, status, summary, payload_json
          FROM assistant_message_audit_steps
          WHERE message_id = ?
          ORDER BY created_at ASC
        `
      )
      .all(messageID) as Array<{
        id: string;
        stage: string;
        status: string;
        summary: string;
        payload_json: string;
      }>;

    return rows.map((row) => ({
      id: row.id,
      stage: row.stage,
      status: row.status,
      summary: row.summary,
      payload: jsonDictionary(row.payload_json) as Record<string, string>
    }));
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

  private assistantMutationAction(
    actionType: string,
    payload: Record<string, unknown>
  ): string {
    if (actionType === "save_memory") {
      return "assistant_memory_confirm";
    }
    if (actionType === "save_daily_plan" || actionType === "delete_daily_plan") {
      return "assistant_daily_plan_confirm";
    }
    if (payload.project_id) {
      return "assistant_project_next_action_confirm";
    }
    return "assistant_capture_confirm";
  }

  private assistantMutationTargetTable(actionType: string): string {
    if (actionType === "save_memory") {
      return "memory_entries";
    }
    if (actionType === "save_daily_plan" || actionType === "delete_daily_plan") {
      return "daily_plan_entries";
    }
    return "items";
  }

  private nextMessageTimestamp(sessionID: string): string {
    const latest = this.db.prepare(
      `
        SELECT created_at
        FROM assistant_messages
        WHERE session_id = ?
        ORDER BY created_at DESC
        LIMIT 1
      `
    ).get(sessionID) as { created_at?: string } | undefined;
    const latestTime = latest?.created_at ? Date.parse(latest.created_at) : 0;
    const nextTime = Math.max(Date.now(), latestTime + 1000);
    return new Date(nextTime).toISOString();
  }

  private insertInboxCapture(taskID: string, title: string, timestamp: string): void {
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
  }

  private insertProjectTask(taskID: string, title: string, projectID: string, timestamp: string): void {
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
  ): void {
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
  }

  private replaceDailyPlanEntries(
    planDate: string,
    topItemIDs: string[],
    bonusItemIDs: string[],
    timestamp: string
  ): void {
    this.db.prepare("DELETE FROM daily_plan_entries WHERE plan_date = ?").run(planDate);
    const insert = this.db.prepare(
      `
        INSERT INTO daily_plan_entries (plan_date, item_id, bucket, position, created_at)
        VALUES (?, ?, ?, ?, ?)
      `
    );
    topItemIDs.forEach((itemID, index) => {
      insert.run(planDate, itemID, "top", index + 1, timestamp);
    });
    bonusItemIDs.forEach((itemID, index) => {
      insert.run(planDate, itemID, "bonus", index + 1, timestamp);
    });
  }

  private archiveAssistantItem(itemID: string): void {
    const timestamp = nowIso();
    this.db.prepare(
      "UPDATE items SET status = 'archived', updated_at = ? WHERE id = ?"
    ).run(timestamp, itemID);
    this.db.prepare("UPDATE tasks SET status = 'archived', updated_at = ? WHERE id = ?").run(timestamp, itemID);
    this.db.prepare(
      "UPDATE inbox_items SET inbox_state = 'rejected', updated_at = ? WHERE id = ?"
    ).run(timestamp, itemID);
  }
}

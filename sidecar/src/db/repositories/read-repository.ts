import type { DatabaseSync } from "node:sqlite";
import type {
  AssistantSuggestion,
  FlowAssistantAuditStep,
  FlowAssistantProposal,
  FlowAssistantMessage,
  FlowAssistantSession,
  FlowAssistantTurn,
  FlowDailyPlanState,
  FlowMemoryRecord,
  FlowNotificationCandidate,
  FlowNotificationPolicyState,
  FlowProject,
  FlowProjectHealth,
  FlowReviewCleanupAction,
  FlowTask,
  FlowTaskSource,
  FlowTaskStatus,
  FlowWeeklyReviewPackage,
  MemoryEntrySummary,
  ReviewSummary,
  WorkspaceSnapshot
} from "../../domain/read-models.js";

interface TaskRow {
  id: string;
  title: string;
  status: string;
  context_tags: string | null;
  due_date: string | null;
  estimated_duration: number | null;
  updated_at: string | null;
  project_title?: string | null;
}

interface AssistantTurnRow {
  id: string;
  prompt: string;
  response: string;
  route: string;
  proposal_json: string | null;
  proposal_status: string;
  created_at: string | null;
}

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

function parseAuditPayload(rawJson: string | null | undefined): Record<string, string> {
  if (!rawJson) {
    return {};
  }

  try {
    const parsed = JSON.parse(rawJson) as Record<string, unknown>;
    if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
      return {};
    }
    return Object.fromEntries(
      Object.entries(parsed).map(([key, value]) => [key, String(value)])
    );
  } catch {
    return {};
  }
}

function providerDetails(
  steps: FlowAssistantAuditStep[]
): {
  provider: string;
  providerStatus: string;
  providerDetail: string;
  providerModel?: string;
} {
  const providerStep = steps.find((step) => step.stage === "provider")
    ?? steps.find((step) => step.stage === "fallback");
  const payload = providerStep?.payload ?? {};
  return {
    provider: payload.provider ?? "unknown",
    providerStatus: payload.provider_status ?? "unknown",
    providerDetail: payload.provider_detail ?? providerStep?.summary ?? "No provider evidence recorded.",
    providerModel: payload.provider_model || undefined
  };
}

function messageProviderDetails(
  message: AssistantMessageRow,
  steps: FlowAssistantAuditStep[]
): {
  provider: string;
  providerStatus: string;
  providerDetail: string;
  providerModel?: string;
} {
  const providerStep = steps.find((step) => step.stage === "provider")
    ?? steps.find((step) => step.stage === "fallback");
  return {
    provider: message.provider || providerStep?.payload.provider || "unknown",
    providerStatus: message.provider_status || providerStep?.payload.provider_status || "unknown",
    providerDetail: message.provider_detail || providerStep?.summary || "No provider evidence recorded.",
    providerModel: message.provider_model || providerStep?.payload.provider_model || undefined
  };
}

function isoTimestamp(value: Date): string {
  return value.toISOString();
}

function parseDate(value: string | null | undefined): Date | null {
  if (!value) {
    return null;
  }

  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? null : date;
}

function formatDueLabel(value: string | null | undefined): string | undefined {
  const date = parseDate(value);
  if (!date) {
    return value ?? undefined;
  }

  const now = new Date();
  const today = now.toISOString().slice(0, 10);
  const tomorrow = new Date(now.getTime() + 24 * 60 * 60 * 1000)
    .toISOString()
    .slice(0, 10);
  const target = date.toISOString().slice(0, 10);
  if (target === today) {
    return "Today";
  }
  if (target === tomorrow) {
    return "Tomorrow";
  }
  return new Intl.DateTimeFormat("en-US", {
    dateStyle: "medium",
    timeZone: "UTC"
  }).format(date);
}

function relativeUpdatedLabel(value: string | null | undefined): string | undefined {
  if (!value) {
    return undefined;
  }
  return `Updated ${value}`;
}

function decodeTags(rawValue: string | null | undefined): string[] {
  if (!rawValue) {
    return [];
  }

  try {
    const decoded = JSON.parse(rawValue) as unknown;
    return Array.isArray(decoded)
      ? decoded.filter((value): value is string => typeof value === "string")
      : [];
  } catch {
    return [];
  }
}

function sourceSummary(source: FlowTaskSource): string {
  switch (source) {
    case "capture":
      return "Fresh capture awaiting a confident next step.";
    case "planned":
      return "Selected for the active day and ready to move.";
    case "project":
      return "Project-linked work kept visible without flooding the plan.";
    case "reminders":
      return "Imported from Apple Reminders.";
    case "assistant":
      return "Assistant-suggested refinement of your current flow.";
  }
}

function inferTaskSource(
  source: FlowTaskSource,
  projectName?: string
): FlowTaskSource {
  if (source === "capture" && projectName) {
    return "project";
  }
  return source;
}

function whyMemoryMatters(kind: string, scope: string): string {
  switch (kind) {
    case "planning_preference":
    case "explicit_preference":
      return `This can influence planning and assistant suggestions in the ${scope} scope.`;
    case "project_context":
      return "This keeps project context visible when the assistant or planner reasons about related work.";
    default:
      return "This remains inspectable product memory that can shape workflow suggestions.";
  }
}

export class FlowReadRepository {
  constructor(private readonly db: DatabaseSync) {}

  loadWorkspaceSnapshot(): WorkspaceSnapshot {
    const inbox = this.fetchInboxItems();
    const today = this.fetchPlannedItems();
    const later = this.fetchLaterItems(new Set(today.map((task) => task.id)));
    const projects = this.fetchProjects();
    const stale = this.fetchStaleItems();
    const review = this.buildReviewSummary(stale.length);
    const assistant = this.buildAssistantSuggestions(inbox, today, stale);
    const memory = this.buildMemoryEntries(projects, inbox);
    const headline = this.buildFocusHeadline(today.length, inbox.length);

    return {
      inboxItems: inbox,
      todayItems: today,
      laterItems: later,
      projects,
      staleItems: stale,
      review,
      assistantSuggestions: assistant,
      memoryEntries: memory,
      focusHeadline: headline
    };
  }

  loadAssistantTurns(limit = 30): FlowAssistantTurn[] {
    const rows = this.db
      .prepare(
        `
          SELECT id, prompt, response, route, proposal_json, proposal_status, created_at
          FROM assistant_turns
          ORDER BY created_at DESC
          LIMIT ?
        `
      )
      .all(limit) as unknown as AssistantTurnRow[];

    return rows.map((row) => {
      const auditSteps = this.fetchAssistantAuditSteps(row.id);
      const provider = providerDetails(auditSteps);
      return {
        id: row.id,
        prompt: row.prompt,
        response: row.response,
        route: row.route,
        proposal: this.parseAssistantProposal(row.proposal_json),
        proposalStatus: row.proposal_status,
        auditSteps,
        provider: provider.provider,
        providerStatus: provider.providerStatus,
        providerDetail: provider.providerDetail,
        providerModel: provider.providerModel,
        createdAtLabel: relativeUpdatedLabel(row.created_at) ?? "Just now"
      };
      });
  }

  loadAssistantSessions(limit = 30): FlowAssistantSession[] {
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

    return rows.map((row) => ({
      id: row.id,
      title: row.title,
      latestPreview: row.latest_preview,
      messageCount: Number(row.message_count ?? 0),
      createdAtLabel: relativeUpdatedLabel(row.created_at) ?? "Just now",
      updatedAtLabel: relativeUpdatedLabel(row.updated_at) ?? "Just now"
    }));
  }

  loadAssistantMessages(sessionID: string, limit = 30): FlowAssistantMessage[] {
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

    return rows.reverse().map((row) => {
      const auditSteps = this.fetchAssistantMessageAuditSteps(row.id);
      const provider = messageProviderDetails(row, auditSteps);
      return {
        id: row.id,
        sessionID: row.session_id,
        role: row.role,
        content: row.content,
        route: row.route,
        proposal: this.parseAssistantProposal(row.proposal_json),
        proposalStatus: row.proposal_status,
        auditSteps,
        provider: provider.provider,
        providerStatus: provider.providerStatus,
        providerDetail: provider.providerDetail,
        providerModel: provider.providerModel,
        sourceTurnID: row.source_turn_id ?? undefined,
        createdAtLabel: relativeUpdatedLabel(row.created_at) ?? "Just now",
        updatedAtLabel: relativeUpdatedLabel(row.updated_at) ?? "Just now"
      };
    });
  }

  loadMemoryRecords(
    query?: string,
    includeDisabled = false
  ): FlowMemoryRecord[] {
    let sql = `
      SELECT id, kind, scope, scope_ref, value, source, confidence, enabled, updated_at
      FROM memory_entries
    `;
    const clauses: string[] = [];
    const bindings: string[] = [];

    if (!includeDisabled) {
      clauses.push("enabled = 1");
    }
    if (query && query.trim()) {
      clauses.push("LOWER(value) LIKE ?");
      bindings.push(`%${query.trim().toLowerCase()}%`);
    }
    if (clauses.length > 0) {
      sql += ` WHERE ${clauses.join(" AND ")}`;
    }
    sql += " ORDER BY updated_at DESC, created_at DESC";

    const rows = this.db.prepare(sql).all(...bindings) as Array<Record<string, unknown>>;
    return rows.map((row) => {
      const kind = String(row.kind ?? "");
      const scope = String(row.scope ?? "");
      return {
        id: String(row.id ?? ""),
        kind,
        scope,
        scopeRef: row.scope_ref ? String(row.scope_ref) : undefined,
        value: String(row.value ?? ""),
        source: String(row.source ?? ""),
        confidence: Number(row.confidence ?? 0),
        enabled: Number(row.enabled ?? 0) === 1,
        updatedAtLabel: relativeUpdatedLabel(String(row.updated_at ?? "")) ?? "Just now",
        whyItMatters: whyMemoryMatters(kind, scope)
      };
    });
  }

  loadDailyPlanState(planDate: string): FlowDailyPlanState {
    const topItems = this.fetchPlanItems(planDate, "top");
    const bonusItems = this.fetchPlanItems(planDate, "bonus");
    const plannedIDs = new Set([...topItems, ...bonusItems].map((task) => task.id));
    const mustAddress = this.fetchTasks(
      `
        SELECT id, title, status, context_tags, due_date, estimated_duration, updated_at
        FROM items
        WHERE type = 'action' AND status = 'active' AND due_date IS NOT NULL AND date(due_date) <= date(?)
        ORDER BY due_date ASC
      `,
      [planDate],
      "planned"
    ).filter((task) => !plannedIDs.has(task.id));
    const mustAddressIDs = new Set(mustAddress.map((task) => task.id));
    const inbox = this.fetchInboxItems().filter((task) => !plannedIDs.has(task.id));
    const readyActions = this.fetchTasks(
      `
        SELECT id, title, status, context_tags, due_date, estimated_duration, updated_at
        FROM items
        WHERE type = 'action' AND status = 'active' AND parent_id IS NULL
        ORDER BY updated_at DESC
      `,
      [],
      "planned"
    ).filter((task) => !plannedIDs.has(task.id) && !mustAddressIDs.has(task.id));
    const projectTasks = this.fetchTasks(
      `
        SELECT i.id, i.title, i.status, i.context_tags, i.due_date, i.estimated_duration, i.updated_at, p.title AS project_title
        FROM items i
        LEFT JOIN items p ON p.id = i.parent_id AND p.type = 'project'
        WHERE i.type = 'action' AND i.status = 'active' AND i.parent_id IS NOT NULL
        ORDER BY i.updated_at DESC
      `,
      [],
      "project",
      undefined,
      7
    ).filter((task) => !plannedIDs.has(task.id) && !mustAddressIDs.has(task.id));

    const riskFlags: string[] = [];
    if (topItems.length > 3) {
      riskFlags.push("Top focus exceeds three items.");
    }
    if (bonusItems.length > 2) {
      riskFlags.push("Bonus load may crowd the day.");
    }
    if (mustAddress.length > topItems.length && mustAddress.length > 0) {
      riskFlags.push("Due-soon work exceeds the current committed focus.");
    }

    return {
      planDate,
      topItems,
      bonusItems,
      mustAddress,
      inbox,
      readyActions,
      projectTasks,
      riskFlags,
      calendarStatus:
        "Calendar-aware reasoning is currently limited to task due dates. Live calendar integration is not connected yet."
    };
  }

  loadWeeklyReviewPackage(referenceDate = new Date()): FlowWeeklyReviewPackage {
    const weekAgo = new Date(referenceDate.getTime() - 7 * 24 * 60 * 60 * 1000);
    const staleThreshold = new Date(
      referenceDate.getTime() - 14 * 24 * 60 * 60 * 1000
    );
    const soon = new Date(referenceDate.getTime() + 7 * 24 * 60 * 60 * 1000);

    const completed = this.fetchTasks(
      `
        SELECT id, title, status, context_tags, due_date, estimated_duration, updated_at
        FROM items
        WHERE status = 'done' AND updated_at >= ?
        ORDER BY updated_at DESC
        LIMIT 12
      `,
      [isoTimestamp(weekAgo)],
      "project"
    );
    const stale = this.fetchTasks(
      `
        SELECT id, title, status, context_tags, due_date, estimated_duration, updated_at
        FROM items
        WHERE status = 'active' AND updated_at < ?
        ORDER BY updated_at ASC
        LIMIT 12
      `,
      [isoTimestamp(staleThreshold)],
      "project"
    );
    const inbox = this.fetchInboxItems();
    const upcomingDeadlines = this.fetchTasks(
      `
        SELECT id, title, status, context_tags, due_date, estimated_duration, updated_at
        FROM items
        WHERE status = 'active' AND due_date IS NOT NULL AND due_date <= ?
        ORDER BY due_date ASC
        LIMIT 12
      `,
      [isoTimestamp(soon)],
      "planned"
    );
    const projects = this.fetchProjects();

    return {
      generatedAtLabel: referenceDate.toISOString().slice(0, 10),
      completedWork: completed,
      staleItems: stale,
      inboxItems: inbox,
      projectHealth: this.makeProjectHealth(projects),
      upcomingDeadlines,
      cleanupActions: this.makeWeeklyReviewCleanupActions(
        stale,
        inbox,
        projects,
        upcomingDeadlines
      )
    };
  }

  loadNotificationPolicy(): FlowNotificationPolicyState {
    const permissionStatus = this.fetchNotificationPermissionStatus();
    const degradedReasons = this.notificationDegradedReasons(permissionStatus);
    const deliveryMode = degradedReasons.length === 0 ? "flow_owned_local" : "degraded";

    return {
      permissionStatus,
      deliveryMode,
      degradedReasons,
      pendingNotifications:
        deliveryMode === "flow_owned_local"
          ? this.fetchPendingNotificationCandidates()
          : [],
      offlineDescription:
        "Flow-owned notifications are local to this Mac; if permission or system services are unavailable, tasks remain visible in Today and Daily Plan."
    };
  }

  private fetchInboxItems(): FlowTask[] {
    return this.fetchTasks(
      `
        SELECT id, title, status, context_tags, due_date, estimated_duration, updated_at
        FROM items
        WHERE type = 'inbox' AND status = 'active' AND parent_id IS NULL
        ORDER BY created_at DESC
        LIMIT 40
      `,
      [],
      "capture"
    );
  }

  private fetchPlannedItems(): FlowTask[] {
    return this.fetchTasks(
      `
        SELECT i.id, i.title, i.status, i.context_tags, i.due_date, i.estimated_duration, i.updated_at, p.title AS project_title
        FROM daily_plan_entries d
        JOIN items i ON i.id = d.item_id
        LEFT JOIN items p ON p.id = i.parent_id AND p.type = 'project'
        WHERE i.status = 'active'
        ORDER BY d.plan_date DESC, d.bucket ASC, d.position ASC
        LIMIT 12
      `,
      [],
      "planned",
      undefined,
      7
    );
  }

  private fetchLaterItems(plannedIDs: Set<string>): FlowTask[] {
    return this.fetchTasks(
      `
        SELECT i.id, i.title, i.status, i.context_tags, i.due_date, i.estimated_duration, i.updated_at, p.title AS project_title
        FROM items i
        LEFT JOIN items p ON p.id = i.parent_id AND p.type = 'project'
        WHERE i.status IN ('active', 'waiting') AND i.type IN ('action', 'inbox')
        ORDER BY i.due_date IS NOT NULL DESC, i.due_date ASC, i.updated_at DESC
        LIMIT 24
      `,
      [],
      "project",
      undefined,
      7
    ).filter((task) => !plannedIDs.has(task.id));
  }

  private fetchProjects(): FlowProject[] {
    const rows = this.db
      .prepare(
        `
          SELECT id, title, status
          FROM items
          WHERE type = 'project' AND status = 'active'
          ORDER BY updated_at DESC, created_at DESC
          LIMIT 12
        `
      )
      .all() as Array<Record<string, unknown>>;

    return rows.map((row) => {
      const projectID = String(row.id ?? "");
      const title = String(row.title ?? "");
      const tasks = this.fetchTasks(
        `
          SELECT id, title, status, context_tags, due_date, estimated_duration, updated_at
          FROM items
          WHERE parent_id = ?
          ORDER BY status = 'done' ASC, updated_at DESC, created_at DESC
          LIMIT 8
        `,
        [projectID],
        "project",
        title
      );
      const nextAction = tasks.find(
        (task) => task.status === "active" || task.status === "waiting"
      );

      return {
        id: projectID,
        title,
        summary:
          tasks.length === 0
            ? "Needs its first clearly defined next action."
            : "Balance execution and planning without widening the day.",
        nextActionTitle: nextAction?.title,
        activeCount: tasks.filter(
          (task) => task.status !== "done" && task.status !== "archived"
        ).length,
        completedCount: tasks.filter((task) => task.status === "done").length,
        tasks
      };
    });
  }

  private fetchStaleItems(): FlowTask[] {
    const threshold = new Date(Date.now() - 14 * 24 * 60 * 60 * 1000);
    return this.fetchTasks(
      `
        SELECT id, title, status, context_tags, due_date, estimated_duration, updated_at
        FROM items
        WHERE status = 'active' AND updated_at < ?
        ORDER BY updated_at ASC
        LIMIT 10
      `,
      [isoTimestamp(threshold)],
      "project"
    );
  }

  private buildReviewSummary(staleCount: number): ReviewSummary {
    const weekAgo = new Date(Date.now() - 7 * 24 * 60 * 60 * 1000);
    const soon = new Date(Date.now() + 3 * 24 * 60 * 60 * 1000);
    const completedThisWeek = this.scalarCount(
      "SELECT COUNT(*) AS count FROM items WHERE status = 'done' AND updated_at >= ?",
      [isoTimestamp(weekAgo)]
    );
    const dueSoonCount = this.scalarCount(
      "SELECT COUNT(*) AS count FROM items WHERE status = 'active' AND due_date IS NOT NULL AND due_date <= ?",
      [isoTimestamp(soon)]
    );

    if (staleCount === 0 && dueSoonCount <= 1) {
      return {
        completedThisWeek,
        staleCount,
        dueSoonCount,
        headline: "Healthy system, light maintenance",
        prompt: "Keep the inbox moving and preserve space for deep work."
      };
    }
    if (staleCount >= 5) {
      return {
        completedThisWeek,
        staleCount,
        dueSoonCount,
        headline: "Backlog drift is building",
        prompt: "Prune stale commitments before adding more work."
      };
    }
    return {
      completedThisWeek,
      staleCount,
      dueSoonCount,
      headline: "Strong progress, tighten follow-through",
      prompt: "Resolve stale edges and keep upcoming commitments visible."
    };
  }

  private buildAssistantSuggestions(
    inbox: FlowTask[],
    today: FlowTask[],
    stale: FlowTask[]
  ): AssistantSuggestion[] {
    const suggestions: AssistantSuggestion[] = [];
    const firstInbox = inbox[0];
    if (firstInbox) {
      suggestions.push({
        id: "assistant-inbox",
        title: "Clarify your newest capture",
        detail: `"${firstInbox.title}" still looks like raw intent. Turn it into a concrete next action.`,
        outcomeLabel: "Preview"
      });
    }
    if (today.length >= 3) {
      suggestions.push({
        id: "assistant-plan",
        title: "Keep the plan constrained",
        detail:
          "Three primary items are already active. Push additional work into later, not into today.",
        outcomeLabel: "Guardrail"
      });
    }
    const staleItem = stale[0];
    if (staleItem) {
      suggestions.push({
        id: "assistant-stale",
        title: "Clean up stale work",
        detail: `Revisit "${staleItem.title}" before it silently becomes background stress.`,
        outcomeLabel: "Review"
      });
    }
    return suggestions;
  }

  private buildMemoryEntries(
    projects: FlowProject[],
    inbox: FlowTask[]
  ): MemoryEntrySummary[] {
    if (projects.length === 0 && inbox.length === 0) {
      return [
        {
          id: "memory-empty",
          title: "No inferred patterns yet",
          detail: "Seed the system with a few tasks, projects, or reviews to shape visible memory cues.",
          confidenceLabel: "Empty",
          scopeLabel: "Global"
        }
      ];
    }

    const entries: MemoryEntrySummary[] = [
      {
        id: "memory-plan-shape",
        title: "Prefers a small daily focus set",
        detail:
          "The current workspace emphasizes a compact set of primary work rather than a broad queue.",
        confidenceLabel: "Working assumption",
        scopeLabel: "Planning"
      }
    ];

    if (inbox.length > 0) {
      entries.push({
        id: "memory-capture",
        title: "Recent captures need clarification support",
        detail:
          "The native shell should continue nudging capture-to-clarify transitions instead of leaving them raw.",
        confidenceLabel: "Observed",
        scopeLabel: "Inbox"
      });
    }

    const firstProject = projects[0];
    if (firstProject) {
      entries.push({
        id: "memory-project",
        title: `Active project context: ${firstProject.title}`,
        detail:
          "Project surfaces should keep the next action visible without flattening project state into a plain list.",
        confidenceLabel: "Context",
        scopeLabel: "Project"
      });
    }

    return entries;
  }

  private buildFocusHeadline(todayCount: number, inboxCount: number): string {
    if (todayCount >= 3) {
      return "Deliberate plan in place, protect the next block";
    }
    if (inboxCount > 0) {
      return "Clear the freshest ambiguity before widening the day";
    }
    return "Quiet system, ready for a thoughtful start";
  }

  private fetchPlanItems(planDate: string, bucket: string): FlowTask[] {
    return this.fetchTasks(
      `
        SELECT i.id, i.title, i.status, i.context_tags, i.due_date, i.estimated_duration, i.updated_at, p.title AS project_title
        FROM daily_plan_entries d
        JOIN items i ON i.id = d.item_id
        LEFT JOIN items p ON p.id = i.parent_id AND p.type = 'project'
        WHERE d.plan_date = ? AND d.bucket = ? AND i.status = 'active'
        ORDER BY d.position ASC
      `,
      [planDate, bucket],
      "planned",
      undefined,
      7
    );
  }

  private fetchTasks(
    sql: string,
    bindings: Array<string | number>,
    source: FlowTaskSource,
    projectName?: string,
    projectColumnIndex?: number
  ): FlowTask[] {
    const rows = this.db.prepare(sql).all(...bindings) as unknown as TaskRow[];

    return rows.map((row) => {
      const resolvedProjectName =
        projectColumnIndex !== undefined
          ? row.project_title || projectName
          : projectName;

      return {
        id: row.id,
        title: row.title,
        summary: resolvedProjectName
          ? `Linked to ${resolvedProjectName}.`
          : sourceSummary(source),
        status: (row.status as FlowTaskStatus) || "active",
        source: inferTaskSource(source, resolvedProjectName),
        projectName: resolvedProjectName ?? undefined,
        dueLabel: formatDueLabel(row.due_date),
        tags: decodeTags(row.context_tags),
        estimatedMinutes:
          row.estimated_duration === null ? undefined : row.estimated_duration,
        isFlagged: row.due_date !== null,
        lastUpdatedLabel: relativeUpdatedLabel(row.updated_at)
      };
    });
  }

  private scalarCount(sql: string, bindings: Array<string | number>): number {
    const row = this.db.prepare(sql).get(...bindings) as { count?: number } | undefined;
    return Number(row?.count ?? 0);
  }

  private parseAssistantProposal(
    rawJson: string | null | undefined
  ): FlowAssistantProposal | undefined {
    if (!rawJson) {
      return undefined;
    }

    try {
      const parsed = JSON.parse(rawJson) as Record<string, unknown>;
      return {
        actionType: String(parsed.action_type ?? ""),
        title: String(parsed.title ?? ""),
        detail: String(parsed.detail ?? ""),
        requiresConfirmation: Boolean(parsed.requires_confirmation ?? false)
      };
    } catch {
      return undefined;
    }
  }

  private fetchAssistantAuditSteps(turnID: string): FlowAssistantAuditStep[] {
    const rows = this.db
      .prepare(
        `
          SELECT id, stage, status, summary, payload_json
          FROM assistant_audit_steps
          WHERE turn_id = ?
          ORDER BY created_at ASC
        `
      )
      .all(turnID) as Array<Record<string, unknown>>;

    return rows.map((row) => ({
      id: String(row.id ?? ""),
      stage: String(row.stage ?? ""),
      status: String(row.status ?? ""),
      summary: String(row.summary ?? ""),
      payload: parseAuditPayload(String(row.payload_json ?? ""))
    }));
  }

  private fetchAssistantMessageAuditSteps(messageID: string): FlowAssistantAuditStep[] {
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
        payload_json: string | null;
      }>;

    return rows.map((row) => ({
      id: row.id,
      stage: row.stage,
      status: row.status,
      summary: row.summary,
      payload: parseAuditPayload(row.payload_json)
    }));
  }

  private makeProjectHealth(projects: FlowProject[]): FlowProjectHealth[] {
    if (projects.length === 0) {
      return [
        {
          id: "project-health-empty",
          title: "Projects",
          statusLabel: "No active projects",
          detail:
            "The weekly review can stay focused on inbox, deadlines, and stale standalone work."
        }
      ];
    }

    return projects.map((project) => {
      if (project.activeCount === 0) {
        return {
          id: project.id,
          title: project.title,
          statusLabel: "Needs next action",
          detail: "Add or clarify a next action before this project can move."
        };
      }
      if (project.completedCount > 0) {
        return {
          id: project.id,
          title: project.title,
          statusLabel: "Progressing",
          detail: "Completed work exists; confirm the next visible commitment."
        };
      }
      return {
        id: project.id,
        title: project.title,
        statusLabel: "Active",
        detail: project.nextActionTitle
          ? `Next action: ${project.nextActionTitle}`
          : project.summary
      };
    });
  }

  private makeWeeklyReviewCleanupActions(
    stale: FlowTask[],
    inbox: FlowTask[],
    projects: FlowProject[],
    dueSoon: FlowTask[]
  ): FlowReviewCleanupAction[] {
    const actions = stale.map((task) => ({
      id: `archive-stale-${task.id}`,
      kind: "archive_stale_item",
      title: `Archive stale: ${task.title}`,
      detail: "Move this aging active item out of the live system.",
      targetIDs: [task.id],
      destructive: true
    }));

    if (inbox.length > 0) {
      actions.push({
        id: "clarify-inbox",
        kind: "clarify_inbox",
        title: `Clarify ${inbox.length} inbox item${inbox.length === 1 ? "" : "s"}`,
        detail: "Work through the raw captures still waiting for a decision.",
        targetIDs: inbox.map((task) => task.id),
        destructive: false
      });
    }

    const projectsNeedingNextAction = projects.filter(
      (project) => project.activeCount === 0
    );
    if (projectsNeedingNextAction.length > 0) {
      actions.push({
        id: "project-next-actions",
        kind: "project_next_action_review",
        title: "Add missing project next actions",
        detail: `${projectsNeedingNextAction.length} active project${projectsNeedingNextAction.length === 1 ? "" : "s"} need a concrete next step.`,
        targetIDs: projectsNeedingNextAction.map((project) => project.id),
        destructive: false
      });
    }

    if (dueSoon.length > 0) {
      actions.push({
        id: "deadline-check",
        kind: "deadline_review",
        title: `Check ${dueSoon.length} upcoming deadline${dueSoon.length === 1 ? "" : "s"}`,
        detail: "Confirm these commitments still fit the coming week.",
        targetIDs: dueSoon.map((task) => task.id),
        destructive: false
      });
    }

    return actions;
  }

  private fetchNotificationPermissionStatus(): string {
    const row = this.db
      .prepare(
        "SELECT permission_status FROM notification_policy WHERE id = 'flow' LIMIT 1"
      )
      .get() as { permission_status?: string } | undefined;
    return row?.permission_status ?? "not_determined";
  }

  private fetchPendingNotificationCandidates(): FlowNotificationCandidate[] {
    const rows = this.db
      .prepare(
        `
          SELECT id, title, due_date
          FROM items
          WHERE status = 'active' AND due_date IS NOT NULL
          ORDER BY due_date ASC
          LIMIT 20
        `
      )
      .all() as Array<Record<string, unknown>>;

    return rows.map((row) => ({
      id: `notification-${String(row.id ?? "")}`,
      taskID: String(row.id ?? ""),
      title: String(row.title ?? ""),
      fireAtLabel: formatDueLabel(String(row.due_date ?? "")) ?? "Scheduled",
      policyLabel: "Flow-owned local"
    }));
  }

  private notificationDegradedReasons(permissionStatus: string): string[] {
    switch (permissionStatus) {
      case "authorized":
      case "provisional":
        return [];
      case "denied":
        return [
          "Notifications are denied in macOS settings; Flow will keep reminders visible in-app only."
        ];
      case "unavailable":
        return [
          "macOS notification services are unavailable; Flow is running in degraded local-only mode."
        ];
      default:
        return [
          "Local notification permission has not been requested; Flow will not schedule alerts yet."
        ];
    }
  }
}

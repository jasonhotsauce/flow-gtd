export type FlowSection =
  | "today"
  | "inbox"
  | "projects"
  | "review"
  | "assistant"
  | "memory";

export type FlowTaskStatus =
  | "active"
  | "done"
  | "waiting"
  | "someday"
  | "archived";

export type FlowTaskSource =
  | "capture"
  | "planned"
  | "project"
  | "reminders"
  | "assistant";

export interface FlowTask {
  id: string;
  title: string;
  summary: string;
  status: FlowTaskStatus;
  source: FlowTaskSource;
  projectName?: string;
  dueLabel?: string;
  tags: string[];
  estimatedMinutes?: number;
  isFlagged: boolean;
  lastUpdatedLabel?: string;
}

export interface FlowProject {
  id: string;
  title: string;
  summary: string;
  nextActionTitle?: string;
  activeCount: number;
  completedCount: number;
  tasks: FlowTask[];
}

export interface ReviewSummary {
  completedThisWeek: number;
  staleCount: number;
  dueSoonCount: number;
  headline: string;
  prompt: string;
}

export interface AssistantSuggestion {
  id: string;
  title: string;
  detail: string;
  outcomeLabel: string;
}

export interface MemoryEntrySummary {
  id: string;
  title: string;
  detail: string;
  confidenceLabel: string;
  scopeLabel: string;
}

export interface WorkspaceSnapshot {
  inboxItems: FlowTask[];
  todayItems: FlowTask[];
  laterItems: FlowTask[];
  projects: FlowProject[];
  staleItems: FlowTask[];
  review: ReviewSummary;
  assistantSuggestions: AssistantSuggestion[];
  memoryEntries: MemoryEntrySummary[];
  focusHeadline: string;
}

export interface FlowAssistantProposal {
  actionType: string;
  title: string;
  detail: string;
  requiresConfirmation: boolean;
}

export interface FlowAssistantAuditStep {
  id: string;
  stage: string;
  status: string;
  summary: string;
  payload: Record<string, string>;
}

export interface FlowAssistantTurn {
  id: string;
  prompt: string;
  response: string;
  route: string;
  proposal?: FlowAssistantProposal;
  proposalStatus: string;
  auditSteps: FlowAssistantAuditStep[];
  provider: string;
  providerStatus: string;
  providerDetail: string;
  providerModel?: string;
  createdAtLabel: string;
}

export interface FlowAssistantSession {
  id: string;
  title: string;
  latestPreview: string;
  messageCount: number;
  createdAtLabel: string;
  updatedAtLabel: string;
}

export interface FlowAssistantMessage {
  id: string;
  sessionID: string;
  role: string;
  content: string;
  route: string;
  proposal?: FlowAssistantProposal;
  proposalStatus: string;
  auditSteps: FlowAssistantAuditStep[];
  provider: string;
  providerStatus: string;
  providerDetail: string;
  providerModel?: string;
  sourceTurnID?: string;
  createdAtLabel: string;
  updatedAtLabel: string;
}

export interface FlowMemoryRecord {
  id: string;
  kind: string;
  scope: string;
  scopeRef?: string;
  value: string;
  source: string;
  confidence: number;
  enabled: boolean;
  updatedAtLabel: string;
  whyItMatters: string;
}

export interface FlowDailyPlanState {
  planDate: string;
  topItems: FlowTask[];
  bonusItems: FlowTask[];
  mustAddress: FlowTask[];
  inbox: FlowTask[];
  readyActions: FlowTask[];
  projectTasks: FlowTask[];
  riskFlags: string[];
  calendarStatus: string;
}

export interface FlowProjectHealth {
  id: string;
  title: string;
  statusLabel: string;
  detail: string;
}

export interface FlowReviewCleanupAction {
  id: string;
  kind: string;
  title: string;
  detail: string;
  targetIDs: string[];
  destructive: boolean;
}

export interface FlowWeeklyReviewPackage {
  generatedAtLabel: string;
  completedWork: FlowTask[];
  staleItems: FlowTask[];
  inboxItems: FlowTask[];
  projectHealth: FlowProjectHealth[];
  upcomingDeadlines: FlowTask[];
  cleanupActions: FlowReviewCleanupAction[];
}

export interface FlowNotificationCandidate {
  id: string;
  taskID: string;
  title: string;
  fireAtLabel: string;
  policyLabel: string;
}

export interface FlowNotificationPolicyState {
  permissionStatus: string;
  deliveryMode: string;
  degradedReasons: string[];
  pendingNotifications: FlowNotificationCandidate[];
  offlineDescription: string;
}

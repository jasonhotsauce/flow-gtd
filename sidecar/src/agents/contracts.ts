export type AgentCapability =
  | "read_gtd_context"
  | "propose_inbox_write"
  | "propose_memory_write"
  | "propose_planning_change"
  | "propose_review_cleanup"
  | "execute_tool"
  | "access_coding_workspace";

export type ProviderName = "openai" | "anthropic" | "deterministic" | "codex";

export type ProviderExecutionStatus =
  | "success"
  | "degraded"
  | "unavailable"
  | "failed";

export type AssistantOutputMode = "text" | "json" | "proposal";

export type SpecialistKind =
  | "assistant_orchestrator"
  | "capture_clarifier"
  | "daily_planner"
  | "weekly_reviewer"
  | "project_health_analyst"
  | "memory_curator";

export type VerificationStatus = "draft" | "validated" | "failed";

export interface TraceEvent {
  stage: string;
  summary: string;
  provider: string;
  payload?: Record<string, string>;
}

export interface ProviderEvidence {
  provider: ProviderName;
  status: ProviderExecutionStatus;
  runtime: string;
  detail: string;
  model?: string;
  command?: string;
  fallbackReason?: FallbackReason;
}

export interface AssistantWriteProposal {
  actionType: string;
  targetTable: string;
  targetID: string;
  previewText: string;
  rationale: string;
  confidence: number;
  requiresConfirmation: boolean;
  verificationStatus: VerificationStatus;
  payload: Record<string, string>;
}

export interface AssistantRequest {
  requestID: string;
  prompt: string;
  routeHint?: string;
  specialist?: SpecialistKind;
  capabilities: AgentCapability[];
  provider?: ProviderName;
  outputMode?: AssistantOutputMode;
  context?: Record<string, unknown>;
  metadata?: Record<string, unknown>;
}

export interface SpecialistStructuredOutput {
  kind: SpecialistKind;
  summary: string;
  rationale: string[];
  writeProposals?: AssistantWriteProposal[];
  [key: string]: unknown;
}

export interface ProviderRunRequest {
  requestID: string;
  prompt: string;
  specialist: SpecialistKind;
  capabilities: AgentCapability[];
  outputMode: AssistantOutputMode;
  context: Record<string, unknown>;
  metadata: Record<string, unknown>;
}

export interface ProviderRunResult {
  responseText: string;
  structuredOutput?: unknown;
  traceEvents?: TraceEvent[];
  usage?: Record<string, unknown>;
  model?: string;
  providerEvidence?: ProviderEvidence;
}

export type FallbackReason =
  | "capability_denied"
  | "provider_failed"
  | "validation_failed"
  | "provider_unavailable";

export interface AssistantResponse {
  requestID: string;
  specialist: SpecialistKind;
  provider: string;
  providerEvidence: ProviderEvidence;
  responseText: string;
  structuredOutput?: SpecialistStructuredOutput;
  writeProposals: AssistantWriteProposal[];
  traceEvents: TraceEvent[];
  failed: boolean;
  fallbackReason?: FallbackReason;
  usage: Record<string, unknown>;
  model?: string;
}

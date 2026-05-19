import type {
  AssistantRequest,
  AssistantResponse,
  FallbackReason,
  ProviderEvidence,
  ProviderName,
  SpecialistStructuredOutput,
  TraceEvent
} from "./contracts.js";
import { createDefaultProviderRegistry, type ProviderRegistry, ProviderUnavailableError } from "./providers.js";
import { CodexProviderError } from "./codex-provider.js";
import {
  createDefaultSpecialistRegistry,
  resolveSpecialist,
  type SpecialistDefinition
} from "./specialists.js";
import {
  ensureCapabilities,
  validateAssistantRequest,
  validateSpecialistStructuredOutput
} from "./validators.js";

export interface AssistantOrchestratorOptions {
  specialists?: Map<string, SpecialistDefinition>;
  providers?: ProviderRegistry;
}

function fallbackResponse(
  request: AssistantRequest,
  definition: SpecialistDefinition,
  provider: ProviderName,
  reason: FallbackReason,
  detail: string,
  traceEvents: TraceEvent[]
): AssistantResponse {
  const providerEvidence: ProviderEvidence = {
    provider,
    status: reason === "provider_unavailable" ? "unavailable" : "failed",
    runtime: "deterministic fallback",
    detail,
    fallbackReason: reason
  };
  const responseText = [
    `${definition.fallbackSummary}`,
    `Specialist: ${definition.kind}.`,
    `Reason: ${detail}.`,
    "Returning deterministic fallback."
  ].join(" ");
  const fallbackTrace: TraceEvent = {
    stage: "fallback",
    summary: `Returned deterministic fallback for ${definition.kind}.`,
    provider,
    payload: {
      reason,
      provider,
      provider_status: providerEvidence.status,
      provider_runtime: providerEvidence.runtime,
      provider_detail: providerEvidence.detail
    }
  };

  return {
    requestID: request.requestID,
    specialist: definition.kind,
    provider,
    providerEvidence,
    responseText,
    structuredOutput: {
      kind: definition.kind,
      summary: responseText,
      rationale: [detail],
      writeProposals: []
    } as SpecialistStructuredOutput,
    writeProposals: [],
    traceEvents: [...traceEvents, fallbackTrace],
    failed: true,
    fallbackReason: reason,
    usage: {}
  };
}

export class AssistantOrchestrator {
  private readonly specialists: Map<string, SpecialistDefinition>;
  private readonly providers: ProviderRegistry;

  constructor(options: AssistantOrchestratorOptions = {}) {
    this.specialists = options.specialists ?? createDefaultSpecialistRegistry();
    this.providers = options.providers ?? createDefaultProviderRegistry();
  }

  async handle(request: AssistantRequest): Promise<AssistantResponse> {
    validateAssistantRequest(request);

    const definition = resolveSpecialist(
      this.specialists as Map<any, SpecialistDefinition>,
      request.routeHint,
      request.specialist
    );
    const providerName = request.provider ?? "codex";
    const traceEvents: TraceEvent[] = [
      {
        stage: "route",
        summary: `Resolved assistant request to ${definition.kind}.`,
        provider: providerName,
        payload: {
          routeHint: request.routeHint ?? ""
        }
      }
    ];

    const missingCapabilities = ensureCapabilities(
      definition,
      request.capabilities
    );
    if (missingCapabilities.length > 0) {
      return fallbackResponse(
        request,
        definition,
        providerName,
        "capability_denied",
        `Missing capabilities: ${missingCapabilities.join(", ")}`,
        traceEvents
      );
    }

    let provider;
    try {
      provider = this.providers.resolve(providerName);
    } catch (error) {
      const detail =
        error instanceof Error ? error.message : "Provider registry lookup failed.";
      return fallbackResponse(
        request,
        definition,
        providerName,
        "provider_unavailable",
        detail,
        traceEvents
      );
    }

    try {
      const providerResult = await provider.run({
        requestID: request.requestID,
        prompt: request.prompt,
        specialist: definition.kind,
        capabilities: request.capabilities,
        outputMode: request.outputMode ?? "json",
        context: request.context ?? {},
        metadata: request.metadata ?? {}
      });

      const structuredOutput = validateSpecialistStructuredOutput(
        definition,
        providerResult.structuredOutput
      );

      return {
        requestID: request.requestID,
        specialist: definition.kind,
        provider: provider.name,
        providerEvidence:
          providerResult.providerEvidence ?? {
            provider: provider.name,
            status: "success",
            runtime: provider.name,
            detail: "Provider completed successfully.",
            model: providerResult.model
          },
        responseText: providerResult.responseText,
        structuredOutput,
        writeProposals: structuredOutput.writeProposals ?? [],
        traceEvents: [...traceEvents, ...(providerResult.traceEvents ?? [])],
        failed: false,
        usage: providerResult.usage ?? {},
        model: providerResult.model
      };
    } catch (error) {
      const reason: FallbackReason =
        error instanceof ProviderUnavailableError
          ? "provider_unavailable"
          : error instanceof CodexProviderError
            ? error.code === "missing_cli" || error.code === "timeout"
              ? "provider_unavailable"
              : "provider_failed"
            : error instanceof Error && error.message.includes("Expected")
              ? "validation_failed"
              : error instanceof Error && error.message.includes("does not allow actionType")
                ? "validation_failed"
                : error instanceof Error && error.message.includes("Write proposal")
                  ? "validation_failed"
                  : "provider_failed";
      const detail =
        error instanceof Error ? error.message : "Unknown provider failure.";
      return fallbackResponse(
        request,
        definition,
        providerName,
        reason,
        detail,
        traceEvents
      );
    }
  }
}

import type {
  AssistantRequest,
  AssistantResponse
} from "../agents/contracts.js";
import {
  AssistantOrchestrator,
  type AssistantOrchestratorOptions
} from "../agents/orchestrator.js";

export async function executeAssistantRequest(
  request: AssistantRequest,
  options: AssistantOrchestratorOptions = {}
): Promise<AssistantResponse> {
  const orchestrator = new AssistantOrchestrator(options);
  return orchestrator.handle(request);
}

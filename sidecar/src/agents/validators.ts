import type {
  AssistantRequest,
  AssistantWriteProposal,
  SpecialistStructuredOutput
} from "./contracts.js";
import type { SpecialistDefinition } from "./specialists.js";

function assertRecord(value: unknown, field: string): asserts value is Record<string, unknown> {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    throw new Error(`Expected object for ${field}.`);
  }
}

function assertVerificationStatus(
  value: unknown
): asserts value is "draft" | "validated" | "failed" {
  if (value !== "draft" && value !== "validated" && value !== "failed") {
    throw new Error("Write proposal verificationStatus is invalid.");
  }
}

function validateWriteProposal(
  proposal: unknown,
  definition: SpecialistDefinition
): AssistantWriteProposal {
  assertRecord(proposal, "writeProposal");
  const actionType = proposal.actionType;
  if (typeof actionType !== "string") {
    throw new Error("Expected string actionType in write proposal.");
  }
  if (!definition.allowedActionTypes.includes(actionType)) {
    throw new Error(
      `${definition.kind} does not allow actionType ${actionType}.`
    );
  }
  if (typeof proposal.targetTable !== "string" || typeof proposal.targetID !== "string") {
    throw new Error("Expected write proposal targetTable and targetID.");
  }
  if (
    typeof proposal.previewText !== "string" ||
    typeof proposal.rationale !== "string" ||
    typeof proposal.confidence !== "number" ||
    typeof proposal.requiresConfirmation !== "boolean"
  ) {
    throw new Error("Write proposal metadata is incomplete.");
  }
  assertVerificationStatus(proposal.verificationStatus);
  assertRecord(proposal.payload, "writeProposal.payload");
  for (const [key, value] of Object.entries(proposal.payload)) {
    if (typeof value !== "string") {
      throw new Error(`Write proposal payload field ${key} must be a string.`);
    }
  }
  return {
    actionType,
    targetTable: proposal.targetTable,
    targetID: proposal.targetID,
    previewText: proposal.previewText,
    rationale: proposal.rationale,
    confidence: proposal.confidence,
    requiresConfirmation: proposal.requiresConfirmation,
    verificationStatus: proposal.verificationStatus,
    payload: proposal.payload as Record<string, string>
  };
}

export function validateAssistantRequest(request: AssistantRequest): void {
  if (typeof request.requestID !== "string" || request.requestID.trim().length === 0) {
    throw new Error("Assistant request requires requestID.");
  }
  if (typeof request.prompt !== "string" || request.prompt.trim().length === 0) {
    throw new Error("Assistant request requires prompt.");
  }
  if (!Array.isArray(request.capabilities) || request.capabilities.length === 0) {
    throw new Error("Assistant request requires at least one capability.");
  }
}

export function validateSpecialistStructuredOutput(
  definition: SpecialistDefinition,
  payload: unknown
): SpecialistStructuredOutput {
  assertRecord(payload, "structuredOutput");
  const structuredOutput = payload as SpecialistStructuredOutput;
  definition.validate(structuredOutput);

  const validatedProposals = Array.isArray(structuredOutput.writeProposals)
    ? structuredOutput.writeProposals.map((proposal) =>
        validateWriteProposal(proposal, definition)
      )
    : [];

  return {
    ...structuredOutput,
    writeProposals: validatedProposals
  };
}

export function ensureCapabilities(
  definition: SpecialistDefinition,
  capabilities: string[]
): string[] {
  return definition.requiredCapabilities.filter(
    (capability) => !capabilities.includes(capability)
  );
}

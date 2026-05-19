export type MutationVerificationStatus =
  | "draft"
  | "validated"
  | "executed"
  | "skipped";

export interface MutationProposal {
  actionType: string;
  targetTable: string;
  targetID: string;
  previewText: string;
  rationale: string;
  confidence: number;
  requiresConfirmation: boolean;
  verificationStatus: MutationVerificationStatus;
  idempotencyKey?: string;
  payload: Record<string, string>;
}

export interface MutationBatchResult {
  batchID: string;
  executed: boolean;
  skippedReason?: string;
}

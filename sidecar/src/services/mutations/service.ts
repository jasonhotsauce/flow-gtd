import type { DatabaseSync } from "node:sqlite";
import type {
  MutationBatchResult,
  MutationProposal
} from "../../domain/mutations.js";

function nowIso(): string {
  return new Date().toISOString();
}

function stableStringify(payload: Record<string, string>): string {
  return JSON.stringify(
    Object.keys(payload)
      .sort()
      .reduce<Record<string, string>>((result, key) => {
        result[key] = payload[key];
        return result;
      }, {})
  );
}

export class MutationService {
  constructor(private readonly db: DatabaseSync) {}

  executeProposal(
    source: string,
    proposal: MutationProposal,
    apply: (batchID: string) => void
  ): MutationBatchResult {
    const payloadWithMetadata: Record<string, string> = {
      ...proposal.payload,
      actionType: proposal.actionType,
      previewText: proposal.previewText,
      rationale: proposal.rationale,
      confidence: proposal.confidence.toString(),
      requiresConfirmation: proposal.requiresConfirmation ? "true" : "false",
      verificationStatus: proposal.verificationStatus
    };
    if (proposal.idempotencyKey) {
      payloadWithMetadata.idempotencyKey = proposal.idempotencyKey;
    }

    const payloadJSON = stableStringify(payloadWithMetadata);
    if (proposal.idempotencyKey && this.hasExistingExecution(source, proposal)) {
      return {
        batchID: "",
        executed: false,
        skippedReason: "idempotent_replay"
      };
    }

    const batchID = crypto.randomUUID();
    const createdAt = nowIso();

    this.db.exec("BEGIN");
    try {
      this.insertMutationBatch(
        batchID,
        source,
        proposal.requiresConfirmation,
        createdAt
      );
      apply(batchID);
      this.insertMutationRecord(
        batchID,
        proposal.targetTable,
        proposal.targetID,
        proposal.actionType,
        payloadJSON,
        createdAt
      );
      this.db.exec("COMMIT");
      return {
        batchID,
        executed: true
      };
    } catch (error) {
      this.db.exec("ROLLBACK");
      throw error;
    }
  }

  private hasExistingExecution(
    source: string,
    proposal: MutationProposal
  ): boolean {
    if (!proposal.idempotencyKey) {
      return false;
    }

    const row = this.db
      .prepare(
        `
          SELECT mr.id
          FROM mutation_records mr
          JOIN mutation_batches mb ON mb.id = mr.batch_id
          WHERE mb.source = ?
            AND mr.target_table = ?
            AND mr.target_id = ?
            AND mr.action = ?
            AND COALESCE(json_extract(mr.payload_json, '$.idempotencyKey'), '') = ?
          LIMIT 1
        `
      )
      .get(
        source,
        proposal.targetTable,
        proposal.targetID,
        proposal.actionType,
        proposal.idempotencyKey
      ) as { id?: string } | undefined;

    return Boolean(row?.id);
  }

  private insertMutationBatch(
    batchID: string,
    source: string,
    requiresConfirmation: boolean,
    createdAt: string
  ): void {
    this.db
      .prepare(
        `
          INSERT INTO mutation_batches (id, source, requires_confirmation, created_at)
          VALUES (?, ?, ?, ?)
        `
      )
      .run(batchID, source, requiresConfirmation ? 1 : 0, createdAt);
  }

  private insertMutationRecord(
    batchID: string,
    targetTable: string,
    targetID: string,
    action: string,
    payloadJSON: string,
    createdAt: string
  ): void {
    this.db
      .prepare(
        `
          INSERT INTO mutation_records (
            id, batch_id, target_table, target_id, action, payload_json, created_at
          ) VALUES (?, ?, ?, ?, ?, ?, ?)
        `
      )
      .run(
        crypto.randomUUID(),
        batchID,
        targetTable,
        targetID,
        action,
        payloadJSON,
        createdAt
      );
  }
}

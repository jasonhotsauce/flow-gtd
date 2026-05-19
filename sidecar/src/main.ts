import { fileURLToPath } from "node:url";
import {
  createSidecarServer,
  type SidecarReadyEvent
} from "./ipc/server.js";
import {
  PROTOCOL_VERSION,
  type HealthCheckResponse
} from "./ipc/protocol.js";
import {
  createHealthCheckRequest,
  handleHealthCheck
} from "./ipc/messages/health.js";
import { executeRead, type SidecarReadKind } from "./services/read-service.js";
import { executeWrite, type SidecarWriteKind } from "./services/write-service.js";
import { executeAssistantRequest } from "./services/assistant-service.js";
import type { AssistantRequest } from "./agents/contracts.js";
import {
  createProviderRegistry,
  type AssistantProviderAdapter
} from "./agents/providers.js";
import { bootstrapFlowDatabase } from "./db/database.js";
import { AssistantTurnService } from "./services/assistant-turn-service.js";

export interface WritableLike {
  write(chunk: string): boolean;
}

export interface RunSidecarOptions {
  args?: string[];
  stdout?: WritableLike;
  providerAdapters?: AssistantProviderAdapter[];
}

const SIDECAR_VERSION = "0.1.0";

function formatReadyEvent(event: SidecarReadyEvent): string {
  return `${JSON.stringify(event)}\n`;
}

function formatHealthCheckResponse(response: HealthCheckResponse): string {
  return `${JSON.stringify(response)}\n`;
}

function readOptionValue(args: string[], option: string): string | undefined {
  const inline = args.find((arg) => arg.startsWith(`${option}=`));
  if (inline) {
    return inline.slice(option.length + 1);
  }

  const index = args.indexOf(option);
  if (index >= 0 && index + 1 < args.length) {
    return args[index + 1];
  }

  return undefined;
}

function parseBooleanOption(args: string[], option: string): boolean | undefined {
  const value = readOptionValue(args, option);
  if (value === undefined) {
    return undefined;
  }
  return value === "1" || value.toLowerCase() === "true";
}

export async function runSidecar(
  options: RunSidecarOptions = {}
): Promise<number> {
  const args = options.args ?? [];
  const stdout = options.stdout ?? process.stdout;
  const once = args.includes("--once");
  const healthCheck = args.includes("--health-check");
  const readMode = readOptionValue(args, "--read") as SidecarReadKind | undefined;
  const writeMode = readOptionValue(args, "--write") as SidecarWriteKind | undefined;
  const assistantRequestJSON = readOptionValue(args, "--assistant-request");
  const assistantMode = readOptionValue(args, "--assistant-mode");

  if (healthCheck) {
    const requestedProtocolVersion =
      readOptionValue(args, "--protocol-version") ?? PROTOCOL_VERSION;
    const response = handleHealthCheck(
      createHealthCheckRequest({
        id:
          requestedProtocolVersion === PROTOCOL_VERSION
            ? "health-check-1"
            : "health-check-2",
        protocolVersion: requestedProtocolVersion
      }),
      {
        sidecarVersion: SIDECAR_VERSION
      }
    );
    stdout.write(formatHealthCheckResponse(response));
    return 0;
  }

  if (readMode) {
    const result = executeRead({
      kind: readMode,
      planDate: readOptionValue(args, "--plan-date"),
      limit: Number(readOptionValue(args, "--limit") ?? "30"),
      sessionID: readOptionValue(args, "--session-id"),
      query: readOptionValue(args, "--query"),
      includeDisabled: parseBooleanOption(args, "--include-disabled"),
      referenceDate: readOptionValue(args, "--reference-date")
    });
    stdout.write(`${JSON.stringify(result)}\n`);
    return 0;
  }

  if (writeMode) {
    const payloadBase64 = readOptionValue(args, "--payload-base64");
    const payload = payloadBase64
      ? (JSON.parse(Buffer.from(payloadBase64, "base64").toString("utf8")) as Record<
          string,
          unknown
        >)
      : {};
    const result = await executeWrite({
      kind: writeMode,
      payload
    });
    stdout.write(`${JSON.stringify(result)}\n`);
    return 0;
  }

  if (assistantRequestJSON) {
    const request = JSON.parse(assistantRequestJSON) as AssistantRequest;
    const result = await executeAssistantRequest(request, {
      providers: options.providerAdapters
        ? createProviderRegistry(options.providerAdapters)
        : undefined
    });
    stdout.write(`${JSON.stringify(result)}\n`);
    return 0;
  }

  if (assistantMode) {
    const payloadBase64 = readOptionValue(args, "--payload-base64");
    const payload = payloadBase64
      ? (JSON.parse(Buffer.from(payloadBase64, "base64").toString("utf8")) as Record<
          string,
          unknown
        >)
      : {};
    const owner = bootstrapFlowDatabase(process.env.FLOW_DB_PATH || undefined);
    try {
      const service = new AssistantTurnService(owner.connection());
      let result: unknown;
      switch (assistantMode) {
        case "send-prompt":
          result = await service.sendPrompt(
            String(payload.prompt ?? ""),
            String(payload.planDate ?? "")
          );
          break;
        case "project-next-action-review":
          result = await service.proposeProjectNextActionReview(
            String(payload.projectID ?? "")
          );
          break;
        case "confirm-proposal":
          result = { message: service.confirmProposal(String(payload.turnID ?? "")) };
          break;
        case "dismiss-proposal":
          service.dismissProposal(String(payload.turnID ?? ""));
          result = { ok: true };
          break;
        case "undo-last-mutation":
          result = { message: service.undoLastMutation() ?? null };
          break;
        default:
          throw new Error(`Unknown assistant mode ${assistantMode}.`);
      }
      stdout.write(`${JSON.stringify(result)}\n`);
      return 0;
    } finally {
      owner.close();
    }
  }

  const server = createSidecarServer({
    once,
    version: SIDECAR_VERSION
  });

  const readyEvent = await server.start();
  stdout.write(formatReadyEvent(readyEvent));
  await server.stop();

  return 0;
}

async function main(): Promise<void> {
  process.exitCode = await runSidecar({
    args: process.argv.slice(2)
  });
}

const currentFile = fileURLToPath(import.meta.url);

if (process.argv[1] === currentFile) {
  void main();
}

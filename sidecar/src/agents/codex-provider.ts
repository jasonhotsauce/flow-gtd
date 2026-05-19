import { existsSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { spawnSync, type SpawnSyncOptionsWithStringEncoding, type SpawnSyncReturns } from "node:child_process";
import type {
  AssistantProviderAdapter
} from "./providers.js";
import type {
  ProviderEvidence,
  ProviderRunRequest,
  ProviderRunResult,
  SpecialistStructuredOutput,
  TraceEvent
} from "./contracts.js";

export type CodexProviderErrorCode =
  | "missing_cli"
  | "timeout"
  | "runtime_failure"
  | "invalid_output"
  | "schema_mismatch";

export class CodexProviderError extends Error {
  constructor(
    public readonly code: CodexProviderErrorCode,
    message: string,
    public readonly detail?: string
  ) {
    super(message);
    this.name = "CodexProviderError";
  }
}

export interface CodexProviderAdapterOptions {
  codexBinary?: string;
  commandRunner?: (
    command: string,
    args: string[],
    options: SpawnSyncOptionsWithStringEncoding
  ) => SpawnSyncReturns<string>;
  timeoutMs?: number;
}

interface CodexProviderResponse {
  responseText: string;
  structuredOutput: SpecialistStructuredOutput;
  usage?: Record<string, unknown>;
  model?: string;
}

function resolveCodexBinary(explicit?: string): string {
  if (explicit && explicit.trim().length > 0) {
    return explicit.trim();
  }

  const configured = process.env.FLOW_CODEX_BIN?.trim() ?? process.env.CODEX_BINARY?.trim();
  if (configured) {
    return configured;
  }

  const homebrewBinary = "/opt/homebrew/bin/codex";
  if (existsSync(homebrewBinary)) {
    return homebrewBinary;
  }

  return "codex";
}

function resolveCodexWorkingDirectory(): string {
  const configured = process.env.FLOW_CODEX_CWD?.trim();
  if (configured) {
    return configured;
  }
  return process.cwd();
}

function resolveCodexModel(): string | undefined {
  const configured = process.env.FLOW_CODEX_MODEL?.trim();
  return configured ? configured : undefined;
}

function buildAssistantPrompt(request: ProviderRunRequest): string {
  return [
    "You are the Codex-backed provider for the Flow GTD sidecar runtime.",
    "Return only data that matches the provided JSON schema.",
    "Do not call external tools, do not edit files, and do not ask follow-up questions.",
    "Use context.agentTools as the available Flow tool contract. For writes, return confirmation-gated writeProposals instead of executing the tool directly.",
    "The JSON object must contain:",
    "- responseText: string",
    "- structuredOutput: object that matches the requested specialist contract",
    "",
    `Specialist: ${request.specialist}`,
    `Assistant output mode: ${request.outputMode}`,
    `Capabilities: ${request.capabilities.join(", ")}`,
    `Request ID: ${request.requestID}`,
    "",
    `Prompt: ${request.prompt}`,
    "",
    specialistInstructions(request),
    "",
    `Context: ${JSON.stringify(request.context)}`,
    `Metadata: ${JSON.stringify(request.metadata)}`
  ].join("\n");
}

function specialistInstructions(request: ProviderRunRequest): string {
  switch (request.specialist) {
    case "daily_planner":
      return [
        "Daily planner requirements:",
        "- Keep the response grounded in the provided dailyPlanState only.",
        "- Consider dailyPlanState.mustAddress, readyActions, projectTasks, and inbox when no confirmed plan exists.",
        "- If context.agentTools is present, use it to describe or propose bounded plan, project, and task CRUD actions.",
        "- structuredOutput.focusItems must contain at least one bounded focus item.",
        "- structuredOutput.risks must be an array of concise strings.",
        "- structuredOutput.writeProposals must be an array; use [] when no confirmation-gated write is needed.",
        "- If returning a write proposal payload, include every payload field from the schema and set unused fields to an empty string."
      ].join("\n");
    case "weekly_reviewer":
      return [
        "Weekly reviewer requirements:",
        "- Summarize the current review package only.",
        "- structuredOutput.cleanupCandidates must be a bounded array of candidate ids/titles.",
        "- Do not invent writes unless they are represented as bounded proposals."
      ].join("\n");
    case "project_health_analyst":
      return [
        "Project health requirements:",
        "- Use the provided project and suggestedTitle context.",
        "- Return exactly one bounded planning proposal in structuredOutput.writeProposals.",
        "- The proposal actionType must be create_task and requiresConfirmation must be true.",
        "- The proposal payload must contain only string values."
      ].join("\n");
    default:
      return "General assistant requirements: stay grounded in provided context and keep outputs bounded.";
  }
}

function outputSchemaForSpecialist(
  specialist: ProviderRunRequest["specialist"]
): Record<string, unknown> {
  const genericWriteProposalSchema = {
    type: "array",
    items: {
      type: "object",
      additionalProperties: false,
      properties: {
        actionType: { type: "string" },
        targetTable: { type: "string" },
        targetID: { type: "string" },
        previewText: { type: "string" },
        rationale: { type: "string" },
        confidence: { type: "number" },
        requiresConfirmation: { type: "boolean", const: true },
        verificationStatus: { type: "string", enum: ["draft", "validated", "failed"] },
        payload: {
          type: "object",
          additionalProperties: false,
          properties: {
            planDate: { type: "string" },
            topItemIDs: { type: "string" },
            bonusItemIDs: { type: "string" },
            title: { type: "string" },
            project_id: { type: "string" },
            project_title: { type: "string" },
            id: { type: "string" },
            status: { type: "string" },
            dueDate: { type: "string" },
            estimatedMinutes: { type: "string" }
          },
          required: [
            "planDate",
            "topItemIDs",
            "bonusItemIDs",
            "title",
            "project_id",
            "project_title",
            "id",
            "status",
            "dueDate",
            "estimatedMinutes"
          ]
        }
      },
      required: [
        "actionType",
        "targetTable",
        "targetID",
        "previewText",
        "rationale",
        "confidence",
        "requiresConfirmation",
        "verificationStatus",
        "payload"
      ]
    }
  };
  const baseStructuredOutput: {
    type: string;
    additionalProperties: boolean;
    properties: Record<string, unknown>;
    required: string[];
  } = {
    type: "object",
    additionalProperties: false,
    properties: {
      kind: { type: "string", const: specialist },
      summary: { type: "string" },
      rationale: {
        type: "array",
        items: { type: "string" }
      }
    },
    required: ["kind", "summary", "rationale"]
  };

  const structuredOutput = (() => {
    switch (specialist) {
      case "daily_planner":
        return {
          ...baseStructuredOutput,
          properties: {
            ...baseStructuredOutput.properties,
            focusItems: {
              type: "array",
              minItems: 1,
              items: {
                type: "object",
                additionalProperties: false,
                properties: {
                  title: { type: "string" },
                  energy: { type: "string" },
                  reason: { type: "string" }
                },
                required: ["title", "energy", "reason"]
              }
            },
            risks: {
              type: "array",
              items: { type: "string" }
            },
            writeProposals: genericWriteProposalSchema
          },
          required: ["kind", "summary", "rationale", "focusItems", "risks", "writeProposals"]
        };
      case "weekly_reviewer":
        return {
          ...baseStructuredOutput,
          properties: {
            ...baseStructuredOutput.properties,
            cleanupCandidates: {
              type: "array",
              items: {
                type: "object",
                additionalProperties: false,
                properties: {
                  id: { type: "string" },
                  title: { type: "string" }
                },
                required: ["id", "title"]
              }
            }
          },
          required: ["kind", "summary", "rationale", "cleanupCandidates"]
        };
      case "project_health_analyst":
        return {
          ...baseStructuredOutput,
          properties: {
            ...baseStructuredOutput.properties,
            projects: {
              type: "array",
              minItems: 1,
              items: {
                type: "object",
                additionalProperties: false,
                properties: {
                  id: { type: "string" },
                  title: { type: "string" },
                  suggestedTitle: { type: "string" }
                },
                required: ["id", "title", "suggestedTitle"]
              }
            },
            writeProposals: {
              type: "array",
              minItems: 1,
              maxItems: 1,
              items: {
                type: "object",
                additionalProperties: false,
                properties: {
                  actionType: { type: "string", const: "create_task" },
                  targetTable: { type: "string" },
                  targetID: { type: "string" },
                  previewText: { type: "string" },
                  rationale: { type: "string" },
                  confidence: { type: "number" },
                  requiresConfirmation: { type: "boolean", const: true },
                  verificationStatus: { type: "string", enum: ["draft", "validated", "failed"] },
                  payload: {
                    type: "object",
                    additionalProperties: false,
                    properties: {
                      title: { type: "string" },
                      project_id: { type: "string" },
                      project_title: { type: "string" }
                    },
                    required: ["title", "project_id", "project_title"]
                  }
                },
                required: [
                  "actionType",
                  "targetTable",
                  "targetID",
                  "previewText",
                  "rationale",
                  "confidence",
                  "requiresConfirmation",
                  "verificationStatus",
                  "payload"
                ]
              }
            }
          },
          required: ["kind", "summary", "rationale", "projects", "writeProposals"]
        };
      default:
        return baseStructuredOutput;
    }
  })();

  return {
    type: "object",
    additionalProperties: false,
    properties: {
      responseText: { type: "string" },
      structuredOutput
    },
    required: ["responseText", "structuredOutput"]
  };
}

function stripJsonFences(value: string): string {
  const trimmed = value.trim();
  if (trimmed.startsWith("```")) {
    return trimmed
      .replace(/^```(?:json)?/i, "")
      .replace(/```$/, "")
      .trim();
  }
  return trimmed;
}

function parseResponseJSON(rawText: string): CodexProviderResponse {
  const trimmed = stripJsonFences(rawText);
  if (!trimmed) {
    throw new CodexProviderError(
      "invalid_output",
      "Codex did not return any output.",
      rawText
    );
  }

  const attempts = [trimmed];
  const start = trimmed.indexOf("{");
  const end = trimmed.lastIndexOf("}");
  if (start >= 0 && end > start) {
    attempts.push(trimmed.slice(start, end + 1));
  }

  let parsed: unknown;
  for (const attempt of attempts) {
    try {
      parsed = JSON.parse(attempt);
      break;
    } catch {
      continue;
    }
  }

  if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
    throw new CodexProviderError(
      "invalid_output",
      "Codex output was not valid JSON.",
      rawText
    );
  }

  const response = parsed as Record<string, unknown>;
  if (typeof response.responseText !== "string") {
    throw new CodexProviderError(
      "schema_mismatch",
      "Codex output is missing responseText.",
      rawText
    );
  }
  if (
    !response.structuredOutput ||
    typeof response.structuredOutput !== "object" ||
    Array.isArray(response.structuredOutput)
  ) {
    throw new CodexProviderError(
      "schema_mismatch",
      "Codex output is missing structuredOutput.",
      rawText
    );
  }

  return {
    responseText: response.responseText,
    structuredOutput: response.structuredOutput as SpecialistStructuredOutput,
    usage:
      response.usage && typeof response.usage === "object" && !Array.isArray(response.usage)
        ? (response.usage as Record<string, unknown>)
        : undefined,
    model: typeof response.model === "string" ? response.model : undefined
  };
}

function commandSummary(binary: string, args: string[]): string {
  return [binary, ...args.filter((arg) => arg !== "-")].join(" ");
}

function codexTraceEvent(
  request: ProviderRunRequest,
  status: ProviderEvidence["status"],
  detail: string,
  model?: string,
  command?: string
): TraceEvent {
  return {
    stage: "provider",
    summary: detail,
    provider: "codex",
    payload: {
      provider: "codex",
      provider_status: status,
      provider_runtime: "codex exec",
      provider_detail: detail,
      provider_model: model ?? "",
      provider_command: command ?? "",
      specialist: request.specialist
    }
  };
}

function runCodexCommand(
  commandRunner: NonNullable<CodexProviderAdapterOptions["commandRunner"]>,
  binary: string,
  request: ProviderRunRequest,
  timeoutMs: number,
  model?: string
): CodexProviderResponse {
  const tempDir = mkdtempSync(join(tmpdir(), "flow-codex-provider-"));
  const outputFile = join(tempDir, "last-message.json");
  const schemaFile = join(tempDir, "output-schema.json");
  const workingDirectory = resolveCodexWorkingDirectory();
  const prompt = buildAssistantPrompt(request);
  writeFileSync(
    schemaFile,
    JSON.stringify(outputSchemaForSpecialist(request.specialist))
  );
  const args = [
    "exec",
    "--skip-git-repo-check",
    "--ephemeral",
    "--ignore-user-config",
    "--ignore-rules",
    "--disable",
    "codex_hooks",
    "--sandbox",
    "read-only",
    "--cd",
    workingDirectory,
    "--output-schema",
    schemaFile,
    "--output-last-message",
    outputFile
  ];
  if (model) {
    args.push("--model", model);
  }
  args.push("-");

  try {
    const result = commandRunner(binary, args, {
      cwd: workingDirectory,
      encoding: "utf8",
      timeout: timeoutMs,
      input: prompt
    });

    if (result.error) {
      if ((result.error as NodeJS.ErrnoException).code === "ENOENT") {
        throw new CodexProviderError(
          "missing_cli",
          `Unable to locate Codex binary: ${binary}.`,
          String(result.error)
        );
      }
      if ((result.error as NodeJS.ErrnoException).code === "ETIMEDOUT") {
        throw new CodexProviderError(
          "timeout",
          `Codex timed out after ${timeoutMs}ms.`,
          String(result.error)
        );
      }
      throw new CodexProviderError(
        "runtime_failure",
        "Codex execution failed before completion.",
        String(result.error)
      );
    }

    if (result.signal || result.status !== 0) {
      const stderr = typeof result.stderr === "string" ? result.stderr.trim() : "";
      const detail = stderr || `Codex exited with status ${result.status ?? "unknown"}.`;
      const code: CodexProviderErrorCode = /timeout/i.test(detail)
        ? "timeout"
        : "runtime_failure";
      throw new CodexProviderError(code, detail, detail);
    }

    try {
      const rawOutput = readFileSync(outputFile, "utf8");
      return parseResponseJSON(rawOutput);
    } catch (error) {
      throw new CodexProviderError(
        "invalid_output",
        "Codex did not produce a readable last message.",
        error instanceof Error ? error.message : String(error)
      );
    }
  } finally {
    rmSync(tempDir, { recursive: true, force: true });
  }
}

export function createCodexProvider(
  options: CodexProviderAdapterOptions = {}
): AssistantProviderAdapter {
  const commandRunner = options.commandRunner ?? spawnSync;
  const binary = resolveCodexBinary(options.codexBinary);
  const timeoutMs = options.timeoutMs ?? 120_000;
  const model = resolveCodexModel();

  return {
    name: "codex",
    async run(request: ProviderRunRequest): Promise<ProviderRunResult> {
      const response = runCodexCommand(commandRunner, binary, request, timeoutMs, model);
      const command = commandSummary(binary, [
        "exec",
        "--skip-git-repo-check",
        "--ephemeral",
        "--ignore-user-config",
        "--ignore-rules",
        "--disable",
        "codex_hooks",
        "--sandbox",
        "read-only",
        "--cd",
        resolveCodexWorkingDirectory(),
        "--output-schema",
        "<output-schema.json>",
        "--output-last-message",
        "<last-message.json>"
      ]);
      return {
        responseText: response.responseText,
        structuredOutput: response.structuredOutput,
        usage: response.usage,
        model: response.model,
        providerEvidence: {
          provider: "codex",
          status: "success",
          runtime: "codex exec",
          detail: "Codex completed successfully.",
          model: response.model ?? model,
          command
        },
        traceEvents: [
          codexTraceEvent(
            request,
            "success",
            "Codex completed successfully.",
            response.model ?? model,
            command
          )
        ]
      };
    }
  };
}

import type { AssistantWriteProposal, ProviderRunRequest, ProviderRunResult } from "./contracts.js";
import type { AssistantProviderAdapter } from "./providers.js";

function extractCaptureTitle(prompt: string): string {
  const lowered = prompt.toLowerCase();
  if (lowered.startsWith("remind me to ")) {
    return prompt.slice("remind me to ".length).trim();
  }
  for (const prefix of ["add ", "capture ", "todo "]) {
    if (lowered.startsWith(prefix)) {
      return prompt.slice(prefix.length).trim();
    }
  }
  return prompt.trim();
}

function extractMemoryValue(prompt: string): string {
  const lowered = prompt.toLowerCase();
  if (lowered.startsWith("remember that ")) {
    return prompt.slice("remember that ".length).trim();
  }
  if (lowered.startsWith("remember ")) {
    return prompt.slice("remember ".length).trim();
  }
  return prompt.trim();
}

function proposal(input: {
  actionType: string;
  targetTable: string;
  targetID: string;
  previewText: string;
  rationale: string;
  confidence: number;
  payload: Record<string, string>;
}): AssistantWriteProposal {
  return {
    ...input,
    requiresConfirmation: true,
    verificationStatus: "validated"
  };
}

function evidence(detail: string): ProviderRunResult["providerEvidence"] {
  return {
    provider: "deterministic",
    status: "success",
    runtime: "deterministic",
    detail
  };
}

export function createDeterministicProvider(): AssistantProviderAdapter {
  return {
    name: "deterministic",
    run(request: ProviderRunRequest): ProviderRunResult {
      switch (request.specialist) {
        case "capture_clarifier": {
          const title = extractCaptureTitle(request.prompt);
          return {
            responseText: `I can add this to Inbox: ${title}`,
            structuredOutput: {
              kind: "capture_clarifier",
              summary: "Prepared a confirmation-gated inbox capture.",
              rationale: ["User asked Flow to capture work into the system."],
              clarifications: [{ title }],
              writeProposals: [
                proposal({
                  actionType: "create_task",
                  targetTable: "items",
                  targetID: request.requestID,
                  previewText: `Create inbox item: ${title}`,
                  rationale: "User asked Flow to capture a task-like item.",
                  confidence: 0.95,
                  payload: { title }
                })
              ]
            },
            traceEvents: [{
              stage: "provider",
              summary: "Prepared deterministic capture proposal.",
              provider: "deterministic",
              payload: {
                provider: "deterministic",
                provider_status: "success",
                provider_runtime: "deterministic",
                provider_detail: "Prepared deterministic capture proposal."
              }
            }]
            ,
            providerEvidence: evidence("Prepared deterministic capture proposal.")
          };
        }
        case "memory_curator": {
          const value = extractMemoryValue(request.prompt);
          return {
            responseText: `I can save this as a preference memory: ${value}`,
            structuredOutput: {
              kind: "memory_curator",
              summary: "Prepared an explicit preference memory.",
              rationale: ["User made an explicit preference statement."],
              memoryCandidates: [{ value }],
              writeProposals: [
                proposal({
                  actionType: "save_memory",
                  targetTable: "memory_entries",
                  targetID: request.requestID,
                  previewText: `Remember preference: ${value}`,
                  rationale: "User made an explicit preference statement.",
                  confidence: 1.0,
                  payload: {
                    kind: "explicit_preference",
                    scope: "global",
                    value,
                    source: "assistant-chat",
                    confidence: "1.0"
                  }
                })
              ]
            },
            traceEvents: [{
              stage: "provider",
              summary: "Prepared deterministic memory proposal.",
              provider: "deterministic",
              payload: {
                provider: "deterministic",
                provider_status: "success",
                provider_runtime: "deterministic",
                provider_detail: "Prepared deterministic memory proposal."
              }
            }]
            ,
            providerEvidence: evidence("Prepared deterministic memory proposal.")
          };
        }
        case "daily_planner": {
          const state = (request.context.dailyPlanState ?? {}) as Record<string, unknown>;
          const topItems = Array.isArray(state.topItems) ? state.topItems : [];
          const bonusItems = Array.isArray(state.bonusItems) ? state.bonusItems : [];
          const mustAddress = Array.isArray(state.mustAddress) ? state.mustAddress : [];
          const readyActions = Array.isArray(state.readyActions) ? state.readyActions : [];
          const projectTasks = Array.isArray(state.projectTasks) ? state.projectTasks : [];
          const inboxItems = Array.isArray(state.inbox) ? state.inbox : [];
          const plannedItems = [...topItems, ...bonusItems];
          const availableCandidates = [
            ...mustAddress,
            ...readyActions,
            ...projectTasks,
            ...inboxItems
          ];
          const focusItems = plannedItems.map((item) => ({
            title: String((item as Record<string, unknown>).title ?? "Focus item"),
            energy: "high",
            reason: "Already selected in the current daily plan."
          }));
          if (focusItems.length === 0) {
            const candidate = availableCandidates[0] as Record<string, unknown> | undefined;
            focusItems.push({
              title: candidate
                ? String(candidate.title ?? "Pick the next available task")
                : "Clarify the inbox",
              energy: "medium",
              reason: candidate
                ? "No confirmed plan exists yet, so this available candidate can anchor today's plan."
                : "No confirmed plan exists yet."
            });
          }
          const planDate = String(state.planDate ?? "today");
          const candidateTitles = availableCandidates
            .slice(0, 5)
            .map((item) => String((item as Record<string, unknown>).title ?? "Untitled"))
            .filter((title) => title.trim().length > 0);
          const responseText =
            plannedItems.length > 0
              ? `Your plan for ${planDate} includes: ${plannedItems.map((item) => String((item as Record<string, unknown>).title ?? "Untitled")).join("; ")}`
              : candidateTitles.length > 0
                ? `You do not have a confirmed plan for ${planDate} yet. Available planning candidates include: ${candidateTitles.join("; ")}.`
                : `You do not have a confirmed plan for ${planDate} yet. No inbox, ready, or project-linked tasks are available to plan.`;
          return {
            responseText,
            structuredOutput: {
              kind: "daily_planner",
              summary: "Summarized the current daily planning state.",
              rationale: ["Used the current daily plan and unplanned candidate state already stored in Flow."],
              focusItems,
              risks: Array.isArray(state.riskFlags) ? state.riskFlags : []
            },
            traceEvents: [{
              stage: "provider",
              summary: "Prepared deterministic daily planning summary.",
              provider: "deterministic",
              payload: {
                provider: "deterministic",
                provider_status: "success",
                provider_runtime: "deterministic",
                provider_detail: "Prepared deterministic daily planning summary."
              }
            }]
            ,
            providerEvidence: evidence("Prepared deterministic daily planning summary.")
          };
        }
        case "weekly_reviewer": {
          const review = (request.context.weeklyReviewPackage ?? {}) as Record<string, unknown>;
          const staleItems = Array.isArray(review.staleItems) ? review.staleItems : [];
          const cleanupActions = Array.isArray(review.cleanupActions) ? review.cleanupActions : [];
          return {
            responseText: `Weekly review pressure is moderate: ${staleItems.length} stale items are currently available.`,
            structuredOutput: {
              kind: "weekly_reviewer",
              summary: "Summarized stale work and review pressure.",
              rationale: ["Used the weekly review package already stored in Flow."],
              cleanupCandidates: cleanupActions.map((action) => ({
                id: String((action as Record<string, unknown>).id ?? ""),
                title: String((action as Record<string, unknown>).title ?? "")
              }))
            },
            traceEvents: [{
              stage: "provider",
              summary: "Prepared deterministic weekly review summary.",
              provider: "deterministic",
              payload: {
                provider: "deterministic",
                provider_status: "success",
                provider_runtime: "deterministic",
                provider_detail: "Prepared deterministic weekly review summary."
              }
            }]
            ,
            providerEvidence: evidence("Prepared deterministic weekly review summary.")
          };
        }
        case "project_health_analyst": {
          const project = (request.context.project ?? {}) as Record<string, unknown>;
          const projectID = String(project.id ?? "");
          const projectTitle = String(project.title ?? "the project");
          const suggestedTitle = String(request.context.suggestedTitle ?? `Define the next concrete step for ${projectTitle}`);
          return {
            responseText: `I found a project in Review that needs a next action. I drafted one bounded next step for ${projectTitle} from the current local project context and left it pending for confirmation.`,
            structuredOutput: {
              kind: "project_health_analyst",
              summary: "Prepared one confirmation-gated project next-action draft from local project context.",
              rationale: ["The project has no current next action, so Review should propose one bounded next step."],
              projects: [{ id: projectID, title: projectTitle, suggestedTitle }],
              writeProposals: [
                proposal({
                  actionType: "create_task",
                  targetTable: "items",
                  targetID: projectID,
                  previewText: `Create next action in ${projectTitle}: ${suggestedTitle}`,
                  rationale: "This project has no current next action, so Review should propose one bounded next step.",
                  confidence: 0.86,
                  payload: {
                    title: suggestedTitle,
                    project_id: projectID,
                    project_title: projectTitle
                  }
                })
              ]
            },
            traceEvents: [{
              stage: "provider",
              summary: "Prepared deterministic project-health next action draft.",
              provider: "deterministic",
              payload: {
                provider: "deterministic",
                provider_status: "success",
                provider_runtime: "deterministic",
                provider_detail: "Prepared deterministic project-health next action draft."
              }
            }]
            ,
            providerEvidence: evidence("Prepared deterministic project-health next action draft.")
          };
        }
        default: {
          const inboxCount = Number(request.context.inboxCount ?? 0);
          const memoryCount = Number(request.context.memoryCount ?? 0);
          return {
            responseText: `I can help capture work, summarize today's plan, or save a preference. Right now you have ${inboxCount} inbox items and ${memoryCount} saved memories.`,
            structuredOutput: {
              kind: "assistant_orchestrator",
              summary: "Answered using the current GTD system summary.",
              rationale: ["Used stored workspace counts to generate a deterministic response."]
            },
            traceEvents: [{
              stage: "provider",
              summary: "Prepared deterministic general assistant response.",
              provider: "deterministic",
              payload: {
                provider: "deterministic",
                provider_status: "success",
                provider_runtime: "deterministic",
                provider_detail: "Prepared deterministic general assistant response."
              }
            }]
            ,
            providerEvidence: evidence("Prepared deterministic general assistant response.")
          };
        }
      }
    }
  };
}

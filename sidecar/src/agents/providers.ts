import type {
  ProviderName,
  ProviderRunRequest,
  ProviderRunResult
} from "./contracts.js";
import { createCodexProvider } from "./codex-provider.js";
import { createDeterministicProvider } from "./deterministic-provider.js";

export interface AssistantProviderAdapter {
  name: ProviderName;
  run(request: ProviderRunRequest): Promise<ProviderRunResult> | ProviderRunResult;
}

export class ProviderUnavailableError extends Error {
  constructor(
    public readonly providerName: ProviderName,
    message: string
  ) {
    super(message);
    this.name = "ProviderUnavailableError";
  }
}

class UnavailableProviderAdapter implements AssistantProviderAdapter {
  constructor(
    public readonly name: ProviderName,
    private readonly reason: string
  ) {}

  async run(_request: ProviderRunRequest): Promise<ProviderRunResult> {
    throw new ProviderUnavailableError(this.name, this.reason);
  }
}

export class ProviderRegistry {
  private readonly adapters = new Map<ProviderName, AssistantProviderAdapter>();

  constructor(adapters: AssistantProviderAdapter[]) {
    for (const adapter of adapters) {
      this.adapters.set(adapter.name, adapter);
    }
  }

  resolve(name: ProviderName): AssistantProviderAdapter {
    const adapter = this.adapters.get(name);
    if (!adapter) {
      throw new ProviderUnavailableError(
        name,
        `Provider ${name} is not registered in the sidecar runtime.`
      );
    }
    return adapter;
  }
}

export function createProviderRegistry(
  adapters: AssistantProviderAdapter[]
): ProviderRegistry {
  return new ProviderRegistry(adapters);
}

export function createDefaultProviderRegistry(): ProviderRegistry {
  return createProviderRegistry([
    createCodexProvider(),
    createDeterministicProvider(),
    new UnavailableProviderAdapter(
      "openai",
      "OpenAI provider adapter is staged but not configured in this phase."
    ),
    new UnavailableProviderAdapter(
      "anthropic",
      "Anthropic provider adapter is staged but not configured in this phase."
    )
  ]);
}

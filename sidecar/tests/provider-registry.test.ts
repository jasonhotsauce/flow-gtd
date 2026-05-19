import { describe, expect, it } from "vitest";
import { createDefaultProviderRegistry } from "../src/agents/providers.js";

describe("Provider registry", () => {
  it("resolves the Codex provider and keeps deterministic available explicitly", () => {
    const registry = createDefaultProviderRegistry();

    expect(registry.resolve("codex").name).toBe("codex");
    expect(registry.resolve("deterministic").name).toBe("deterministic");
  });
});

from __future__ import annotations

import builtins

import pytest

from flow.agents import AgentRequest
from flow.agents.adapters.claude_agent import ClaudeAgentSDKAdapter
from flow.agents.adapters.codex_cli import CodexCLIAdapter
from flow.agents.adapters.openai_agents import OpenAIAgentsSDKAdapter


@pytest.mark.parametrize(
    ("adapter", "provider"),
    [
        (OpenAIAgentsSDKAdapter(model="gpt-5.4"), "openai-agents"),
        (ClaudeAgentSDKAdapter(model="claude-opus-4-7"), "claude-agent"),
        (CodexCLIAdapter(model="gpt-5.4"), "codex-cli"),
    ],
)
def test_optional_adapter_shells_import_without_sdk_dependencies(
    adapter: object, provider: str
) -> None:
    assert getattr(adapter, "name") == provider


def test_optional_adapter_shells_fail_only_when_run(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    real_import = builtins.__import__

    def fake_import(
        name: str,
        globals: dict[str, object] | None = None,
        locals: dict[str, object] | None = None,
        fromlist: tuple[str, ...] = (),
        level: int = 0,
    ) -> object:
        if name == "agents":
            raise ImportError("blocked for test")
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    adapter = OpenAIAgentsSDKAdapter(model="gpt-5.4")

    with pytest.raises(RuntimeError, match="openai-agents"):
        adapter.run(AgentRequest(prompt="hello"))

from __future__ import annotations

import builtins
import sys
from types import ModuleType, SimpleNamespace

import pytest

from flow.agents import AgentRequest
from flow.agents.adapters.openai_agents import OpenAIAgentsSDKAdapter


def _install_fake_agents_module(
    monkeypatch: pytest.MonkeyPatch,
    *,
    final_output: object,
    last_agent_name: str = "Flow Runtime Agent",
    usage: object | None = None,
    runner_error: Exception | None = None,
) -> dict[str, object]:
    calls: dict[str, object] = {}
    module = ModuleType("agents")

    class FakeAgent:
        def __init__(self, **kwargs: object) -> None:
            calls["agent_kwargs"] = kwargs

    class FakeRunConfig:
        def __init__(self, **kwargs: object) -> None:
            calls["run_config_kwargs"] = kwargs

    class FakeRunner:
        @staticmethod
        def run_sync(agent: object, input: object, run_config: object | None = None) -> object:
            calls["runner_agent"] = agent
            calls["runner_input"] = input
            calls["runner_run_config"] = run_config
            if runner_error is not None:
                raise runner_error
            context_wrapper = SimpleNamespace(
                usage=usage
                or SimpleNamespace(
                    requests=1,
                    input_tokens=10,
                    output_tokens=4,
                    total_tokens=14,
                    request_usage_entries=[],
                )
            )
            return SimpleNamespace(
                final_output=final_output,
                last_agent=SimpleNamespace(name=last_agent_name),
                context_wrapper=context_wrapper,
            )

    module.Agent = FakeAgent
    module.Runner = FakeRunner
    module.RunConfig = FakeRunConfig
    module.set_default_openai_client = lambda client, use_for_tracing=False: (
        calls.setdefault("default_openai_clients", []).append(client),
        calls.setdefault("default_openai_client_use_for_tracing", []).append(
            use_for_tracing
        ),
    )
    module.set_default_openai_key = lambda key, use_for_tracing=False: calls.update(
        {
            "default_openai_key": key,
            "default_openai_key_use_for_tracing": use_for_tracing,
        }
    )
    monkeypatch.setitem(sys.modules, "agents", module)
    return calls


def _install_fake_openai_module(
    monkeypatch: pytest.MonkeyPatch,
    calls: dict[str, object],
) -> None:
    openai_module = ModuleType("openai")

    class FakeAsyncOpenAI:
        def __init__(self, **kwargs: object) -> None:
            calls.setdefault("async_openai_kwargs", []).append(kwargs)

    openai_module.AsyncOpenAI = FakeAsyncOpenAI
    monkeypatch.setitem(sys.modules, "openai", openai_module)


def _block_agents_import(monkeypatch: pytest.MonkeyPatch) -> None:
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


def test_openai_agents_adapter_maps_text_response_and_usage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = _install_fake_agents_module(monkeypatch, final_output="Planned response")
    _install_fake_openai_module(monkeypatch, calls)
    adapter = OpenAIAgentsSDKAdapter(model="gpt-5.4")

    result = adapter.run(
        AgentRequest(
            prompt="Summarize today",
            route_hint="general",
            context={"inbox_count": 3},
            metadata={"instructions": "Be concise.", "trace_metadata": {"surface": "assistant"}},
        )
    )

    assert result.response_text == "Planned response"
    assert result.structured_output is None
    assert result.provider == "openai-agents"
    assert result.model == "gpt-5.4"
    assert result.usage["requests"] == 1
    assert result.trace_events[-1].payload["last_agent"] == "Flow Runtime Agent"
    assert calls["agent_kwargs"] == {
        "name": "Flow Runtime Agent",
        "instructions": "Be concise.",
        "model": "gpt-5.4",
    }
    assert calls["runner_input"] == (
        "User request:\nSummarize today\n\nContext:\n- inbox_count: 3"
    )
    assert calls["run_config_kwargs"] == {
        "workflow_name": "Flow assistant general",
        "tracing_disabled": True,
        "trace_metadata": {"surface": "assistant"},
    }


def test_openai_agents_adapter_parses_json_output(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = _install_fake_agents_module(
        monkeypatch,
        final_output='{"summary":"Focus on inbox","reasons":["stale items"]}',
    )
    _install_fake_openai_module(monkeypatch, calls)
    adapter = OpenAIAgentsSDKAdapter(model="gpt-5.4")

    result = adapter.run(
        AgentRequest(
            prompt="Return a planning summary",
            output_mode="json",
            metadata={"instructions": "Return JSON."},
        )
    )

    assert result.response_text == '{"summary":"Focus on inbox","reasons":["stale items"]}'
    assert result.structured_output == {
        "summary": "Focus on inbox",
        "reasons": ["stale items"],
    }


def test_openai_agents_adapter_accepts_dict_output_without_parsing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = _install_fake_agents_module(
        monkeypatch,
        final_output={"summary": "Structured already"},
    )
    _install_fake_openai_module(monkeypatch, calls)
    adapter = OpenAIAgentsSDKAdapter(model="gpt-5.4")

    result = adapter.run(AgentRequest(prompt="Structured", output_mode="json"))

    assert result.response_text == '{"summary": "Structured already"}'
    assert result.structured_output == {"summary": "Structured already"}


def test_openai_agents_adapter_raises_clear_error_when_sdk_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _block_agents_import(monkeypatch)
    monkeypatch.delitem(sys.modules, "agents", raising=False)
    adapter = OpenAIAgentsSDKAdapter(model="gpt-5.4")

    with pytest.raises(RuntimeError, match="openai-agents runtime is not installed"):
        adapter.run(AgentRequest(prompt="hello"))


def test_openai_agents_adapter_surfaces_runner_failures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = _install_fake_agents_module(
        monkeypatch,
        final_output="unused",
        runner_error=RuntimeError("sdk failed"),
    )
    _install_fake_openai_module(monkeypatch, calls)
    adapter = OpenAIAgentsSDKAdapter(model="gpt-5.4")

    with pytest.raises(RuntimeError, match="OpenAI Agents SDK run failed"):
        adapter.run(AgentRequest(prompt="hello"))


def test_openai_agents_adapter_configures_custom_client_with_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = _install_fake_agents_module(monkeypatch, final_output="Planned response")
    _install_fake_openai_module(monkeypatch, calls)

    adapter = OpenAIAgentsSDKAdapter(
        model="gpt-5.4",
        timeout=12.5,
        api_key="test-openai-key",
        base_url="https://example.openai.test/v1",
    )

    adapter.run(AgentRequest(prompt="hello"))

    assert calls["async_openai_kwargs"][-1] == {
        "api_key": "test-openai-key",
        "base_url": "https://example.openai.test/v1",
        "timeout": 12.5,
    }
    assert calls["default_openai_client_use_for_tracing"][-1] is False


def test_openai_agents_adapter_reconfigures_client_for_each_run(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = _install_fake_agents_module(monkeypatch, final_output="Planned response")
    _install_fake_openai_module(monkeypatch, calls)

    custom_adapter = OpenAIAgentsSDKAdapter(
        model="gpt-5.4",
        timeout=12.5,
        api_key="test-openai-key",
        base_url="https://example.openai.test/v1",
    )
    default_adapter = OpenAIAgentsSDKAdapter(model="gpt-5.4")

    custom_adapter.run(AgentRequest(prompt="first"))
    default_adapter.run(AgentRequest(prompt="second"))

    assert calls["async_openai_kwargs"] == [
        {
            "api_key": "test-openai-key",
            "base_url": "https://example.openai.test/v1",
            "timeout": 12.5,
        },
        {
            "api_key": None,
            "base_url": None,
            "timeout": 60.0,
        },
    ]

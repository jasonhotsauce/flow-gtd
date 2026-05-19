"""OpenAI Agents SDK adapter shell.

The real SDK integration is intentionally lazy so default installs and tests do
not require `openai-agents` or live API credentials.
"""

from __future__ import annotations

import json
from typing import Any

from flow.agents.contracts import AgentRequest, AgentResult
from flow.agents.contracts import AgentTraceEvent
from flow.utils.llm.json_parser import parse_json_response


class OpenAIAgentsSDKAdapter:
    """Adapter boundary for OpenAI Agents SDK backed product agents."""

    name = "openai-agents"

    def __init__(
        self,
        *,
        model: str = "",
        timeout: float = 60.0,
        api_key: str = "",
        base_url: str = "",
    ) -> None:
        self.model = model
        self.timeout = timeout
        self.api_key = api_key
        self.base_url = base_url

    def run(self, request: AgentRequest) -> AgentResult:
        try:
            import agents
        except ImportError as exc:
            raise RuntimeError(
                "openai-agents runtime is not installed; install the optional "
                "OpenAI Agents SDK dependency before enabling this provider."
            ) from exc

        self._configure_openai_client(agents)

        instructions = str(
            request.metadata.get("instructions")
            or "You are Flow's assistant runtime. Follow the provided route and "
            "context, stay concise, and do not perform hidden writes."
        )
        model = str(request.metadata.get("model") or self.model or "").strip() or None
        agent_name = str(request.metadata.get("agent_name") or "Flow Runtime Agent")
        workflow_name = str(
            request.metadata.get("workflow_name")
            or f"Flow assistant {request.route_hint or 'general'}"
        )
        trace_metadata = request.metadata.get("trace_metadata", {})
        tracing_disabled = bool(request.metadata.get("tracing_disabled", True))

        agent_kwargs: dict[str, Any] = {
            "name": agent_name,
            "instructions": self._augment_instructions(instructions, request),
        }
        if model is not None:
            agent_kwargs["model"] = model

        try:
            agent = agents.Agent(**agent_kwargs)
            run_config = agents.RunConfig(
                workflow_name=workflow_name,
                tracing_disabled=tracing_disabled,
                trace_metadata=trace_metadata,
            )
            result = agents.Runner.run_sync(
                agent,
                self._build_input(request),
                run_config=run_config,
            )
        except Exception as exc:
            raise RuntimeError("OpenAI Agents SDK run failed") from exc

        response_text, structured_output = self._coerce_output(
            getattr(result, "final_output", "")
        )
        usage = self._extract_usage(getattr(result, "context_wrapper", None))
        last_agent = getattr(getattr(result, "last_agent", None), "name", agent_name)

        return AgentResult(
            response_text=response_text,
            structured_output=structured_output,
            provider=self.name,
            model=model or self.model or None,
            usage=usage,
            trace_events=[
                AgentTraceEvent(
                    stage="openai_agents",
                    summary="Completed OpenAI Agents SDK run.",
                    provider=self.name,
                    payload={
                        "last_agent": last_agent,
                        "workflow_name": workflow_name,
                        "requests": usage.get("requests", 0),
                    },
                )
            ],
        )

    def _augment_instructions(self, instructions: str, request: AgentRequest) -> str:
        if request.output_mode != "json":
            return instructions
        return (
            f"{instructions}\n\n"
            "Return only a JSON object for the final answer."
        )

    def _build_input(self, request: AgentRequest) -> str:
        parts = [f"User request:\n{request.prompt}"]
        if request.context:
            context_lines = [f"- {key}: {value}" for key, value in request.context.items()]
            parts.append("Context:\n" + "\n".join(context_lines))
        return "\n\n".join(parts)

    def _coerce_output(
        self, final_output: object
    ) -> tuple[str, dict[str, Any] | None]:
        if isinstance(final_output, dict):
            return json.dumps(final_output, sort_keys=True), final_output
        if hasattr(final_output, "model_dump"):
            structured = final_output.model_dump()
            return json.dumps(structured, sort_keys=True), structured

        response_text = str(final_output)
        structured_output = parse_json_response(response_text)
        return response_text, structured_output

    def _extract_usage(self, context_wrapper: object | None) -> dict[str, Any]:
        usage = getattr(context_wrapper, "usage", None)
        if usage is None:
            return {}
        return {
            "requests": getattr(usage, "requests", 0),
            "input_tokens": getattr(usage, "input_tokens", 0),
            "output_tokens": getattr(usage, "output_tokens", 0),
            "total_tokens": getattr(usage, "total_tokens", 0),
            "request_usage_entries": getattr(usage, "request_usage_entries", []),
        }

    def _configure_openai_client(self, agents_module: object) -> None:
        if hasattr(agents_module, "set_default_openai_client"):
            try:
                from openai import AsyncOpenAI
            except ImportError as exc:
                raise RuntimeError(
                    "openai package is required when configuring the OpenAI Agents runtime."
                ) from exc
            client = AsyncOpenAI(
                api_key=self.api_key or None,
                base_url=self.base_url or None,
                timeout=self.timeout,
            )
            agents_module.set_default_openai_client(client, use_for_tracing=False)
            return

        if hasattr(agents_module, "set_default_openai_key"):
            agents_module.set_default_openai_key(self.api_key, use_for_tracing=False)

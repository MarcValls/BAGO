"""Execute an agent definition locally or via an LLM adapter."""

from __future__ import annotations

import time
from typing import Any

from bago_core.agent_kit.errors import AgentKitError, AgentNotFound
from bago_core.agent_kit.llm_adapter import LLMAdapterError, call_agent_prompt
from bago_core.agent_kit.models import AgentDefinition, AgentRequest, AgentResult
from bago_core.agent_kit.registry import default_registry


class AgentRunner:
    def __init__(self, registry=None):
        self.registry = registry or default_registry()

    def run(self, request: AgentRequest) -> AgentResult:
        try:
            agent = self.registry.get(request.agent_id)
        except AgentNotFound as exc:
            return AgentResult(
                success=False,
                agent_id=request.agent_id,
                error=str(exc),
            )

        t0 = time.perf_counter()

        if request.mode == "describe":
            return self._describe(agent, request, t0)

        if request.mode in {"chat", "run"}:
            return self._execute(agent, request, t0)

        return AgentResult(
            success=False,
            agent_id=agent.id,
            error=f"unsupported mode {request.mode!r}",
        )

    def _describe(self, agent: AgentDefinition, request: AgentRequest, t0: float) -> AgentResult:
        lines = [
            f"id: {agent.id}",
            f"name: {agent.name}",
            f"category: {agent.category}",
            f"sandbox_mode: {agent.sandbox_mode}",
            f"model: {agent.model or '(none)'}",
            f"source: {agent.source_path}",
            f"description: {agent.description}",
        ]
        return AgentResult(
            success=True,
            agent_id=agent.id,
            output="\n".join(lines),
            duration_ms=_elapsed_ms(t0),
        )

    def _execute(self, agent: AgentDefinition, request: AgentRequest, t0: float) -> AgentResult:
        dry_run = request.options.get("dry_run", True)
        provider = request.provider
        model = request.model
        use_bago = request.use_bago_provider

        if not dry_run and not provider and not use_bago:
            return AgentResult(
                success=False,
                agent_id=agent.id,
                error="a provider is required for a real LLM call; use --provider, --use-bago-provider, or --no-dry-run with an explicit provider",
            )

        try:
            result = call_agent_prompt(
                agent,
                request,
                provider=provider,
                model=model,
                use_bago_provider=use_bago,
                base_url=request.options.get("base_url", ""),
                api_key=request.options.get("api_key", ""),
                temperature=float(request.options.get("temperature", 0.7)),
                max_tokens=int(request.options.get("max_tokens", 0)) or None,
                dry_run=bool(dry_run),
            )
        except LLMAdapterError as exc:
            return AgentResult(
                success=False,
                agent_id=agent.id,
                error=str(exc),
            )

        output = result["output"]
        if dry_run:
            output = (
                f"[DRY RUN] provider={result.get('provider') or '(none)'} "
                f"model={result.get('model') or '(none)'}\n\n{output}"
            )

        return AgentResult(
            success=True,
            agent_id=agent.id,
            output=output,
            duration_ms=_elapsed_ms(t0),
        )


def _elapsed_ms(t0: float) -> int:
    return int((time.perf_counter() - t0) * 1000)


def run_agent(agent_id: str, task: str = "", **options: Any) -> AgentResult:
    request = AgentRequest(agent_id=agent_id, task=task, options=options)
    return AgentRunner().run(request)

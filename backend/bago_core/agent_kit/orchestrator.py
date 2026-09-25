"""BAGO assistant orchestrator.

Implements a resolve -> audit -> plan -> execute -> verify cycle
using the portable agent registry and LLM adapter.

Agent selection is done via a structured JSON response so the LLM can
reason about the minimal safe set of agents and return a machine-parseable
plan.  Plans are persisted to `.bago/state/orchestrator_plans.jsonl` for
traceability.
"""

from __future__ import annotations

import datetime
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from bago_core.agent_kit.errors import AgentKitError
from bago_core.agent_kit.llm_adapter import LLMAdapterError, call_llm
from bago_core.agent_kit.models import AgentDefinition, AgentRequest
from bago_core.agent_kit.registry import AgentRegistry

try:
    from jsonschema import ValidationError, validate
except ModuleNotFoundError:  # pragma: no cover
    validate = None  # type: ignore[assignment]
    ValidationError = Exception  # type: ignore[misc,assignment]


@dataclass
class OrchestrationResult:
    success: bool
    output: str = ""
    error: str = ""
    plan: dict[str, Any] = field(default_factory=dict)


_AGENT_SELECTOR_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "reasoning": {"type": "string", "minLength": 1},
        "audit": {
            "type": "array",
            "uniqueItems": True,
            "items": {"type": "string"},
            "description": "Read-only agents to run before planning.",
        },
        "execute": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Implementation agents authorized to act.",
        },
        "verify": {
            "type": "string",
            "description": "Final verifier agent id.",
        },
    },
    "required": ["reasoning", "audit", "execute", "verify"],
}


def _default_state_root() -> Path:
    """Return the BAGO state directory relative to the repository root."""
    return Path(".bago/state").resolve()


def _plan_store_path(state_root: Path | None = None) -> Path:
    root = state_root or _default_state_root()
    return root / "orchestrator_plans.jsonl"


def save_orchestrator_plan(
    plan: dict[str, Any],
    *,
    task: str = "",
    context: dict[str, Any] | None = None,
    provider: str = "",
    model: str = "",
    dry_run: bool = True,
    state_root: Path | None = None,
) -> Path:
    """Append a plan record to the JSONL store and return the file path."""
    record = {
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "task": task,
        "context": context or {},
        "provider": provider,
        "model": model,
        "dry_run": dry_run,
        "plan": plan,
    }
    path = _plan_store_path(state_root)
    from bago_core.atomic_json import append_text_durable

    append_text_durable(path, json.dumps(record, ensure_ascii=False) + "\n")
    return path


class AgentOrchestrator:
    """Run the BAGO assistant cycle over a user task."""

    def __init__(self, registry: AgentRegistry | None = None, state_root: Path | None = None):
        self.registry = registry or AgentRegistry()
        self.state_root = state_root or _default_state_root()

    def plan(
        self,
        task: str,
        *,
        context: dict[str, Any] | None = None,
        provider: str = "",
        model: str = "",
        use_bago_provider: bool = False,
        base_url: str = "",
        api_key: str = "",
        temperature: float = 0.7,
        max_tokens: int | None = None,
        dry_run: bool = True,
    ) -> OrchestrationResult:
        """Select agents from the live catalog and persist without running them."""
        effective_provider = self._effective_provider(provider, use_bago_provider)
        effective_model = self._effective_model(model, use_bago_provider)
        if dry_run:
            selected = self._select_agents_by_task(task)
        else:
            try:
                selected = self._resolve(
                    task, context, provider, model, use_bago_provider, base_url,
                    api_key, temperature, max_tokens,
                )
            except LLMAdapterError as exc:
                return OrchestrationResult(success=False, error=f"agent selection failed: {exc}")

        path = save_orchestrator_plan(
            selected,
            task=task,
            context=context,
            provider=effective_provider,
            model=effective_model,
            dry_run=dry_run,
            state_root=self.state_root,
        )
        output = json.dumps({"plan": selected, "saved_to": str(path)}, ensure_ascii=False, indent=2)
        return OrchestrationResult(success=True, output=output, plan=selected)

    def run(
        self,
        task: str,
        *,
        context: dict[str, Any] | None = None,
        provider: str = "",
        model: str = "",
        use_bago_provider: bool = False,
        base_url: str = "",
        api_key: str = "",
        temperature: float = 0.7,
        max_tokens: int | None = None,
        dry_run: bool = True,
    ) -> OrchestrationResult:
        effective_provider = self._effective_provider(provider, use_bago_provider)
        effective_model = self._effective_model(model, use_bago_provider)

        if dry_run:
            selected = self._select_agents_by_task(task)
            save_orchestrator_plan(
                selected,
                task=task,
                context=context,
                provider=effective_provider,
                model=effective_model,
                dry_run=True,
                state_root=self.state_root,
            )
            return self._dry_run_plan(task, context)

        try:
            agent_plan = self._resolve(task, context, provider, model, use_bago_provider, base_url, api_key, temperature, max_tokens)
        except LLMAdapterError as exc:
            return OrchestrationResult(success=False, error=f"resolve failed: {exc}")

        save_orchestrator_plan(
            agent_plan,
            task=task,
            context=context,
            provider=effective_provider,
            model=effective_model,
            dry_run=False,
            state_root=self.state_root,
        )

        audit_reports: list[str] = []
        for agent_id in agent_plan.get("audit", []):
            report = self._run_agent_llm(agent_id, task, context, provider, model, use_bago_provider, base_url, api_key, temperature, max_tokens)
            audit_reports.append(f"## {agent_id}\n{report}")

        plan_text = self._plan(task, context, audit_reports, provider, model, use_bago_provider, base_url, api_key, temperature, max_tokens)

        exec_report = ""
        for agent_id in agent_plan.get("execute", []):
            exec_report = self._run_agent_llm(agent_id, task, context, provider, model, use_bago_provider, base_url, api_key, temperature, max_tokens)

        verify_report = ""
        if agent_plan.get("verify"):
            verify_report = self._run_agent_llm(
                agent_plan["verify"],
                task,
                {**(context or {}), "audit": "\n\n".join(audit_reports), "plan": plan_text, "execution": exec_report},
                provider, model, use_bago_provider, base_url, api_key, temperature, max_tokens,
            )

        output = f"""# BAGO Assistant Result

## Selected agents
- audit: {agent_plan.get('audit', [])}
- execute: {agent_plan.get('execute', [])}
- verify: {agent_plan.get('verify', '')}

## Reasoning
{agent_plan.get('reasoning', '(none)')}

## Audit
{chr(10).join(audit_reports) or "(none)"}

## Plan
{plan_text}

## Execution
{exec_report or "(none)"}

## Verification
{verify_report or "(none)"}
""".strip()

        return OrchestrationResult(success=True, output=output, plan=agent_plan)

    def _effective_provider(self, provider: str, use_bago_provider: bool) -> str:
        if use_bago_provider:
            from bago_core.agent_kit.llm_adapter import resolve_bago_provider
            try:
                return resolve_bago_provider()["provider"]
            except LLMAdapterError:
                return "bago"
        return provider or "(none)"

    def _effective_model(self, model: str, use_bago_provider: bool) -> str:
        if use_bago_provider:
            from bago_core.agent_kit.llm_adapter import resolve_bago_provider
            try:
                return resolve_bago_provider()["model"]
            except LLMAdapterError:
                return ""
        return model or "(none)"

    def _dry_run_plan(self, task: str, context: dict[str, Any] | None) -> OrchestrationResult:
        selected = self._select_agents_by_task(task)
        output = f"""[DRY RUN] BAGO agent selection plan

Task: {task}
Context: {context or {}}

Selected agents:
- audit: {selected['audit']}
- execute: {selected['execute']}
- verify: {selected['verify']}

Plan saved to .bago/state/orchestrator_plans.jsonl
No LLM calls were made. Use --no-dry-run with --provider or --use-bago-provider to execute.
""".strip()
        return OrchestrationResult(success=True, output=output, plan=selected)

    def _known_agent_ids(self) -> set[str]:
        try:
            return {a.id for a in self.registry.all()}
        except AgentKitError:
            return set()

    def _agents_by_category(self) -> dict[str, list[str]]:
        """Return agent ids grouped by discovered category."""
        try:
            agents = self.registry.all()
        except AgentKitError:
            return {}
        return {
            "audit": [a.id for a in agents if a.category == "audit" or a.is_read_only],
            "implement": [a.id for a in agents if a.category == "implement"],
            "verify": [a.id for a in agents if a.category == "verify"],
        }

    def _default_verifier(self) -> str:
        by_cat = self._agents_by_category()
        return by_cat.get("verify", [""])[0]

    def _select_agents_by_task(self, task: str) -> dict[str, Any]:
        """Heuristic selection based on task keywords mapped to categories."""
        task_lower = task.lower()
        by_cat = self._agents_by_category()
        audit = []

        if any(k in task_lower for k in ("backend", "api", "route", "server")):
            audit.extend([a for a in by_cat.get("audit", []) if "backend" in a or "api" in a])
        if any(k in task_lower for k in ("frontend", "ui", "react", "component")):
            audit.extend([a for a in by_cat.get("audit", []) if "frontend" in a])
        if any(k in task_lower for k in ("architect", "structure", "design")):
            audit.extend([a for a in by_cat.get("audit", []) if "architecture" in a or "architect" in a])
        if not any(k in task_lower for k in ("backend", "frontend", "architect")):
            audit.extend(by_cat.get("audit", []))

        # Deduplicate while preserving order.
        seen = set()
        unique_audit = []
        for a in audit:
            if a not in seen:
                seen.add(a)
                unique_audit.append(a)

        wants_changes = any(k in task_lower for k in ("implement", "fix", "add", "create", "build"))
        execute = by_cat.get("implement", []) if wants_changes else []

        return {
            "reasoning": "heuristic category-based selection over the discovered agent catalog",
            "audit": unique_audit,
            "execute": execute,
            "verify": self._default_verifier(),
        }

    def _resolve(
        self,
        task: str,
        context: dict[str, Any] | None,
        provider: str,
        model: str,
        use_bago_provider: bool,
        base_url: str,
        api_key: str,
        temperature: float,
        max_tokens: int | None,
    ) -> dict[str, Any]:
        """Return a validated agent plan parsed from a structured JSON response."""
        selected = self._select_agents_by_task(task)
        known_ids = self._known_agent_ids()

        schema_text = json.dumps(_AGENT_SELECTOR_SCHEMA, indent=2)
        catalog_window = self._catalog_window(known_ids)
        system = f"""You select agents from BAGO's dynamically discovered external catalog.
Your job is to choose the minimum set of agents needed to handle the user task safely.
Respond ONLY with a JSON object matching this schema:
{schema_text}

Rules:
- 'audit' must contain only read-only / audit-category agent ids.
- 'execute' must contain only implementation agents, and only when the task asks to change code.
- 'verify' must be a single verifier agent id.
- Include a short 'reasoning' field explaining your choices.

Available agents (id | category | sandbox):
{catalog_window}

Return ONLY JSON, no markdown, no prose."""
        user = f"Task: {task}\n\nInitial heuristic selection: {json.dumps(selected)}\n\nReturn the final JSON plan."
        messages = [{"role": "user", "content": user}]
        response = self._call_provider(provider, model, messages, system, use_bago_provider, base_url, api_key, temperature, max_tokens)
        return self._parse_agent_plan(response.content, selected, known_ids)

    def _catalog_window(self, known_ids: set[str]) -> str:
        """Return a compact, dynamic description of available agents."""
        try:
            agents = [a for a in self.registry.all() if a.id in known_ids]
        except AgentKitError:
            agents = []
        if not agents:
            return "(no agents discovered)"
        lines = []
        for a in agents:
            desc = (a.description or "").replace("\n", " ")[:80]
            lines.append(f"- {a.id} | {a.category} | {a.sandbox_mode} | {desc}")
        return "\n".join(lines)

    def _parse_agent_plan(self, text: str, fallback: dict[str, Any], known_ids: set[str]) -> dict[str, Any]:
        """Parse, validate against the JSON schema, and filter known agent ids."""
        plan = dict(fallback)
        raw = text.strip()
        if raw.startswith("```"):
            lines = raw.splitlines()
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            raw = "\n".join(lines).strip()

        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return plan

        if not isinstance(parsed, dict):
            return plan

        if (
            not isinstance(parsed.get("reasoning"), str)
            or not parsed["reasoning"].strip()
            or not isinstance(parsed.get("audit"), list)
            or not all(isinstance(agent_id, str) for agent_id in parsed["audit"])
            or not isinstance(parsed.get("execute"), list)
            or not all(isinstance(agent_id, str) for agent_id in parsed["execute"])
            or not isinstance(parsed.get("verify"), str)
            or set(parsed) != {"reasoning", "audit", "execute", "verify"}
        ):
            return plan

        # Strict JSON schema validation when jsonschema is available.
        if validate is not None:
            try:
                validate(instance=parsed, schema=_AGENT_SELECTOR_SCHEMA)
            except ValidationError:
                return plan

        definitions = {agent.id: agent for agent in self.registry.all()}
        audit = [
            agent_id for agent_id in parsed.get("audit", [])
            if isinstance(agent_id, str) and agent_id in known_ids
            and definitions[agent_id].category == "audit"
        ]
        execute = [
            agent_id for agent_id in parsed.get("execute", [])
            if isinstance(agent_id, str) and agent_id in known_ids
            and definitions[agent_id].category == "implement"
        ]
        verify = parsed.get("verify", "")
        if (not isinstance(verify, str) or verify not in known_ids
                or definitions[verify].category != "verify"):
            verify = fallback.get("verify", "")

        plan["reasoning"] = str(parsed.get("reasoning", fallback.get("reasoning", "")))
        plan["audit"] = audit or fallback.get("audit", [])
        plan["execute"] = execute or fallback.get("execute", [])
        plan["verify"] = verify
        return plan

    def _plan(
        self,
        task: str,
        context: dict[str, Any] | None,
        audit_reports: list[str],
        provider: str,
        model: str,
        use_bago_provider: bool,
        base_url: str,
        api_key: str,
        temperature: float,
        max_tokens: int | None,
    ) -> str:
        system = "You are BAGO's planning role. Given the task and audit reports, produce a concise, safe execution plan with acceptance criteria."
        user = f"Task: {task}\n\nAudit reports:\n\n{chr(10).join(audit_reports)}\n\nPlan:"
        messages = [{"role": "user", "content": user}]
        response = self._call_provider(provider, model, messages, system, use_bago_provider, base_url, api_key, temperature, max_tokens)
        return response.content

    def _run_agent_llm(
        self,
        agent_id: str,
        task: str,
        context: dict[str, Any] | None,
        provider: str,
        model: str,
        use_bago_provider: bool,
        base_url: str,
        api_key: str,
        temperature: float,
        max_tokens: int | None,
    ) -> str:
        try:
            agent = self.registry.get(agent_id)
        except AgentKitError:
            return f"[missing agent {agent_id}]"
        system = f"You are {agent.name}.\n\n{agent.description}\n\n{agent.prompt_template[:2000]}"
        user_lines = [f"Task: {task}"]
        if context:
            for key, value in context.items():
                user_lines.append(f"{key}: {value}")
        user = "\n".join(user_lines)
        messages = [{"role": "user", "content": user}]
        response = self._call_provider(provider, model, messages, system, use_bago_provider, base_url, api_key, temperature, max_tokens)
        return response.content

    def _call_provider(
        self,
        provider: str,
        model: str,
        messages: list[dict[str, str]],
        system: str,
        use_bago_provider: bool,
        base_url: str,
        api_key: str,
        temperature: float,
        max_tokens: int | None,
    ) -> Any:
        from bago_core.agent_kit.llm_adapter import call_llm, resolve_bago_provider

        resolved_provider = provider
        resolved_model = model
        resolved_base_url = base_url
        resolved_api_key = api_key

        if use_bago_provider:
            cfg = resolve_bago_provider()
            resolved_provider = cfg["provider"]
            resolved_model = cfg["model"] or model
            resolved_base_url = cfg["base_url"] or base_url
            resolved_api_key = cfg["api_key"] or api_key
            temperature = cfg.get("temperature", temperature)

        return call_llm(
            provider=resolved_provider,
            model=resolved_model,
            messages=messages,
            system=system,
            base_url=resolved_base_url,
            api_key=resolved_api_key,
            temperature=temperature,
            max_tokens=max_tokens,
        )


def orchestrate_task(
    task: str,
    *,
    context: dict[str, Any] | None = None,
    **options: Any,
) -> OrchestrationResult:
    """Compatibility entry point; plans are persisted without dispatching agents."""
    return AgentOrchestrator().plan(task, context=context, **options)


def plan_agents(
    task: str,
    *,
    context: dict[str, Any] | None = None,
    registry: AgentRegistry | None = None,
    state_root: Path | None = None,
    **options: Any,
) -> OrchestrationResult:
    """Public BAGO agent selection entry point; does not execute selected roles."""
    return AgentOrchestrator(registry=registry, state_root=state_root).plan(
        task, context=context, **options
    )


__all__ = [
    "AgentOrchestrator",
    "OrchestrationResult",
    "orchestrate_task",
    "plan_agents",
    "save_orchestrator_plan",
]

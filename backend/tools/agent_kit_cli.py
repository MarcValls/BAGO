"""CLI bridge for bago_core.agent_kit via bago agent ...."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Ensure bago_core is importable when this file is loaded by cmd_tools.
_BACKEND = Path(__file__).resolve().parents[1]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from bago_core.agent_kit.catalog import DEFAULT_CATALOG_PATH
from bago_core.agent_kit.errors import AgentKitError
from bago_core.agent_kit.models import AgentRequest
from bago_core.agent_kit.registry import AgentRegistry
from bago_core.agent_kit.runner import AgentRunner


def _format_agent(agent, mode: str = "text"):
    if mode == "json":
        return {
            "id": agent.id,
            "name": agent.name,
            "description": agent.description,
            "category": agent.category,
            "sandbox_mode": agent.sandbox_mode,
            "model": agent.model,
            "source": str(agent.source_path),
        }
    return (
        f"{agent.id:36} {agent.category:12} {agent.sandbox_mode:12} {agent.model or '':16} {agent.name}"
    )


def cmd_list(args: argparse.Namespace) -> int:
    registry = AgentRegistry(args.catalog)
    agents = registry.all()
    if args.json:
        print(json.dumps([_format_agent(a, "json") for a in agents], indent=2, ensure_ascii=False))
    else:
        print(f"{'id':36} {'category':12} {'sandbox':12} {'model':16} name")
        print("-" * 90)
        for agent in agents:
            print(_format_agent(agent))
    return 0


def cmd_describe(args: argparse.Namespace) -> int:
    registry = AgentRegistry(args.catalog)
    agent = registry.get(args.agent_id)
    request = AgentRequest(agent_id=agent.id, options={"mode": "describe"})
    result = AgentRunner(registry).run(request)
    print(result.output)
    return 0 if result.success else 1


def cmd_run(args: argparse.Namespace) -> int:
    registry = AgentRegistry(args.catalog)
    options: dict = {
        "mode": args.mode,
        "dry_run": not args.no_dry_run,
    }
    if args.provider:
        options["provider"] = args.provider
    if args.model:
        options["model"] = args.model
    if args.use_bago_provider:
        options["use_bago_provider"] = True
    if args.base_url:
        options["base_url"] = args.base_url
    if args.api_key:
        options["api_key"] = args.api_key
    if args.temperature is not None:
        options["temperature"] = args.temperature
    if args.max_tokens is not None:
        options["max_tokens"] = args.max_tokens
    context = {}
    if args.root:
        context["root"] = args.root
    request = AgentRequest(
        agent_id=args.agent_id,
        task=" ".join(args.task_words),
        context=context,
        options=options,
    )
    result = AgentRunner(registry).run(request)
    print(result.output)
    if result.error:
        print(f"error: {result.error}", file=sys.stderr)
    return 0 if result.success else 1


def cmd_plan(args: argparse.Namespace) -> int:
    from bago_core.agent_kit.orchestrator import plan_agents

    root = Path(args.root).expanduser().resolve() if args.root else Path.cwd().resolve()
    context = {"root": str(root)}
    result = plan_agents(
        " ".join(args.task_words),
        context=context,
        registry=AgentRegistry(args.catalog),
        state_root=root / ".bago" / "state",
        provider=args.provider,
        model=args.model,
        use_bago_provider=args.use_bago_provider,
        base_url=args.base_url,
        api_key=args.api_key,
        temperature=args.temperature if args.temperature is not None else 0.7,
        max_tokens=args.max_tokens,
        dry_run=not args.no_dry_run,
    )
    print(result.output)
    if result.error:
        print(f"error: {result.error}", file=sys.stderr)
    return 0 if result.success else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="bago agent", description="BAGO portable agent pack", allow_abbrev=False)
    sub = parser.add_subparsers(dest="cmd")

    list_parser = sub.add_parser("list", help="List available agents")
    list_parser.add_argument("--catalog", default=str(DEFAULT_CATALOG_PATH), help="External agent catalog directory")
    list_parser.add_argument("--json", action="store_true", help="JSON output")

    describe_parser = sub.add_parser("describe", help="Show agent definition")
    describe_parser.add_argument("--catalog", default=str(DEFAULT_CATALOG_PATH), help="External agent catalog directory")
    describe_parser.add_argument("agent_id")

    run_parser = sub.add_parser("run", help="Run an agent")
    run_parser.add_argument("--catalog", default=str(DEFAULT_CATALOG_PATH), help="External agent catalog directory")
    run_parser.add_argument("agent_id")
    run_parser.add_argument("--mode", default="run", choices=["run", "chat", "describe"])
    run_parser.add_argument("--provider", default="", help="LLM provider (ollama, openai, anthropic, openrouter, copilot, codex, ...)")
    run_parser.add_argument("--model", default="", help="Model name")
    run_parser.add_argument("--use-bago-provider", action="store_true", help="Use BAGO configured provider/model")
    run_parser.add_argument("--base-url", default="", help="Override provider base URL")
    run_parser.add_argument("--api-key", default="", help="API key (or rely on env var)")
    run_parser.add_argument("--temperature", type=float, default=None, help="Sampling temperature")
    run_parser.add_argument("--max-tokens", type=int, default=None, help="Max output tokens")
    run_parser.add_argument("--no-dry-run", action="store_true", help="Actually call the LLM instead of rendering the prompt")
    run_parser.add_argument("--root", default="", help="Project root context")
    run_parser.add_argument("task_words", nargs="*", default=[], help="Task words")

    plan_parser = sub.add_parser("plan", help="Select agents and persist a JSON plan without running them")
    plan_parser.add_argument("--catalog", default=str(DEFAULT_CATALOG_PATH), help="External agent catalog directory")
    plan_parser.add_argument("--provider", default="", help="LLM provider for structured selection")
    plan_parser.add_argument("--model", default="", help="Model for structured selection")
    plan_parser.add_argument("--use-bago-provider", action="store_true", help="Use BAGO configured provider/model")
    plan_parser.add_argument("--base-url", default="", help="Override provider base URL")
    plan_parser.add_argument("--api-key", default="", help="API key (or rely on environment variable)")
    plan_parser.add_argument("--temperature", type=float, default=None, help="Sampling temperature")
    plan_parser.add_argument("--max-tokens", type=int, default=None, help="Maximum output tokens")
    plan_parser.add_argument("--no-dry-run", action="store_true", help="Use the LLM for structured selection")
    plan_parser.add_argument("--root", default="", help="Project root whose .bago/state stores the plan")
    plan_parser.add_argument("task_words", nargs="*", default=[], help="Task words")

    args = parser.parse_args(argv)
    if args.cmd is None:
        parser.print_help()
        return 0

    try:
        if args.cmd == "list":
            return cmd_list(args)
        if args.cmd == "describe":
            return cmd_describe(args)
        if args.cmd == "run":
            return cmd_run(args)
        if args.cmd == "plan":
            return cmd_plan(args)
    except AgentKitError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

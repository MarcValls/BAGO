#!/usr/bin/env python3
"""Structured SessionManager bridge for the Installation Manager."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

CORE_DIR = Path(__file__).resolve().parents[1] / ".bago" / "core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from context_store import ContextStore  # noqa: E402
from session_manager import ADAPTER_REGISTRY, BAGO_MODES, SessionManager  # noqa: E402


def _base_path(value: str) -> Path:
    return Path(value or ".").expanduser().resolve()


def _summary_path(base_path: Path, session_id: str) -> Path:
    return base_path / ".bago" / "state" / "sessions" / f"{session_id}.json"


def list_sessions(base_path: Path) -> list[dict[str, Any]]:
    sessions = ContextStore.list_sessions(base_dir=base_path / ".bago" / "state")
    for item in sessions:
        path = _summary_path(base_path, item["sid"])
        if not path.exists():
            continue
        try:
            saved = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        item.update({
            "provider": saved.get("provider", item.get("last_provider", "")),
            "model": saved.get("model", item.get("last_model", "")),
            "bago_mode": saved.get("bago_mode", "B"),
            "active_agent": saved.get("active_agent", "default"),
            "total_tokens": saved.get("total_tokens", 0),
            "total_calls": saved.get("total_calls", 0),
        })
    return sessions


def session_payload(manager: SessionManager) -> dict[str, Any]:
    status = manager.status()
    status["providers"] = manager.available_providers()
    status["bago_modes"] = BAGO_MODES
    status["agents"] = sorted(agent.name for agent in manager.agent_gateway.list_agents())
    status["history"] = manager.store.get_history()[-30:]
    return status


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="BAGO SessionManager JSON bridge")
    parser.add_argument("--base-path", default=".")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("list")

    create = sub.add_parser("create")
    create.add_argument("--provider", default="ollama-local", choices=sorted(ADAPTER_REGISTRY))
    create.add_argument("--model", default="qwen2.5:14b")
    create.add_argument("--mode", default="B", choices=sorted(BAGO_MODES))
    create.add_argument("--agent", default="default")
    create.add_argument("--bridges", default="")

    for name in ("status", "apply", "send"):
        command = sub.add_parser(name)
        command.add_argument("--session-id", required=True)
        if name == "apply":
            command.add_argument("--provider", choices=sorted(ADAPTER_REGISTRY))
            command.add_argument("--model")
            command.add_argument("--mode", choices=sorted(BAGO_MODES))
            command.add_argument("--agent")
            command.add_argument("--bridges")
            command.add_argument("--force", action="store_true")
        if name == "send":
            command.add_argument("--prompt", required=True)
            command.add_argument("--orchestrate", action="store_true")
    return parser


def run(args: argparse.Namespace) -> dict[str, Any]:
    base_path = _base_path(args.base_path)
    if args.command == "list":
        return {"ok": True, "base_path": str(base_path), "sessions": list_sessions(base_path)}

    manager: SessionManager | None = None
    try:
        if args.command == "create":
            manager = SessionManager(
                provider=args.provider,
                model=args.model,
                base_path=str(base_path),
                bago_mode=args.mode,
                active_agent=args.agent,
                active_bridges=[item for item in args.bridges.split(",") if item],
            )
            manager.save()
            return {"ok": True, "session": session_payload(manager)}

        manager = SessionManager.load(args.session_id, base_path=str(base_path))
        if args.command == "apply":
            target_provider = args.provider or manager.provider
            target_model = args.model or manager.model
            if target_provider != manager.provider or target_model != manager.model:
                switched = manager.switch(target_provider, target_model, force=args.force)
                if not switched.get("ok"):
                    return {"ok": False, "error": switched.get("warnings") or switched.get("error"), "switch": switched}
            if args.mode:
                manager.set_bago_mode(args.mode)
            if args.agent:
                activated = manager.activate_agent(args.agent)
                if not activated.get("ok"):
                    return {"ok": False, "error": activated.get("error"), "agent": activated}
            if args.bridges is not None:
                manager.set_active_bridges([item for item in args.bridges.split(",") if item])
            manager.save()
        elif args.command == "send":
            response = manager.orchestrate(args.prompt) if args.orchestrate else manager.send(args.prompt)
            manager.save()
            if args.orchestrate:
                successes = [item["ok"] for item in response.values()]
                return {
                    "ok": any(successes),
                    "partial": not all(successes),
                    "error": "" if any(successes) else "Todos los bridges fallaron",
                    "response": response,
                    "session": session_payload(manager),
                }
            return {"ok": True, "response": response, "session": session_payload(manager)}
        return {"ok": True, "session": session_payload(manager)}
    finally:
        if manager is not None:
            manager.close()


def main(argv: list[str] | None = None) -> int:
    try:
        payload = run(build_parser().parse_args(argv))
    except Exception as exc:
        payload = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
    print(json.dumps(payload, ensure_ascii=False))
    return 0 if payload.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())

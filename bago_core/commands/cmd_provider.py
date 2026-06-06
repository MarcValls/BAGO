#!/usr/bin/env python3
"""
cmd_provider.py -- Inspect and patch providers in .bago/config.json.

Uso:
    python bago_core\\cli.py provider list
    python bago_core\\cli.py provider set-fallback qwen2.5:1.5b
    python bago_core\\cli.py provider remove-fallback
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

def _user_bago_root() -> Path:
    return Path.home() / ".bago"

def _read_config(user_root: Path) -> dict:
    cfg = user_root / "config.json"
    if not cfg.exists():
        return {"providers": {}}
    try:
        return json.loads(cfg.read_text(encoding="utf-8"))
    except Exception:
        return {"providers": {}}

def _write_config(user_root: Path, data: dict) -> None:
    cfg = user_root / "config.json"
    cfg.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

def cmd_provider_list(args: argparse.Namespace) -> int:
    user_root = Path(args.user_bago or str(_user_bago_root()))
    data = _read_config(user_root)
    providers = data.get("providers", {})
    for name, body in providers.items():
        print(f"{name}: {json.dumps(body, ensure_ascii=False)}")
    if data.get("default_model"):
        print(f"default_model: {data['default_model']}")
    return 0

def cmd_provider_set_fallback(args: argparse.Namespace) -> int:
    user_root = Path(args.user_bago or str(_user_bago_root()))
    data = _read_config(user_root)
    providers = data.setdefault("providers", {})
    ollama = providers.setdefault("ollama-local", {"enabled": True, "base_url": "http://127.0.0.1:11434"})
    ollama["fallback_model"] = args.model
    _write_config(user_root, data)
    print(f"set ollama-local.fallback_model={args.model}")
    return 0

def cmd_provider_remove_fallback(args: argparse.Namespace) -> int:
    user_root = Path(args.user_bago or str(_user_bago_root()))
    data = _read_config(user_root)
    providers = data.get("providers", {})
    ollama = providers.get("ollama-local", {})
    if "fallback_model" in ollama:
        ollama.pop("fallback_model", None)
        _write_config(user_root, data)
        print("removed ollama-local.fallback_model")
    else:
        print("no fallback_model set")
    return 0

def build_subparser(parser):
    p = parser.add_subparsers(dest="command", required=False)
    pp = p.add_parser("provider", help="Provider inspection/patching")
    sp = pp.add_subparsers(dest="provider_cmd", required=False)
    sl = sp.add_parser("list", help="List providers and default_model")
    sl.add_argument("--user-bago", default=None)
    ss = sp.add_parser("set-fallback", help="Set ollama-local fallback_model")
    ss.add_argument("--user-bago", default=None)
    ss.add_argument("--model", required=True)
    sr = sp.add_parser("remove-fallback", help="Remove ollama-local fallback_model")
    sr.add_argument("--user-bago", default=None)

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="bago")
    build_subparser(parser)
    args = parser.parse_args(argv)
    if args.command != "provider":
        parser.print_help()
        return 0
    cmd = getattr(args, "provider_cmd", "list") or "list"
    if cmd == "list":
        return cmd_provider_list(args)
    if cmd == "set-fallback":
        return cmd_provider_set_fallback(args)
    if cmd == "remove-fallback":
        return cmd_provider_remove_fallback(args)
    return 1

if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""
cmd_route.py -- Routing status & preset management.

Expone `bago route status` que reporta el preset activo y valida el contrato
contra `docs/contracts/bago_v4_routing_presets.json`.

Uso:
    python bago_core\\cli.py route status
    python bago_core\\cli.py route validate --preset balanced
    python bago_core\\cli.py route activate --preset cheap
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from bago_core.workspace_paths import workspace_root

def _user_bago_root() -> Path:
    return workspace_root()

def _read_runtime(root: Path) -> dict:
    p = root / "routing_runtime.json"
    if not p.exists():
        return {"active_preset": None, "contract": {"text": "", "source": "none"}}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {"active_preset": None, "contract": {"text": "", "source": "none"}}

def _load_presets(repo: Path) -> dict:
    p = repo / "BAGO" / "docs" / "contracts" / "bago_v4_routing_presets.json"
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8")).get("presets", {})
    except Exception:
        return {}

def _is_contract_valid(runtime: dict, presets: dict) -> tuple[bool, str]:
    def _norm(s: str) -> str:
        return (s or "").replace("\n", " ").strip()

    preset = runtime.get("active_preset")
    contract = runtime.get("contract") or {}
    if not preset or preset == "null":
        return False, "active_preset is null"
    text = (contract.get("text") or "").strip()
    if not text:
        return False, "contract.text is empty"
    source = (contract.get("source") or "none").strip()
    if source == "none" or not source:
        return False, "contract.source is 'none'"
    expected = presets.get(preset, {}).get("contract", {}).get("text", "").strip()
    if expected and _norm(expected) != _norm(text):
        return False, f"contract.text drift vs preset {preset!r}"
    return True, f"preset={preset} source={source}"

def cmd_route_status(args: argparse.Namespace) -> int:
    user_root = Path(args.user_bago or str(_user_bago_root()))
    repo = Path(args.repo or str(Path(user_root).parent))
    runtime = _read_runtime(user_root)
    presets = _load_presets(repo)
    valid, reason = _is_contract_valid(runtime, presets)

    if args.json:
        out = {
            "user_bago": str(user_root),
            "runtime": runtime,
            "valid": valid,
            "reason": reason,
            "known_presets": list(presets.keys()),
        }
        print(json.dumps(out, indent=2, ensure_ascii=False))
    else:
        print(f"user_bago: {user_root}")
        print(f"active_preset: {runtime.get('active_preset')}")
        print(f"contract.source: {(runtime.get('contract') or {}).get('source')}")
        text = (runtime.get("contract") or {}).get("text") or ""
        preview = text[:80] + ("..." if len(text) > 80 else "")
        print(f"contract.text: {preview}")
        print(f"valid: {valid}")
        print(f"reason: {reason}")
        print(f"known_presets: {list(presets.keys())}")
    return 0 if valid or args.tolerant else 1

def cmd_route_validate(args: argparse.Namespace) -> int:
    user_root = Path(args.user_bago or str(_user_bago_root()))
    repo = Path(args.repo or str(Path(user_root).parent))
    runtime = _read_runtime(user_root)
    presets = _load_presets(repo)
    preset = args.preset or runtime.get("active_preset")
    if not preset or preset not in presets:
        print(f"invalid preset: {preset!r}")
        return 1
    def _norm(s: str) -> str:
        return (s or "").replace("\n", " ").strip()
    expected = _norm(presets[preset].get("contract", {}).get("text", ""))
    actual = _norm((runtime.get("contract") or {}).get("text", ""))
    if expected == actual and (runtime.get("contract") or {}).get("source", "none") != "none":
        print(f"preset {preset!r}: contract valid")
        return 0
    print(f"preset {preset!r}: contract drift")
    return 1

def cmd_route_activate(args: argparse.Namespace) -> int:
    user_root = Path(args.user_bago or str(_user_bago_root()))
    repo = Path(args.repo or str(Path(user_root).parent))
    presets = _load_presets(repo)
    if args.preset not in presets:
        print(f"unknown preset: {args.preset}")
        return 1
    preset_block = presets[args.preset]
    runtime = {
        "active_preset": args.preset,
        "contract": preset_block.get("contract", {}),
    }
    target = user_root / "routing_runtime.json"
    target.write_text(
        json.dumps(runtime, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"activated preset {args.preset!r} -> {target}")
    return 0

def build_subparser(parser) -> None:
    p_route = parser.add_subparsers(dest="command")
    p_route.required = False
    route = p_route.add_parser("route", help="Routing preset management")
    sp = route.add_subparsers(dest="route_cmd", required=False)
    status_p = sp.add_parser("status", help="Show active routing preset and contract")
    validate_p = sp.add_parser("validate", help="Validate active or named preset contract")
    validate_p.add_argument("--preset", default=None, help="Preset to validate (default: active)")
    activate_p = sp.add_parser("activate", help="Activate a preset and write routing_runtime.json")
    activate_p.add_argument("--preset", required=True, help="Preset to activate")
    for sub in (status_p, validate_p, activate_p):
        sub.add_argument("--user-bago", default=None, help="Path to user workspace root (default: ~/.gabo)")
        sub.add_argument("--repo", default=None, help="Path to BAGO repo root (default: parent of user-bago)")
        sub.add_argument("--json", action="store_true", help="Emit JSON output")
        sub.add_argument("--tolerant", action="store_true", help="Exit 0 even on invalid contract")

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="bago")
    build_subparser(parser)
    args = parser.parse_args(argv)
    if args.command != "route":
        parser.print_help()
        return 0
    cmd = getattr(args, "route_cmd", "status") or "status"
    if cmd == "status" or cmd is None:
        return cmd_route_status(args)
    if cmd == "validate":
        return cmd_route_validate(args)
    if cmd == "activate":
        return cmd_route_activate(args)
    print(f"unknown subcommand: {cmd}")
    return 1

if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from bago.routing_runtime import active_settings, apply_preset, load_presets  # type: ignore


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Gestiona presets estaticos del runtime BAGO")
    sub = parser.add_subparsers(dest="cmd")
    sub.add_parser("list")
    sub.add_parser("show")
    apply_p = sub.add_parser("apply")
    apply_p.add_argument("name")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--test", action="store_true")
    args = parser.parse_args(argv)

    presets = load_presets()
    if args.test:
        print("preset self-test OK" if presets else "preset self-test FAIL")
        return 0 if presets else 1

    if args.cmd == "apply":
        apply_preset(args.name)

    settings = active_settings()
    if args.cmd == "list":
        payload = [{"name": name, **info} for name, info in presets.items()]
        if args.json:
            print(json.dumps(payload, indent=2, ensure_ascii=False))
        else:
            for item in payload:
                print(f"{item['name']}: {item.get('description', '')}")
        return 0

    current = settings["preset_name"]
    payload = {"active": current, "preset": presets.get(current, {})}
    if args.json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        print(current)
        desc = payload["preset"].get("description", "")
        if desc:
            print(desc)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

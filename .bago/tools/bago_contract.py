#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from bago.routing_runtime import clear_contract, infer_contract, load_runtime, set_contract  # type: ignore


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Gestiona el contrato de salida BAGO")
    sub = parser.add_subparsers(dest="cmd")
    sub.add_parser("show")
    set_p = sub.add_parser("set")
    set_p.add_argument("text")
    sub.add_parser("clear")
    infer_p = sub.add_parser("infer")
    infer_p.add_argument("--task", required=True)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--test", action="store_true")
    args = parser.parse_args(argv)

    if args.test:
        print("contract self-test OK")
        return 0

    if args.cmd == "set":
        set_contract(args.text, source="explicit")
    elif args.cmd == "clear":
        clear_contract()

    if args.cmd == "infer":
        text = infer_contract(args.task)
        if args.json:
            print(json.dumps({"task": args.task, "contract": text}, indent=2, ensure_ascii=False))
        else:
            print(text or "(sin contrato inferido)")
        return 0

    runtime = load_runtime()
    payload = runtime.get("contract", {"text": "", "source": "none"})
    if args.json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        print(payload.get("text", "") or "(sin contrato activo)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

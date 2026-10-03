"""Session-bound entry point for governed BAGO runtime control.

The model tool is dispatched by ``ToolRegistry`` to ``SessionManager`` and
the ``ExecutionGateway``. Running this module directly is intentionally
refused because it has no trusted session, world-state authority, or Permit.
"""
from __future__ import annotations

import argparse
import json


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--action", choices=("start", "start_and_open", "status", "stop"), default="start_and_open")
    args = parser.parse_args()
    print(json.dumps({
        "ok": False,
        "action": args.action,
        "error": "runtime-control requiere una SessionManager activa; el adapter del Gateway ejecuta la acción.",
        "gateway_owned": True,
    }, ensure_ascii=False))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

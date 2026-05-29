"""
CLI mínimo para BAGO Truth Gate.

Uso:
  python -m bago.truth_cli run --purpose "baseline tests" -- "python -m pytest .bago/tools/tests -q"
  python -m bago.truth_cli claim --kind test_pass --text "tests pasan" --conclusion "validado" --evidence ev_xxx
  python -m bago.truth_cli close
  python -m bago.truth_cli report
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .truth_gate import (
    TruthGateError,
    add_claim,
    assert_can_close_task,
    render_trace_report,
    run_command,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser("bago truth")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_run = sub.add_parser("run")
    p_run.add_argument("--purpose", required=True)
    p_run.add_argument("--cwd", default=None)
    p_run.add_argument("--timeout", type=int, default=120)
    p_run.add_argument("--allow-fail", action="store_true")
    p_run.add_argument("command", nargs=argparse.REMAINDER)

    p_claim = sub.add_parser("claim")
    p_claim.add_argument("--kind", default="generic")
    p_claim.add_argument("--text", required=True)
    p_claim.add_argument("--conclusion", required=True)
    p_claim.add_argument("--evidence", action="append", default=[])

    sub.add_parser("close")
    sub.add_parser("report")

    args = parser.parse_args(argv)

    try:
        if args.cmd == "run":
            command = " ".join(args.command).strip()
            if command.startswith("-- "):
                command = command[3:]
            if not command:
                raise TruthGateError("Falta comando después de --")
            ev = run_command(
                command,
                cwd=args.cwd,
                purpose=args.purpose,
                timeout=args.timeout,
                allow_fail=args.allow_fail,
            )
            print(ev.evidence_id)
            return 0

        if args.cmd == "claim":
            cl = add_claim(
                args.text,
                conclusion=args.conclusion,
                evidence_ids=args.evidence,
                kind=args.kind,
            )
            print(cl.claim_id)
            return 0

        if args.cmd == "close":
            assert_can_close_task()
            print("TRUTH_GATE_OK")
            return 0

        if args.cmd == "report":
            print(render_trace_report())
            return 0

    except TruthGateError as e:
        print(f"TRUTH_GATE_BLOCKED: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

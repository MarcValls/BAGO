#!/usr/bin/env python3
"""bago_music.py — BAGO music score pipeline router.

This is the BAGO-facing tool entrypoint for music-score workflows.

It exposes the first operational subcommands:

  python3 .bago/tools/bago_music.py plan ...
  python3 .bago/tools/bago_music.py convert ...
  python3 .bago/tools/bago_music.py run ...

The current implementation wires the existing planning and input-to-MusicXML
conversion stages. Transposition, validation, and rendering subcommands are
reserved and return honest "not implemented yet" messages until their dedicated
modules exist.

Design rule:
  Never claim semantic music transposition unless the pipeline has structured
  notation data and has validated that only the requested target changed.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


TOOLS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TOOLS_DIR.parent.parent
PLAN_SCRIPT = TOOLS_DIR / "music_transpose_plan.py"
CONVERT_SCRIPT = TOOLS_DIR / "music_to_musicxml_pipeline.py"


EXIT_USAGE = 1
EXIT_CONVERSION = 2
EXIT_TARGET_AMBIGUITY = 3
EXIT_TRANSPOSITION_NOT_IMPLEMENTED = 4
EXIT_VALIDATION_NOT_IMPLEMENTED = 5
EXIT_RENDER_NOT_IMPLEMENTED = 6


def run_python(script: Path, args: list[str]) -> int:
    if not script.exists():
        print(f"Missing script: {script}", file=sys.stderr)
        return EXIT_USAGE
    proc = subprocess.run([sys.executable, str(script), *args], cwd=str(REPO_ROOT))
    return proc.returncode


def cmd_plan(args: argparse.Namespace) -> int:
    delegated = ["--input", args.input]
    if args.target:
        delegated += ["--target", args.target]
    if args.to:
        delegated += ["--to", args.to]
    if args.interval:
        delegated += ["--interval", args.interval]
    if args.instrument:
        delegated += ["--instrument", args.instrument]
    if args.preserve_sounding_pitch:
        delegated.append("--preserve-sounding-pitch")
    if args.json:
        delegated.append("--json")
    if args.output:
        delegated += ["--output", args.output]
    return run_python(PLAN_SCRIPT, delegated)


def cmd_convert(args: argparse.Namespace) -> int:
    delegated = ["--input", args.input, "--out-dir", args.out_dir]
    if args.execute:
        delegated.append("--execute")
    if args.json:
        delegated.append("--json")
    if args.report:
        delegated += ["--report", args.report]
    return run_python(CONVERT_SCRIPT, delegated)


def cmd_run(args: argparse.Namespace) -> int:
    """Run the available safe stages of the end-to-end pipeline.

    Current state:
      1. Plan target and operation.
      2. Convert input toward MusicXML if possible.
      3. Stop before transposition because the MusicXML transposer is not yet implemented.
    """
    print("BAGO music run")
    print("==============")
    print("Stage 1/2: planning")
    plan_args = argparse.Namespace(
        input=args.input,
        target=args.target,
        to=args.to,
        interval=args.interval,
        instrument=args.instrument,
        preserve_sounding_pitch=args.preserve_sounding_pitch,
        json=False,
        output=str(Path(args.out_dir) / "pipeline_plan.txt"),
    )
    rc = cmd_plan(plan_args)
    if rc != 0:
        return rc

    print("Stage 2/2: converting input toward MusicXML")
    convert_args = argparse.Namespace(
        input=args.input,
        out_dir=args.out_dir,
        execute=args.execute_conversion,
        json=False,
        report=str(Path(args.out_dir) / "conversion_report.json"),
    )
    rc = cmd_convert(convert_args)
    if rc != 0:
        return EXIT_CONVERSION

    print()
    print("Stopped before transposition.")
    print("Reason: musicxml_transpose.py is not implemented yet.")
    print("Next module to build: .bago/tools/musicxml_transpose.py")
    print()
    print("Generated planning/conversion artifacts are in:")
    print(f"- {args.out_dir}")
    return EXIT_TRANSPOSITION_NOT_IMPLEMENTED


def not_implemented(name: str, exit_code: int) -> int:
    print(f"bago music {name}: not implemented yet")
    print("Next integration step: build the dedicated MusicXML module for this stage.")
    return exit_code


def cmd_inventory(_: argparse.Namespace) -> int:
    return not_implemented("inventory", EXIT_TARGET_AMBIGUITY)


def cmd_transpose(_: argparse.Namespace) -> int:
    return not_implemented("transpose", EXIT_TRANSPOSITION_NOT_IMPLEMENTED)


def cmd_validate(_: argparse.Namespace) -> int:
    return not_implemented("validate", EXIT_VALIDATION_NOT_IMPLEMENTED)


def cmd_render(_: argparse.Namespace) -> int:
    return not_implemented("render", EXIT_RENDER_NOT_IMPLEMENTED)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="bago music",
        description="BAGO music score pipeline: plan, convert to MusicXML, and later transpose/validate/render.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    plan = sub.add_parser("plan", help="Create an auditable semantic transposition plan.")
    plan.add_argument("--input", required=True)
    plan.add_argument("--target", default="unspecified")
    plan.add_argument("--to", default=None)
    plan.add_argument("--interval", default=None)
    plan.add_argument("--instrument", default=None)
    plan.add_argument("--preserve-sounding-pitch", action="store_true")
    plan.add_argument("--json", action="store_true")
    plan.add_argument("--output", default=None)
    plan.set_defaults(func=cmd_plan)

    convert = sub.add_parser("convert", help="Classify input and convert/recover MusicXML when possible.")
    convert.add_argument("--input", required=True)
    convert.add_argument("--out-dir", default="build/musicxml")
    convert.add_argument("--execute", action="store_true", help="Run external conversion tools when available.")
    convert.add_argument("--json", action="store_true")
    convert.add_argument("--report", default=None)
    convert.set_defaults(func=cmd_convert)

    run = sub.add_parser("run", help="Run currently available pipeline stages: plan + convert.")
    run.add_argument("--input", required=True)
    run.add_argument("--target", default="unspecified")
    run.add_argument("--to", default=None)
    run.add_argument("--interval", default=None)
    run.add_argument("--instrument", default=None)
    run.add_argument("--preserve-sounding-pitch", action="store_true")
    run.add_argument("--out-dir", default="build/music")
    run.add_argument("--execute-conversion", action="store_true")
    run.set_defaults(func=cmd_run)

    inventory = sub.add_parser("inventory", help="Reserved: inspect MusicXML parts/staves/voices/measures.")
    inventory.set_defaults(func=cmd_inventory)

    transpose = sub.add_parser("transpose", help="Reserved: transpose selected material inside MusicXML.")
    transpose.set_defaults(func=cmd_transpose)

    validate = sub.add_parser("validate", help="Reserved: validate target-only changes and rhythmic integrity.")
    validate.set_defaults(func=cmd_validate)

    render = sub.add_parser("render", help="Reserved: render MusicXML to PDF/SVG/PNG.")
    render.set_defaults(func=cmd_render)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())

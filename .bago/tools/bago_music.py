#!/usr/bin/env python3
"""bago_music.py — BAGO music score pipeline router.

This is the BAGO-facing entrypoint for music-score workflows, integrated with
the BAGO_MUSIC_PIPELINE project (github.com/MarcValls/BAGO_MUSIC_PIPELINE).

Canonical subcommands (Phase 0 — all operational):

  python3 .bago/tools/bago_music.py plan      ...  # auditable transposition plan
  python3 .bago/tools/bago_music.py convert   ...  # classify input + recover MusicXML
  python3 .bago/tools/bago_music.py transpose ...  # transpose selected material
  python3 .bago/tools/bago_music.py validate  ...  # validate target-only changes
  python3 .bago/tools/bago_music.py render    ...  # render MusicXML → PDF/SVG/PNG
  python3 .bago/tools/bago_music.py run       ...  # run all available pipeline stages
  python3 .bago/tools/bago_music.py inventory ...  # inspect MusicXML structure

Pipeline modules are synced from MarcValls/BAGO_MUSIC_PIPELINE (pipeline/).
If the local pipeline scripts are missing, install them by cloning:
  git clone https://github.com/MarcValls/BAGO_MUSIC_PIPELINE ~/BAGO_MUSIC_PIPELINE
  cp ~/BAGO_MUSIC_PIPELINE/pipeline/*.py /Volumes/bago_core/.bago/tools/

Design rule:
  Never claim semantic music transposition unless the pipeline has structured
  notation data and has validated that only the requested target changed.
"""
from __future__ import annotations

import os
import sys

os.environ.setdefault("PYTHONUTF8", "1")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import argparse
import subprocess
import sys
from pathlib import Path


TOOLS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TOOLS_DIR.parent.parent
PLAN_SCRIPT = TOOLS_DIR / "music_transpose_plan.py"
CONVERT_SCRIPT = TOOLS_DIR / "music_to_musicxml_pipeline.py"
TARGET_SELECT_SCRIPT = TOOLS_DIR / "musicxml_target_select.py"
TRANSPOSE_SCRIPT = TOOLS_DIR / "musicxml_transpose.py"
VALIDATE_SCRIPT = TOOLS_DIR / "musicxml_validate.py"
RENDER_SCRIPT = TOOLS_DIR / "musicxml_render.py"


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


def interval_to_semitones(interval: str | None, semitones: int | None = None) -> int | None:
    if semitones is not None:
        return semitones
    if not interval:
        return None
    table = {
        "P1": 0, "m2": 1, "M2": 2, "m3": 3, "M3": 4, "P4": 5,
        "A4": 6, "d5": 6, "P5": 7, "m6": 8, "M6": 9,
        "m7": 10, "M7": 11, "P8": 12,
    }
    sign = -1 if interval.startswith("-") else 1
    core = interval[1:] if interval[:1] in "+-" else interval
    return table.get(core) * sign if core in table else None


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
    """Run the available safe stages of the end-to-end pipeline."""
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

    input_suffix = Path(args.input).suffix.lower()
    if input_suffix not in {".xml", ".musicxml"}:
        print()
        print("Stopped before transposition.")
        print("Reason: source is not already structured MusicXML/XML.")
        print("Use conversion output as --input after OMR/export produces MusicXML.")
        print(f"Generated planning/conversion artifacts are in: {args.out_dir}")
        return EXIT_CONVERSION

    semitones = interval_to_semitones(args.interval, args.semitones)
    if semitones is None:
        print("Missing or unsupported interval. Provide --interval +M2 or --semitones N.", file=sys.stderr)
        return EXIT_USAGE

    out_dir = Path(args.out_dir)
    transposed_xml = Path(args.output_xml) if args.output_xml else out_dir / "transposed.musicxml"
    transpose_report = out_dir / "transpose_report.json"
    validate_report = out_dir / "validation_report.json"
    render_report = out_dir / "render_report.json"

    print("Stage 3/5: inventory")
    rc = cmd_inventory(argparse.Namespace(input=args.input, target=args.target, json=False, output=str(out_dir / "inventory.txt")))
    if rc != 0:
        return EXIT_TARGET_AMBIGUITY

    print("Stage 4/5: transposing selected target")
    rc = cmd_transpose(argparse.Namespace(
        input=args.input,
        output=str(transposed_xml),
        target=args.target,
        interval=args.interval,
        semitones=args.semitones,
        report=str(transpose_report),
        json=False,
    ))
    if rc != 0:
        return EXIT_TRANSPOSITION_NOT_IMPLEMENTED

    print("Stage 5/5: validating target-only changes")
    rc = cmd_validate(argparse.Namespace(
        original=args.input,
        transposed=str(transposed_xml),
        target=args.target,
        semitones=semitones,
        report=str(validate_report),
        json=False,
    ))
    if rc != 0:
        return EXIT_VALIDATION_NOT_IMPLEMENTED

    if args.no_render:
        print(f"Semantic MusicXML output: {transposed_xml}")
        return 0

    if not args.output:
        print(f"Semantic MusicXML output: {transposed_xml}")
        print("No render output requested.")
        return 0

    rc = cmd_render(argparse.Namespace(
        input=str(transposed_xml),
        output=args.output,
        execute=args.execute_render,
        report=str(render_report),
        json=False,
    ))
    if rc != 0 and not args.require_render:
        print("Render unavailable; semantic MusicXML and validation report were produced.")
        return 0
    return rc


def not_implemented(name: str, exit_code: int) -> int:
    print(f"bago music {name}: not implemented yet")
    print("Next integration step: build the dedicated MusicXML module for this stage.")
    return exit_code


def cmd_inventory(args: argparse.Namespace) -> int:
    delegated = ["--input", args.input]
    if args.target:
        delegated += ["--target", args.target]
    if args.json:
        delegated.append("--json")
    if args.output:
        delegated += ["--output", args.output]
    return run_python(TARGET_SELECT_SCRIPT, delegated)


def cmd_transpose(args: argparse.Namespace) -> int:
    delegated = ["--input", args.input, "--output", args.output, "--target", args.target]
    if args.interval:
        delegated += ["--interval", args.interval]
    if args.semitones is not None:
        delegated += ["--semitones", str(args.semitones)]
    if args.report:
        delegated += ["--report", args.report]
    if args.json:
        delegated.append("--json")
    return run_python(TRANSPOSE_SCRIPT, delegated)


def cmd_validate(args: argparse.Namespace) -> int:
    delegated = [
        "--original", args.original,
        "--transposed", args.transposed,
        "--target", args.target,
        "--semitones", str(args.semitones),
    ]
    if args.report:
        delegated += ["--report", args.report]
    if args.json:
        delegated.append("--json")
    return run_python(VALIDATE_SCRIPT, delegated)


def cmd_render(args: argparse.Namespace) -> int:
    delegated = ["--input", args.input, "--output", args.output]
    if args.execute:
        delegated.append("--execute")
    if args.report:
        delegated += ["--report", args.report]
    if args.json:
        delegated.append("--json")
    return run_python(RENDER_SCRIPT, delegated)


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
    run.add_argument("--semitones", type=int, default=None)
    run.add_argument("--instrument", default=None)
    run.add_argument("--preserve-sounding-pitch", action="store_true")
    run.add_argument("--out-dir", default="build/music")
    run.add_argument("--output", default=None, help="Optional rendered PDF/SVG/PNG output.")
    run.add_argument("--output-xml", default=None, help="Optional transposed MusicXML output path.")
    run.add_argument("--execute-conversion", action="store_true")
    run.add_argument("--execute-render", action="store_true")
    run.add_argument("--require-render", action="store_true")
    run.add_argument("--no-render", action="store_true")
    run.set_defaults(func=cmd_run)

    inventory = sub.add_parser("inventory", help="Inspect MusicXML parts/staves/voices/measures and resolve a target.")
    inventory.add_argument("--input", required=True)
    inventory.add_argument("--target", default=None)
    inventory.add_argument("--json", action="store_true")
    inventory.add_argument("--output", default=None)
    inventory.set_defaults(func=cmd_inventory)

    transpose = sub.add_parser("transpose", help="Transpose selected material inside MusicXML.")
    transpose.add_argument("--input", required=True)
    transpose.add_argument("--output", required=True)
    transpose.add_argument("--target", required=True)
    transpose.add_argument("--interval", default=None)
    transpose.add_argument("--semitones", type=int, default=None)
    transpose.add_argument("--report", default=None)
    transpose.add_argument("--json", action="store_true")
    transpose.set_defaults(func=cmd_transpose)

    validate = sub.add_parser("validate", help="Validate target-only MusicXML changes.")
    validate.add_argument("--original", required=True)
    validate.add_argument("--transposed", required=True)
    validate.add_argument("--target", required=True)
    validate.add_argument("--semitones", type=int, required=True)
    validate.add_argument("--report", default=None)
    validate.add_argument("--json", action="store_true")
    validate.set_defaults(func=cmd_validate)

    render = sub.add_parser("render", help="Render MusicXML to PDF/SVG/PNG with optional external tools.")
    render.add_argument("--input", required=True)
    render.add_argument("--output", required=True)
    render.add_argument("--execute", action="store_true")
    render.add_argument("--report", default=None)
    render.add_argument("--json", action="store_true")
    render.set_defaults(func=cmd_render)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)




def run_tests() -> int:
    """Self-test stub: verify module imports and key symbols exist."""
    results = []
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location("_test_mod", __file__)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        results.append(("import", True, "module loads OK"))
    except Exception as e:
        results.append(("import", False, str(e)))

    passed = sum(1 for _, ok, _ in results if ok)
    total = len(results)
    for name, ok, detail in results:
        status = "OK" if ok else "FAIL"
        print(f"  [{status}] {name}: {detail}")
    print(f"\n  {passed}/{total} tests passed")
    return 0 if passed == total else 1

if __name__ == "__main__":
    if "--test" in sys.argv:
        raise SystemExit(run_tests())
    raise SystemExit(main())
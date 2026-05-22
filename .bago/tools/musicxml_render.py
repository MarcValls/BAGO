#!/usr/bin/env python3
"""musicxml_render.py - render MusicXML with optional external tools."""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path


@dataclass
class RenderReport:
    input_path: str
    output_path: str
    renderer: str | None
    command: list[str] = field(default_factory=list)
    exit_code: int | None = None
    output_exists: bool = False
    warnings: list[str] = field(default_factory=list)


def find_musescore() -> str | None:
    names = ["musescore", "mscore", "MuseScore4", "MuseScore3"]
    for name in names:
        found = shutil.which(name)
        if found:
            return found
    return None


def find_verovio() -> str | None:
    return shutil.which("verovio")


def render(input_path: str, output_path: str, execute: bool) -> RenderReport:
    suffix = Path(output_path).suffix.lower()
    report = RenderReport(input_path=input_path, output_path=output_path, renderer=None)
    if suffix in {".pdf", ".png"}:
        renderer = find_musescore()
        if renderer:
            report.renderer = "musescore"
            report.command = [renderer, input_path, "-o", output_path]
        else:
            report.warnings.append("MuseScore CLI not found; cannot render PDF/PNG.")
            return report
    elif suffix == ".svg":
        renderer = find_verovio()
        if renderer:
            report.renderer = "verovio"
            report.command = [renderer, input_path, "-o", output_path]
        else:
            mscore = find_musescore()
            if mscore:
                report.renderer = "musescore"
                report.command = [mscore, input_path, "-o", output_path]
            else:
                report.warnings.append("No SVG renderer found. Install Verovio or MuseScore.")
                return report
    else:
        report.warnings.append(f"Unsupported render output extension: {suffix}")
        return report

    report.warnings.append("Rendering may re-engrave layout; compare preview before editorial use.")
    if not execute:
        report.warnings.append("Dry run only. Add --execute to run renderer.")
        return report
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    proc = subprocess.run(report.command, capture_output=True, text=True)
    report.exit_code = proc.returncode
    report.output_exists = Path(output_path).exists()
    if proc.returncode != 0:
        report.warnings.append((proc.stderr or proc.stdout or "Renderer failed.").strip()[:1000])
    return report


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render MusicXML to PDF/SVG/PNG with optional external tools.")
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--report", default=None)
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        report = render(args.input, args.output, args.execute)
        payload = json.dumps(asdict(report), indent=2, ensure_ascii=False) + "\n"
        if args.report:
            Path(args.report).parent.mkdir(parents=True, exist_ok=True)
            Path(args.report).write_text(payload, encoding="utf-8")
        if args.json:
            print(payload, end="")
        else:
            print(f"Renderer: {report.renderer or 'unavailable'}")
            print(f"Output exists: {report.output_exists}")
            if args.report:
                print(f"Report: {args.report}")
        if report.renderer is None:
            return 6
        if args.execute and not report.output_exists:
            return 6
        return 0
    except Exception as exc:
        print(f"MusicXML render failed: {exc}", file=sys.stderr)
        return 6


if __name__ == "__main__":
    raise SystemExit(main())

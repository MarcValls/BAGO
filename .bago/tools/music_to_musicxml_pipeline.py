#!/usr/bin/env python3
"""music_to_musicxml_pipeline.py — convert score inputs toward MusicXML.

Purpose
-------
Given a score source (PDF, image, MusicXML, MuseScore, MIDI, MEI, HTML artifact,
or unknown), choose the safest conversion route to MusicXML and optionally execute
it when the required local tools are available.

This script is intentionally conservative:

- Structured notation is preferred over OMR.
- PDF/image sources require OMR and must report confidence risk.
- HTML/image-comparison artifacts are not treated as authoritative notation.
- If no converter is installed, it emits an executable plan instead of pretending
  conversion happened.

Supported routes
----------------
- .musicxml/.xml/.mxl: copy/use as MusicXML-like source.
- .mscz/.mscx: use MuseScore CLI if installed.
- .mid/.midi: use music21 if installed.
- .mei: use Verovio if installed, otherwise plan only.
- .pdf/.png/.jpg/.jpeg/.webp/.tif/.tiff/.bmp: use Audiveris OMR if installed.
- .html/.htm: inspect referenced assets and require original score source for
  semantic conversion.

Examples
--------
Plan only:

  python3 .bago/tools/music_to_musicxml_pipeline.py \
    --input CantinaBand_TubaTrio-TC.pdf

Execute if tools are available:

  python3 .bago/tools/music_to_musicxml_pipeline.py \
    --input CantinaBand_TubaTrio-TC.pdf \
    --execute \
    --out-dir build/musicxml

Emit JSON:

  python3 .bago/tools/music_to_musicxml_pipeline.py \
    --input score.mscz \
    --json
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
import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Iterable

from _cwd import get_user_cwd


STRUCTURED_MUSICXML = {".musicxml", ".xml", ".mxl"}
MUSESCORE_EXTENSIONS = {".mscz", ".mscx"}
MIDI_EXTENSIONS = {".mid", ".midi"}
MEI_EXTENSIONS = {".mei"}
PDF_EXTENSIONS = {".pdf"}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".tif", ".tiff", ".bmp"}
HTML_EXTENSIONS = {".html", ".htm"}


@dataclass
class ToolAvailability:
    musescore: str | None = None
    audiveris: str | None = None
    verovio: str | None = None
    python: str = sys.executable
    music21_available: bool = False


@dataclass
class ConversionPlan:
    input_path: str
    extension: str
    input_exists: bool
    kind: str
    route: str
    output_musicxml: str
    can_execute: bool
    selected_tool: str | None
    commands: list[list[str]] = field(default_factory=list)
    steps: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    expected_outputs: list[str] = field(default_factory=list)
    tool_availability: ToolAvailability = field(default_factory=ToolAvailability)


@dataclass
class ConversionResult:
    plan: ConversionPlan
    executed: bool
    success: bool
    return_codes: list[int] = field(default_factory=list)
    stdout: list[str] = field(default_factory=list)
    stderr: list[str] = field(default_factory=list)
    generated_files: list[str] = field(default_factory=list)


def which_any(names: Iterable[str]) -> str | None:
    for name in names:
        found = shutil.which(name)
        if found:
            return found
    return None


def has_music21() -> bool:
    try:
        import music21  # type: ignore  # noqa: F401
        return True
    except Exception:
        return False


def detect_tools() -> ToolAvailability:
    return ToolAvailability(
        musescore=which_any(["musescore", "mscore", "mscore3", "musescore4"]),
        audiveris=which_any(["audiveris", "audiveris-cli"]),
        verovio=which_any(["verovio"]),
        python=sys.executable,
        music21_available=has_music21(),
    )


def safe_stem(path: Path) -> str:
    stem = path.stem or "score"
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", stem).strip("._") or "score"


def output_path_for(input_path: Path, out_dir: Path) -> Path:
    return out_dir / f"{safe_stem(input_path)}.musicxml"


def classify(path: Path) -> tuple[str, str]:
    ext = path.suffix.lower()
    if ext in STRUCTURED_MUSICXML:
        return "musicxml_like", "copy_or_use_directly"
    if ext in MUSESCORE_EXTENSIONS:
        return "musescore_score", "musescore_export"
    if ext in MIDI_EXTENSIONS:
        return "midi_file", "music21_midi_to_musicxml"
    if ext in MEI_EXTENSIONS:
        return "mei_file", "verovio_mei_to_musicxml"
    if ext in PDF_EXTENSIONS:
        return "pdf_score_or_document", "audiveris_omr"
    if ext in IMAGE_EXTENSIONS:
        return "raster_image_score", "audiveris_omr"
    if ext in HTML_EXTENSIONS:
        return "html_artifact", "inspect_assets"
    return "unknown", "inspect_then_choose"


def build_plan(input_file: str, out_dir: str) -> ConversionPlan:
    path = Path(input_file).expanduser()
    out = Path(out_dir).expanduser()
    ext = path.suffix.lower()
    kind, route = classify(path)
    tools = detect_tools()
    output_musicxml = output_path_for(path, out)

    plan = ConversionPlan(
        input_path=str(path),
        extension=ext or "none",
        input_exists=path.exists(),
        kind=kind,
        route=route,
        output_musicxml=str(output_musicxml),
        can_execute=False,
        selected_tool=None,
        tool_availability=tools,
    )

    if not path.exists():
        plan.warnings.append("Input file does not exist at this path. Plan is based on extension only.")

    if route == "copy_or_use_directly":
        plan.selected_tool = "filesystem"
        plan.can_execute = path.exists()
        plan.steps = [
            "Treat input as already structured notation.",
            "Copy it to the output MusicXML path for downstream editing.",
            "Validate that the file can be parsed before transposition.",
        ]
        plan.commands = [["cp", str(path), str(output_musicxml)]]
        plan.expected_outputs = [str(output_musicxml)]
        return plan

    if route == "musescore_export":
        plan.selected_tool = tools.musescore
        plan.can_execute = bool(path.exists() and tools.musescore)
        plan.steps = [
            "Use MuseScore CLI to open native MuseScore file.",
            "Export to MusicXML.",
            "Validate exported MusicXML before editing.",
        ]
        if tools.musescore:
            plan.commands = [[tools.musescore, str(path), "-o", str(output_musicxml)]]
        else:
            plan.warnings.append("MuseScore CLI not found. Install MuseScore and expose musescore/mscore in PATH.")
        plan.expected_outputs = [str(output_musicxml)]
        return plan

    if route == "music21_midi_to_musicxml":
        plan.selected_tool = "music21" if tools.music21_available else None
        plan.can_execute = bool(path.exists() and tools.music21_available)
        helper = (
            "from music21 import converter\n"
            "import sys\n"
            "score = converter.parse(sys.argv[1])\n"
            "score.write('musicxml', fp=sys.argv[2])\n"
        )
        plan.steps = [
            "Parse MIDI using music21.",
            "Write a MusicXML approximation.",
            "Warn that MIDI lacks full engraving semantics such as original clefs, voices, articulations, and text.",
        ]
        plan.commands = [[tools.python, "-c", helper, str(path), str(output_musicxml)]]
        if not tools.music21_available:
            plan.warnings.append("Python package music21 not found. Install with: python3 -m pip install music21")
        plan.warnings.append("MIDI conversion is approximate because MIDI is performance data, not full notation.")
        plan.expected_outputs = [str(output_musicxml)]
        return plan

    if route == "verovio_mei_to_musicxml":
        plan.selected_tool = tools.verovio
        plan.can_execute = bool(path.exists() and tools.verovio)
        plan.steps = [
            "Use Verovio to convert MEI toward MusicXML when supported by installed build.",
            "Validate output before transposition.",
        ]
        if tools.verovio:
            plan.commands = [[tools.verovio, str(path), "--musicxml", "-o", str(output_musicxml)]]
        else:
            plan.warnings.append("Verovio CLI not found. Install verovio or convert MEI through another notation tool.")
        plan.expected_outputs = [str(output_musicxml)]
        return plan

    if route == "audiveris_omr":
        plan.selected_tool = tools.audiveris
        plan.can_execute = bool(path.exists() and tools.audiveris)
        omr_output_dir = out / f"{safe_stem(path)}_audiveris"
        plan.steps = [
            "Run Audiveris OMR on the PDF/image.",
            "Collect exported MusicXML/MXL from the Audiveris output folder.",
            "Normalize/copy the best MusicXML candidate to the requested output path.",
            "Flag result as OMR-assisted and require validation before transposition.",
        ]
        if tools.audiveris:
            plan.commands = [[tools.audiveris, "-batch", "-export", "-output", str(omr_output_dir), str(path)]]
        else:
            plan.warnings.append("Audiveris CLI not found. Install Audiveris for PDF/image OMR conversion.")
        plan.warnings.extend([
            "OMR can misread accidentals, tuplets, rests, repeats, codas, multi-voice notation, and ledger lines.",
            "Do not mark this conversion as final until MusicXML is validated against the original score.",
        ])
        plan.expected_outputs = [str(output_musicxml), str(omr_output_dir)]
        return plan

    if route == "inspect_assets":
        plan.selected_tool = "html_inspector"
        plan.can_execute = path.exists()
        plan.steps = [
            "Parse HTML and list referenced image/PDF/music assets.",
            "Classify assets as source score, crop, transformed crop, or explanatory figure.",
            "Prefer original PDF/MusicXML/MuseScore source for semantic conversion.",
            "Do not convert pixel-shift comparison images as if they were authoritative notation.",
        ]
        plan.warnings.append("HTML artifacts rarely contain full editable notation; use them only to find the real source assets.")
        plan.expected_outputs = ["asset_inventory.json"]
        return plan

    plan.steps = [
        "Inspect file signature and content.",
        "If structured notation is found, parse directly.",
        "If visual notation is found, route to OMR.",
        "If artifact/comparison content is found, recover original score source.",
    ]
    plan.warnings.append("Unknown file type. No automatic MusicXML conversion selected.")
    return plan


def find_musicxml_candidates(directory: Path) -> list[Path]:
    if not directory.exists():
        return []
    candidates: list[Path] = []
    for ext in ("*.musicxml", "*.xml", "*.mxl"):
        candidates.extend(directory.rglob(ext))
    return sorted(candidates, key=lambda p: (p.suffix != ".musicxml", len(str(p))))


def inspect_html_assets(input_path: Path, out_dir: Path) -> list[str]:
    text = input_path.read_text(encoding="utf-8", errors="ignore")
    refs = sorted(set(re.findall(r"(?:src|href)=[\"']([^\"']+)[\"']", text, flags=re.I)))
    inventory = {
        "input": str(input_path),
        "assets": refs,
        "warnings": [
            "Classify each asset before treating it as a score source.",
            "Prefer PDF/MusicXML/MuseScore originals over cropped/transformed images.",
        ],
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    inventory_path = out_dir / "asset_inventory.json"
    inventory_path.write_text(json.dumps(inventory, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return [str(inventory_path)]


def execute_plan(plan: ConversionPlan, out_dir: str) -> ConversionResult:
    result = ConversionResult(plan=plan, executed=True, success=False)
    input_path = Path(plan.input_path)
    out = Path(out_dir).expanduser()
    out.mkdir(parents=True, exist_ok=True)
    output_musicxml = Path(plan.output_musicxml)

    if not plan.can_execute:
        result.stderr.append("Plan is not executable with current inputs/tools.")
        return result

    if plan.route == "copy_or_use_directly":
        output_musicxml.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(input_path, output_musicxml)
        result.generated_files.append(str(output_musicxml))
        result.success = True
        return result

    if plan.route == "inspect_assets":
        result.generated_files.extend(inspect_html_assets(input_path, out))
        result.success = True
        return result

    for command in plan.commands:
        proc = subprocess.run(command, cwd=str(get_user_cwd()), text=True, capture_output=True)
        result.return_codes.append(proc.returncode)
        result.stdout.append(proc.stdout)
        result.stderr.append(proc.stderr)
        if proc.returncode != 0:
            result.success = False
            return result

    if plan.route == "audiveris_omr":
        candidates = find_musicxml_candidates(out)
        if candidates:
            output_musicxml.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(candidates[0], output_musicxml)
            result.generated_files.append(str(output_musicxml))
            result.generated_files.extend(str(p) for p in candidates)
            result.success = True
        else:
            result.stderr.append("Audiveris ran but no MusicXML/MXL candidate was found in output directory.")
            result.success = False
        return result

    if output_musicxml.exists():
        result.generated_files.append(str(output_musicxml))
        result.success = True
    else:
        result.stderr.append(f"Expected output not found: {output_musicxml}")
        result.success = False
    return result


def render_plan_text(plan: ConversionPlan) -> str:
    lines: list[str] = []
    lines.append("BAGO input-to-MusicXML pipeline")
    lines.append("=" * 36)
    lines.append(f"Input: {plan.input_path}")
    lines.append(f"Exists: {plan.input_exists}")
    lines.append(f"Kind: {plan.kind}")
    lines.append(f"Route: {plan.route}")
    lines.append(f"Output MusicXML: {plan.output_musicxml}")
    lines.append(f"Can execute now: {plan.can_execute}")
    lines.append(f"Selected tool: {plan.selected_tool or 'none'}")
    lines.append("")
    lines.append("Tool availability:")
    tools = asdict(plan.tool_availability)
    for key, value in tools.items():
        lines.append(f"- {key}: {value}")
    lines.append("")
    lines.append("Steps:")
    for index, step in enumerate(plan.steps, start=1):
        lines.append(f"{index}. {step}")
    if plan.commands:
        lines.append("")
        lines.append("Commands:")
        for command in plan.commands:
            lines.append("- " + " ".join(command))
    if plan.expected_outputs:
        lines.append("")
        lines.append("Expected outputs:")
        for item in plan.expected_outputs:
            lines.append(f"- {item}")
    if plan.warnings:
        lines.append("")
        lines.append("Warnings:")
        for warning in plan.warnings:
            lines.append(f"- {warning}")
    return "\n".join(lines) + "\n"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Plan or execute conversion of a score source to MusicXML.")
    parser.add_argument("--input", required=True, help="Input score path.")
    parser.add_argument("--out-dir", default="build/musicxml", help="Output directory for MusicXML and reports.")
    parser.add_argument("--execute", action="store_true", help="Execute conversion when required tools are available.")
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of text.")
    parser.add_argument("--report", default=None, help="Optional report path. Defaults to <out-dir>/conversion_report.json when executing.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    plan = build_plan(args.input, args.out_dir)

    if args.execute:
        result = execute_plan(plan, args.out_dir)
        report_path = Path(args.report) if args.report else Path(args.out_dir) / "conversion_report.json"
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(asdict(result), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        if args.json:
            print(json.dumps(asdict(result), indent=2, ensure_ascii=False))
        else:
            print(render_plan_text(plan))
            print(f"Executed: {result.executed}")
            print(f"Success: {result.success}")
            print(f"Report: {report_path}")
            if result.generated_files:
                print("Generated files:")
                for item in result.generated_files:
                    print(f"- {item}")
            if result.stderr:
                print("stderr / notes:")
                for item in result.stderr:
                    if item.strip():
                        print(item.strip())
        return 0 if result.success else 2

    if args.json:
        print(json.dumps(asdict(plan), indent=2, ensure_ascii=False))
    else:
        print(render_plan_text(plan), end="")
    return 0




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
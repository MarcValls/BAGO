#!/usr/bin/env python3
"""music_transpose_plan.py — planning pipeline for semantic music score transposition.

This script does NOT perform OMR or final notation rendering yet. It creates a
structured, auditable plan for the correct pipeline based on the input file type,
target selection, and requested transformation.

Usage examples:

  python3 .bago/tools/music_transpose_plan.py \
    --input CantinaBand_TubaTrio-TC.pdf \
    --target "bottom staff" \
    --to "E minor"

  python3 .bago/tools/music_transpose_plan.py \
    --input score.musicxml \
    --target "staff 3 measures 1-26 including coda" \
    --interval +M2 \
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
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


STRUCTURED_EXTENSIONS = {
    ".musicxml",
    ".xml",
    ".mxl",
    ".mscz",
    ".mscx",
    ".mei",
    ".mid",
    ".midi",
}
PDF_EXTENSIONS = {".pdf"}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".tif", ".tiff", ".bmp"}
HTML_EXTENSIONS = {".html", ".htm"}


@dataclass
class SourceClassification:
    path: str
    extension: str
    kind: str
    confidence: str
    route: str
    notes: list[str] = field(default_factory=list)


@dataclass
class IntentAnalysis:
    target: str
    operation: str | None
    destination_key: str | None
    interval: str | None
    destination_clef: str | None
    instrument_profile: str | None
    preserve_sounding_pitch: bool
    ambiguities: list[str] = field(default_factory=list)
    normalized_target_hints: list[str] = field(default_factory=list)


@dataclass
class PipelinePlan:
    source: SourceClassification
    intent: IntentAnalysis
    stages: list[str]
    preservation_requirements: list[str]
    validation_gates: list[str]
    expected_outputs: list[str]
    risks: list[str]
    status: str


def classify_source(input_path: str) -> SourceClassification:
    path = Path(input_path)
    ext = path.suffix.lower()
    exists_note = []
    if input_path and not path.exists():
        exists_note.append("Input path does not exist locally; planning continues from filename/extension only.")

    if ext in STRUCTURED_EXTENSIONS:
        return SourceClassification(
            path=input_path,
            extension=ext,
            kind="structured_music_file",
            confidence="high",
            route="structured",
            notes=exists_note + ["Use direct music-structure parsing before any visual/OCR route."],
        )
    if ext in PDF_EXTENSIONS:
        return SourceClassification(
            path=input_path,
            extension=ext,
            kind="pdf_score_or_document",
            confidence="medium",
            route="omr",
            notes=exists_note + ["PDF may be vector/text/image; treat as visual notation until semantic music data is proven."],
        )
    if ext in IMAGE_EXTENSIONS:
        return SourceClassification(
            path=input_path,
            extension=ext,
            kind="raster_image_score",
            confidence="medium",
            route="image_omr",
            notes=exists_note + ["Image requires preprocessing before OMR: deskew, contrast, denoise, crop/dewarp."],
        )
    if ext in HTML_EXTENSIONS:
        return SourceClassification(
            path=input_path,
            extension=ext,
            kind="html_artifact",
            confidence="medium",
            route="artifact_inspection",
            notes=exists_note + ["HTML with score crops is an artifact, not reliable semantic notation."],
        )
    return SourceClassification(
        path=input_path,
        extension=ext or "none",
        kind="unknown",
        confidence="low",
        route="inspect_then_choose",
        notes=exists_note + ["Unknown extension; inspect file before choosing structured, OMR, or artifact route."],
    )


def _contains_any(text: str, terms: list[str]) -> bool:
    t = text.lower()
    return any(term.lower() in t for term in terms)


def analyze_intent(args: argparse.Namespace) -> IntentAnalysis:
    target = args.target or "unspecified"
    target_l = target.lower()
    destination = args.to
    operation = "transpose" if (destination or args.interval or args.instrument) else None
    ambiguities: list[str] = []
    hints: list[str] = []

    if _contains_any(target_l, ["bottom", "lower", "lowest", "abajo", "inferior"]):
        hints.append("Likely target: bottom staff / lowest part / last visible staff in each system.")
    if _contains_any(target_l, ["third", "3rd", "tercera", "tercer"]):
        hints.append("Potential target: third staff OR voice index 3; confirm if both exist.")
    if _contains_any(target_l, ["bass clef", "clave de fa", "f clef"]):
        hints.append("Bass clef detected as target descriptor; this is a clef, not a key.")

    destination_key = destination
    destination_clef = None
    if destination and _contains_any(destination, ["clef", "clave"]):
        destination_clef = destination
        destination_key = None

    if destination and _contains_any(destination, ["bass clef", "clave de fa", "f clef"]):
        ambiguities.append("Destination mentions bass/F clef. Clef rewrite is different from key transposition.")
    if destination and _contains_any(destination, ["minor", "major", "menor", "mayor"]):
        ambiguities.append("Destination appears to be a key. Original key/desired interval must be known to compute exact transposition.")
    if target == "unspecified":
        ambiguities.append("Target staff/voice/part/range is unspecified.")
    if not operation:
        ambiguities.append("Transposition operation is unspecified: provide --to, --interval, or --instrument.")
    if _contains_any(target_l, ["voice", "voz"]) and _contains_any(target_l, ["staff", "pentagrama"]):
        ambiguities.append("Target mentions both voice and staff. These may be different music structures.")

    return IntentAnalysis(
        target=target,
        operation=operation,
        destination_key=destination_key,
        interval=args.interval,
        destination_clef=destination_clef,
        instrument_profile=args.instrument,
        preserve_sounding_pitch=args.preserve_sounding_pitch,
        ambiguities=ambiguities,
        normalized_target_hints=hints,
    )


def build_stages(route: str) -> list[str]:
    if route == "structured":
        return [
            "Parse structured music file into notation objects.",
            "Identify parts, staves, voices, measures, clefs, key signatures, repeats, codas, and layout metadata.",
            "Map user target to exact part/staff/voice/measure selection.",
            "Apply semantic transposition to selected notes only.",
            "Export MusicXML plus rendered PDF/SVG/PNG preview.",
            "Emit validation and diff report.",
        ]
    if route == "omr":
        return [
            "Render PDF pages to high-resolution images.",
            "Detect systems, staves, barlines, measures, clefs, key signatures, repeats, codas, and text regions.",
            "Run OMR to recover structured notation.",
            "Confirm target mapping visually if confidence is low.",
            "Apply semantic transposition to selected notes only.",
            "Re-render the complete score preserving non-target notation.",
            "Emit validation and diff report.",
        ]
    if route == "image_omr":
        return [
            "Preprocess image: deskew, dewarp, denoise, crop, contrast normalize.",
            "Detect page regions, systems, staves, barlines, and measure groups.",
            "Run OMR to recover structured notation.",
            "Store confidence scores per symbol and measure.",
            "Confirm target mapping visually if confidence is low.",
            "Transpose selected material semantically and re-render.",
            "Emit validation and diff report.",
        ]
    if route == "artifact_inspection":
        return [
            "Inspect HTML and locate referenced score assets.",
            "Classify assets as original crops, transformed crops, or explanatory images.",
            "Recover or request the original score source for semantic editing.",
            "Do not accept pixel shifts as final transposition.",
            "If only artifact is available, label output as visual proof-of-concept only.",
        ]
    return [
        "Inspect file headers/content.",
        "Choose structured, OMR, image OMR, or artifact route.",
        "Normalize user target and operation.",
        "Run chosen route with validation gates.",
    ]


def build_plan(args: argparse.Namespace) -> PipelinePlan:
    source = classify_source(args.input)
    intent = analyze_intent(args)

    preservation = [
        "Preserve all non-target staves, voices, and parts.",
        "Preserve measure count and rhythmic duration.",
        "Preserve title, composer/arranger text, dynamics, articulations, ties, slurs, repeats, coda/DC/DS markings.",
        "Preserve layout where possible; report any necessary reflow.",
    ]

    gates = [
        "Every measure preserves total rhythmic duration.",
        "Non-target notation is unchanged or semantically equivalent.",
        "Target notes are transposed according to interval/key/clef/instrument rule.",
        "Accidentals and key signatures are coherent with destination intent.",
        "Low-confidence OMR regions are reported, not hidden.",
        "Output is labeled semantic, OMR-assisted, or visual proof-of-concept.",
    ]

    outputs = [
        "normalized_request.json",
        "pipeline_plan.txt",
        "validation_report.json",
        "diff_report.json",
    ]
    if source.route in {"structured", "omr", "image_omr"}:
        outputs.extend(["output.musicxml", "preview.pdf or preview.svg/png"])

    risks = list(source.notes)
    if intent.ambiguities:
        risks.extend(intent.ambiguities)
    if source.route in {"omr", "image_omr"}:
        risks.append("OMR can misread accidentals, tuplets, rests, repeats, coda jumps, or multi-voice notation.")
    if source.route == "artifact_inspection":
        risks.append("HTML/image artifacts may only support visual comparison, not true notation editing.")

    status = "ready_to_plan"
    if intent.ambiguities:
        status = "needs_clarification_before_execution"
    if source.route in {"omr", "image_omr"}:
        status += "+requires_omr"

    return PipelinePlan(
        source=source,
        intent=intent,
        stages=build_stages(source.route),
        preservation_requirements=preservation,
        validation_gates=gates,
        expected_outputs=outputs,
        risks=risks,
        status=status,
    )


def render_text(plan: PipelinePlan) -> str:
    lines: list[str] = []
    lines.append("BAGO music score transposition plan")
    lines.append("=" * 40)
    lines.append(f"Status: {plan.status}")
    lines.append("")
    lines.append("Input classification:")
    lines.append(f"- path: {plan.source.path}")
    lines.append(f"- kind: {plan.source.kind}")
    lines.append(f"- route: {plan.source.route}")
    lines.append(f"- confidence: {plan.source.confidence}")
    lines.append("")
    lines.append("Target / operation:")
    lines.append(f"- target: {plan.intent.target}")
    lines.append(f"- operation: {plan.intent.operation or 'unspecified'}")
    lines.append(f"- destination_key: {plan.intent.destination_key or 'unspecified'}")
    lines.append(f"- interval: {plan.intent.interval or 'unspecified'}")
    lines.append(f"- destination_clef: {plan.intent.destination_clef or 'unspecified'}")
    lines.append(f"- instrument_profile: {plan.intent.instrument_profile or 'unspecified'}")
    lines.append(f"- preserve_sounding_pitch: {plan.intent.preserve_sounding_pitch}")
    if plan.intent.normalized_target_hints:
        lines.append("")
        lines.append("Target hints:")
        for item in plan.intent.normalized_target_hints:
            lines.append(f"- {item}")
    if plan.intent.ambiguities:
        lines.append("")
        lines.append("Ambiguities to resolve:")
        for item in plan.intent.ambiguities:
            lines.append(f"- {item}")
    lines.append("")
    lines.append("Pipeline stages:")
    for i, stage in enumerate(plan.stages, start=1):
        lines.append(f"{i}. {stage}")
    lines.append("")
    lines.append("Preservation requirements:")
    for item in plan.preservation_requirements:
        lines.append(f"- {item}")
    lines.append("")
    lines.append("Validation gates:")
    for item in plan.validation_gates:
        lines.append(f"- {item}")
    lines.append("")
    lines.append("Expected outputs:")
    for item in plan.expected_outputs:
        lines.append(f"- {item}")
    lines.append("")
    lines.append("Risks / notes:")
    for item in plan.risks:
        lines.append(f"- {item}")
    return "\n".join(lines) + "\n"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Plan a semantic music score transposition pipeline.")
    parser.add_argument("--input", required=True, help="Input score path or filename.")
    parser.add_argument("--target", default="unspecified", help="Target staff/voice/part/region description.")
    parser.add_argument("--to", default=None, help="Destination key or clef, e.g. 'E minor' or 'treble clef'.")
    parser.add_argument("--interval", default=None, help="Explicit transposition interval, e.g. +M2, -m3, +P5.")
    parser.add_argument("--instrument", default=None, help="Destination transposing instrument profile, e.g. Bb clarinet.")
    parser.add_argument(
        "--preserve-sounding-pitch",
        action="store_true",
        help="Use for clef rewrite/transposed notation where sounding pitch must remain unchanged.",
    )
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of text.")
    parser.add_argument("--output", default=None, help="Optional file path to write the plan.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    plan = build_plan(args)
    payload = json.dumps(asdict(plan), indent=2, ensure_ascii=False) + "\n" if args.json else render_text(plan)

    if args.output:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(payload, encoding="utf-8")
        print(f"Wrote plan to {out}")
    else:
        print(payload, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

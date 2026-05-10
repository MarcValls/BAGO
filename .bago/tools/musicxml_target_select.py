#!/usr/bin/env python3
"""musicxml_target_select.py - inventory and target selection for MusicXML.

This module inspects MusicXML with Python's standard library and maps casual
user target descriptions such as "bottom staff", "staff 3", or "voice 2" to a
structured selector that downstream tools can use safely.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class PartInventory:
    id: str
    name: str | None
    measures: int
    staves: list[int]
    voices: list[str]
    clefs: dict[str, str]
    note_count: int
    rest_count: int
    pitched_note_count: int


@dataclass
class TargetSelector:
    part_ids: list[str] | None = None
    staff: int | None = None
    voice: str | None = None
    measure_start: int | None = None
    measure_end: int | None = None
    include_coda: bool = False
    target_text: str = ""
    confidence: str = "low"
    ambiguities: list[str] = field(default_factory=list)
    hints: list[str] = field(default_factory=list)


@dataclass
class InventoryResult:
    input_path: str
    parts: list[PartInventory]
    selector: TargetSelector


def lname(elem_or_tag: Any) -> str:
    tag = elem_or_tag.tag if hasattr(elem_or_tag, "tag") else str(elem_or_tag)
    return tag.rsplit("}", 1)[-1]


def child_text(elem: ET.Element, name: str, default: str | None = None) -> str | None:
    for child in list(elem):
        if lname(child) == name:
            text = child.text.strip() if child.text else ""
            return text or default
    return default


def first_child(elem: ET.Element, name: str) -> ET.Element | None:
    for child in list(elem):
        if lname(child) == name:
            return child
    return None


def direct_children(elem: ET.Element, name: str) -> list[ET.Element]:
    return [child for child in list(elem) if lname(child) == name]


def parse_int(text: str | None) -> int | None:
    if text is None:
        return None
    try:
        return int(str(text).strip())
    except Exception:
        return None


def score_part_names(root: ET.Element) -> dict[str, str]:
    names: dict[str, str] = {}
    for elem in root.iter():
        if lname(elem) != "score-part":
            continue
        pid = elem.attrib.get("id")
        if not pid:
            continue
        pname = child_text(elem, "part-name") or child_text(elem, "part-abbreviation") or pid
        names[pid] = pname
    return names


def inspect_musicxml(path: str) -> list[PartInventory]:
    tree = ET.parse(path)
    root = tree.getroot()
    part_names = score_part_names(root)
    inventories: list[PartInventory] = []

    for part in direct_children(root, "part"):
        part_id = part.attrib.get("id", "unknown")
        staves: set[int] = set()
        voices: set[str] = set()
        clefs: dict[str, str] = {}
        note_count = 0
        rest_count = 0
        pitched_count = 0
        measures = direct_children(part, "measure")

        for measure in measures:
            for attributes in direct_children(measure, "attributes"):
                staves_text = child_text(attributes, "staves")
                staves_count = parse_int(staves_text)
                if staves_count:
                    staves.update(range(1, staves_count + 1))
                for clef in direct_children(attributes, "clef"):
                    number = clef.attrib.get("number", "1")
                    sign = child_text(clef, "sign") or "unknown"
                    line = child_text(clef, "line") or ""
                    clefs[number] = f"{sign}{line}"
                    staves.add(int(number) if number.isdigit() else 1)

            for note in direct_children(measure, "note"):
                note_count += 1
                staff_value = parse_int(child_text(note, "staff")) or 1
                staves.add(staff_value)
                voice_value = child_text(note, "voice")
                if voice_value:
                    voices.add(voice_value)
                if first_child(note, "rest") is not None:
                    rest_count += 1
                if first_child(note, "pitch") is not None:
                    pitched_count += 1

        if not staves:
            staves.add(1)

        inventories.append(
            PartInventory(
                id=part_id,
                name=part_names.get(part_id),
                measures=len(measures),
                staves=sorted(staves),
                voices=sorted(voices, key=lambda v: (not v.isdigit(), int(v) if v.isdigit() else v)),
                clefs=clefs,
                note_count=note_count,
                rest_count=rest_count,
                pitched_note_count=pitched_count,
            )
        )
    return inventories


def parse_measure_range(text: str) -> tuple[int | None, int | None]:
    patterns = [
        r"(?:measures?|bars?|compases?)\s*(\d+)\s*[-–]\s*(\d+)",
        r"(?:measure|bar|comp[aá]s)\s*(\d+)",
        r"\b(\d+)\s*[-–]\s*(\d+)\b",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.I)
        if match:
            if len(match.groups()) == 2:
                return int(match.group(1)), int(match.group(2))
            return int(match.group(1)), int(match.group(1))
    return None, None


def resolve_target(parts: list[PartInventory], target: str) -> TargetSelector:
    text = target or "unspecified"
    low = text.lower()
    selector = TargetSelector(target_text=text)
    max_staff = max((max(part.staves) for part in parts if part.staves), default=1)

    m_start, m_end = parse_measure_range(low)
    selector.measure_start = m_start
    selector.measure_end = m_end
    selector.include_coda = "coda" in low

    staff_match = re.search(r"(?:staff|pentagrama)\s*(\d+)", low)
    voice_match = re.search(r"(?:voice|voz)\s*(\d+)", low)
    part_match = re.search(r"(?:part|parte)\s+([A-Za-z0-9_.-]+)", text)

    if staff_match:
        selector.staff = int(staff_match.group(1))
        selector.hints.append(f"Explicit staff selector: staff {selector.staff}.")
    elif any(term in low for term in ["bottom", "lowest", "lower", "abajo", "inferior", "grave"]):
        selector.staff = max_staff
        selector.hints.append(f"Bottom/lowest target mapped to staff {max_staff}.")
    elif any(term in low for term in ["third staff", "3rd staff", "tercer pentagrama", "tercera linea", "tercera línea"]):
        selector.staff = 3
        selector.hints.append("Third-staff language mapped to staff 3.")
    elif any(term in low for term in ["third voice", "3rd voice", "tercera voz"]):
        selector.ambiguities.append("'Third voice' may mean staff 3 or MusicXML voice 3. Use 'staff 3' or 'voice 3'.")

    if voice_match:
        selector.voice = voice_match.group(1)
        selector.hints.append(f"Explicit voice selector: voice {selector.voice}.")

    if part_match:
        wanted = part_match.group(1).lower()
        matched = [part.id for part in parts if part.id.lower() == wanted or (part.name and wanted in part.name.lower())]
        if matched:
            selector.part_ids = matched
            selector.hints.append(f"Part selector matched: {', '.join(matched)}.")
        else:
            selector.ambiguities.append(f"Requested part '{part_match.group(1)}' did not match any MusicXML part.")

    if any(term in low for term in ["bass clef", "clave de fa", "f clef"]):
        bass_staffs: set[int] = set()
        for part in parts:
            for number, clef in part.clefs.items():
                if clef.startswith("F"):
                    try:
                        bass_staffs.add(int(number))
                    except Exception:
                        bass_staffs.add(1)
        if len(bass_staffs) == 1 and selector.staff is None:
            selector.staff = sorted(bass_staffs)[0]
            selector.hints.append(f"Bass clef mapped to staff {selector.staff}.")
        elif len(bass_staffs) > 1:
            selector.ambiguities.append(f"Bass clef appears on multiple staves: {sorted(bass_staffs)}.")
        else:
            selector.hints.append("Bass clef mentioned, but no F clef was found in the MusicXML attributes.")

    if selector.staff is None and selector.voice is None and selector.part_ids is None:
        selector.ambiguities.append("No deterministic staff, voice, or part target was resolved.")

    selector.confidence = "high" if not selector.ambiguities and (selector.staff or selector.voice or selector.part_ids) else "medium" if selector.hints else "low"
    return selector


def render_text(result: InventoryResult) -> str:
    lines = ["BAGO MusicXML inventory", "=" * 24, f"Input: {result.input_path}", ""]
    lines.append("Parts:")
    for part in result.parts:
        lines.append(f"- {part.id} ({part.name or 'unnamed'}): measures={part.measures}, staves={part.staves}, voices={part.voices or 'none'}")
        lines.append(f"  clefs={part.clefs or {}}, notes={part.note_count}, rests={part.rest_count}, pitched={part.pitched_note_count}")
    lines.append("")
    selector = result.selector
    lines.append("Resolved target:")
    lines.append(f"- staff: {selector.staff if selector.staff is not None else 'unspecified'}")
    lines.append(f"- voice: {selector.voice or 'unspecified'}")
    lines.append(f"- parts: {selector.part_ids or 'all'}")
    lines.append(f"- measures: {selector.measure_start or 'start'}-{selector.measure_end or 'end'}")
    lines.append(f"- include_coda: {selector.include_coda}")
    lines.append(f"- confidence: {selector.confidence}")
    if selector.hints:
        lines.append("Hints:")
        lines.extend(f"- {item}" for item in selector.hints)
    if selector.ambiguities:
        lines.append("Ambiguities:")
        lines.extend(f"- {item}" for item in selector.ambiguities)
    return "\n".join(lines) + "\n"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Inspect MusicXML and resolve a target staff/voice/part/range.")
    parser.add_argument("--input", required=True, help="Input MusicXML/XML/MXL path.")
    parser.add_argument("--target", default="unspecified", help="Target description, e.g. 'bottom staff measures 1-26'.")
    parser.add_argument("--json", action="store_true", help="Emit JSON.")
    parser.add_argument("--output", default=None, help="Optional output path.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        parts = inspect_musicxml(args.input)
        selector = resolve_target(parts, args.target)
        result = InventoryResult(input_path=args.input, parts=parts, selector=selector)
        payload = json.dumps(asdict(result), indent=2, ensure_ascii=False) + "\n" if args.json else render_text(result)
        if args.output:
            out = Path(args.output)
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(payload, encoding="utf-8")
            print(f"Wrote inventory to {out}")
        else:
            print(payload, end="")
        return 0 if selector.confidence != "low" else 3
    except Exception as exc:
        print(f"MusicXML inventory failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

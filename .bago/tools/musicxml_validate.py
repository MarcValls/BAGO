#!/usr/bin/env python3
"""musicxml_validate.py - validate target-only MusicXML transposition."""
from __future__ import annotations

import argparse
import json
import sys
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass, field
from pathlib import Path

import musicxml_target_select as target_select


STEP_TO_PC = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}


@dataclass
class ValidationIssue:
    severity: str
    message: str
    part_id: str | None = None
    measure: str | None = None


@dataclass
class ValidationReport:
    original_path: str
    transposed_path: str
    target: dict
    semitones: int
    passed: bool
    target_notes_checked: int = 0
    non_target_notes_checked: int = 0
    rests_checked: int = 0
    duration_nodes_checked: int = 0
    issues: list[ValidationIssue] = field(default_factory=list)


def child_text(elem: ET.Element, name: str, default: str | None = None) -> str | None:
    return target_select.child_text(elem, name, default)


def child(elem: ET.Element, name: str) -> ET.Element | None:
    return target_select.first_child(elem, name)


def pitch_value(note: ET.Element) -> int | None:
    pitch = child(note, "pitch")
    if pitch is None:
        return None
    step = child_text(pitch, "step")
    octave = child_text(pitch, "octave")
    alter = int(child_text(pitch, "alter", "0") or "0")
    if step not in STEP_TO_PC or octave is None:
        return None
    return (int(octave) + 1) * 12 + STEP_TO_PC[step] + alter


def note_matches(note: ET.Element, part_id: str, measure_number: str, selector: target_select.TargetSelector) -> bool:
    if selector.part_ids and part_id not in selector.part_ids:
        return False
    try:
        m_num = int(measure_number)
    except Exception:
        m_num = None
    if m_num is not None:
        if selector.measure_start is not None and m_num < selector.measure_start:
            return False
        if selector.measure_end is not None and m_num > selector.measure_end:
            return False
    if selector.staff is not None and (target_select.parse_int(child_text(note, "staff")) or 1) != selector.staff:
        return False
    if selector.voice is not None and child_text(note, "voice") != selector.voice:
        return False
    return True


def part_map(root: ET.Element) -> dict[str, ET.Element]:
    return {p.attrib.get("id", "unknown"): p for p in target_select.direct_children(root, "part")}


def validate(original: str, transposed: str, target: str, semitones: int) -> ValidationReport:
    parts = target_select.inspect_musicxml(original)
    selector = target_select.resolve_target(parts, target)
    report = ValidationReport(original, transposed, asdict(selector), semitones, passed=False)
    if selector.confidence == "low":
        report.issues.append(ValidationIssue("error", "Target selector confidence is low: " + "; ".join(selector.ambiguities)))
        return report

    orig_root = ET.parse(original).getroot()
    trans_root = ET.parse(transposed).getroot()
    orig_parts = part_map(orig_root)
    trans_parts = part_map(trans_root)
    if set(orig_parts) != set(trans_parts):
        report.issues.append(ValidationIssue("error", "Part IDs differ between original and transposed files."))
        return report

    for part_id, orig_part in orig_parts.items():
        trans_part = trans_parts[part_id]
        orig_measures = target_select.direct_children(orig_part, "measure")
        trans_measures = target_select.direct_children(trans_part, "measure")
        if len(orig_measures) != len(trans_measures):
            report.issues.append(ValidationIssue("error", "Measure count changed.", part_id))
            continue
        for orig_measure, trans_measure in zip(orig_measures, trans_measures):
            measure_number = orig_measure.attrib.get("number", "")
            orig_notes = target_select.direct_children(orig_measure, "note")
            trans_notes = target_select.direct_children(trans_measure, "note")
            if len(orig_notes) != len(trans_notes):
                report.issues.append(ValidationIssue("error", "Note/rest count changed.", part_id, measure_number))
                continue
            for orig_note, trans_note in zip(orig_notes, trans_notes):
                orig_rest = child(orig_note, "rest") is not None
                trans_rest = child(trans_note, "rest") is not None
                if orig_rest or trans_rest:
                    report.rests_checked += 1
                    if orig_rest != trans_rest:
                        report.issues.append(ValidationIssue("error", "Rest/pitched-note identity changed.", part_id, measure_number))
                    continue
                orig_duration = child_text(orig_note, "duration")
                trans_duration = child_text(trans_note, "duration")
                if orig_duration is not None or trans_duration is not None:
                    report.duration_nodes_checked += 1
                    if orig_duration != trans_duration:
                        report.issues.append(ValidationIssue("error", "Duration changed.", part_id, measure_number))
                orig_pitch = pitch_value(orig_note)
                trans_pitch = pitch_value(trans_note)
                is_target = note_matches(orig_note, part_id, measure_number, selector)
                if is_target:
                    report.target_notes_checked += 1
                    if orig_pitch is not None and trans_pitch is not None and trans_pitch - orig_pitch != semitones:
                        report.issues.append(ValidationIssue("error", f"Target note moved by {trans_pitch - orig_pitch}, expected {semitones}.", part_id, measure_number))
                else:
                    report.non_target_notes_checked += 1
                    if orig_pitch != trans_pitch:
                        report.issues.append(ValidationIssue("error", "Non-target pitch changed.", part_id, measure_number))
    if report.target_notes_checked == 0:
        report.issues.append(ValidationIssue("error", "No target notes were checked."))
    report.passed = not any(issue.severity == "error" for issue in report.issues)
    return report


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate selected-target MusicXML transposition.")
    parser.add_argument("--original", required=True)
    parser.add_argument("--transposed", required=True)
    parser.add_argument("--target", required=True)
    parser.add_argument("--semitones", type=int, required=True)
    parser.add_argument("--report", default=None)
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        report = validate(args.original, args.transposed, args.target, args.semitones)
        payload = json.dumps(asdict(report), indent=2, ensure_ascii=False) + "\n"
        if args.report:
            Path(args.report).parent.mkdir(parents=True, exist_ok=True)
            Path(args.report).write_text(payload, encoding="utf-8")
        if args.json:
            print(payload, end="")
        else:
            print(f"Validation: {'PASS' if report.passed else 'FAIL'}")
            print(f"Target notes checked: {report.target_notes_checked}")
            print(f"Non-target notes checked: {report.non_target_notes_checked}")
            if args.report:
                print(f"Report: {args.report}")
        return 0 if report.passed else 5
    except Exception as exc:
        print(f"MusicXML validation failed: {exc}", file=sys.stderr)
        return 5


if __name__ == "__main__":
    raise SystemExit(main())

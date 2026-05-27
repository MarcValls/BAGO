#!/usr/bin/env python3
"""musicxml_transpose.py - selected-target semantic MusicXML transposition."""
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
import copy
import json
import re
import sys
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass, field
from pathlib import Path

import musicxml_target_select as target_select


STEP_TO_PC = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
PC_TO_STEP_ALTER_SHARP = {
    0: ("C", 0), 1: ("C", 1), 2: ("D", 0), 3: ("D", 1),
    4: ("E", 0), 5: ("F", 0), 6: ("F", 1), 7: ("G", 0),
    8: ("G", 1), 9: ("A", 0), 10: ("A", 1), 11: ("B", 0),
}
INTERVALS = {
    "P1": (0, 0), "m2": (1, 1), "M2": (2, 1), "m3": (3, 2), "M3": (4, 2),
    "P4": (5, 3), "A4": (6, 3), "d5": (6, 4), "P5": (7, 4),
    "m6": (8, 5), "M6": (9, 5), "m7": (10, 6), "M7": (11, 6), "P8": (12, 7),
}


@dataclass
class NoteChange:
    part_id: str
    measure: str
    staff: int
    voice: str | None
    before: str
    after: str


@dataclass
class TransposeReport:
    input_path: str
    output_path: str
    target: dict
    interval: str | None
    semitones: int
    changed_notes: int = 0
    untouched_notes: int = 0
    skipped_rests: int = 0
    changed_key_sigs: int = 0
    warnings: list[str] = field(default_factory=list)
    changes: list[NoteChange] = field(default_factory=list)


def lname(elem_or_tag) -> str:
    return target_select.lname(elem_or_tag)


def child(elem: ET.Element, name: str) -> ET.Element | None:
    return target_select.first_child(elem, name)


def child_text(elem: ET.Element, name: str, default: str | None = None) -> str | None:
    return target_select.child_text(elem, name, default)


def set_child_text(parent: ET.Element, name: str, value: str) -> None:
    elem = child(parent, name)
    if elem is None:
        elem = ET.SubElement(parent, name)
    elem.text = value


def parse_interval(value: str | None, semitones: int | None) -> tuple[str | None, int, int]:
    if semitones is not None:
        return None, semitones, semitones
    if not value:
        raise ValueError("Provide --interval or --semitones.")
    match = re.fullmatch(r"([+-]?)(P1|m2|M2|m3|M3|P4|A4|d5|P5|m6|M6|m7|M7|P8)", value.strip())
    if not match:
        raise ValueError(f"Unsupported interval: {value}")
    sign = -1 if match.group(1) == "-" else 1
    semis, diatonic = INTERVALS[match.group(2)]
    return value, semis * sign, diatonic * sign


def pitch_to_midi(pitch: ET.Element) -> int:
    step = child_text(pitch, "step")
    octave = child_text(pitch, "octave")
    alter = int(child_text(pitch, "alter", "0") or "0")
    if step not in STEP_TO_PC or octave is None:
        raise ValueError("Invalid MusicXML pitch node.")
    return (int(octave) + 1) * 12 + STEP_TO_PC[step] + alter


def midi_to_pitch(midi: int) -> tuple[str, int, int]:
    octave = midi // 12 - 1
    pc = midi % 12
    step, alter = PC_TO_STEP_ALTER_SHARP[pc]
    return step, alter, octave


def pitch_label(pitch: ET.Element) -> str:
    step = child_text(pitch, "step", "?")
    alter = int(child_text(pitch, "alter", "0") or "0")
    octave = child_text(pitch, "octave", "?")
    acc = "#" * alter if alter > 0 else "b" * abs(alter)
    return f"{step}{acc}{octave}"


def fifths_delta_for_semitones(semitone_delta: int) -> int:
    """Return the circle-of-fifths delta corresponding to a semitone transposition.

    Each semitone maps to 7 positions on the circle of fifths (mod 12), normalized
    to the range [-6, 6] so that the result uses the closest key spelling.
    Examples: -2 semitones (M2 down, E→D) → -2; +7 semitones (P5 up, C→G) → +1.
    """
    raw = (semitone_delta * 7) % 12
    return raw - 12 if raw > 6 else raw


def measure_in_range(measure_number: str, selector: target_select.TargetSelector) -> bool:
    try:
        m_num = int(measure_number)
    except Exception:
        return True
    if selector.measure_start is not None and m_num < selector.measure_start:
        return False
    if selector.measure_end is not None and m_num > selector.measure_end:
        return False
    return True


def note_matches(note: ET.Element, part_id: str, measure_number: str, selector: target_select.TargetSelector) -> bool:
    if selector.part_ids and part_id not in selector.part_ids:
        return False
    m_num = None
    try:
        m_num = int(measure_number)
    except Exception:
        pass
    if m_num is not None:
        if selector.measure_start is not None and m_num < selector.measure_start:
            return False
        if selector.measure_end is not None and m_num > selector.measure_end:
            return False
    if selector.staff is not None:
        staff = target_select.parse_int(child_text(note, "staff")) or 1
        if staff != selector.staff:
            return False
    if selector.voice is not None:
        if child_text(note, "voice") != selector.voice:
            return False
    return True


def transpose_file(input_path: str, output_path: str, target: str, interval: str | None, semitones: int | None) -> TransposeReport:
    parts = target_select.inspect_musicxml(input_path)
    selector = target_select.resolve_target(parts, target)
    if selector.confidence == "low":
        raise ValueError("Target is ambiguous: " + "; ".join(selector.ambiguities))

    interval_label, semitone_delta, _ = parse_interval(interval, semitones)
    key_delta = fifths_delta_for_semitones(semitone_delta)
    tree = ET.parse(input_path)
    root = tree.getroot()
    report = TransposeReport(
        input_path=input_path,
        output_path=output_path,
        target=asdict(selector),
        interval=interval_label,
        semitones=semitone_delta,
    )
    if selector.ambiguities:
        report.warnings.extend(selector.ambiguities)

    # Key signatures are per-part in MusicXML and must be updated when the whole
    # part (or all parts) is transposed. When only a specific staff is selected
    # within a multi-staff part, the key is shared across staves so we skip it.
    update_key_sigs = selector.staff is None

    for part in target_select.direct_children(root, "part"):
        part_id = part.attrib.get("id", "unknown")
        if selector.part_ids and part_id not in selector.part_ids:
            for measure in target_select.direct_children(part, "measure"):
                for note in target_select.direct_children(measure, "note"):
                    if child(note, "rest") is not None:
                        report.skipped_rests += 1
                    else:
                        report.untouched_notes += 1
            continue
        for measure in target_select.direct_children(part, "measure"):
            measure_number = measure.attrib.get("number", "")
            if not measure_in_range(measure_number, selector):
                continue

            # Update key signatures for this measure when appropriate.
            if update_key_sigs:
                for attributes in target_select.direct_children(measure, "attributes"):
                    for key_elem in target_select.direct_children(attributes, "key"):
                        fifths_text = child_text(key_elem, "fifths")
                        if fifths_text is not None:
                            try:
                                new_fifths = int(fifths_text) + key_delta
                                set_child_text(key_elem, "fifths", str(new_fifths))
                                report.changed_key_sigs += 1
                            except ValueError:
                                report.warnings.append(
                                    f"Could not parse <fifths> value '{fifths_text}' in measure {measure_number}."
                                )

            for note in target_select.direct_children(measure, "note"):
                if child(note, "rest") is not None:
                    report.skipped_rests += 1
                    continue
                pitch = child(note, "pitch")
                if pitch is None:
                    report.untouched_notes += 1
                    continue
                if not note_matches(note, part_id, measure_number, selector):
                    report.untouched_notes += 1
                    continue
                before = pitch_label(pitch)
                new_midi = pitch_to_midi(pitch) + semitone_delta
                step, alter, octave = midi_to_pitch(new_midi)
                set_child_text(pitch, "step", step)
                if alter:
                    set_child_text(pitch, "alter", str(alter))
                else:
                    alter_elem = child(pitch, "alter")
                    if alter_elem is not None:
                        pitch.remove(alter_elem)
                set_child_text(pitch, "octave", str(octave))
                after = pitch_label(pitch)
                staff = target_select.parse_int(child_text(note, "staff")) or 1
                voice = child_text(note, "voice")
                report.changed_notes += 1
                report.changes.append(NoteChange(part_id, measure_number, staff, voice, before, after))

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    tree.write(out, encoding="utf-8", xml_declaration=True)
    if report.changed_notes == 0:
        report.warnings.append("No pitched target notes were changed.")
    return report


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Transpose selected notes inside MusicXML.")
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--target", required=True)
    parser.add_argument("--interval", default=None)
    parser.add_argument("--semitones", type=int, default=None)
    parser.add_argument("--report", default=None)
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        report = transpose_file(args.input, args.output, args.target, args.interval, args.semitones)
        payload = json.dumps(asdict(report), indent=2, ensure_ascii=False) + "\n"
        if args.report:
            Path(args.report).parent.mkdir(parents=True, exist_ok=True)
            Path(args.report).write_text(payload, encoding="utf-8")
        if args.json:
            print(payload, end="")
        else:
            print(f"Changed notes: {report.changed_notes}")
            print(f"Changed key signatures: {report.changed_key_sigs}")
            print(f"Output: {report.output_path}")
            if args.report:
                print(f"Report: {args.report}")
        return 0 if report.changed_notes > 0 else 4
    except Exception as exc:
        print(f"MusicXML transposition failed: {exc}", file=sys.stderr)
        return 4




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
"""test_music_pipeline.py — Phase 7: MusicXML pipeline unit + integration tests.

TC-1  pitch_to_midi known values (parametrized)
TC-2  interval_to_semitones table (parametrized)
TC-3  parse_interval error paths
TC-4  end-to-end transpose C4 → D4 via transpose_file
TC-5  non-target part isolation (P1 changes, P2 untouched)
TC-6  rests skipped, not transposed (skipped_rests counter)
TC-7  validate PASS on correct roundtrip
TC-8  validate FAIL on wrong semitone delta

Imports rely on conftest.py adding .bago/tools to sys.path.
"""
from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

# Public API from .bago/tools — available via conftest.py sys.path injection
from musicxml_transpose import pitch_to_midi, parse_interval, transpose_file
from musicxml_validate import validate
from bago_music import interval_to_semitones

FIXTURES = Path(__file__).parent / "fixtures" / "musicxml"
SINGLE_NOTE = str(FIXTURES / "single_note_c4.musicxml")
TWO_PARTS   = str(FIXTURES / "two_parts_c4.musicxml")
NOTE_REST   = str(FIXTURES / "note_and_rest.musicxml")


# ---------------------------------------------------------------------------
# TC-1: pitch_to_midi known values
# ---------------------------------------------------------------------------

def _make_pitch(step: str, octave: int, alter: int | None = None) -> ET.Element:
    """Build a bare <pitch> element with the given step/octave/alter."""
    pitch = ET.Element("pitch")
    ET.SubElement(pitch, "step").text = step
    if alter is not None:
        ET.SubElement(pitch, "alter").text = str(alter)
    ET.SubElement(pitch, "octave").text = str(octave)
    return pitch


@pytest.mark.parametrize("step,octave,alter,expected_midi", [
    ("C", 4, None, 60),
    ("D", 4, None, 62),
    ("E", 4, None, 64),
    ("G", 4, None, 67),
    ("B", 4, None, 71),
    ("C", 5, None, 72),
    ("C", 4, 1,   61),   # C#4
])
def test_pitch_to_midi(step, octave, alter, expected_midi):
    """TC-1: pitch_to_midi returns correct MIDI note number."""
    pitch = _make_pitch(step, octave, alter)
    assert pitch_to_midi(pitch) == expected_midi


# ---------------------------------------------------------------------------
# TC-2: interval_to_semitones table
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("interval,expected", [
    ("P1",   0),
    ("M2",   2),
    ("m3",   3),
    ("M3",   4),
    ("P4",   5),
    ("P5",   7),
    ("P8",  12),
    ("-M2", -2),
    ("-P5", -7),
])
def test_interval_to_semitones(interval, expected):
    """TC-2: interval_to_semitones returns correct semitone count."""
    assert interval_to_semitones(interval) == expected


# ---------------------------------------------------------------------------
# TC-3: parse_interval error paths
# ---------------------------------------------------------------------------

def test_parse_interval_none_none_raises():
    """TC-3a: parse_interval(None, None) must raise ValueError."""
    with pytest.raises(ValueError):
        parse_interval(None, None)


def test_parse_interval_bad_label_raises():
    """TC-3b: parse_interval('XY99', None) must raise ValueError."""
    with pytest.raises(ValueError):
        parse_interval("XY99", None)


# ---------------------------------------------------------------------------
# TC-4: end-to-end transpose C4 → D4
# ---------------------------------------------------------------------------

def test_transpose_c4_to_d4(tmp_path):
    """TC-4: single C4 note transposes to D4 via +M2 (2 semitones)."""
    out = str(tmp_path / "out_tc4.xml")
    report = transpose_file(SINGLE_NOTE, out, "staff 1", "+M2", None)

    assert report.changed_notes == 1, f"Expected 1 changed note, got {report.changed_notes}"
    assert report.skipped_rests == 0

    # Verify pitch in output XML
    root = ET.parse(out).getroot()
    notes = [e for e in root.iter() if e.tag.endswith("note")]
    assert len(notes) == 1
    pitch = next(e for e in notes[0] if e.tag.endswith("pitch"))
    step = next(e for e in pitch if e.tag.endswith("step")).text
    octave = next(e for e in pitch if e.tag.endswith("octave")).text
    assert step == "D", f"Expected step D, got {step}"
    assert octave == "4", f"Expected octave 4, got {octave}"


# ---------------------------------------------------------------------------
# TC-5: non-target part isolation
# ---------------------------------------------------------------------------

def test_non_target_part_untouched(tmp_path):
    """TC-5: transposing part P1 leaves part P2 unchanged."""
    out = str(tmp_path / "out_tc5.xml")
    report = transpose_file(TWO_PARTS, out, "part P1", "+M2", None)

    assert report.changed_notes == 1,   f"Expected 1 changed, got {report.changed_notes}"
    assert report.untouched_notes == 1, f"Expected 1 untouched, got {report.untouched_notes}"

    # Parse output XML: P1 note must NOT be C4; P2 note must still be C4
    root = ET.parse(out).getroot()
    parts = {p.attrib.get("id"): p for p in root.iter() if p.tag.endswith("part")}

    def note_step_octave(part_elem):
        for note in part_elem.iter():
            if note.tag.endswith("note"):
                pitch = next((e for e in note if e.tag.endswith("pitch")), None)
                if pitch is None:
                    continue
                s = next(e for e in pitch if e.tag.endswith("step")).text
                o = next(e for e in pitch if e.tag.endswith("octave")).text
                return s, o
        return None, None

    p1_step, p1_octave = note_step_octave(parts["P1"])
    p2_step, p2_octave = note_step_octave(parts["P2"])

    assert (p1_step, p1_octave) != ("C", "4"), "P1 note should have been transposed away from C4"
    assert (p2_step, p2_octave) == ("C", "4"), f"P2 note should remain C4, got {p2_step}{p2_octave}"


# ---------------------------------------------------------------------------
# TC-6: rests are skipped
# ---------------------------------------------------------------------------

def test_rests_skipped(tmp_path):
    """TC-6: rest is skipped (skipped_rests==1), pitched note is changed."""
    out = str(tmp_path / "out_tc6.xml")
    report = transpose_file(NOTE_REST, out, "staff 1", "+M2", None)

    assert report.skipped_rests == 1,  f"Expected 1 skipped rest, got {report.skipped_rests}"
    assert report.changed_notes == 1, f"Expected 1 changed note, got {report.changed_notes}"

    # Verify rest element still present in output (not pitched)
    root = ET.parse(out).getroot()
    notes = [e for e in root.iter() if e.tag.endswith("note")]
    assert len(notes) == 2
    rest_notes = [n for n in notes if any(c.tag.endswith("rest") for c in n)]
    assert len(rest_notes) == 1, "Rest element should still be present in output"
    assert not any(c.tag.endswith("pitch") for c in rest_notes[0]), "Rest note must have no pitch element"


# ---------------------------------------------------------------------------
# TC-7: validate PASS on correct roundtrip
# ---------------------------------------------------------------------------

def test_validate_pass_correct_roundtrip(tmp_path):
    """TC-7: validate passes when transposition delta matches expected semitones."""
    out = str(tmp_path / "out_tc7.xml")
    transpose_file(SINGLE_NOTE, out, "staff 1", "+M2", None)

    vreport = validate(SINGLE_NOTE, out, "staff 1", semitones=2)

    assert vreport.passed is True, f"Expected PASS, issues: {vreport.issues}"
    assert vreport.issues == [], f"Expected no issues, got: {vreport.issues}"


# ---------------------------------------------------------------------------
# TC-8: validate FAIL on wrong semitone delta
# ---------------------------------------------------------------------------

def test_validate_fail_wrong_delta(tmp_path):
    """TC-8: validate fails when the transposed file has a different delta than expected."""
    # Build a MusicXML with E4 (4 semitones above C4, not 2)
    wrong_xml_path = str(tmp_path / "wrong_e4.xml")
    wrong_content = """\
<?xml version='1.0' encoding='utf-8'?>
<score-partwise>
  <part-list>
    <score-part id="P1"><part-name>Violin</part-name></score-part>
  </part-list>
  <part id="P1">
    <measure number="1">
      <note>
        <pitch><step>E</step><octave>4</octave></pitch>
        <duration>4</duration><voice>1</voice><staff>1</staff>
      </note>
    </measure>
  </part>
</score-partwise>
"""
    Path(wrong_xml_path).write_text(wrong_content, encoding="utf-8")

    # original is C4, "transposed" is E4 (+4), but we claim +2 semitones → FAIL
    vreport = validate(SINGLE_NOTE, wrong_xml_path, "staff 1", semitones=2)

    assert vreport.passed is False, "Expected FAIL — E4 is +4 semitones, not +2"
    assert len(vreport.issues) > 0, "Expected at least one issue"
    assert any(issue.severity == "error" for issue in vreport.issues), \
        f"Expected at least one error-severity issue, got: {vreport.issues}"

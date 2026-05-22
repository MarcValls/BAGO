#!/usr/bin/env python3
from __future__ import annotations
import argparse
from pathlib import Path

def make_musicxml(title, key_fifths, mode, clef_sign, clef_line, notes, tempo=120):
    key_tag = '<key><fifths>%d</fifths><mode>%s</mode></key>' % (key_fifths, mode)
    time_tag = '<time><beats>4</beats><beat-type>4</beat-type></time>'
    clef_tag = '<clef><sign>%s</sign><line>%d</line></clef>' % (clef_sign, clef_line)
    measures_xml = []
    for i, chunk in enumerate([notes[j:j+4] for j in range(0, len(notes), 4)]):
        if not chunk: continue
        measure_num = i + 1
        measure_notes = []
        for step, octave, duration, ntype in chunk:
            measure_notes.append(
                '      <note><pitch><step>%s</step><octave>%d</octave></pitch>'
                '<duration>%d</duration><type>%s</type></note>'
                % (step, octave, duration, ntype)
            )
        attrs = ''
        if i == 0:
            attrs = (
                '\n      <attributes>\n'
                '        <divisions>4</divisions>\n'
                '        %s\n'
                '        %s\n'
                '        %s\n'
                '      </attributes>'
            ) % (key_tag, time_tag, clef_tag)
        measures_xml.append(
            '    <measure number=\"%d\">%s\n' % (measure_num, attrs)
            + '\n'.join(measure_notes)
            + '\n    </measure>'
        )
    lines = ['<?xml version=\"1.0\" encoding=\"UTF-8\"?>',
             '<!DOCTYPE score-partwise PUBLIC \"-//Recordare//DTD MusicXML 3.1 Partwise//EN\"',
             '  \"http://www.musicxml.org/dtds/partwise.dtd\">',
             '<score-partwise version=\"3.1\">',
             '  <work><work-title>%s</work-title></work>' % title,
             '  <identification><creator type=\"composer\">BAGO Test Generator</creator></identification>',
             '  <part-list>',
             '    <score-part id=\"P1\"><part-name>%s</part-name></score-part>' % title,
             '  </part-list>',
             '  <part id=\"P1\">',
             '\n'.join(measures_xml),
             '  </part>',
             '</score-partwise>']
    return '\n'.join(lines)


def generate_test_scores(output_dir):
    output_dir.mkdir(parents=True, exist_ok=True)
    generated = []
    notes_c_major = [("C", 4, 4, "quarter"), ("D", 4, 4, "quarter"), ("E", 4, 4, "quarter"), ("F", 4, 4, "quarter"),
                     ("G", 4, 4, "quarter"), ("A", 4, 4, "quarter"), ("B", 4, 4, "quarter"), ("C", 5, 4, "quarter")]
    xml = make_musicxml("Escala Do Mayor", 0, "major", "G", 2, notes_c_major)
    p = output_dir / "c_major_scale.musicxml"
    p.write_text(xml, encoding="utf-8")
    generated.append(p)
    notes_e_major = [("E", 2, 4, "quarter"), ("F", 2, 4, "quarter"), ("G", 2, 4, "quarter"), ("A", 2, 4, "quarter"),
                     ("B", 2, 4, "quarter"), ("C", 3, 4, "quarter"), ("D", 3, 4, "quarter"), ("E", 3, 4, "quarter")]
    xml = make_musicxml("Escala Mi Mayor - Bajo", 4, "major", "F", 4, notes_e_major)
    p = output_dir / "e_major_bass.musicxml"
    p.write_text(xml, encoding="utf-8")
    generated.append(p)
    notes_d_progression = [("D", 4, 4, "quarter"), ("F", 4, 4, "quarter"), ("A", 4, 4, "quarter"), ("D", 5, 4, "quarter"),
                         ("A", 4, 4, "quarter"), ("C", 5, 4, "quarter"), ("E", 5, 4, "quarter"), ("A", 5, 4, "quarter"),
                         ("B", 4, 4, "quarter"), ("D", 5, 4, "quarter"), ("F", 5, 4, "quarter"), ("B", 5, 4, "quarter"),
                         ("G", 4, 4, "quarter"), ("B", 4, 4, "quarter"), ("D", 5, 4, "quarter"), ("G", 5, 4, "quarter")]
    xml = make_musicxml("Progresion Re Mayor", 2, "major", "G", 2, notes_d_progression)
    p = output_dir / "d_major_progression.musicxml"
    p.write_text(xml, encoding="utf-8")
    generated.append(p)
    notes_a_minor = [("A", 4, 4, "quarter"), ("B", 4, 4, "quarter"), ("C", 5, 4, "quarter"), ("D", 5, 4, "quarter"),
                     ("E", 5, 4, "quarter"), ("F", 5, 4, "quarter"), ("G", 5, 4, "quarter"), ("A", 5, 4, "quarter")]
    xml = make_musicxml("Escala La Menor", 0, "minor", "G", 2, notes_a_minor)
    p = output_dir / "a_minor_scale.musicxml"
    p.write_text(xml, encoding="utf-8")
    generated.append(p)
    notes_g_arpeggio = [("G", 2, 4, "quarter"), ("B", 2, 4, "quarter"), ("D", 3, 4, "quarter"), ("G", 3, 4, "quarter"),
                      ("B", 3, 4, "quarter"), ("D", 4, 4, "quarter"), ("G", 4, 4, "quarter"), ("B", 4, 4, "quarter")]
    xml = make_musicxml("Arpegio Sol Mayor - Bajo", 1, "major", "F", 4, notes_g_arpeggio)
    p = output_dir / "g_major_arpeggio_bass.musicxml"
    p.write_text(xml, encoding="utf-8")
    generated.append(p)
    notes_f_major = [("F", 4, 4, "quarter"), ("G", 4, 4, "quarter"), ("A", 4, 4, "quarter"), ("B", 4, 4, "quarter"),
                     ("C", 5, 4, "quarter"), ("D", 5, 4, "quarter"), ("E", 5, 4, "quarter"), ("F", 5, 4, "quarter")]
    xml = make_musicxml("Escala Fa Mayor", -1, "major", "G", 2, notes_f_major)
    p = output_dir / "f_major_scale.musicxml"
    p.write_text(xml, encoding="utf-8")
    generated.append(p)
    notes_bb_major = [("B", 4, 4, "quarter"), ("C", 5, 4, "quarter"), ("D", 5, 4, "quarter"), ("E", 5, 4, "quarter"),
                    ("F", 5, 4, "quarter"), ("G", 5, 4, "quarter"), ("A", 5, 4, "quarter"), ("B", 5, 4, "quarter")]
    xml = make_musicxml("Escala Si Bemol Mayor", -2, "major", "G", 2, notes_bb_major)
    p = output_dir / "bb_major_scale.musicxml"
    p.write_text(xml, encoding="utf-8")
    generated.append(p)
    notes_e_minor = [("E", 2, 4, "quarter"), ("F", 2, 4, "quarter"), ("G", 2, 4, "quarter"), ("A", 2, 4, "quarter"),
                     ("B", 2, 4, "quarter"), ("C", 3, 4, "quarter"), ("D", 3, 4, "quarter"), ("E", 3, 4, "quarter")]
    xml = make_musicxml("Escala Mi Menor - Bajo", 1, "minor", "F", 4, notes_e_minor)
    p = output_dir / "e_minor_bass.musicxml"
    p.write_text(xml, encoding="utf-8")
    generated.append(p)
    # 9. Partitura larga para test de paginacion (12 compases)
    notes_long = []
    for i in range(12):
        notes_long.extend([
            ("C", 4, 4, "quarter"), ("E", 4, 4, "quarter"), 
            ("G", 4, 4, "quarter"), ("C", 5, 4, "quarter"),
        ])
    xml = make_musicxml("Partitura Larga - Test Paginacion", 0, "major", "G", 2, notes_long)
    p = output_dir / "long_pagination_test.musicxml"
    p.write_text(xml, encoding="utf-8")
    generated.append(p)

    return generated

def main():
    parser = argparse.ArgumentParser(description="Genera partituras de prueba para BAGO")
    parser.add_argument("--output-dir", default="./test_scores", help="Directorio de salida")
    args = parser.parse_args()
    out = Path(args.output_dir)
    scores = generate_test_scores(out)
    print("\n  BAGO Music Test Generator")
    print("  ----------------------------------------------")
    print("  Generadas %d partituras en: %s" % (len(scores), out))
    for s in scores:
        size = s.stat().st_size
        print("    - %s (%d bytes)" % (s.name, size))
    print()
    return 0

if __name__ == "__main__":
    exit(main())


"""test_music_integration.py — Tests de integracion: generador + exportador + transposicion.

Valida end-to-end:
  1. Generacion de partituras de prueba
  2. Transposicion MusicXML
  3. Exportacion a HTML renderer (PDF-ready)
"""
from __future__ import annotations

import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / ".bago" / "tools"))

from bago_music_test_generator import generate_test_scores, make_musicxml
from bago_music_pdf_export import musicxml_to_notes, generate_html_renderer
from musicxml_transpose import transpose_file

FIXTURES = Path(__file__).parent / "fixtures" / "generated"


class TestGenerator:
    def test_generate_creates_valid_musicxml(self, tmp_path):
        scores = generate_test_scores(tmp_path)
        assert len(scores) == 9
        for s in scores:
            assert s.exists()
            assert s.stat().st_size > 0
            # Validar que es XML bien formado
            tree = ET.parse(str(s))
            root = tree.getroot()
            assert root.tag.endswith("score-partwise")

    def test_c_major_has_correct_notes(self, tmp_path):
        scores = generate_test_scores(tmp_path)
        c_major = next(s for s in scores if "c_major" in s.name)
        tree = ET.parse(str(c_major))
        steps = [e.text for e in tree.iter() if e.tag.endswith("step")]
        assert steps == ["C", "D", "E", "F", "G", "A", "B", "C"]

    def test_e_major_bass_has_bass_clef(self, tmp_path):
        scores = generate_test_scores(tmp_path)
        e_bass = next(s for s in scores if "e_major_bass" in s.name)
        tree = ET.parse(str(e_bass))
        signs = [e.text for e in tree.iter() if e.tag.endswith("sign")]
        assert "F" in signs


class TestPdfExport:
    def test_export_html_contains_vexflow(self, tmp_path):
        scores = generate_test_scores(tmp_path)
        c_major = next(s for s in scores if "c_major" in s.name)
        out = tmp_path / "test.html"
        generate_html_renderer("Test", musicxml_to_notes(c_major), out)
        assert out.exists()
        html = out.read_text(encoding="utf-8")
        assert "Vex.Flow" in html or "vexflow" in html.lower()
        assert "@page" in html
        assert "@media print" in html

    def test_notes_extraction(self, tmp_path):
        scores = generate_test_scores(tmp_path)
        c_major = next(s for s in scores if "c_major" in s.name)
        notes = musicxml_to_notes(c_major)
        assert len(notes) == 8
        assert notes[0]["keys"] == ["C/4"]


class TestTransposition:
    def test_transpose_c_to_d(self, tmp_path):
        scores = generate_test_scores(tmp_path)
        c_major = next(s for s in scores if "c_major" in s.name)
        out = str(tmp_path / "transposed.xml")
        report = transpose_file(str(c_major), out, "staff 1", "+M2", None)
        assert report.changed_notes == 8
        tree = ET.parse(out)
        steps = [e.text for e in tree.iter() if e.tag.endswith("step")]
        assert steps == ["D", "E", "F", "G", "A", "B", "C", "D"]

    def test_transpose_preserves_structure(self, tmp_path):
        scores = generate_test_scores(tmp_path)
        c_major = next(s for s in scores if "c_major" in s.name)
        out = str(tmp_path / "transposed.xml")
        report = transpose_file(str(c_major), out, "staff 1", "+P5", None)
        assert report.changed_notes == 8
        tree = ET.parse(out)
        measures = list(tree.iter("{http://www.musicxml.org/dtds/partwise.dtd}measure"))
        if not measures:
            measures = list(tree.iter("measure"))
        assert len(measures) == 2


class TestEndToEnd:
    def test_full_pipeline(self, tmp_path):
        # 1. Generar
        scores = generate_test_scores(tmp_path)
        c_major = next(s for s in scores if "c_major" in s.name)

        # 2. Transponer
        transposed = str(tmp_path / "transposed.xml")
        report = transpose_file(str(c_major), transposed, "staff 1", "+M3", None)
        assert report.changed_notes == 8

        # 3. Exportar a HTML
        out_html = tmp_path / "score.html"
        generate_html_renderer("Transposed Score", musicxml_to_notes(Path(transposed)), out_html)
        assert out_html.exists()
        html = out_html.read_text(encoding="utf-8")
        assert "Vex.Flow" in html

        # 4. Validar
        from musicxml_validate import validate
        vreport = validate(str(c_major), transposed, "staff 1", semitones=4)
        assert vreport.passed is True

    def test_pagination_avoids_page_breaks(self, tmp_path):
        scores = generate_test_scores(tmp_path)
        long_score = next(s for s in scores if "long_pagination" in s.name)
        out = tmp_path / "pagination_test.html"
        generate_html_renderer("Long Score", musicxml_to_notes(long_score), out)
        html = out.read_text(encoding="utf-8")
        # Verificar que cada compas tiene page-break-inside: avoid
        assert "page-break-inside: avoid" in html
        assert "break-inside: avoid" in html
        # Verificar que hay stave-block para cada compas
        assert html.count("stave-block") >= 2


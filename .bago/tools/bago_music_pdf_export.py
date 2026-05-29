#!/usr/bin/env python3
"""bago_music_pdf_export.py — Exporta MusicXML a PDF-ready HTML autocontenido.

Estrategia:
  1. Parsea MusicXML
  2. Genera HTML autocontenido con VexFlow embebido
  3. Cada compas en div separado para evitar cortes al imprimir
  4. Usuario usa Ctrl+P -> Guardar como PDF

Uso:
  python bago_music_pdf_export.py input.musicxml --output output.html
"""
from __future__ import annotations

from bago_utils import load_json, save_json, timestamp_iso

import argparse
import json
import webbrowser
from pathlib import Path


def musicxml_to_notes(musicxml_path: Path) -> list[dict]:
    """Parsea MusicXML y extrae notas."""
    try:
        import xml.etree.ElementTree as ET
    except ImportError:
        return []

    tree = ET.parse(str(musicxml_path))
    root = tree.getroot()
    ns = {"m": "http://www.musicxml.org/dtds/partwise.dtd"}

    notes = []
    for note_elem in root.iter("{http://www.musicxml.org/dtds/partwise.dtd}note"):
        pitch = note_elem.find("m:pitch", ns)
        if pitch is None:
            continue
        step = pitch.find("m:step", ns)
        octave = pitch.find("m:octave", ns)
        alter = pitch.find("m:alter", ns)
        duration = note_elem.find("m:duration", ns)
        ntype = note_elem.find("m:type", ns)

        key = "%s/%s" % (step.text, octave.text) if step is not None and octave is not None else "b/4"
        if alter is not None and alter.text:
            key = key.replace("/", "%s/%s" % (step.text + ("#" if alter.text == "1" else "b"), octave.text))

        notes.append({
            "keys": [key],
            "duration": _duration_to_vf(duration.text if duration is not None else "4"),
            "type": ntype.text if ntype is not None else "quarter",
        })

    if not notes:
        for note_elem in root.iter("note"):
            pitch = note_elem.find("pitch")
            if pitch is None:
                continue
            step = pitch.find("step")
            octave = pitch.find("octave")
            duration = note_elem.find("duration")
            ntype = note_elem.find("type")
            key = "%s/%s" % (step.text, octave.text) if step is not None and octave is not None else "b/4"
            notes.append({
                "keys": [key],
                "duration": _duration_to_vf(duration.text if duration is not None else "4"),
                "type": ntype.text if ntype is not None else "quarter",
            })

    return notes


def _duration_to_vf(duration: str) -> str:
    mapping = {"1": "w", "2": "h", "4": "q", "8": "8", "16": "16"}
    return mapping.get(duration, "q")


def generate_html_renderer(title: str, notes: list[dict], output_path: Path) -> Path:
    """Genera HTML autocontenido con VexFlow inline. Cada compas en div separado."""
    notes_json = json.dumps(notes, ensure_ascii=False)

    # Dividir notas en compases de 4 tiempos
    measures = []
    current_measure = []
    current_beats = 0
    for n in notes:
        beat_value = {"w": 4, "h": 2, "q": 1, "8": 0.5, "16": 0.25}.get(n["duration"], 1)
        if current_beats + beat_value > 4 and current_measure:
            measures.append(current_measure)
            current_measure = [n]
            current_beats = beat_value
        else:
            current_measure.append(n)
            current_beats += beat_value
    if current_measure:
        measures.append(current_measure)

    measures_json = json.dumps(measures, ensure_ascii=False)

    html = '''<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<title>%s — BAGO PDF Export</title>
<style>
  @page { size: A4 landscape; margin: 10mm; }
  @media print {
    body { background: white; margin: 0; padding: 0; }
    .container { max-width: none; margin: 0; padding: 0; border-radius: 0; box-shadow: none; }
    .no-print { display: none !important; }
    #score { border: none; padding: 0; min-height: auto; }
    h1 { font-size: 16px; margin: 0 0 4px 0; }
    .meta { font-size: 10px; margin-bottom: 8px; }
    .stave-block { page-break-inside: avoid; break-inside: avoid; margin-bottom: 2px; }
    svg { max-width: 100%%; height: auto; display: block; }
  }
  body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; background: #f5f5f5; margin: 0; padding: 16px; }
  .container { max-width: 1000px; margin: 0 auto; background: white; border-radius: 10px; box-shadow: 0 2px 12px rgba(0,0,0,.08); padding: 24px; }
  h1 { font-size: 20px; margin-bottom: 2px; color: #222; }
  .meta { font-size: 12px; color: #666; margin-bottom: 16px; }
  #score { border: 1px solid #e0e0e0; border-radius: 6px; padding: 16px; min-height: 160px; }
  .btn-bar { margin-top: 16px; display: flex; gap: 8px; }
  button { padding: 8px 16px; border-radius: 6px; border: none; cursor: pointer; font-size: 13px; font-weight: 600; }
  .btn-primary { background: #00d4aa; color: white; }
  .btn-secondary { background: #eee; color: #333; }
  .error { color: #c00; font-size: 13px; padding: 16px; }
</style>
</head>
<body>
<div class="container">
  <h1>%s</h1>
  <div class="meta">Generado por BAGO Music Pipeline — %d notas, %d compases</div>
  <div id="score"></div>
  <div class="btn-bar no-print">
    <button class="btn-primary" onclick="window.print()">Imprimir / Guardar PDF</button>
    <button class="btn-secondary" onclick="window.close()">Cerrar</button>
  </div>
</div>
<script src="https://unpkg.com/vexflow@4.2.5/build/cjs/vexflow.js"></script>
<script>
  const measures = %s;
  const div = document.getElementById("score");

  function render() {
    if (typeof Vex === "undefined") {
      div.innerHTML = "<div class=\\"error\\">No se pudo cargar VexFlow. Conecta a internet o descarga VexFlow localmente.</div>";
      return;
    }
    const VF = Vex.Flow;

    measures.forEach((measureNotes, idx) => {
      const block = document.createElement("div");
      block.className = "stave-block";
      div.appendChild(block);

      const renderer = new VF.Renderer(block, VF.Renderer.Backends.SVG);
      const staveWidth = Math.min(block.clientWidth || 1100, 1100);
      renderer.resize(staveWidth, 85);
      const ctx = renderer.getContext();

      const stave = new VF.Stave(10, 10, staveWidth - 20);
      if (idx === 0) {
        stave.addClef("treble").addTimeSignature("4/4");
      }
      stave.setContext(ctx).draw();

      const vfNotes = measureNotes.map(n => new VF.StaveNote({clef: "treble", keys: n.keys, duration: n.duration}));
      const voice = new VF.Voice({num_beats: 4, beat_value: 4});
      voice.addTickables(vfNotes);
      new VF.Formatter().joinVoices([voice]).format([voice], staveWidth - 30);
      voice.draw(ctx, stave);
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", render);
  } else {
    render();
  }
  setTimeout(render, 1000);
</script>
</body>
</html>''' % (title, title, len(notes), len(measures), measures_json)

    output_path.write_text(html, encoding="utf-8")
    return output_path


def export_pdf(musicxml_path: Path, output_path: Path | None = None) -> Path:
    """Exporta MusicXML a HTML renderer listo para imprimir a PDF."""
    notes = musicxml_to_notes(musicxml_path)
    if not notes:
        raise ValueError("No se pudieron extraer notas de %s" % musicxml_path)

    if output_path is None:
        output_path = musicxml_path.with_suffix(".pdf.html")

    generate_html_renderer(musicxml_path.stem, notes, output_path)
    webbrowser.open("file:///%s" % output_path)
    return output_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Exporta MusicXML a PDF-ready HTML")
    parser.add_argument("input", help="Archivo MusicXML de entrada")
    parser.add_argument("--output", "-o", help="Archivo HTML de salida")
    args = parser.parse_args()

    inp = Path(args.input)
    out = Path(args.output) if args.output else None

    try:
        path = export_pdf(inp, out)
        print("\n  OK Exportado: %s" % path)
        print("  Abriendo en navegador... Usa Ctrl+P / Imprimir para guardar como PDF\n")
        return 0
    except Exception as e:
        print("\n  ERROR: %s\n" % e)
        return 1


if __name__ == "__main__":
    exit(main())


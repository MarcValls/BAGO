# BAGO music tool usage

BAGO now includes a music-score pipeline tool router:

```bash
bago music --help
```

This router exposes the first integrated stages of the music-score pipeline as a BAGO-owned tool.

## Available subcommands

### Plan

Creates an auditable semantic transposition plan.

```bash
bago music plan \
  --input CantinaBand_TubaTrio-TC.pdf \
  --target "bottom staff" \
  --to "E minor"
```

This delegates to:

```text
.bago/tools/music_transpose_plan.py
```

It detects ambiguity such as:

- bass clef vs key;
- E minor as destination key;
- bottom voice vs staff vs part;
- missing interval/instrument intent.

### Convert

Classifies the input and chooses the safest path toward MusicXML.

```bash
bago music convert \
  --input score.pdf \
  --out-dir build/musicxml
```

Execution mode:

```bash
bago music convert \
  --input score.pdf \
  --out-dir build/musicxml \
  --execute
```

This delegates to:

```text
.bago/tools/music_to_musicxml_pipeline.py
```

It supports these routes:

- MusicXML/XML/MXL: use or copy directly;
- MuseScore MSCZ/MSCX: export through MuseScore CLI when installed;
- MIDI: convert with music21 when installed;
- MEI: convert with Verovio when installed;
- PDF/image: use Audiveris OMR when installed;
- HTML: inspect assets and recover the real source score.

### Inventory

Inspects a MusicXML/XML/MXL file and maps casual target language to a structured selector.

```bash
bago music inventory \
  --input score.musicxml \
  --target "bottom staff measures 1-26"
```

This delegates to:

```text
.bago/tools/musicxml_target_select.py
```

It reports parts, staff/voice usage, measure ranges, clefs, ambiguities, and selector hints.

### Run

Runs the currently available safe pipeline stages for already structured MusicXML/XML inputs:

1. planning;
2. conversion toward MusicXML;
3. inventory;
4. selected-target transposition;
5. validation;
6. optional rendering.

```bash
bago music run \
  --input score.musicxml \
  --target "part Tuba III" \
  --interval +M2 \
  --out-dir build/music \
  --output-xml build/music/tuba_iii_transposed.musicxml \
  --no-render
```

For PDF/image sources, the command still stops before transposition unless a structured MusicXML file has been produced by OMR/export first.

### Transpose

Transposes only the selected target in MusicXML and writes a change report.

```bash
bago music transpose \
  --input score.musicxml \
  --target "part Tuba III" \
  --interval +M2 \
  --output build/music/transposed.musicxml \
  --report build/music/transpose_report.json
```

Supported interval spelling includes `+M2`, `-M2`, `+m3`, `+P4`, `+P5`, and `+P8`.

### Validate

Checks that target notes moved by the expected semitone delta and non-target notes stayed unchanged.

```bash
bago music validate \
  --original score.musicxml \
  --transposed build/music/transposed.musicxml \
  --target "part Tuba III" \
  --semitones 2 \
  --report build/music/validation_report.json
```

### Render

Renders MusicXML when an optional renderer is installed.

```bash
bago music render \
  --input build/music/transposed.musicxml \
  --output build/music/transposed.pdf \
  --execute \
  --report build/music/render_report.json
```

PDF/PNG rendering uses MuseScore CLI. SVG rendering uses Verovio when available, falling back to MuseScore.

## Reserved subcommands

No subcommands are currently reserved. The active pipeline entrypoints are:

```bash
bago music plan
bago music convert
bago music inventory
bago music transpose
bago music validate
bago music render
```

## Why this is a BAGO tool

This file acts as the BAGO-facing router for the music domain. It groups the domain scripts under one tool entrypoint and enforces the same sincerity principle as the workflow docs:

> Do not claim semantic music transposition unless structured notation exists and validation confirms that only the requested target changed.

## BAGO CLI entrypoint

`music` is now registered in `.bago/tools/tool_registry.py`, so users can run:

```bash
bago music plan --input score.pdf --target "bottom staff" --interval +M2
```

## Direct script fallback

If the launcher is unavailable, the router can still be run directly:

```bash
python3 .bago/tools/bago_music.py plan --input score.pdf --target "bottom staff" --interval +M2
```

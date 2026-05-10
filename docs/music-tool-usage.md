# BAGO music tool usage

BAGO now includes a music-score pipeline tool router:

```bash
python3 .bago/tools/bago_music.py --help
```

This router exposes the first integrated stages of the music-score pipeline as a BAGO-owned tool.

## Available subcommands

### Plan

Creates an auditable semantic transposition plan.

```bash
python3 .bago/tools/bago_music.py plan \
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
python3 .bago/tools/bago_music.py convert \
  --input score.pdf \
  --out-dir build/musicxml
```

Execution mode:

```bash
python3 .bago/tools/bago_music.py convert \
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

### Run

Runs the currently available safe pipeline stages:

1. planning;
2. conversion toward MusicXML;
3. stop before transposition.

```bash
python3 .bago/tools/bago_music.py run \
  --input score.pdf \
  --target "bottom staff" \
  --interval +M2 \
  --out-dir build/music \
  --execute-conversion
```

The command intentionally stops before transposition because these modules are not implemented yet:

- `.bago/tools/musicxml_target_select.py`
- `.bago/tools/musicxml_transpose.py`
- `.bago/tools/musicxml_validate.py`
- `.bago/tools/musicxml_render.py`

## Reserved subcommands

The router already reserves these subcommands:

```bash
python3 .bago/tools/bago_music.py inventory
python3 .bago/tools/bago_music.py transpose
python3 .bago/tools/bago_music.py validate
python3 .bago/tools/bago_music.py render
```

For now they return honest not-implemented messages instead of pretending that the full pipeline exists.

## Why this is a BAGO tool

This file acts as the BAGO-facing router for the music domain. It groups the domain scripts under one tool entrypoint and enforces the same sincerity principle as the workflow docs:

> Do not claim semantic music transposition unless structured notation exists and validation confirms that only the requested target changed.

## BAGO CLI entrypoint

`music` is now registered in `.bago/tools/tool_registry.py`, so users can run:

```bash
bago music plan --input score.pdf --target "bottom staff" --interval +M2
```

Direct invocation is still supported when needed:

```bash
python3 .bago/tools/bago_music.py plan --input score.pdf --target "bottom staff" --interval +M2
```

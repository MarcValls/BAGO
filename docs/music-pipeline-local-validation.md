# Local validation for the BAGO music pipeline

This document records how to validate the current BAGO music pipeline locally with a real PDF score.

## Scope

The current implementation validates these stages:

1. File classification.
2. Route selection toward MusicXML.
3. Planning for semantic transposition.
4. Honest stop before unimplemented stages.

The current implementation does **not** yet perform final semantic transposition from PDF because the required OMR and MusicXML transposition modules are still separate future stages.

## Test file

Example input used during design:

```text
CantinaBand_TubaTrio-TC.pdf
```

It is a two-page PDF score for a three-part tuba/euphonium trio. The relevant target is the bottom staff / third visible staff in each system.

## Expected pipeline route

For this PDF, the expected route is:

```text
PDF score
-> Audiveris OMR
-> MusicXML
-> target selection: bottom staff / staff 3
-> MusicXML transposition
-> validation
-> render final PDF
```

Because the source is PDF, BAGO must not claim final semantic transposition until OMR has generated structured notation and validation has passed.

## Commands

From the repository root:

```bash
python3 .bago/tools/bago_music.py plan \
  --input input/CantinaBand_TubaTrio-TC.pdf \
  --target "bottom staff" \
  --to "E minor"
```

Expected behavior:

- Detects that the file is a PDF.
- Chooses an OMR route.
- Detects that `bottom staff` likely maps to the lowest visible staff.
- Warns that `E minor` is a key and needs exact musical interpretation.
- Does not claim transposition.

Conversion planning:

```bash
python3 .bago/tools/bago_music.py convert \
  --input input/CantinaBand_TubaTrio-TC.pdf \
  --out-dir build/musicxml
```

Expected behavior:

- `kind = pdf_score_or_document`
- `route = audiveris_omr`
- `selected_tool = audiveris` if installed, otherwise `none`
- reports missing Audiveris honestly if unavailable.

End-to-end current-stage run:

```bash
python3 .bago/tools/bago_music.py run \
  --input input/CantinaBand_TubaTrio-TC.pdf \
  --target "bottom staff" \
  --interval +M2 \
  --out-dir build/music \
  --execute-conversion
```

Expected behavior today:

- writes `build/music/pipeline_plan.txt`;
- writes `build/music/conversion_report.json`;
- attempts conversion only if Audiveris is installed;
- stops before transposition with an explicit message because `musicxml_transpose.py` is not implemented yet.

## Dependency expectations

The pipeline can plan without optional dependencies.

Execution depends on file type:

| Input | Optional tool needed for execution |
|---|---|
| MusicXML/XML/MXL | none, copy/use directly |
| MSCZ/MSCX | MuseScore CLI |
| MIDI | Python package `music21` |
| MEI | Verovio CLI |
| PDF/image | Audiveris CLI |
| HTML | none for asset inventory |

## Validation result from current implementation

When tested against the PDF score in an environment without Audiveris, MuseScore, Verovio, or music21 installed, the correct result is:

```text
Input: CantinaBand_TubaTrio-TC.pdf
Kind: pdf_score_or_document
Route: audiveris_omr
Can execute now: False
Selected tool: none
```

This is a pass for the current stage because BAGO chooses the correct route and refuses to pretend that PDF pixels have been semantically transposed.

## Pass criteria

The local validation passes if:

1. `python3 bago validate` passes.
2. `python3 bago health` does not show critical breakage.
3. `python3 .bago/tools/bago_music.py --help` works.
4. `plan` produces a transposition plan.
5. `convert` classifies PDF as `audiveris_omr`.
6. `run` produces reports and stops honestly before unimplemented transposition.

## Fail criteria

The validation fails if BAGO:

- claims a real transposition from PDF without MusicXML;
- changes non-target notation without validation;
- hides missing OMR/rendering dependencies;
- treats an HTML/image crop artifact as semantic notation;
- silently skips validation.

## Next implementation modules

To complete the full semantic pipeline, implement:

```text
.bago/tools/musicxml_target_select.py
.bago/tools/musicxml_transpose.py
.bago/tools/musicxml_validate.py
.bago/tools/musicxml_render.py
```

Once those exist, `bago_music.py run` should be upgraded from current-stage orchestration to full end-to-end orchestration.

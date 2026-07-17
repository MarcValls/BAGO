# Music score transposition operational workflow

## Trigger

Use this workflow when the user asks BAGO to work with a musical score and any of these intents appear:

- transpose a score, staff, part, voice, line, instrument, section, or measure range;
- read notation from PDF, image, MusicXML, MuseScore, MIDI, MEI, or HTML score artifact;
- preserve the original score but change only one musical layer;
- convert a bass-clef, treble-clef, key, or instrument-specific part;
- verify whether a visual transposition is musically real.

## Principle

BAGO must distinguish visual manipulation from semantic music editing.

Pixel movement is not enough. A final answer may only claim real transposition if notes, durations, accidentals, clefs, key signatures, voices/staves, and measure structure were represented semantically.

## Stage 1: classify the input

Classify the source before choosing the method.

1. Structured music file: MusicXML, MSCZ/MSCX, MEI, MIDI.
2. Digital PDF: visually clean score, possibly vector glyphs but not necessarily editable notation.
3. Scanned PDF or image: raster notation requiring cleanup and OMR.
4. HTML artifact: explanatory or before/after page containing image crops.
5. Unknown: inspect and choose the safest route.

## Stage 2: normalize user intent

Convert casual language into a structured request.

Required fields:

- target type: staff, part, voice inside staff, visual region, measure range, page range;
- operation type: interval transposition, destination key, clef rewrite, transposing-instrument adaptation;
- preservation mode: preserve sounding pitch or change sounding pitch;
- scope: whole score, selected pages, selected measures, coda/repeats included or excluded.

Terminology checks:

- Bass clef / F clef is a clef, not a key.
- E minor is a key, not a clef.
- Third voice can mean third staff or voice index 3 inside one staff.
- Bottom voice often means lowest visible staff or part.

Ask only the minimum clarification needed when these are ambiguous.

## Stage 3: select technical route

### Structured route

Use when the source is MusicXML, MSCZ/MSCX, MEI, or MIDI.

1. Parse structured notation.
2. Select target part/staff/voice/range.
3. Transpose semantically.
4. Export MusicXML plus rendered preview.
5. Produce validation report.

### OMR route

Use when the source is PDF or image.

1. Render or preprocess pages.
2. Detect systems, staves, barlines, measures, clefs, key signatures, repeats, codas, and text regions.
3. Run OMR to recover structured notation.
4. Confirm low-confidence target mapping visually.
5. Transpose selected material semantically.
6. Re-render full score.
7. Produce validation report.

### Artifact route

Use when the source is HTML or image comparison.

1. Locate embedded assets.
2. Determine whether the file is source material or proof-of-concept.
3. Recover/request original score source for semantic editing.
4. Do not treat shifted pixels as authoritative music data.

## Stage 4: preserve non-target material

The workflow must preserve:

- all non-target staves/voices/parts;
- measure count and rhythmic duration;
- title, composer, arranger, and text markings;
- dynamics, articulations, ties, slurs, repeats, codas, DC/DS markings;
- layout where possible;
- original notation outside the selected target.

## Stage 5: validate honesty

Before claiming success, verify:

1. Target notes changed according to the requested interval/key/clef/instrument rule.
2. Non-target notes did not change.
3. Every measure still balances rhythmically.
4. Accidentals and key signatures are coherent.
5. Repeats, codas, text, articulations, ties, and slurs remain present.
6. Low-confidence OMR regions are explicitly reported.
7. The output is labeled correctly as semantic, OMR-assisted, or visual proof-of-concept.

## Output template

When planning or reporting a score transposition task, BAGO should emit:

```text
Input classification:
Target selection:
Ambiguities:
Chosen route:
Transposition operation:
Preservation requirements:
Validation gates:
Expected output:
Risks / low-confidence areas:
```

## Example

User request:

> Transpose only the bottom staff of this PDF score across the whole piece, including coda.

BAGO interpretation:

```text
Input classification: digital PDF score
Target selection: bottom staff / third staff in every system
Ambiguities: destination key or interval must be specified
Chosen route: render PDF -> detect staves -> OMR -> transpose target staff -> render full score
Transposition operation: pending user confirmation
Preservation requirements: keep top two staves, text, coda, repeats, and layout unchanged
Validation gates: rhythmic duration, non-target equality, target transposition, OMR confidence report
Expected output: reconstructed PDF + MusicXML + diff report
Risks / low-confidence areas: OMR may misread accidentals, repeats, tuplets, or coda jumps
```

## Workflow mapping

- W2 Controlled Implementation: implement the feature with evidence.
- W4 Multi-cause Debug: debug OMR/segmentation/rendering failures.
- W8 Exploration: evaluate OMR engines and notation renderers.
- W10 Sincerity Audit: prevent false claims about visual edits being real transpositions.

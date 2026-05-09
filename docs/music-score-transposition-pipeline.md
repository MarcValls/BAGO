# Music score transposition workflow for BAGO

## Purpose

This document teaches BAGO the workflow for reading a musical score from PDF, image, MusicXML, MuseScore, MIDI, MEI, HTML artifact, or similar input; selecting one staff, part, voice, section, or measure range; transposing only that selected material; and reconstructing the complete score while preserving everything else.

Core rule:

> Do not confuse a visual edit of score pixels with a real semantic transposition of music notation.

A visual proof-of-concept may help verification, but the production goal is structured music editing.

## Motivating example

A user provides a PDF score for a three-part tuba/euphonium trio. The score displays three horizontal musical lines per system. The requested operation is not to transpose the whole score, but only the bottom line, written in bass clef, across the full piece including coda.

BAGO must interpret this as:

- identify the bottom staff in every system;
- preserve the top two staves unchanged;
- preserve title, layout, repeats, text markings, coda/DC markings, measure structure, articulations, ties, slurs, dynamics, and all non-target notation;
- transpose only the target musical content;
- export a reconstructed score plus a verification report.

## Terminology normalization

Users may not use formal music terminology. BAGO should normalize casual language into precise operations.

- "bottom voice" can mean bottom staff, lowest part, or last visible staff.
- "third voice" can mean third staff in the system or voice index 3 inside one staff.
- "bass clef" or "F clef" is a clef, not a key.
- "E minor" is a key, not a clef.
- "from bass clef to E minor" is ambiguous and must be resolved as key transposition, clef rewrite, or instrument transposition.
- "same score but with this part transposed" means reconstruct the full score, not crop only the selected staff.

Minimal clarifications when ambiguous:

1. Is the target a staff, part, voice inside a staff, or visual region?
2. Is the operation a destination key, interval, new clef, or transposing-instrument conversion?
3. Should sounding pitch be preserved or changed?
4. Should the whole score or only selected measures be processed?

## File-type strategy

### Structured music files

Examples: MusicXML, MuseScore MSCZ/MSCX, MEI, MIDI.

Preferred method:

1. Parse directly into structured music objects.
2. Identify parts, staves, voices, measures, notes, rests, clefs, key signatures, time signatures, ties, slurs, articulations, dynamics, text, repeats, codas, and layout metadata.
3. Apply target selection.
4. Transpose using musical semantics.
5. Export MusicXML plus rendered PDF/SVG/PNG preview.

### Digital PDF

A clean PDF may still contain only vector glyphs and text rather than editable music.

Preferred method:

1. Render pages to high-resolution images.
2. Detect systems, staves, barlines, measure boundaries, clefs, key signatures, repeats, codas, and text markings.
3. Run OMR, optical music recognition, to convert notation into structured data.
4. Map the user target to a staff/part/voice/measure selection.
5. Apply semantic transposition.
6. Re-render the complete score.

### Scanned PDF or raster image

Preferred method:

1. Deskew, dewarp, crop, denoise, and increase contrast.
2. Detect page regions, systems, staves, barlines, and measure groups.
3. Run OMR.
4. Store confidence scores per symbol and per measure.
5. Ask for visual confirmation if confidence is low.
6. Transpose and re-render.

### HTML artifact or image-comparison page

An HTML file containing score crops or before/after images is not a reliable source of music semantics.

Preferred method:

1. Locate referenced image assets.
2. Decide whether they are original crops, transformed crops, or explanatory images.
3. If musical editing is required, recover or request the original score source.
4. Do not accept pixel shifting as final transposition.

## Normalized request schema

```json
{
  "source": {
    "type": "pdf | image | musicxml | mscz | mei | midi | html | unknown",
    "path": "..."
  },
  "target": {
    "part_id": null,
    "staff_index": 3,
    "voice_index": null,
    "page_range": [1, 2],
    "measure_range": [1, 26],
    "region": null,
    "include_coda": true
  },
  "operation": {
    "type": "transpose",
    "interval": null,
    "destination_key": null,
    "destination_clef": null,
    "instrument_profile": null,
    "preserve_sounding_pitch": false
  },
  "preserve": {
    "other_parts": true,
    "layout": true,
    "text": true,
    "repeats": true,
    "articulations": true,
    "dynamics": true
  },
  "quality": {
    "require_user_confirmation_for_low_confidence_omr": true,
    "minimum_symbol_confidence": 0.9,
    "emit_diff_report": true
  }
}
```

## Architecture BAGO should recommend

1. File classifier: structured notation, PDF, raster image, HTML artifact, or unknown.
2. Score segmentation: pages, systems, staves, barlines, measures, clefs, key signatures, repeats, codas, text regions.
3. OMR adapter: convert visual notation into structured notation. Candidate engines/libraries: Audiveris, MuseScore import/export, Verovio, music21, LilyPond, OpenSheetMusicDisplay, VexFlow, and custom adapters.
4. Target selector: map human language and/or visual selection to part, staff, voice, measure, page, coda, or region.
5. Transposition engine: apply semantic transposition to selected notes only while preserving non-target notation.
6. Renderer/exporter: export MusicXML and render PDF/SVG/PNG previews plus a diff report.

## Quality gates

A score transposition result is not final unless these checks pass:

1. Every measure preserves its total rhythmic duration.
2. Non-target staves or voices are unchanged or semantically equivalent.
3. Target notes are transposed according to the requested interval, key, clef rule, or instrument profile.
4. Accidentals and key signatures are coherent with the requested destination.
5. Ties, slurs, articulations, dynamics, repeats, codas, and text markings are retained.
6. The system produces a before/after preview.
7. Low-confidence OMR symbols are reported.
8. The output distinguishes clearly between proof-of-concept visual edits and editorially valid notation.

## MVP plan

1. PDF/image upload.
2. Page rendering to images.
3. Automatic staff detection.
4. Manual selection of the target staff or region.
5. OMR conversion to MusicXML.
6. Staff-level transposition by interval or destination key.
7. Full-score PDF preview preserving non-target staves.
8. Diff report with changed notes, unchanged staves, and warnings.

## Non-goals

- Do not move pixels and claim that the music was transposed.
- Do not transpose the whole score when the request targets one staff or voice.
- Do not conflate clef and key.
- Do not claim editorial quality if OMR confidence is low.
- Do not discard layout, coda, repeat marks, or non-target parts.

## Example acceptance test

Given a two-page score with three staves per system, when the user asks:

> Transpose only the bottom staff across the whole piece, including coda.

Then BAGO should:

1. Identify the bottom staff in every system.
2. Preserve the top two staves unchanged.
3. Preserve the score title, text, repetitions, coda/DC markings, and measure layout.
4. Transpose only the notes belonging to the bottom staff.
5. Export a reconstructed score and a validation report.

## Workflow integration inside BAGO

This feature maps to existing BAGO workflows:

- W2 Controlled Implementation: build the feature with validation evidence.
- W4 Multi-cause Debug: investigate OMR, segmentation, and rendering failures.
- W8 Exploration: compare OMR engines and notation renderers.
- W10 Sincerity Audit: prevent false claims, especially claiming semantic transposition when only visual pixel movement was done.

BAGO's rule for this domain:

> Always preserve the distinction between visual score manipulation and semantic music-notation editing.

# Music pipeline integration plan for BAGO

## Objective

Integrate a complete score-processing pipeline into BAGO so it can:

1. Accept a score-like input file: PDF, image, MusicXML, MuseScore, MIDI, MEI, HTML artifact, or unknown file.
2. Detect the file type and choose the safest route toward structured notation.
3. Convert or recover MusicXML when possible.
4. Select a target staff, part, voice, visual region, or measure range.
5. Transpose only that selected musical material.
6. Preserve all non-target score content.
7. Render a final score preview/output.
8. Emit an honest validation report that distinguishes semantic notation editing from OMR-assisted or visual proof-of-concept work.

This plan extends the existing documentation and scripts:

- `docs/music-score-transposition-pipeline.md`
- `.bago/workflows/music-score-transposition.md`
- `.bago/tools/music_transpose_plan.py`
- `.bago/tools/music_to_musicxml_pipeline.py`

## Integration principle

The system must never claim that a score has been musically transposed unless it has a structured notation representation and has applied the operation to musical objects: notes, rests, voices, staves, measures, clefs, key signatures, and accidentals.

For PDF/image sources, MusicXML produced through OMR must be treated as OMR-assisted and validated before final use.

## Target CLI shape

Add an experimental BAGO command:

```bash
bago music ...
```

Proposed subcommands:

```bash
bago music plan --input score.pdf --target "bottom staff" --to "E minor"
bago music convert --input score.pdf --out-dir build/musicxml
bago music transpose --input score.musicxml --target "staff 3" --interval +M2 --output out.musicxml
bago music validate --original score.musicxml --transposed out.musicxml --target "staff 3"
bago music render --input out.musicxml --output out.pdf
bago music run --input score.pdf --target "bottom staff" --interval +M2 --output out.pdf
```

Initial command can be experimental and safe-by-default. Mutating or external-tool execution should require explicit flags where appropriate.

## Phase 0 — Repository integration and command registration

### Goal

Expose the existing scripts through BAGO's CLI in a way consistent with the framework.

### Tasks

1. Create `.bago/tools/bago_music.py` as a router for music-related commands.
2. Register `music` in `.bago/tools/tool_registry.py` as experimental and safe/mutating depending on subcommand.
3. Add preflight checks for:
   - `.bago/tools/bago_music.py`
   - `.bago/tools/music_transpose_plan.py`
   - `.bago/tools/music_to_musicxml_pipeline.py`
4. Update README experimental commands list if needed.
5. Add command documentation to `docs/COMMANDS.md` if generated docs are part of the normal process.

### Acceptance criteria

- `bago music --help` prints available music subcommands.
- `bago music plan ...` delegates to `music_transpose_plan.py`.
- `bago music convert ...` delegates to `music_to_musicxml_pipeline.py`.
- `bago validate` still passes.
- `python3 .bago/tools/tool_registry.py --test` still passes if registry self-tests exist.

## Phase 1 — Conversion-to-MusicXML pipeline hardening

### Goal

Make `music_to_musicxml_pipeline.py` robust enough to serve as the canonical input-normalization stage.

### Tasks

1. Add explicit route objects instead of route strings if complexity grows.
2. Add `--dry-run` alias for plan-only behavior.
3. Add `--strict` mode:
   - fail if input does not exist;
   - fail if required external tool is missing;
   - fail if expected MusicXML output is not generated.
4. Add tool-specific probes:
   - `musescore --version`
   - `audiveris -version` or equivalent
   - `verovio --version`
   - `python -c 'import music21'`
5. Add better Audiveris output discovery:
   - search per-book output folders;
   - prefer `.musicxml` over `.xml` and `.mxl` only when appropriate;
   - record all candidates in the report.
6. Add HTML asset classification:
   - PDF-like assets;
   - image-like assets;
   - MusicXML/MuseScore-like assets;
   - transformed crop / comparison asset warning.
7. Write normalized request and conversion report to output folder.

### Acceptance criteria

- For MusicXML input, the script copies or references the file without OMR.
- For MuseScore input, the script emits a MuseScore command and executes it when MuseScore is available.
- For PDF/image input, the script selects Audiveris and reports missing Audiveris honestly.
- For HTML input, the script produces `asset_inventory.json` and does not claim semantic conversion.
- JSON output is stable enough for downstream orchestration.

## Phase 2 — MusicXML parser and target selector

### Goal

Read MusicXML and map user language to exact musical targets.

### Proposed script

```text
.bago/tools/musicxml_target_select.py
```

### Tasks

1. Parse MusicXML with Python standard XML libraries first.
2. Extract:
   - parts;
   - measures;
   - staves;
   - voices;
   - notes/rests;
   - clefs;
   - key signatures;
   - time signatures;
   - repeats/coda text where available.
3. Build a score inventory:

```json
{
  "parts": [
    {
      "id": "P1",
      "name": "...",
      "measures": 26,
      "staves": [1, 2, 3],
      "voices": [1, 2]
    }
  ]
}
```

4. Implement selector normalization:
   - `bottom staff` -> maximum staff index per system/part when available;
   - `third staff` -> staff index 3;
   - `voice 3` -> MusicXML voice value 3;
   - `bass clef` -> staff/part where clef sign is F;
   - measure range syntax: `1-26`, `8-14`, `including coda`.
5. If target is ambiguous, produce a structured ambiguity report rather than guessing silently.

### Acceptance criteria

- Given a MusicXML file, BAGO can list parts/staves/voices/measures.
- Given `--target "staff 3"`, it resolves to a deterministic selector.
- Given `--target "bottom voice"`, it emits either a confident selector or a minimal clarification.
- No transposition occurs in this stage.

## Phase 3 — MusicXML transposition engine

### Goal

Transpose selected musical material in MusicXML while preserving everything else.

### Proposed script

```text
.bago/tools/musicxml_transpose.py
```

### Tasks

1. Implement pitch representation:
   - step: A-G;
   - alter: sharps/flats;
   - octave;
   - MIDI-like semitone value for interval math;
   - diatonic step movement for spelling where possible.
2. Support explicit intervals first:
   - `+M2`, `-M2`, `+m3`, `-m3`, `+P4`, `+P5`, `+P8`;
   - semitone fallback: `--semitones 2`.
3. Add destination key support after interval support:
   - infer original key from MusicXML key signature when possible;
   - compute interval to destination key;
   - warn if original key is uncertain.
4. Apply operation only to selected notes:
   - skip rests;
   - preserve duration;
   - preserve tie/slur/articulation nodes;
   - preserve voice/staff tags;
   - update pitch step/alter/octave.
5. Preserve non-target nodes byte-for-byte where feasible or semantically equivalent where XML serialization changes formatting.
6. Emit a change log:

```json
{
  "changed_notes": 123,
  "untouched_notes": 456,
  "target": {...},
  "interval": "+M2",
  "warnings": []
}
```

### Acceptance criteria

- Transposing `staff 3` changes only notes whose `<staff>` value matches 3.
- Rests are unchanged.
- Durations are unchanged.
- Non-target staves/voices are unchanged semantically.
- A JSON diff report is produced.

## Phase 4 — Validation engine

### Goal

Prevent false success claims.

### Proposed script

```text
.bago/tools/musicxml_validate.py
```

### Tasks

1. Compare original and transposed MusicXML.
2. Validate non-target preservation:
   - count notes/rests by part/staff/voice/measure;
   - compare pitch data outside target;
   - compare durations outside target.
3. Validate target transformation:
   - every target note moved by requested interval/semitones;
   - rests preserved;
   - durations preserved.
4. Validate measure rhythmic totals where possible.
5. Report OMR-derived uncertainty if conversion report exists.
6. Produce machine-readable validation result and human summary.

### Acceptance criteria

- Validation fails if non-target notes changed.
- Validation fails if target notes did not transpose consistently.
- Validation warns, not hides, if OMR confidence or conversion origin is uncertain.
- Exit code is non-zero on validation failure.

## Phase 5 — Rendering/export stage

### Goal

Render MusicXML output back to user-friendly PDF/SVG/PNG.

### Proposed script

```text
.bago/tools/musicxml_render.py
```

### Tasks

1. Detect renderers:
   - MuseScore CLI first;
   - Verovio for SVG/MEI-related workflows;
   - LilyPond only if a conversion route is later added.
2. Support:

```bash
bago music render --input out.musicxml --output out.pdf
bago music render --input out.musicxml --output out.svg
```

3. Generate renderer report:
   - tool used;
   - command run;
   - exit code;
   - output files.
4. Warn if layout differs from original due to re-engraving.

### Acceptance criteria

- MusicXML renders to PDF when MuseScore is installed.
- Missing renderer is reported as a dependency issue, not as pipeline failure.
- Output report is created.

## Phase 6 — End-to-end orchestrator

### Goal

Create one command that runs the whole process safely.

### Proposed command

```bash
bago music run --input score.pdf --target "bottom staff" --interval +M2 --output out.pdf
```

### Proposed script/router behavior

```text
bago_music.py
  plan       -> music_transpose_plan.py
  convert    -> music_to_musicxml_pipeline.py
  inventory  -> musicxml_target_select.py
  transpose  -> musicxml_transpose.py
  validate   -> musicxml_validate.py
  render     -> musicxml_render.py
  run        -> convert -> inventory -> transpose -> validate -> render
```

### Tasks

1. Define a working directory layout:

```text
build/music/
  input/
  musicxml/
  reports/
  rendered/
  logs/
```

2. Generate normalized request:

```text
build/music/reports/normalized_request.json
```

3. Execute stages with stop-on-failure behavior.
4. Use clear exit codes:
   - 0 success;
   - 1 usage/config error;
   - 2 conversion failure;
   - 3 target ambiguity;
   - 4 transposition failure;
   - 5 validation failure;
   - 6 rendering failure.
5. Add `--no-render` and `--plan-only` options.
6. Add `--accept-omr-risk` or similar flag before using OMR output as final.

### Acceptance criteria

- End-to-end command works for already-structured MusicXML without external OMR.
- PDF/image route produces a plan and dependency report even if Audiveris is missing.
- The orchestrator never silently skips validation.

## Phase 7 — Tests and fixtures

### Goal

Make the pipeline safe to evolve.

### Tasks

1. Add minimal synthetic MusicXML fixtures:
   - one part, one staff;
   - one part, three staves;
   - one staff with multiple voices;
   - rests and tied notes;
   - accidentals.
2. Add unit tests for:
   - file classification;
   - route selection;
   - target selector;
   - interval parser;
   - MusicXML pitch transformation;
   - non-target preservation;
   - validation failures.
3. Add tests for JSON schema stability.
4. Add fixture notes explaining that copyrighted scores should not be committed as test fixtures unless licensed.

### Acceptance criteria

- Tests run without external OMR tools by using MusicXML fixtures.
- External-tool tests are skipped when dependencies are missing.
- Core pipeline logic is covered independently from Audiveris/MuseScore availability.

## Phase 8 — BAGO quality and sincerity integration

### Goal

Make the new pipeline align with BAGO's evidence and honesty model.

### Tasks

1. Integrate with W2 Controlled Implementation for feature delivery.
2. Integrate with W4 Multi-cause Debug for OMR/rendering failures.
3. Integrate with W8 Exploration for tool comparisons.
4. Integrate with W10 Sincerity Audit:
   - reject claims of semantic transposition if only pixel shifting occurred;
   - mark OMR-derived results as OMR-assisted;
   - require validation report for final claims.
5. Ensure reports are stored as evidence artifacts when run inside a BAGO session.

### Acceptance criteria

- The pipeline output includes evidence files.
- The CLI summary states whether output is semantic, OMR-assisted, or visual-only.
- BAGO's existing validation/health commands are not degraded.

## Dependency strategy

BAGO currently presents itself as installable with Python standard library only. This pipeline should preserve that baseline by making external music tools optional.

Recommended dependency model:

- Core BAGO remains standard-library-only.
- Music pipeline scripts can plan without extra dependencies.
- Execution requires optional tools depending on route:
  - MuseScore CLI for `.mscz/.mscx` conversion and rendering;
  - Audiveris for PDF/image OMR;
  - music21 for MIDI or advanced MusicXML operations if chosen later;
  - Verovio for MEI/SVG workflows.

Document these as optional extras, not hard install requirements for BAGO core.

## Implementation order summary

1. Register `bago music` router.
2. Harden `music_to_musicxml_pipeline.py`.
3. Build MusicXML inventory/target selector.
4. Build interval-based MusicXML transposer.
5. Build validator.
6. Build renderer wrapper.
7. Build end-to-end `bago music run` orchestrator.
8. Add tests and fixtures.
9. Integrate evidence reporting and sincerity language.

## Definition of done

The integration is complete when this works:

```bash
bago music run \
  --input score.musicxml \
  --target "staff 3 measures 1-26" \
  --interval +M2 \
  --output build/music/rendered/score_transposed.pdf
```

And BAGO produces:

- converted/intermediate MusicXML;
- transposed MusicXML;
- validation report;
- diff report;
- rendered PDF or an honest renderer-missing report;
- clear statement of whether the result is semantic, OMR-assisted, or only planned.

For PDF/image inputs, the definition of done additionally requires:

- OMR conversion report;
- explicit OMR confidence/risk warning;
- validation against the original or human review checkpoint before claiming final editorial accuracy.

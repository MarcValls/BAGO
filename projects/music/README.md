# BAGO Music Pipeline

Music score processing, transposition, synthesis and MIDI integration tools — extracted from the [BAGO Framework](https://github.com/MarcValls/BAGO).

---

## What this is

A collection of Python tools and operational guides for:

1. **Score pipeline** — convert PDF / image / MusicXML / MIDI / MuseScore into structured notation and transpose selected parts
2. **Synthesis** — generate synth patterns (Karpovich, Disc Superstar)
3. **Ableton Live integration** — create MIDI tracks, manage sets, keyboard reference
4. **MIDI device setup** — configure BAGO as a virtual MIDI device via loopMIDI + teVirtualMIDI on Windows

---

## Structure

```
pipeline/           ← MusicXML score pipeline
  bago_music.py                   CLI router (plan / convert / transpose / validate / render)
  music_to_musicxml_pipeline.py   Convert PDF·image·MIDI·MSCZ → MusicXML
  music_transpose_plan.py         Generate transposition plan from user request
  musicxml_target_select.py       Select staff / part / voice / measure range
  musicxml_transpose.py           Semantic transposition engine
  musicxml_validate.py            Quality gates (duration, accidentals, non-target staves)
  musicxml_render.py              Export PDF / SVG / PNG preview + diff report

synths/             ← Pattern generators
  karpovich_synth.py              Karpovich harmonic synth engine
  disc_superstar_synth.py         Disc Superstar pattern generator

ableton/            ← Ableton Live integration (Windows)
  ableton_template.py             Create/manage Ableton sets via COM + SendKeys
  ableton_live_synth_setup.md     Mount synth channel in a live Ableton session (KK S49)
  ableton_keyboard_shortcuts.md   Full keyboard reference for Ableton 11
  ableton_techno_live_procedure.md Step-by-step live techno performance guide
  ableton_project_testing.md      How to test and validate an Ableton project

midi/               ← MIDI device setup
  bago_midi_device_setup.md       Configure BAGO as virtual MIDI port (loopMIDI + teVirtualMIDI)

docs/               ← Architecture and workflow docs
  music-score-transposition-pipeline.md   Full pipeline spec: file types, OMR, quality gates
  music-score-transposition.md            Operational workflow checklist
  music-tool-usage.md                     CLI usage examples
  music-pipeline-local-validation.md      Local validation procedure
  music-pipeline-integration-plan.md      Integration plan with BAGO workflows
```

---

## Quick start

### Score pipeline

```bash
# Plan only (no tools required)
python pipeline/bago_music.py plan --input score.pdf

# Convert to MusicXML (requires MuseScore or music21 installed)
python pipeline/bago_music.py convert --input score.mscz --out-dir build/

# Full pipeline: convert → select target → transpose → validate → render
python pipeline/bago_music.py run \
  --input score.pdf \
  --target "bottom staff" \
  --operation "transpose to E minor" \
  --out-dir build/
```

### MIDI device (Windows)

Full setup guide: [`midi/bago_midi_device_setup.md`](midi/bago_midi_device_setup.md)

Requirements: loopMIDI + teVirtualMIDI driver (one-time admin install).

Once installed, BAGO can create virtual MIDI ports and send notes to Ableton without admin rights:

```powershell
# Send a middle-C note to Ableton via virtual MIDI port "BAGO"
Add-Type @"
using System; using System.Runtime.InteropServices;
public class BAGOMIDI {
    public const uint TX_ONLY = 8;
    [DllImport("C:\\Windows\\System32\\teVirtualMIDI64.dll", CharSet=CharSet.Unicode)]
    public static extern IntPtr virtualMIDICreatePortEx2(string name, IntPtr cb, IntPtr inst, uint sysex, uint flags);
    [DllImport("C:\\Windows\\System32\\teVirtualMIDI64.dll")]
    public static extern bool virtualMIDISendData(IntPtr port, byte[] data, uint len);
    [DllImport("C:\\Windows\\System32\\teVirtualMIDI64.dll")]
    public static extern void virtualMIDIClosePort(IntPtr port);
}
"@
$port = [BAGOMIDI]::virtualMIDICreatePortEx2("BAGO", [IntPtr]::Zero, [IntPtr]::Zero, 256, [BAGOMIDI]::TX_ONLY)
[BAGOMIDI]::virtualMIDISendData($port, [byte[]](0x90, 60, 100), 3)  # Note ON C4
```

### Architecture (BAGO → Ableton)

```
BAGO (Python / PowerShell)
  → virtualMIDISendData(port, noteBytes)
  → teVirtualMIDI driver (kernel)
  → Virtual MIDI port "BAGO" (visible in Ableton as MIDI From)
  → MIDI track in Ableton Live
```

---

## Requirements

| Tool | Required for |
|------|-------------|
| Python 3.9+ | All pipeline scripts |
| [music21](https://web.mit.edu/music21/) | MIDI → MusicXML conversion |
| [MuseScore CLI](https://musescore.org/) | MSCZ/MSCX → MusicXML |
| [Audiveris](https://github.com/Audiveris/audiveris) | PDF/image OMR → MusicXML |
| [Verovio](https://www.verovio.org/) | MEI → MusicXML |
| [loopMIDI](https://www.tobias-erichsen.de/software/loopmidi.html) + teVirtualMIDI | Virtual MIDI ports (Windows) |
| Ableton Live 11+ | Live performance + MIDI routing |

All Python tools degrade gracefully: if a converter is not installed, they emit an executable plan instead of failing silently.

---

## Built with BAGO

This project was built across multiple W2 (Controlled Implementation) sessions using [BAGO](https://github.com/MarcValls/BAGO) — a repo-local AI work framework that tracks workflows, ideas, and audit trails between agent sessions.

---

*May 2026 · MIT License*

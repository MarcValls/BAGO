from __future__ import annotations

import copy
import json
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from xml.etree import ElementTree as ET


MUSICXML_SUFFIXES = {".xml", ".musicxml", ".mxl"}
IMAGE_SUFFIXES = {".pdf", ".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp"}
OPERATIONS = {"analizar", "convertir", "transponer", "separar_voces", "completo"}
PITCHES = (("C", 0), ("C", 1), ("D", 0), ("D", 1), ("E", 0), ("F", 0), ("F", 1), ("G", 0), ("G", 1), ("A", 0), ("A", 1), ("B", 0))
STEP_VALUE = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
PITCH_CLASS_NAMES = ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B")
TRIADS = {
    **{frozenset({root, (root + 4) % 12, (root + 7) % 12}): f"{PITCH_CLASS_NAMES[root]} mayor" for root in range(12)},
    **{frozenset({root, (root + 3) % 12, (root + 7) % 12}): f"{PITCH_CLASS_NAMES[root]} menor" for root in range(12)},
}


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def direct_child(element: ET.Element, name: str) -> ET.Element | None:
    return next((child for child in element if local_name(child.tag) == name), None)


def text_of(element: ET.Element, name: str, default: str = "") -> str:
    child = direct_child(element, name)
    return str(child.text or default).strip() if child is not None else default


def safe_name(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9._-]+", "-", value).strip("-.") or "score"


def resolve_output_dir(source: Path, configured: str) -> Path:
    output = Path(configured).expanduser() if configured.strip() else source.parent / f"{safe_name(source.stem)}-bago"
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    return output


def musicxml_bytes(source: Path) -> bytes:
    if source.suffix.lower() != ".mxl":
        return source.read_bytes()
    if source.stat().st_size > 50 * 1024 * 1024:
        raise ValueError("El MXL supera el límite de 50 MB")
    with zipfile.ZipFile(source) as archive:
        members = archive.infolist()
        if len(members) > 1000 or sum(item.file_size for item in members) > 100 * 1024 * 1024:
            raise ValueError("El contenido MXL es demasiado grande")
        container = ET.fromstring(archive.read("META-INF/container.xml"))
        rootfile = next((item.attrib.get("full-path", "") for item in container.iter() if local_name(item.tag) == "rootfile"), "")
        relative = PurePosixPath(rootfile)
        if not rootfile or relative.is_absolute() or ".." in relative.parts:
            raise ValueError("El MXL no declara un MusicXML seguro")
        return archive.read(str(relative))


def parse_musicxml(source: Path) -> ET.ElementTree:
    try:
        root = ET.fromstring(musicxml_bytes(source))
    except (ET.ParseError, KeyError, zipfile.BadZipFile) as exc:
        raise ValueError(f"MusicXML no válido: {exc}") from exc
    if local_name(root.tag) not in {"score-partwise", "score-timewise"}:
        raise ValueError("El XML no contiene una partitura MusicXML")
    return ET.ElementTree(root)


def write_tree(tree: ET.ElementTree, target: Path) -> Path:
    ET.indent(tree, space="  ")
    tree.write(target, encoding="utf-8", xml_declaration=True)
    return target


def midi_value(note: ET.Element) -> int | None:
    pitch = direct_child(note, "pitch")
    if pitch is None:
        return None
    step = text_of(pitch, "step")
    if step not in STEP_VALUE:
        return None
    octave = int(text_of(pitch, "octave", "4"))
    alter = int(float(text_of(pitch, "alter", "0")))
    return (octave + 1) * 12 + STEP_VALUE[step] + alter


def validate_structure(tree: ET.ElementTree) -> dict:
    root = tree.getroot()
    declared_parts = {item.attrib.get("id", "") for item in root.iter() if local_name(item.tag) == "score-part"}
    parts = [item for item in root.iter() if local_name(item.tag) == "part"]
    actual_parts = {item.attrib.get("id", "") for item in parts}
    errors = []
    warnings = []
    if not parts:
        errors.append("La partitura no contiene partes")
    if declared_parts != actual_parts:
        errors.append("part-list y partes musicales no coinciden")
    for part in parts:
        measures = [item for item in part if local_name(item.tag) == "measure"]
        if not measures:
            errors.append(f"La parte {part.attrib.get('id', '?')} no contiene compases")
        for measure in measures:
            notes = [item for item in measure if local_name(item.tag) == "note"]
            if not notes:
                warnings.append(f"Compás {measure.attrib.get('number', '?')} sin notas")
            for note in notes:
                if direct_child(note, "duration") is None and direct_child(note, "grace") is None:
                    warnings.append(f"Nota sin duración en compás {measure.attrib.get('number', '?')}")
    return {"valid": not errors, "errors": errors, "warnings": warnings}


def harmonic_analysis(tree: ET.ElementTree) -> dict:
    histogram = {name: 0 for name in PITCH_CLASS_NAMES}
    measure_chords = []
    for measure in (item for item in tree.getroot().iter() if local_name(item.tag) == "measure"):
        pitch_classes = []
        for note in (item for item in measure.iter() if local_name(item.tag) == "note"):
            midi = midi_value(note)
            if midi is not None:
                pitch_class = midi % 12
                pitch_classes.append(pitch_class)
                histogram[PITCH_CLASS_NAMES[pitch_class]] += 1
        observed = set(pitch_classes)
        matches = [name for tones, name in TRIADS.items() if tones.issubset(observed)]
        measure_chords.append({
            "measure": measure.attrib.get("number", ""),
            "pitch_classes": [PITCH_CLASS_NAMES[value] for value in sorted(observed)],
            "chords": matches,
        })
    return {
        "pitch_class_histogram": {name: count for name, count in histogram.items() if count},
        "measure_chords": measure_chords,
        "method": "pitch-class triad matching",
    }


def find_audiveris_export(output_dir: Path, source: Path) -> Path:
    candidates = [item for item in output_dir.rglob("*") if item.is_file() and item.suffix.lower() in MUSICXML_SUFFIXES]
    if not candidates:
        raise RuntimeError(f"Audiveris terminó sin generar MusicXML para {source.name}")
    return max(candidates, key=lambda item: item.stat().st_mtime)


def native_short_path(path: Path) -> str:
    if sys.platform != "win32":
        return str(path)
    import ctypes

    buffer = ctypes.create_unicode_buffer(32768)
    length = ctypes.windll.kernel32.GetShortPathNameW(str(path), buffer, len(buffer))
    return buffer.value if 0 < length < len(buffer) else str(path)


def run_audiveris(source: Path, output_dir: Path, executable: str, timeout_s: int) -> tuple[Path, dict]:
    audiveris = Path(executable).expanduser().resolve()
    if not audiveris.is_file():
        raise FileNotFoundError(f"Audiveris no está disponible en {audiveris}")
    effective_timeout = max(30, min(int(timeout_s), 540))
    with tempfile.TemporaryDirectory(prefix="bago-score-omr-") as temporary:
        staging = Path(temporary)
        staged_source = staging / f"input{source.suffix.lower()}"
        staged_output = staging / "output"
        staged_output.mkdir()
        shutil.copy2(source, staged_source)
        command = [
            str(audiveris), "-batch", "-export", "-output",
            native_short_path(staged_output), "--", native_short_path(staged_source),
        ]
        try:
            completed = subprocess.run(
                command,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=effective_timeout,
                shell=False,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(f"Audiveris superó el límite de {effective_timeout} segundos") from exc
        diagnostics = {
            "engine": "Audiveris",
            "executable": str(audiveris),
            "exit_code": completed.returncode,
            "staged_input": True,
            "stdout": completed.stdout[-8000:].strip(),
            "stderr": completed.stderr[-8000:].strip(),
        }
        if completed.returncode != 0:
            raise RuntimeError(diagnostics["stderr"] or diagnostics["stdout"] or f"Audiveris terminó con código {completed.returncode}")
        staged_primary = find_audiveris_export(staged_output, source)
        exported = []
        for item in staged_output.rglob("*"):
            if not item.is_file() or item.suffix.lower() not in MUSICXML_SUFFIXES:
                continue
            target_name = re.sub(r"^input", safe_name(source.stem), item.name, flags=re.IGNORECASE)
            target = output_dir / target_name
            shutil.copy2(item, target)
            exported.append(target)
        primary_name = re.sub(r"^input", safe_name(source.stem), staged_primary.name, flags=re.IGNORECASE)
        primary = output_dir / primary_name
        diagnostics["exports"] = [str(item) for item in exported]
        return primary, diagnostics


def normalized_musicxml(source: Path, output_dir: Path) -> tuple[Path, ET.ElementTree]:
    tree = parse_musicxml(source)
    target = output_dir / f"{safe_name(source.stem)}.normalized.musicxml"
    return write_tree(tree, target), tree


def analyze(tree: ET.ElementTree) -> dict:
    root = tree.getroot()
    parts = [element for element in root.iter() if local_name(element.tag) == "part"]
    measures = [element for element in root.iter() if local_name(element.tag) == "measure"]
    notes = [element for element in root.iter() if local_name(element.tag) == "note"]
    rests = [note for note in notes if direct_child(note, "rest") is not None]
    pitched = [note for note in notes if direct_child(note, "pitch") is not None]
    voices = sorted({text_of(note, "voice", "1") for note in notes})
    pitch_values = [value for note in pitched if (value := midi_value(note)) is not None]
    title = next((str(item.text or "").strip() for item in root.iter() if local_name(item.tag) in {"work-title", "movement-title"} and str(item.text or "").strip()), "")
    composer = next((str(item.text or "").strip() for item in root.iter() if local_name(item.tag) == "creator" and item.attrib.get("type") == "composer"), "")
    return {
        "title": title,
        "composer": composer,
        "parts": len(parts),
        "measures": len(measures),
        "notes": len(notes),
        "pitched_notes": len(pitched),
        "rests": len(rests),
        "voices": voices,
        "pitch_midi": {"min": min(pitch_values), "max": max(pitch_values)} if pitch_values else None,
        "structure": validate_structure(tree),
        "harmony": harmonic_analysis(tree),
    }


def transpose(tree: ET.ElementTree, semitones: int, output_dir: Path, stem: str) -> Path:
    shifted = copy.deepcopy(tree)
    for pitch in (element for element in shifted.getroot().iter() if local_name(element.tag) == "pitch"):
        step_node = direct_child(pitch, "step")
        octave_node = direct_child(pitch, "octave")
        alter_node = direct_child(pitch, "alter")
        if step_node is None or octave_node is None or str(step_node.text) not in STEP_VALUE:
            continue
        midi = (int(str(octave_node.text)) + 1) * 12 + STEP_VALUE[str(step_node.text)] + int(float(str(alter_node.text or 0))) if alter_node is not None else (int(str(octave_node.text)) + 1) * 12 + STEP_VALUE[str(step_node.text)]
        target = midi + semitones
        step, alter = PITCHES[target % 12]
        step_node.text = step
        octave_node.text = str(target // 12 - 1)
        if alter:
            if alter_node is None:
                namespace = pitch.tag.split("}", 1)[0] + "}" if "}" in pitch.tag else ""
                alter_node = ET.Element(f"{namespace}alter")
                pitch.insert(1, alter_node)
            alter_node.text = str(alter)
        elif alter_node is not None:
            pitch.remove(alter_node)
    return write_tree(shifted, output_dir / f"{safe_name(stem)}.transpose-{semitones:+d}.musicxml")


def separate_voices(tree: ET.ElementTree, output_dir: Path, stem: str) -> list[str]:
    voices = sorted({text_of(note, "voice", "1") for note in tree.getroot().iter() if local_name(note.tag) == "note"})
    outputs = []
    for voice in voices:
        separated = copy.deepcopy(tree)
        for measure in (element for element in separated.getroot().iter() if local_name(element.tag) == "measure"):
            for note in [child for child in list(measure) if local_name(child.tag) == "note"]:
                if text_of(note, "voice", "1") != voice:
                    measure.remove(note)
        target = write_tree(separated, output_dir / f"{safe_name(stem)}.voice-{safe_name(voice)}.musicxml")
        outputs.append(str(target))
    return outputs


def execute(payload: dict) -> dict:
    inputs = payload.get("input") or {}
    config = payload.get("config") or {}
    source = Path(str(inputs.get("source_path") or "")).expanduser().resolve()
    operation = str(inputs.get("operation") or "completo")
    semitones = int(inputs.get("semitones") or 0)
    if not source.is_file():
        raise FileNotFoundError(f"No existe la partitura: {source}")
    if source.suffix.lower() not in MUSICXML_SUFFIXES | IMAGE_SUFFIXES:
        raise ValueError(f"Formato no soportado: {source.suffix or '(sin extensión)'}")
    if operation not in OPERATIONS:
        raise ValueError(f"Operación no soportada: {operation}")

    output_dir = resolve_output_dir(source, str(config.get("output_dir") or ""))
    route = "musicxml-direct"
    engine = {"engine": "MusicXML", "exit_code": 0}
    working_source = source
    if source.suffix.lower() in IMAGE_SUFFIXES:
        route = "audiveris-omr"
        working_source, engine = run_audiveris(
            source,
            output_dir,
            str(config.get("audiveris_path") or r"C:\Program Files\Audiveris\Audiveris.exe"),
            int(config.get("audiveris_timeout_s") or 540),
        )

    normalized_path, tree = normalized_musicxml(working_source, output_dir)
    result = {
        "ok": True,
        "operation": operation,
        "route": route,
        "source": str(source),
        "normalized_musicxml": str(normalized_path),
        "analysis": analyze(tree),
        "engine": engine,
        "outputs": [str(normalized_path)],
    }
    if operation in {"transponer", "completo"} and semitones:
        transposed = transpose(tree, semitones, output_dir, source.stem)
        result["transposed_musicxml"] = str(transposed)
        result["outputs"].append(str(transposed))
    if operation == "separar_voces" or (operation == "completo" and bool(config.get("separate_voices_in_full", True))):
        voice_outputs = separate_voices(tree, output_dir, source.stem)
        result["voice_musicxml"] = voice_outputs
        result["outputs"].extend(voice_outputs)
    if operation == "convertir":
        result["analysis"] = {"converted": True, "format": "MusicXML"}
    return result


def main() -> None:
    payload = json.load(sys.stdin)
    print(json.dumps(execute(payload), ensure_ascii=False))


if __name__ == "__main__":
    main()

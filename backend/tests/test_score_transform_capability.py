from __future__ import annotations

import base64
import io
import json
import subprocess
import zipfile
from pathlib import Path

import pytest

import capability_packages as packages


ROOT = Path(__file__).resolve().parents[2]
PACKAGE_ROOT = ROOT / "examples" / "capabilities" / "score-transform"
AUDIVERIS = Path(r"C:\Program Files\Audiveris\Audiveris.exe")


def package_base64() -> str:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.write(PACKAGE_ROOT / "capability.json", "capability.json")
        archive.write(PACKAGE_ROOT / "run.py", "run.py")
    return base64.b64encode(buffer.getvalue()).decode("ascii")


def test_package_executes_musicxml_pipeline_with_receipt(tmp_path, monkeypatch):
    monkeypatch.setattr(packages, "state_root", lambda: tmp_path / "state")
    imported = packages.import_package(
        content_base64=package_base64(),
        file_name="music.score-transform-1.0.0.zip",
        confirm_trust=True,
    )
    assert imported["package"]["permissions"] == ["filesystem.read", "filesystem.write", "process"]
    packages.set_enabled("music.score-transform", True)
    packages.configure_package("music.score-transform", {
        "audiveris_path": str(AUDIVERIS),
        "output_dir": str(tmp_path / "output"),
        "audiveris_timeout_s": 540,
        "separate_voices_in_full": True,
    })

    result = packages.execute_package(
        "music.score-transform",
        inputs={
            "source_path": str(PACKAGE_ROOT / "sample.musicxml"),
            "operation": "completo",
            "semitones": 2,
        },
        confirmed=True,
        approved_permissions=["filesystem.read", "filesystem.write", "process"],
    )

    assert result["ok"] is True
    payload = result["receipt"]["result"]
    assert payload["route"] == "musicxml-direct"
    assert payload["analysis"]["notes"] == 4
    assert payload["analysis"]["voices"] == ["1", "2"]
    assert payload["analysis"]["structure"]["valid"] is True
    assert payload["analysis"]["harmony"]["measure_chords"][0]["chords"] == ["C mayor"]
    assert Path(payload["transposed_musicxml"]).is_file()
    assert len(payload["voice_musicxml"]) == 2
    assert all(Path(item).is_file() for item in payload["outputs"])


@pytest.mark.skipif(not AUDIVERIS.is_file(), reason="Audiveris no está instalado")
def test_installed_audiveris_cli_is_available():
    completed = subprocess.run(
        [str(AUDIVERIS), "-version"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
        shell=False,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        check=False,
    )
    assert completed.returncode == 0
    assert "Audiveris" in f"{completed.stdout}\n{completed.stderr}"

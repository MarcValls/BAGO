"""Regression tests for environments without prompt_toolkit."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
CHAT = ROOT / ".bago" / "tools" / "bago_chat.py"
MUSIC_SAAS = ROOT / ".bago" / "tools" / "music_saas.py"


def test_bago_chat_help_works_without_prompt_toolkit():
    env = {
        **os.environ,
        "PYTHONIOENCODING": "utf-8",
        "BAGO_NO_PROMPT_TOOLKIT": "1",
    }
    result = subprocess.run(
        [sys.executable, str(CHAT), "--help"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=15,
        env=env,
    )
    assert result.returncode == 0
    assert "BAGO Orchestrator HUB" in result.stdout


def test_bago_package_import_works_without_litellm():
    env = {
        **os.environ,
        "PYTHONIOENCODING": "utf-8",
        "BAGO_NO_LITELLM": "1",
    }
    code = (
        "import sys; "
        f"sys.path.insert(0, {str(ROOT / '.bago' / 'tools')!r}); "
        "import bago; "
        "print('ok')"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=15,
        env=env,
    )
    assert result.returncode == 0
    assert result.stdout.strip().endswith("ok")


def test_music_saas_no_args_shows_help_without_unknown_command():
    result = subprocess.run(
        [sys.executable, str(MUSIC_SAAS), "music-saas"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=15,
    )
    output = result.stdout + result.stderr
    assert result.returncode == 0
    assert "bago music-saas [comando]" in result.stdout
    assert "Comando desconocido" not in output


def test_music_saas_dev_without_git_fails_cleanly(tmp_path):
    env = {
        **os.environ,
        "PATH": str(tmp_path),
        "BAGO_MUSIC_SAAS_DIR": str(tmp_path / "bago-music-saas"),
    }
    result = subprocess.run(
        [sys.executable, str(MUSIC_SAAS), "dev"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=15,
        env=env,
    )
    output = result.stdout + result.stderr
    assert result.returncode == 2
    assert "No se encuentra 'git'" in output
    assert "Traceback" not in output

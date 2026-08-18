from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _write_minimal_source_tree(root: Path) -> Path:
    current = root / "current"
    (current / "bago_core").mkdir(parents=True, exist_ok=True)
    (current / "bago_core" / "launcher.py").write_text("print('ok')\n", encoding="utf-8")
    (current / "install-v4.ps1").write_text("Write-Host 'install'\n", encoding="utf-8")
    (current / "release_version.txt").write_text("v4.8.0\n", encoding="utf-8")
    manifest = {
        "package": "current",
        "created_at": "2026-01-01T00:00:00+00:00",
        "root": "<repo>",
        "tree_root": "current",
        "release_version": "4.8.0",
        "file_count": 3,
        "tree_sha256": "0" * 64,
        "included_files": [
            {"path": "bago_core/launcher.py", "size": 12, "sha256": "0" * 64},
            {"path": "install-v4.ps1", "size": 20, "sha256": "0" * 64},
            {"path": "release_version.txt", "size": 8, "sha256": "0" * 64},
        ],
        "excluded_prefixes": [],
        "forbidden_names": [],
    }
    (root / "current.manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return current


def test_install_assistant_resolves_current_tree(tmp_path):
    source_root = tmp_path / "release" / "v4"
    current = _write_minimal_source_tree(source_root)
    result = subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(REPO_ROOT / "install-assistant.ps1"),
            "-SourceRoot",
            str(source_root),
            "-DryRun",
            "-AssumeYes",
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    assert str(current) in result.stdout
    assert "No se ejecuta el instalador." in result.stdout

    validate = subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts" / "validate_pack_contents.py"),
            str(source_root),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    assert "tree contents valid" in validate.stdout

    script = (REPO_ROOT / "install-assistant.ps1").read_text(encoding="utf-8")
    assert "$PROFILE.CurrentUserAllHosts" in script
    assert "$PROFILE.CurrentUserCurrentHost" in script

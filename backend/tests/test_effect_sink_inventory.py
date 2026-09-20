from __future__ import annotations

from pathlib import Path

import effect_registry
import effect_sink_inventory as inventory


def test_python_scanner_classifies_material_sinks(tmp_path: Path) -> None:
    source = tmp_path / "sample.py"
    source.write_text(
        "\n".join(
            [
                "from pathlib import Path",
                "import subprocess",
                "import requests",
                "Path('a.txt').write_text('x', encoding='utf-8')",
                "subprocess.run(['echo', 'ok'])",
                "requests.post('https://example.invalid', json={'x': 1})",
            ]
        ),
        encoding="utf-8",
    )

    findings = inventory.scan_python(source)
    effects = {item.effect_id for item in findings}
    assert "filesystem.write" in effects
    assert "process.execute" in effects
    assert "network.external_write" in effects


def test_powershell_scanner_classifies_process_and_delete(tmp_path: Path) -> None:
    script = tmp_path / "sample.ps1"
    script.write_text(
        "Start-Process powershell.exe\nRemove-Item -Recurse -Force $target\n",
        encoding="utf-8",
    )

    findings = inventory.scan_paths([script])
    effects = {item.effect_id for item in findings}
    assert "process.execute" in effects
    assert "filesystem.delete" in effects


def test_all_scanner_effect_ids_exist_in_canonical_registry() -> None:
    declared = {effect.id for effect in effect_registry.REGISTRY.effects}
    scanner_ids = {
        effect_id
        for _, effect_id, _ in inventory.PYTHON_SUFFIX_RULES
    }
    scanner_ids |= {
        effect_id
        for _, effect_id, _ in inventory.POWERSHELL_RULES
    }
    scanner_ids |= {
        effect_id
        for _, effect_id, _ in inventory.JS_RULES
    }
    assert scanner_ids <= declared


def test_known_bago_sinks_are_reported_as_unbound_before_migration() -> None:
    files_handler = inventory.REPO_ROOT / "backend" / ".bago" / "api" / "handlers_files.py"
    github_handler = inventory.REPO_ROOT / "backend" / ".bago" / "api" / "handlers_github.py"

    file_findings = inventory.scan_python(files_handler)
    github_findings = inventory.scan_python(github_handler)

    assert any(
        item.effect_id == "filesystem.write" and item.binding == "unbound"
        for item in file_findings
    )
    assert any(
        item.effect_id == "process.execute" and item.binding == "unbound"
        for item in github_findings
    )


def test_authorization_ledger_sink_is_explicitly_authority_internal() -> None:
    boundary = (
        inventory.REPO_ROOT
        / "backend"
        / ".bago"
        / "core"
        / "authorization_boundary.py"
    )
    findings = inventory.scan_python(boundary)
    assert findings
    assert all(item.binding == "authority_internal" for item in findings)

from __future__ import annotations

import sys
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


def test_gateway_owned_filesystem_findings_are_retained_and_bound(monkeypatch) -> None:
    filesystem_effects = (
        inventory.REPO_ROOT
        / "backend"
        / ".bago"
        / "core"
        / "filesystem_effects.py"
    )
    findings = inventory.scan_python(filesystem_effects)

    with monkeypatch.context() as isolated:
        isolated.setattr(inventory, "GATEWAY_OWNED_PATHS", set())
        unbound_findings = inventory.scan_python(filesystem_effects)

    assert [
        (item.line, item.column, item.sink, item.effect_id, item.confidence)
        for item in findings
    ] == [
        (item.line, item.column, item.sink, item.effect_id, item.confidence)
        for item in unbound_findings
    ]
    assert findings
    assert all(item.binding == "gateway_owned" for item in findings)


def test_execution_gateway_adapter_material_sink_is_gateway_owned(tmp_path: Path, monkeypatch) -> None:
    gateway = tmp_path / "backend" / ".bago" / "core" / "execution_gateway.py"
    gateway.parent.mkdir(parents=True)
    gateway.write_text(
        "from pathlib import Path\n\n"
        "class ExampleEffectAdapter:\n"
        "    def execute(self):\n"
        "        Path('receipt.txt').write_text('ok', encoding='utf-8')\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(inventory, "REPO_ROOT", tmp_path)

    findings = inventory.scan_python(gateway)

    assert len(findings) == 1
    assert findings[0].effect_id == "filesystem.write"
    assert findings[0].binding == "gateway_owned"


def test_handlers_github_remains_unbound() -> None:
    github_handler = inventory.REPO_ROOT / "backend" / ".bago" / "api" / "handlers_github.py"

    github_findings = inventory.scan_python(github_handler)

    assert any(
        item.effect_id == "process.execute" and item.binding == "unbound"
        for item in github_findings
    )
    assert all(item.scope == inventory.SCOPE_RUNTIME_AUTHORITY for item in github_findings)
    assert all(item.binding_class == "runtime_unbound" for item in github_findings)


def test_strict_fails_while_legacy_unbound_sinks_exist(monkeypatch) -> None:
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "effect_sink_inventory.py",
            "--strict",
            "--root",
            "backend/.bago/api/handlers_github.py",
        ],
    )

    assert inventory.main() == 2


def test_global_inventory_has_explicit_scope_and_binding_for_every_finding() -> None:
    result = inventory.build_inventory()
    summary = result["summary"]

    assert summary["unclassified_scope_sinks"] == 0
    assert summary["unclassified_binding_sinks"] == 0
    assert sum(summary["by_scope"].values()) == summary["total_sinks"]
    assert sum(summary["by_binding_class"].values()) == summary["total_sinks"]
    assert all(item["scope"] != inventory.SCOPE_UNCLASSIFIED for item in result["findings"])


def test_strict_classification_closes_inventory_without_promoting_gateway(monkeypatch) -> None:
    monkeypatch.setattr(
        sys,
        "argv",
        ["effect_sink_inventory.py", "--strict-classification"],
    )

    assert inventory.main() == 0


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

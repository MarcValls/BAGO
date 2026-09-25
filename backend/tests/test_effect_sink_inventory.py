from __future__ import annotations

import ast
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


def test_python_scanner_detects_bound_path_open_write_modes(tmp_path: Path) -> None:
    source = tmp_path / "path-open-modes.py"
    source.write_text(
        "from pathlib import Path\n"
        "Path('append.jsonl').open('a', encoding='utf-8')\n"
        "Path('replace.json').open(mode='w', encoding='utf-8')\n"
        "open('builtin.json', 'w', encoding='utf-8')\n"
        "Path.open(Path('unbound.json'), 'x', encoding='utf-8')\n"
        "Path('read.json').open('r', encoding='utf-8')\n"
        "open('read.json', 'r', encoding='utf-8')\n",
        encoding="utf-8",
    )

    findings = inventory.scan_python(source)

    assert [(item.line, item.effect_id) for item in findings] == [
        (2, "filesystem.write"),
        (3, "filesystem.write"),
        (4, "filesystem.write"),
        (5, "filesystem.write"),
    ]


def test_python_scanner_detects_sqlite_database_materialization_and_mutations(tmp_path: Path) -> None:
    source = tmp_path / "sqlite-writes.py"
    source.write_text(
        "import sqlite3\n"
        "connection = sqlite3.connect('knowledge.db')\n"
        "connection.execute('SELECT * FROM memories')\n"
        "connection.execute('CREATE TABLE memories(id INTEGER)')\n"
        "connection.execute('PRAGMA journal_mode=WAL')\n"
        "connection.execute('PRAGMA busy_timeout=30000')\n"
        "connection.execute('PRAGMA synchronous=NORMAL')\n"
        "connection.execute('PRAGMA table_info(memories)')\n"
        "connection.executemany('INSERT INTO memories VALUES (?)', rows)\n"
        "connection.executescript(SCHEMA)\n"
        "readonly = sqlite3.connect('file:readonly.db?mode=ro', uri=True)\n"
        "memory = sqlite3.connect(':memory:')\n",
        encoding="utf-8",
    )

    findings = inventory.scan_python(source)

    assert [(item.line, item.effect_id) for item in findings] == [
        (2, "database.write"),
        (4, "database.write"),
        (5, "database.write"),
        (9, "database.write"),
        (10, "database.write"),
    ]


def test_python_scanner_excludes_explicit_readonly_sqlite_uri(tmp_path: Path) -> None:
    source = tmp_path / "readonly-sqlite.py"
    source.write_text(
        "import sqlite3\n"
        "sqlite3.connect(f'{db.as_uri()}?mode=ro', uri=True)\n",
        encoding="utf-8",
    )

    assert inventory.scan_python(source) == []


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


def test_javascript_scanner_detects_process_termination_but_not_liveness_probe(tmp_path: Path) -> None:
    source = tmp_path / "process-lifecycle.cjs"
    source.write_text(
        "child.kill()\nchild.kill('SIGTERM')\nprocess.kill(pid, 0)\nprocess.kill(pid, signal.SIGTERM)\n",
        encoding="utf-8",
    )

    findings = inventory.scan_paths([source])

    assert [(item.line, item.effect_id) for item in findings] == [
        (1, "process.terminate"),
        (2, "process.terminate"),
        (4, "process.terminate"),
    ]


def test_powershell_scanner_detects_registry_environment_and_dotnet_file_writes(tmp_path: Path) -> None:
    script = tmp_path / "installer-effects.ps1"
    script.write_text(
        "New-ItemProperty -Path $key -Name Path -Value $value\n"
        "Set-Item -Path $key -Value $value\n"
        "[Environment]::SetEnvironmentVariable('Path', $value, 'Machine')\n"
        "[System.IO.File]::WriteAllText($path, $json)\n",
        encoding="utf-8",
    )

    findings = inventory.scan_paths([script])

    assert {(item.line, item.effect_id) for item in findings} == {
        (1, "system.configuration.write"),
        (2, "system.configuration.write"),
        (3, "system.configuration.write"),
        (4, "filesystem.write"),
    }


def test_install_v4_inventory_retains_effects_under_ticket_bound_gateway_owner() -> None:
    installer = inventory.REPO_ROOT / "backend" / "install-v4.ps1"

    findings = inventory.scan_paths([installer])
    configuration_writes = [item for item in findings if item.effect_id == "system.configuration.write"]

    assert len(configuration_writes) == 5
    assert len(findings) >= 40
    assert {item.binding_class for item in findings} == {"gateway_adapter"}
    assert {item.scope for item in findings} == {inventory.SCOPE_RUNTIME_AUTHORITY}


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
    scanner_ids.add(inventory.SQLITE_EFFECT_ID)
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


def test_project_memory_material_sinks_remain_visible_and_gateway_owned(monkeypatch) -> None:
    project_memory = inventory.REPO_ROOT / "backend" / ".bago" / "tools" / "project_memory.py"
    findings = inventory.scan_python(project_memory)
    with monkeypatch.context() as isolated:
        isolated.setattr(inventory, "GATEWAY_OWNED_PATHS", set())
        unbound = inventory.scan_python(project_memory)

    projection = lambda items: [
        (item.line, item.column, item.sink, item.effect_id, item.confidence)
        for item in items
    ]
    assert projection(findings) == projection(unbound)
    assert len(findings) == 14
    assert all(item.binding == "gateway_owned" for item in findings)
    assert all(item.binding_class == "gateway_adapter" for item in findings)


def test_seed_material_sinks_remain_visible_and_gateway_owned(monkeypatch) -> None:
    seed = inventory.REPO_ROOT / "backend" / ".bago" / "seed.py"
    findings = inventory.scan_python(seed)
    with monkeypatch.context() as isolated:
        isolated.setattr(inventory, "GATEWAY_OWNED_PATHS", set())
        unbound = inventory.scan_python(seed)

    projection = lambda items: [
        (item.line, item.column, item.sink, item.effect_id, item.confidence)
        for item in items
    ]
    assert projection(findings) == projection(unbound)
    assert len(findings) == 5
    assert all(item.binding == "gateway_owned" for item in findings)
    assert all(item.binding_class == "gateway_adapter" for item in findings)


def test_evidence_io_sinks_remain_visible_and_gateway_owned(monkeypatch) -> None:
    evidence_io = inventory.REPO_ROOT / "backend" / "bago_core" / "evidence_io.py"
    findings = inventory.scan_python(evidence_io)
    with monkeypatch.context() as isolated:
        isolated.setattr(inventory, "GATEWAY_OWNED_PATHS", set())
        unbound = inventory.scan_python(evidence_io)
    projection = lambda items: [(item.line, item.column, item.sink, item.effect_id, item.confidence) for item in items]
    assert projection(findings) == projection(unbound)
    assert len(findings) == 8
    assert all(item.binding == "gateway_owned" for item in findings)
    assert all(item.binding_class == "gateway_adapter" for item in findings)


def test_evidence_bundle_private_materializer_has_one_gateway_caller() -> None:
    backend = inventory.REPO_ROOT / "backend"
    callsites: list[Path] = []
    for source_path in inventory._iter_files([backend]):
        if source_path.suffix.lower() != ".py" or "tests" in source_path.parts:
            continue
        try:
            tree = ast.parse(source_path.read_text(encoding="utf-8", errors="replace"))
        except (OSError, SyntaxError):
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "_materialize_bundle":
                callsites.append(source_path.resolve())
    expected = (backend / ".bago" / "core" / "execution_adapters" / "evidence_bundle.py").resolve()
    assert set(callsites) == {expected}


def test_standalone_archive_rollback_is_inert_and_gateway_adapter_owns_sinks() -> None:
    script = inventory.REPO_ROOT / "backend" / "rollback-bago.ps1"
    adapter = inventory.REPO_ROOT / "backend" / ".bago" / "core" / "execution_adapters" / "archive_rollback.py"
    assert inventory.scan_paths([script]) == []
    findings = inventory.scan_python(adapter)
    assert findings
    assert all(item.binding == "gateway_owned" for item in findings)
    assert all(item.binding_class == "gateway_adapter" for item in findings)


def test_release_update_helper_sinks_remain_visible_and_require_gateway_ticket() -> None:
    helper = inventory.REPO_ROOT / "backend" / ".bago" / "api" / "apply_release_update.ps1"

    findings = inventory.scan_paths([helper])

    assert len(findings) == 18
    assert all(item.binding == "gateway_owned" for item in findings)
    assert all(item.binding_class == "gateway_adapter" for item in findings)
    assert all(item.scope == inventory.SCOPE_RUNTIME_AUTHORITY for item in findings)


def test_project_memory_runtime_materializers_have_one_gateway_dispatch_path() -> None:
    backend = inventory.REPO_ROOT / "backend"
    materializers = {"init_project", "link_project", "seed_project", "create_demo_project"}
    callsites: list[Path] = []
    for source_path in inventory._iter_files([backend]):
        if source_path.suffix.lower() != ".py" or "tests" in source_path.parts:
            continue
        try:
            tree = ast.parse(source_path.read_text(encoding="utf-8", errors="replace"))
        except (OSError, SyntaxError):
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
                continue
            if (
                isinstance(node.func.value, ast.Name)
                and node.func.value.id == "project_memory"
                and node.func.attr in materializers
            ):
                callsites.append(source_path.resolve())

    expected = (
        backend / ".bago" / "core" / "execution_adapters" / "project.py"
    ).resolve()
    assert callsites
    assert set(callsites) == {expected}


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


def test_execution_adapter_module_material_sink_is_gateway_owned(tmp_path: Path, monkeypatch) -> None:
    adapter = tmp_path / "backend" / ".bago" / "core" / "execution_adapters" / "project.py"
    adapter.parent.mkdir(parents=True)
    adapter.write_text(
        "from pathlib import Path\n\n"
        "class ExampleEffectAdapter:\n"
        "    def execute(self):\n"
        "        Path('receipt.txt').write_text('ok', encoding='utf-8')\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(inventory, "REPO_ROOT", tmp_path)

    findings = inventory.scan_python(adapter)

    assert len(findings) == 1
    assert findings[0].effect_id == "filesystem.write"
    assert findings[0].binding == "gateway_owned"


def test_process_execution_sink_is_owned_by_registered_gateway_adapter() -> None:
    adapter = inventory.REPO_ROOT / "backend" / ".bago" / "core" / "execution_adapters" / "process.py"
    findings = inventory.scan_python(adapter)

    assert len(findings) == 3
    assert {finding.effect_id for finding in findings} == {"process.execute"}
    assert {finding.sink for finding in findings} == {"subprocess.run", "subprocess.Popen"}
    assert all(finding.binding == "gateway_owned" for finding in findings)
    assert all(finding.binding_class == "gateway_adapter" for finding in findings)


def test_manager_settings_materializers_stay_visible_under_registered_gateway_owner() -> None:
    adapter = inventory.REPO_ROOT / "backend" / ".bago" / "core" / "execution_adapters" / "manager_settings.py"
    gateway = (inventory.REPO_ROOT / "backend" / ".bago" / "core" / "execution_gateway.py").read_text(encoding="utf-8")
    findings = inventory.scan_python(adapter)

    assert findings
    assert all(item.binding == "gateway_owned" for item in findings)
    assert all(item.binding_class == "gateway_adapter" for item in findings)
    assert "ManagerSettingsWriteEffectAdapter" in gateway
    assert "registry.register(ManagerSettingsWriteEffectAdapter())" in gateway


def test_uninstall_helper_sinks_are_bound_to_ticketed_gateway_owner() -> None:
    helper = (
        inventory.REPO_ROOT
        / "backend"
        / ".bago"
        / "core"
        / "execution_adapters"
        / "install_uninstall_lifecycle.py"
    )
    adapter = (
        inventory.REPO_ROOT
        / "backend"
        / ".bago"
        / "core"
        / "execution_adapters"
        / "system_install_uninstall.py"
    )
    gateway = (
        inventory.REPO_ROOT
        / "backend"
        / ".bago"
        / "core"
        / "execution_gateway.py"
    ).read_text(encoding="utf-8")
    helper_source = helper.read_text(encoding="utf-8")
    adapter_source = adapter.read_text(encoding="utf-8")
    facade = (
        inventory.REPO_ROOT
        / "backend"
        / "bago_core"
        / "commands"
        / "cmd_lifecycle.py"
    ).read_text(encoding="utf-8")
    findings = inventory.scan_python(helper)

    assert findings
    assert all(item.binding == "gateway_owned" for item in findings)
    assert "SystemInstallUninstallEffectAdapter" in gateway
    assert "registry.register(SystemInstallUninstallEffectAdapter())" in gateway
    assert "run_authorized_uninstall" in facade
    assert "active_cli" in adapter_source
    assert "_validate_ticket(args, claim=False)" in helper_source
    assert "_validate_ticket(args, claim=True)" in helper_source


def test_handlers_github_process_execution_uses_registered_owner() -> None:
    github_handler = inventory.REPO_ROOT / "backend" / ".bago" / "api" / "handlers_github.py"

    github_findings = inventory.scan_python(github_handler)
    assert not any(item.effect_id == "process.execute" and item.binding == "unbound" for item in github_findings)
    assert all(item.scope == inventory.SCOPE_RUNTIME_AUTHORITY for item in github_findings)
    assert all(item.binding_class == "runtime_unbound" for item in github_findings)


def test_secret_store_write_materialization_lives_only_in_credential_adapter() -> None:
    facade = inventory.REPO_ROOT / "backend" / "bago_core" / "secrets.py"
    adapter = inventory.REPO_ROOT / "backend" / ".bago" / "core" / "execution_adapters" / "credentials.py"

    facade_findings = inventory.scan_python(facade)
    adapter_findings = inventory.scan_python(adapter)

    assert facade_findings == []
    assert adapter_findings
    assert all(item.binding == "gateway_owned" for item in adapter_findings)


def test_remote_installer_remains_a_runtime_authority_sink() -> None:
    installer = inventory.REPO_ROOT / "backend" / "install-remote.ps1"
    findings = inventory.scan_paths([installer])

    assert findings
    assert all(item.scope == inventory.SCOPE_RUNTIME_AUTHORITY for item in findings)
    assert all(item.binding == "unbound" for item in findings)
    assert all(item.binding_class == "runtime_unbound" for item in findings)


def test_remote_installer_has_no_running_bago_runtime_callsite() -> None:
    chat_commands = inventory.REPO_ROOT / "backend" / ".bago" / "chat" / "commands.py"
    source = chat_commands.read_text(encoding="utf-8", errors="replace")
    assert "install-remote.ps1" not in source
    assert "from update_manager import start_update" in source


def test_strict_fails_while_runtime_unbound_sinks_exist(monkeypatch) -> None:
    monkeypatch.setattr(
        inventory,
        "build_inventory",
        lambda _roots: {
            "summary": {
                "runtime_unbound_sinks": 1,
                "total_sinks": 1,
                "unbound_sinks": 1,
                "unclassified_scope_sinks": 0,
                "unclassified_binding_sinks": 0,
                "high_confidence_unbound_sinks": 1,
                "by_effect": {},
            }
        },
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "effect_sink_inventory.py",
            "--strict",
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


def test_execution_claim_and_operation_stores_are_authority_internal() -> None:
    paths = (
        inventory.REPO_ROOT / "backend" / ".bago" / "core" / "execution_claims.py",
        inventory.REPO_ROOT / "backend" / ".bago" / "core" / "execution_operations.py",
    )
    findings = [item for path in paths for item in inventory.scan_python(path)]

    assert len(findings) > 2
    assert sum(item.effect_id == "filesystem.write" for item in findings) == 2
    assert any(item.effect_id == "database.write" for item in findings)
    assert all(item.binding == "authority_internal" for item in findings)
    assert all(item.binding_class == "authority_internal" for item in findings)

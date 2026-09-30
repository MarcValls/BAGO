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


def test_inventory_scans_pythonw_entrypoints(tmp_path: Path) -> None:
    source = tmp_path / "silent_supervisor.pyw"
    source.write_text(
        "import os\n"
        "os.makedirs('state', exist_ok=True)\n"
        "with open('state/supervisor.err', 'a', encoding='utf-8') as stream:\n"
        "    stream.write('failed')\n",
        encoding="utf-8",
    )

    findings = inventory.scan_paths([tmp_path])

    assert [(item.line, item.effect_id) for item in findings] == [
        (2, "filesystem.write"),
        (3, "filesystem.write"),
    ]


def test_html_inventory_detects_external_scripts_browser_state_and_network(tmp_path: Path) -> None:
    source = tmp_path / "mini-manager.html"
    source.write_text(
        '<script src="https://cdn.example.invalid/library.js"></script>\n'
        "<script>localStorage.setItem('config', '{}')</script>\n"
        "<script>fetch(url, { method: 'POST' })</script>\n",
        encoding="utf-8",
    )

    findings = inventory.scan_paths([tmp_path])

    assert [(item.line, item.effect_id) for item in findings] == [
        (1, "network.read"),
        (2, "state.write"),
        (3, "network.external_write"),
    ]


def test_android_manager_effects_are_in_runtime_scope() -> None:
    source = inventory.REPO_ROOT / "manager" / "android" / "android.js"

    findings = inventory.scan_paths([source])

    assert {item.scope for item in findings} == {inventory.SCOPE_RUNTIME_AUTHORITY}
    assert any(item.effect_id == "state.write" for item in findings)
    assert any(item.effect_id == "network.read" for item in findings)
    assert any(item.effect_id == "network.external_write" for item in findings)


def test_browser_state_writes_are_runtime_effects_but_api_transport_is_not() -> None:
    frontend = inventory.REPO_ROOT / "frontend" / "src" / "local-state.ts"

    state_binding = inventory._ownership_for(frontend, effect_id="state.write")
    transport_binding = inventory._ownership_for(frontend, effect_id="network.read")

    assert inventory._scope_for_effect(frontend, "state.write") == inventory.SCOPE_RUNTIME_AUTHORITY
    assert state_binding[1] == "runtime_unbound"
    assert transport_binding[1] == "nonruntime_effect"


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
        "Start-Process powershell.exe\n"
        "Remove-Item -Recurse -Force $target\n"
        "Invoke-WebRequest -Uri $url -OutFile $download\n"
        "Invoke-RestMethod -Uri $url -Method POST -Body $body\n",
        encoding="utf-8",
    )

    findings = inventory.scan_paths([script])
    effects = {item.effect_id for item in findings}
    assert "process.execute" in effects
    assert "filesystem.delete" in effects
    assert {item.effect_id for item in findings if item.line == 3} == {
        "filesystem.write",
        "network.read",
    }
    assert any(item.effect_id == "network.external_write" and item.line == 4 for item in findings)


def test_powershell_scanner_detects_call_operator_dot_source_and_archive_write(tmp_path: Path) -> None:
    script = tmp_path / "remote-install.ps1"
    script.write_text(
        "& $gpg.Source --batch --verify $signature $bundle\n"
        "Expand-Archive -Path $bundle -DestinationPath $staging -Force\n"
        "& powershell.exe -ExecutionPolicy Bypass -File $installer\n"
        ". $profilePath\n",
        encoding="utf-8",
    )

    findings = inventory.scan_paths([script])

    assert {(item.line, item.effect_id) for item in findings} == {
        (1, "process.execute"),
        (2, "filesystem.write"),
        (3, "process.execute"),
        (4, "process.execute"),
    }


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


def test_javascript_scanner_detects_network_and_stream_writes(tmp_path: Path) -> None:
    source = tmp_path / "network-and-streams.cjs"
    source.write_text(
        "fetch('http://127.0.0.1:8080/health')\n"
        "fetch(url, {\n"
        "  ...requestInit,\n"
        "})\n"
        "fetch(url, { method: 'GET' })\n"
        "fetch(url, { method: 'POST' })\n"
        "https.request(url, { method: selectedMethod })\n"
        "net.createConnection({ host: '127.0.0.1', port: 8080 })\n"
        "https.request(url, options)\n"
        "fs.createWriteStream(target)\n",
        encoding="utf-8",
    )

    findings = inventory.scan_paths([source])

    assert [(item.line, item.effect_id) for item in findings] == [
        (1, "network.read"),
        (2, "network.external_write"),
        (5, "network.read"),
        (6, "network.external_write"),
        (7, "network.external_write"),
        (8, "network.read"),
        (9, "network.external_write"),
        (10, "filesystem.write"),
    ]


def test_javascript_scanner_does_not_mistake_regexp_exec_for_process_launch(tmp_path: Path) -> None:
    source = tmp_path / "regex.exec.ts"
    source.write_text("const match = expression.exec(line);\n", encoding="utf-8")

    assert inventory.scan_paths([source]) == []


def test_shell_and_cmd_scanners_detect_launcher_effects(tmp_path: Path) -> None:
    shell = tmp_path / "launcher.sh"
    shell.write_text(
        "mkdir -p .run\n"
        "nohup python -m bago_core.launcher serve > backend.log 2>&1 &\n"
        "curl -fsS http://127.0.0.1:8080/health\n"
        "kill -9 1234\n"
        "rm -f backend.pid\n",
        encoding="utf-8",
    )
    batch = tmp_path / "launcher.cmd"
    batch.write_text(
        "start \"\" powershell -File bago.ps1\n"
        "mkdir .run\n"
        "del backend.pid\n"
        "reg add HKCU\\Software\\BAGO\n",
        encoding="utf-8",
    )

    shell_findings = inventory.scan_paths([shell])
    batch_findings = inventory.scan_paths([batch])

    assert [(item.line, item.effect_id) for item in shell_findings] == [
        (1, "filesystem.write"),
        (2, "process.execute"),
        (2, "filesystem.write"),
        (3, "process.execute"),
        (4, "process.terminate"),
        (5, "filesystem.delete"),
    ]
    assert [(item.line, item.effect_id) for item in batch_findings] == [
        (1, "process.execute"),
        (2, "filesystem.write"),
        (3, "filesystem.delete"),
        (4, "system.configuration.write"),
    ]


def test_vbscript_and_nsis_scanners_detect_installer_effects(tmp_path: Path) -> None:
    launcher = tmp_path / "install.vbs"
    launcher.write_text(
        "' objShell.Run is only a comment\n"
        "objShell.Run batchFile, 1, True\n"
        "objFSO.CreateTextFile(target, True)\n"
        "objShell.RegWrite key, value\n",
        encoding="utf-8",
    )
    installer = tmp_path / "installer.nsi"
    installer.write_text(
        "; DeleteRegKey HKCU legacy\n"
        "InitPluginsDir\n"
        "ExecWait 'powershell.exe -File install.ps1'\n"
        "File /oname=payload.zip payload.zip\n"
        "WriteRegStr HKCU Software\\BAGO Version 1\n"
        "RMDir /r $INSTDIR\n",
        encoding="utf-8",
    )

    findings = inventory.scan_paths([launcher, installer])

    assert sorted((Path(item.path).name, item.line, item.effect_id) for item in findings) == [
        ("install.vbs", 2, "process.execute"),
        ("install.vbs", 3, "filesystem.write"),
        ("install.vbs", 4, "system.configuration.write"),
        ("installer.nsi", 2, "filesystem.write"),
        ("installer.nsi", 3, "process.execute"),
        ("installer.nsi", 4, "filesystem.write"),
        ("installer.nsi", 5, "system.configuration.write"),
        ("installer.nsi", 6, "filesystem.delete"),
    ]


def test_default_inventory_roots_include_runtime_entrypoints_and_release_scripts() -> None:
    relative_roots = {inventory._relative(path) for path in inventory.DEFAULT_ROOTS}

    assert "releases" in relative_roots
    assert "frontend" in relative_roots
    assert "ARRANCAR_BAGO.bat" in relative_roots
    assert "DETENER_BAGO.bat" in relative_roots
    assert "install-remote.ps1" in relative_roots
    assert ".github/workflows" in relative_roots
    assert "manager/android" in relative_roots
    assert inventory._scope_for(inventory.REPO_ROOT / "backend/scripts/bago_supervisor.py") == inventory.SCOPE_RUNTIME_AUTHORITY
    assert inventory._scope_for(inventory.REPO_ROOT / "backend/scripts/bago_supervisor.pyw") == inventory.SCOPE_RUNTIME_AUTHORITY
    assert inventory._scope_for(inventory.REPO_ROOT / "backend/scripts/publish_release.py") == inventory.SCOPE_RUNTIME_AUTHORITY
    assert inventory._scope_for(inventory.REPO_ROOT / "ARRANCAR_BAGO.bat") == inventory.SCOPE_RUNTIME_AUTHORITY
    assert inventory._scope_for(inventory.REPO_ROOT / "update-release-v4.8.4.sh") == inventory.SCOPE_BUILD_RELEASE_ADMIN
    assert inventory._scope_for(inventory.REPO_ROOT / "releases" / "compiled" / "backend" / "main.py") == inventory.SCOPE_DERIVED_RELEASE_SNAPSHOT
    assert inventory._scope_for(inventory.REPO_ROOT / "releases" / "install-embedded-payload.ps1") == inventory.SCOPE_RUNTIME_AUTHORITY
    assert inventory._scope_for(inventory.REPO_ROOT / "releases" / "bago-installer.nsi") == inventory.SCOPE_RUNTIME_AUTHORITY
    assert inventory._scope_for(inventory.REPO_ROOT / "frontend" / "src" / "api" / "client.ts") == inventory.SCOPE_RUNTIME_CLIENT_TRANSPORT
    assert inventory._scope_for(inventory.REPO_ROOT / "frontend" / "capture_screenshots.mjs") == inventory.SCOPE_BUILD_RELEASE_ADMIN


def test_github_workflow_scanner_finds_powerShell_run_block_and_inline_effects(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(inventory, "REPO_ROOT", tmp_path)
    workflow = tmp_path / ".github" / "workflows" / "workflow.yml"
    workflow.parent.mkdir(parents=True)
    workflow.write_text(
        "name: scanner fixture\n"
        "jobs:\n"
        "  check:\n"
        "    runs-on: windows-latest\n"
        "    steps:\n"
        "      - shell: pwsh\n"
        "        run: |\n"
        "          $proc = Start-Process app.exe\n"
        "          if (-not $proc.HasExited) { Stop-Process -Id $proc.Id -Force }\n"
        "          Remove-Item Env:BAGO_TEST -ErrorAction SilentlyContinue\n"
        "      - shell: pwsh\n"
        "        run: 'Stop-Process -Id 123 -Force'\n",
        encoding="utf-8",
    )

    findings = inventory.scan_paths([workflow])

    assert [(item.line, item.effect_id, item.scope) for item in findings] == [
        (8, "process.execute", inventory.SCOPE_BUILD_RELEASE_ADMIN),
        (9, "process.terminate", inventory.SCOPE_BUILD_RELEASE_ADMIN),
        (10, "filesystem.delete", inventory.SCOPE_BUILD_RELEASE_ADMIN),
        (12, "process.terminate", inventory.SCOPE_BUILD_RELEASE_ADMIN),
    ]


def test_ci_powershell_terminations_are_inventoried_as_nonruntime() -> None:
    workflows = [
        inventory.REPO_ROOT / ".github" / "workflows" / "build-release-installer.yml",
        inventory.REPO_ROOT / ".github" / "workflows" / "canonical-ci.yml",
    ]

    findings = inventory.scan_paths(workflows)
    terminations = {
        (item.path, item.line, item.binding_class, item.scope)
        for item in findings
        if item.effect_id == "process.terminate"
    }

    assert terminations == {
        (".github/workflows/build-release-installer.yml", 212, "nonruntime_effect", inventory.SCOPE_BUILD_RELEASE_ADMIN),
        (".github/workflows/canonical-ci.yml", 155, "nonruntime_effect", inventory.SCOPE_BUILD_RELEASE_ADMIN),
        (".github/workflows/canonical-ci.yml", 247, "nonruntime_effect", inventory.SCOPE_BUILD_RELEASE_ADMIN),
    }


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


def test_powershell_scanner_tracks_registry_targets_and_ignores_embedded_commands(tmp_path: Path) -> None:
    script = tmp_path / "registry-and-help.ps1"
    script.write_text(
        '$regPath = "HKCU:\\Software\\BAGO"\n'
        "New-Item -Path $regPath -Force | Out-Null\n"
        'Set-ItemProperty -Path $regPath -Name "UninstallString" -Value "Remove-Item $target"\n'
        'Write-Host "Remove-Item $target"\n'
        "# Stop-Process -Id 123\n"
        "Stop-Process -Id 123 -Force\n"
        "taskkill /F /PID 123 /T\n"
        'Write-Host "$(Stop-Process -Id 456)"\n',
        encoding="utf-8",
    )

    findings = inventory.scan_paths([script])

    assert [(item.line, item.effect_id) for item in findings] == [
        (2, "system.configuration.write"),
        (3, "system.configuration.write"),
        (6, "process.terminate"),
        (7, "process.terminate"),
        (8, "process.terminate"),
    ]


def test_reachable_powershell_termination_calls_are_discovered_with_correct_scope() -> None:
    paths = [
        inventory.REPO_ROOT / "scripts" / "dev.ps1",
        inventory.REPO_ROOT / "backend" / "scripts" / "runtime-service.ps1",
        inventory.REPO_ROOT / "releases" / "install-embedded-payload.ps1",
        inventory.REPO_ROOT / "releases" / "Uninstall-BAGO.ps1",
        inventory.REPO_ROOT / "backend" / ".bago" / "api" / "apply_release_update.ps1",
    ]

    findings = inventory.scan_paths(paths)
    terminations = {
        (item.path, item.line, item.binding_class, item.scope)
        for item in findings
        if item.effect_id == "process.terminate"
    }

    assert terminations == {
        ("scripts/dev.ps1", 75, "runtime_unbound", inventory.SCOPE_RUNTIME_AUTHORITY),
        ("scripts/dev.ps1", 87, "runtime_unbound", inventory.SCOPE_RUNTIME_AUTHORITY),
        ("scripts/dev.ps1", 193, "runtime_unbound", inventory.SCOPE_RUNTIME_AUTHORITY),
        ("backend/scripts/runtime-service.ps1", 65, "runtime_unbound", inventory.SCOPE_RUNTIME_AUTHORITY),
        ("backend/scripts/runtime-service.ps1", 91, "runtime_unbound", inventory.SCOPE_RUNTIME_AUTHORITY),
        ("backend/scripts/runtime-service.ps1", 99, "runtime_unbound", inventory.SCOPE_RUNTIME_AUTHORITY),
        ("releases/install-embedded-payload.ps1", 51, "runtime_unbound", inventory.SCOPE_RUNTIME_AUTHORITY),
        ("releases/Uninstall-BAGO.ps1", 22, "runtime_unbound", inventory.SCOPE_RUNTIME_AUTHORITY),
        ("backend/.bago/api/apply_release_update.ps1", 233, "gateway_adapter", inventory.SCOPE_RUNTIME_AUTHORITY),
        ("backend/.bago/api/apply_release_update.ps1", 237, "gateway_adapter", inventory.SCOPE_RUNTIME_AUTHORITY),
    }


def test_legacy_installer_registry_writes_are_not_misclassified_as_filesystem_effects() -> None:
    installer = inventory.REPO_ROOT / "releases" / "Install-BAGO.ps1"

    findings = inventory.scan_paths([installer])
    line_effects: dict[int, set[str]] = {}
    for item in findings:
        line_effects.setdefault(item.line, set()).add(item.effect_id)

    assert line_effects[165] == {"system.configuration.write"}
    assert line_effects[170] == {"system.configuration.write"}
    assert line_effects[173] == {"system.configuration.write"}
    assert 187 not in line_effects


def test_install_v4_inventory_retains_effects_under_ticket_bound_gateway_owner() -> None:
    installer = inventory.REPO_ROOT / "backend" / "install-v4.ps1"

    findings = inventory.scan_paths([installer])
    configuration_writes = [item for item in findings if item.effect_id == "system.configuration.write"]

    assert len(configuration_writes) == 5
    assert len(findings) >= 40
    assert {item.binding_class for item in findings} == {"gateway_adapter"}
    assert {item.scope for item in findings} == {inventory.SCOPE_RUNTIME_AUTHORITY}


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
    scanner_ids |= {
        effect_id
        for _, effect_id, _ in inventory.SHELL_RULES
    }
    scanner_ids |= {
        effect_id
        for _, effect_id, _ in inventory.CMD_RULES
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

    assert len(findings) == 21
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

    assert len(findings) == 4
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


def test_database_write_sink_is_owned_by_the_registered_adapter() -> None:
    adapter_path = (
        inventory.REPO_ROOT
        / "backend"
        / ".bago"
        / "core"
        / "execution_adapters"
        / "database_write.py"
    )
    findings = inventory.scan_python(adapter_path)
    assert findings
    assert all(item.binding_class == "gateway_adapter" for item in findings)
    assert any(item.effect_id == "database.write" for item in findings)
    assert {item.effect_id for item in findings} <= {
        "database.write",
        "filesystem.write",  # state-root creation is covered by the same Permit.
    }

    source = adapter_path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    adapter_class = next(
        node for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "DatabaseWriteEffectAdapter"
    )
    private_schema_helpers = {
        "_ensure_knowledge_schema",
        "_ensure_embedding_schema",
        "_insert_embedding",
    }
    helper_calls = [
        node for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id in private_schema_helpers
    ]
    assert helper_calls
    assert all(
        adapter_class.lineno <= node.lineno <= adapter_class.end_lineno
        for node in helper_calls
    )

    from execution_gateway import build_default_effect_adapter_registry
    from execution_adapters.database_write import DatabaseWriteEffectAdapter

    assert isinstance(
        build_default_effect_adapter_registry().resolve("database.write"),
        DatabaseWriteEffectAdapter,
    )

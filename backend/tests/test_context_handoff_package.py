from __future__ import annotations

import base64
import json
import subprocess

import capability_packages as packages
from package_contract import load_archive


def test_context_handoff_is_listed_and_exports_as_valid_package() -> None:
    listed = packages.list_example_packages()
    entry = next(item for item in listed if item["id"] == "local.context-handoff")
    assert entry["kind"] == "capability"
    assert entry["execution_mode"] == "executable"
    assert entry["permissions"] == []

    encoded, file_name = packages.example_package_archive("local.context-handoff")
    loaded = load_archive(base64.b64decode(encoded))
    assert file_name == "context-handoff.bago.zip"
    assert loaded.manifest["contract_version"] == "bago.package/v1"
    assert loaded.manifest["entrypoint"] == "runtime/run.py"
    assert "runtime/run.py" in loaded.payload
    assert "schemas/input.schema.json" in loaded.payload


def test_context_handoff_formats_only_the_supplied_session_context(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(packages, "state_root", lambda: tmp_path / "state")
    encoded, _ = packages.example_package_archive("local.context-handoff")
    imported = packages._materialize_import(
        content_base64=encoded,
        file_name="context-handoff.bago.zip",
        confirm_trust=True,
    )
    assert imported["package"]["enabled"] is False
    packages.set_enabled("local.context-handoff", True, confirm_trust=True)

    result = packages._execute_package(
        "local.context-handoff",
        inputs={
            "project": "BAGO",
            "agent_role": "MEM",
            "work_item": "relocation",
            "version": "v1.0",
            "cycle": "C01",
            "status": "HANDOFF",
            "result": "Inventory captured.",
            "decisions": "Keep source trees intact.",
            "open_items": "Run receiving runtime smoke.",
            "next_role": "CRIT",
            "next_instruction": "Review package provenance.",
            "inherited_context": "Package formats supplied fields only.",
            "sources": "SRG continuity templates",
            "success_criteria": "Next session can continue.",
        },
        confirmed=True,
        approved_permissions=[],
        process_executor=subprocess.run,
    )

    handoff = result["receipt"]["result"]
    assert result["ok"] is True
    assert handoff["title"] == "BAGO-MEM-relocation-v1.0-HANDOFF-C01"
    assert handoff["status"] == "HANDOFF"
    assert "## Decisiones\n\n- Keep source trees intact." in handoff["handoff_markdown"]
    assert "## Pendientes\n\n- Run receiving runtime smoke." in handoff["handoff_markdown"]
    assert "## Criterio de éxito\n\nNext session can continue." in handoff["handoff_markdown"]

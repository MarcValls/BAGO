from __future__ import annotations

import base64
import io
import json
import zipfile

import pytest

import capability_packages as packages
from capability_contract import validate_capability


MANIFEST = {
    "schema_version": "1.0",
    "contract_version": "bago.capability/v1",
    "id": "local.text-stats",
    "name": "Estadísticas de texto",
    "version": "1.0.0",
    "description": "Cuenta palabras y caracteres.",
    "permissions": [],
    "runtime": {"kind": "python", "entrypoint": "run.py", "timeout_s": 10},
    "configuration_schema": {
        "type": "object",
        "properties": {"lowercase": {"type": "boolean", "default": False}},
    },
    "input_schema": {
        "type": "object",
        "properties": {"text": {"type": "string"}},
        "required": ["text"],
    },
}

RUNNER = """import json, sys
payload = json.load(sys.stdin)
text = payload['input']['text']
if payload['config'].get('lowercase'):
    text = text.lower()
print(json.dumps({'text': text, 'words': len(text.split()), 'characters': len(text)}, ensure_ascii=False))
"""


def archive(*, member_name: str | None = None) -> str:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as package:
        package.writestr("capability.json", json.dumps(MANIFEST))
        package.writestr(member_name or "run.py", RUNNER)
    return base64.b64encode(buffer.getvalue()).decode("ascii")


@pytest.fixture(autouse=True)
def isolated_state(tmp_path, monkeypatch):
    monkeypatch.setattr(packages, "state_root", lambda: tmp_path / "state")


def test_import_enable_configure_execute_and_persist_receipt():
    imported = packages.import_package(content_base64=archive(), file_name="text-stats.zip", confirm_trust=False)
    assert imported["package"]["enabled"] is False
    assert imported["package"]["trust_state"] == "untrusted"
    with pytest.raises(packages.CapabilityPackageError, match="confianza"):
        packages.set_enabled("local.text-stats", True)
    assert packages.set_enabled("local.text-stats", True, confirm_trust=True)["enabled"] is True
    assert packages.configure_package("local.text-stats", {"lowercase": True})["config"] == {"lowercase": True}

    result = packages.execute_package(
        "local.text-stats",
        inputs={"text": "Hola MUNDO"},
        confirmed=True,
        approved_permissions=[],
    )

    assert result["ok"] is True
    assert result["receipt"]["result"] == {"text": "hola mundo", "words": 2, "characters": 10}
    assert packages.list_receipts()[0]["receipt_id"] == result["receipt"]["receipt_id"]
    snapshot = packages.build_package_snapshot("local.text-stats")
    validate_capability(snapshot)
    assert snapshot["runtime_snapshot"]["run_state"] == "succeeded"
    assert snapshot["evidence"][0]["receipt_id"] == result["receipt"]["receipt_id"]


def test_import_is_idempotent_for_same_digest():
    content = archive()
    first = packages.import_package(content_base64=content, file_name="text-stats.zip", confirm_trust=True)
    second = packages.import_package(content_base64=content, file_name="text-stats.zip", confirm_trust=True)
    assert first["already_installed"] is False
    assert second["already_installed"] is True
    assert len(packages.list_packages()) == 1


def test_zip_path_traversal_is_rejected():
    with pytest.raises(packages.CapabilityPackageError, match="ruta relativa segura"):
        packages.import_package(content_base64=archive(member_name="../run.py"), file_name="unsafe.zip", confirm_trust=True)


def test_execution_requires_activation_confirmation_and_permissions():
    manifest = dict(MANIFEST, permissions=["filesystem.read"])
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as package:
        package.writestr("capability.json", json.dumps(manifest))
        package.writestr("run.py", RUNNER)
    content = base64.b64encode(buffer.getvalue()).decode("ascii")
    packages.import_package(content_base64=content, file_name="permissions.zip", confirm_trust=True)
    with pytest.raises(packages.CapabilityPackageError, match="Activa"):
        packages.execute_package("local.text-stats", inputs={"text": "x"}, confirmed=True, approved_permissions=[])
    packages.set_enabled("local.text-stats", True, confirm_trust=True)
    with pytest.raises(packages.CapabilityPackageError, match="confirmación"):
        packages.execute_package("local.text-stats", inputs={"text": "x"}, confirmed=False, approved_permissions=[])
    with pytest.raises(packages.CapabilityPackageError, match="filesystem.read"):
        packages.execute_package("local.text-stats", inputs={"text": "x"}, confirmed=True, approved_permissions=[])

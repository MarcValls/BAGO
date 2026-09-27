"""Role creation is one exact, pre-authorized repository effect."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import pytest

from authorization_boundary import AuthorizationBoundary
from execution_adapter_contract import ExecutionContext
from execution_adapters import role_definition
from execution_gateway import ExecutionGateway, ExecutionGatewayError
from execution_request import build_execution_request


def _request(root: Path, *, family: str = "especialistas", name: str = "security_auditor", digest: str = "missing"):
    return build_execution_request(
        effect_id="role.definition.create",
        actor_kind="user",
        principal_id="interactive-local-user",
        session_id="roles:" + hashlib.sha256(str(root).encode("utf-8")).hexdigest()[:20],
        source_surface="cli.role_factory.create",
        target={"role_root": str(root), "family": family, "name": name, "manifest_sha256": digest},
        arguments={"content": "# SECURITY_AUDITOR\n"},
        scope="workspace",
    )


def _execute(request, monkeypatch):
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
    boundary = AuthorizationBoundary()
    interaction = "cli-role-definition-test"
    challenge = boundary.create_challenge(request, interaction_id=interaction)
    approval = boundary.approve_cli_challenge(
        challenge_id=challenge["challenge_id"], interaction_id=interaction,
        session_id=request.session_id, terminal_confirmed=True,
    )
    return ExecutionGateway(boundary).execute(permit_token=approval["permit"]["token"], request=request)[0]


def test_role_creation_requires_permit_and_writes_both_files(tmp_path: Path, monkeypatch) -> None:
    root = tmp_path / "roles"
    root.mkdir()
    monkeypatch.setattr(role_definition, "ROLE_ROOT", root)
    request = _request(root)

    with pytest.raises(ExecutionGatewayError, match="consumed CLI Permit"):
        role_definition.RoleDefinitionCreateEffectAdapter().execute(request, ExecutionContext())
    assert not (root / "especialistas" / "SECURITY_AUDITOR.md").exists()

    receipt = _execute(request, monkeypatch)
    assert receipt["ok"] is True
    assert (root / "especialistas" / "SECURITY_AUDITOR.md").read_text(encoding="utf-8") == "# SECURITY_AUDITOR\n"
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["roles"]["role_especialistas_security_auditor"]["file"] == "especialistas/SECURITY_AUDITOR.md"


def test_role_creation_blocks_manifest_drift_and_path_escape_before_writing(tmp_path: Path, monkeypatch) -> None:
    root = tmp_path / "roles"
    root.mkdir()
    monkeypatch.setattr(role_definition, "ROLE_ROOT", root)
    (root / "manifest.json").write_text('{"roles": {}}', encoding="utf-8")

    with pytest.raises(ExecutionGatewayError) as drift:
        _execute(_request(root), monkeypatch)
    assert drift.value.code == "role_definition_manifest_changed"

    current = (root / "manifest.json").read_bytes()
    digest = hashlib.sha256(current).hexdigest()
    with pytest.raises(ExecutionGatewayError) as escape:
        _execute(_request(root, family="../outside", digest=digest), monkeypatch)
    assert escape.value.code == "role_definition_target_invalid"
    assert not (root / "especialistas" / "SECURITY_AUDITOR.md").exists()


def test_role_creation_rolls_back_role_when_manifest_publication_fails(tmp_path: Path, monkeypatch) -> None:
    root = tmp_path / "roles"
    root.mkdir()
    monkeypatch.setattr(role_definition, "ROLE_ROOT", root)

    original_replace = role_definition.os.replace

    def fail_replace(source, target):
        if Path(target) == root / "manifest.json":
            raise OSError("simulated publication failure")
        return original_replace(source, target)

    monkeypatch.setattr(role_definition.os, "replace", fail_replace)
    with pytest.raises(ExecutionGatewayError) as failed:
        _execute(_request(root), monkeypatch)

    assert failed.value.code == "role_definition_write_failed"
    assert not (root / "especialistas" / "SECURITY_AUDITOR.md").exists()
    assert not (root / "manifest.json").exists()


def test_role_factory_delegates_create_without_writing_locally(tmp_path: Path, monkeypatch) -> None:
    factory_path = Path(__file__).resolve().parents[1] / ".bago" / "roles" / "role_factory.py"
    spec = importlib.util.spec_from_file_location("test_role_factory_gateway", factory_path)
    assert spec is not None and spec.loader is not None
    factory = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(factory)
    root = tmp_path / "roles"
    root.mkdir()
    monkeypatch.setattr(factory, "ROLES_DIR", root)
    monkeypatch.setattr(factory, "MANIFEST", root / "manifest.json")
    requests = []

    from bago_core import cli_execution
    monkeypatch.setattr(
        cli_execution, "execute_cli_effect",
        lambda request, **_kwargs: requests.append(request) or ({"ok": True}, {"state": "consumed"}),
    )
    assert factory.create_role("especialistas", "security_auditor", "purpose", [], "limits", [], [], "activate", "inactive", [], "success")
    assert requests[0].effect_id == "role.definition.create"
    assert requests[0].target["manifest_sha256"] == "missing"
    assert not (root / "especialistas").exists()
    assert not (root / "manifest.json").exists()

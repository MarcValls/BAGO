from __future__ import annotations

import base64
import hashlib
import io
import json
import stat
import warnings
import zipfile

import pytest

import capability_packages as packages
from package_contract import canonical_archive, canonical_json


DEFINITION = {
    "id": "local.canonical-stats",
    "runtime": {"kind": "python", "timeout_s": 10},
    "configuration_schema": {"type": "object", "properties": {}},
    "input_schema": {
        "type": "object",
        "properties": {"text": {"type": "string"}},
        "required": ["text"],
    },
    "output_schema": {"type": "object"},
}
RUNNER = b"import json, sys\nprint(json.dumps({'length': len(json.load(sys.stdin)['input']['text'])}))\n"


def manifest(**overrides):
    value = {
        "schema_version": "1.0",
        "contract_version": "bago.package/v1",
        "kind": "capability",
        "execution_mode": "executable",
        "id": "local.canonical-stats",
        "name": "Canonical stats",
        "version": "1.0.0",
        "description": "Canonical package fixture.",
        "author": "BAGO tests",
        "definition": "definitions/capability.json",
        "entrypoint": "runtime/run.py",
        "permissions": [],
        "compatibility": {"bago_package": "^1.0"},
        "dependencies": [],
    }
    value.update(overrides)
    return value


def payload():
    return {
        "definitions/capability.json": canonical_json(DEFINITION),
        "runtime/run.py": RUNNER,
    }


def encode(archive: bytes) -> str:
    return base64.b64encode(archive).decode("ascii")


def canonical_bytes(**overrides) -> bytes:
    return canonical_archive(manifest(**overrides), payload())


def package_bytes(
    package_id,
    *,
    kind,
    execution_mode,
    definition,
    runner=None,
    dependencies=None,
    permissions=None,
):
    package_payload = {f"definitions/{kind}.json": canonical_json(definition)}
    package_manifest = {
        "schema_version": "1.0",
        "contract_version": "bago.package/v1",
        "kind": kind,
        "execution_mode": execution_mode,
        "id": package_id,
        "name": package_id,
        "version": "1.0.0",
        "description": f"Fixture for {package_id}.",
        "author": "BAGO tests",
        "definition": f"definitions/{kind}.json",
        "permissions": permissions or [],
        "compatibility": {"bago_package": "^1.0"},
        "dependencies": dependencies or [],
    }
    if execution_mode == "executable":
        package_manifest["entrypoint"] = "runtime/run.py"
        package_payload["runtime/run.py"] = runner or RUNNER
    return canonical_archive(package_manifest, package_payload)


def import_bytes(package_id, archive):
    return packages.import_package(
        content_base64=encode(archive),
        file_name=f"{package_id}.zip",
        confirm_trust=False,
    )


def raw_archive(root_manifest, members, *, duplicate=None, symlink=None) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("bago.package.json", json.dumps(root_manifest))
        for path, content in members.items():
            archive.writestr(path, content)
        if duplicate:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", UserWarning)
                archive.writestr(duplicate, members[duplicate])
        if symlink:
            info = zipfile.ZipInfo(symlink)
            info.create_system = 3
            info.external_attr = (stat.S_IFLNK | 0o777) << 16
            archive.writestr(info, "runtime/run.py")
    return buffer.getvalue()


def inventory(members):
    return [
        {"path": path, "size": len(content), "sha256": hashlib.sha256(content).hexdigest()}
        for path, content in sorted(members.items())
    ]


@pytest.fixture(autouse=True)
def isolated_state(tmp_path, monkeypatch):
    monkeypatch.setattr(packages, "state_root", lambda: tmp_path / "state")


def test_canonical_import_and_unsigned_inspection_does_not_persist():
    content = encode(canonical_bytes())
    inspected = packages.inspect_package(content_base64=content, file_name="canonical.zip")

    assert inspected["ok"] is True
    assert inspected["identity"]["id"] == "local.canonical-stats"
    assert inspected["kind"] == "capability"
    assert inspected["digest_state"] == "verified"
    assert inspected["signature_state"] == "unsigned"
    assert inspected["warnings"]
    assert packages.list_packages() == []

    imported = packages.import_package(content_base64=content, file_name="canonical.zip", confirm_trust=False)
    assert imported["package"]["legacy_source"] is False
    assert imported["package"]["kind"] == "capability"
    assert imported["package"]["signature_state"] == "unsigned"
    assert imported["package"]["trust_state"] == "untrusted"
    assert any("confianza" in warning for warning in imported["package"]["warnings"])


def test_legacy_package_is_normalized_to_generic_record():
    legacy = {
        "schema_version": "1.0",
        "contract_version": "bago.capability/v1",
        "id": "local.legacy-test",
        "name": "Legacy",
        "version": "1.0.0",
        "description": "Legacy fixture.",
        "permissions": [],
        "runtime": {"kind": "python", "entrypoint": "run.py"},
    }
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("capability.json", json.dumps(legacy))
        archive.writestr("run.py", RUNNER)

    result = packages.import_package(
        content_base64=encode(buffer.getvalue()),
        file_name="legacy.zip",
        confirm_trust=True,
    )

    assert result["package"]["contract_version"] == "bago.package/v1"
    assert result["package"]["legacy_source"] is True
    assert result["package"]["execution_mode"] == "executable"
    first_export = packages.export_package("local.legacy-test")
    second_export = packages.export_package("local.legacy-test")
    assert first_export["content_base64"] == second_export["content_base64"]
    assert packages.inspect_package(
        content_base64=first_export["content_base64"],
        file_name=first_export["file_name"],
    )["ok"] is True


def test_export_is_deterministic_and_round_trips():
    packages.import_package(
        content_base64=encode(canonical_bytes()),
        file_name="canonical.zip",
        confirm_trust=True,
    )

    first = packages.export_package("local.canonical-stats")
    second = packages.export_package("local.canonical-stats")

    assert first["content_base64"] == second["content_base64"]
    assert first["digest"] == second["digest"]
    inspected = packages.inspect_package(content_base64=first["content_base64"], file_name=first["file_name"])
    assert inspected["ok"] is True
    assert inspected["identity"]["id"] == "local.canonical-stats"


@pytest.mark.parametrize(
    ("member", "symlink"),
    [
        ("../escape.py", None),
        ("/absolute.py", None),
        ("C:\\drive.py", None),
        (None, "runtime/link.py"),
    ],
)
def test_unsafe_zip_entries_are_rejected(member, symlink):
    members = payload()
    root = manifest(files=inventory(members))
    if member:
        members[member] = b"x"
    archive = raw_archive(root, members, symlink=symlink)

    inspected = packages.inspect_package(content_base64=encode(archive), file_name="unsafe.zip")

    assert inspected["ok"] is False
    assert inspected["errors"][0]["code"] == "unsafe_path"


def test_duplicate_zip_entry_is_rejected():
    members = payload()
    root = manifest(files=inventory(members))
    inspected = packages.inspect_package(
        content_base64=encode(raw_archive(root, members, duplicate="runtime/run.py")),
        file_name="duplicate.zip",
    )
    assert inspected["ok"] is False
    assert inspected["errors"][0]["code"] == "duplicate_entry"


@pytest.mark.parametrize(
    ("mutation", "expected_code"),
    [
        ("undeclared", "undeclared_file"),
        ("missing", "missing_file"),
        ("checksum", "digest_mismatch"),
    ],
)
def test_inventory_failures_block_import(mutation, expected_code):
    members = payload()
    declared = inventory(members)
    if mutation == "undeclared":
        members["assets/extra.txt"] = b"extra"
    elif mutation == "missing":
        declared.append({"path": "assets/missing.txt", "size": 1, "sha256": hashlib.sha256(b"x").hexdigest()})
    else:
        declared[0]["sha256"] = "0" * 64
    archive = raw_archive(manifest(files=declared), members)

    inspected = packages.inspect_package(content_base64=encode(archive), file_name="bad-inventory.zip")
    assert inspected["ok"] is False
    assert inspected["errors"][0]["code"] == expected_code
    with pytest.raises(packages.CapabilityPackageError) as error:
        packages.import_package(
            content_base64=encode(archive),
            file_name="bad-inventory.zip",
            confirm_trust=True,
        )
    assert error.value.code == expected_code


def test_invalid_signature_metadata_blocks_package():
    archive = canonical_bytes(signature={"algorithm": "ed25519", "key_id": "test", "value": "***"})
    inspected = packages.inspect_package(content_base64=encode(archive), file_name="signature.zip")
    assert inspected["ok"] is False
    assert inspected["signature_state"] == "invalid"


def test_declarative_pipeline_is_validated_and_stored_without_execution():
    definition = canonical_json({"id": "local.pipeline-test", "steps": []})
    pipeline_payload = {"definitions/pipeline.json": definition}
    pipeline_manifest = manifest(
        kind="pipeline",
        execution_mode="declarative",
        id="local.pipeline-test",
        name="Pipeline test",
        definition="definitions/pipeline.json",
    )
    pipeline_manifest.pop("entrypoint")
    archive = canonical_archive(pipeline_manifest, pipeline_payload)

    imported = packages.import_package(
        content_base64=encode(archive),
        file_name="pipeline.zip",
        confirm_trust=False,
    )

    assert imported["package"]["kind"] == "pipeline"
    assert imported["package"]["execution_mode"] == "declarative"
    with pytest.raises(packages.CapabilityPackageError, match="confianza"):
        packages.set_enabled("local.pipeline-test", True)
    assert packages.set_enabled("local.pipeline-test", True, confirm_trust=True)["enabled"] is True
    first_export = packages.export_package("local.pipeline-test")
    second_export = packages.export_package("local.pipeline-test")
    assert first_export["content_base64"] == second_export["content_base64"]
    assert packages.inspect_package(
        content_base64=first_export["content_base64"],
        file_name=first_export["file_name"],
    )["ok"] is True


def test_inspect_and_export_routes_are_exposed():
    import api_dispatch

    assert "/api/v1/capability-packages/inspect" in api_dispatch.POST_ROUTES
    matched, export = api_dispatch.resolve_get(
        object(),
        "/api/v1/capability-packages/local.canonical-stats/export",
    )
    assert matched is True
    assert callable(export)


@pytest.mark.parametrize(
    ("steps", "expected_code"),
    [
        (
            [
                {"id": "a", "type": "noop", "depends_on": ["b"]},
                {"id": "b", "type": "noop", "depends_on": ["a"]},
            ],
            "pipeline_cycle",
        ),
        ([{"id": "a", "type": "noop", "depends_on": ["missing"]}], "unknown_step_dependency"),
        (
            [
                {"id": "same", "type": "noop"},
                {"id": "same", "type": "approval"},
            ],
            "duplicate_step",
        ),
        ([{"id": "a", "type": "shell"}], "unsupported_step"),
    ],
)
def test_pipeline_graph_validation_rejects_invalid_steps(steps, expected_code):
    definition = {
        "contract_version": "bago.pipeline/v1",
        "schema_version": "1.0",
        "id": "local.invalid-pipeline",
        "steps": steps,
    }
    archive = package_bytes(
        "local.invalid-pipeline",
        kind="pipeline",
        execution_mode="declarative",
        definition=definition,
    )
    inspected = packages.inspect_package(
        content_base64=encode(archive),
        file_name="invalid-pipeline.zip",
    )
    assert inspected["ok"] is False
    assert inspected["errors"][0]["code"] == expected_code


def test_declarative_pipeline_composes_capability_and_persists_receipt():
    capability_runner = (
        b"import json, sys\n"
        b"payload=json.load(sys.stdin)\n"
        b"print(json.dumps({'seen': payload['input']['text']}))\n"
    )
    capability_definition = {
        "id": "local.echo-capability",
        "runtime": {"kind": "python", "timeout_s": 10},
        "input_schema": {
            "type": "object",
            "properties": {"text": {"type": "string"}},
            "required": ["text"],
        },
    }
    import_bytes(
        "local.echo-capability",
        package_bytes(
            "local.echo-capability",
            kind="capability",
            execution_mode="executable",
            definition=capability_definition,
            runner=capability_runner,
        ),
    )
    packages.set_enabled("local.echo-capability", True, confirm_trust=True)

    pipeline_definition = {
        "contract_version": "bago.pipeline/v1",
        "schema_version": "1.0",
        "id": "local.compose-pipeline",
        "variables": {"label": "ready"},
        "input_schema": {
            "type": "object",
            "properties": {"text": {"type": "string"}},
            "required": ["text"],
        },
        "steps": [
            {"id": "seed", "type": "noop", "with": {"text": "${inputs.text}"}},
            {
                "id": "approve",
                "type": "approval",
                "depends_on": ["seed"],
                "with": {"label": "${variables.label}"},
            },
            {
                "id": "echo",
                "type": "capability",
                "depends_on": ["approve"],
                "uses": "local.echo-capability",
                "with": {"text": "${steps.seed.result.text}"},
                "retry": {"max_attempts": 2, "delay_s": 0},
                "condition": "steps.approve.ok",
            },
        ],
    }
    import_bytes(
        "local.compose-pipeline",
        package_bytes(
            "local.compose-pipeline",
            kind="pipeline",
            execution_mode="declarative",
            definition=pipeline_definition,
            dependencies=[{"id": "local.echo-capability", "version": "1.0.0"}],
        ),
    )
    packages.set_enabled("local.compose-pipeline", True, confirm_trust=True)

    blocked = packages.execute_pipeline_package(
        "local.compose-pipeline",
        inputs={"text": "hola"},
        confirmed=False,
        approved_permissions=[],
        manager=None,
    )
    assert blocked["ok"] is False
    assert blocked["receipt"]["status"] == "blocked"
    assert blocked["receipt"]["steps"][-1]["step_id"] == "approve"

    result = packages.execute_pipeline_package(
        "local.compose-pipeline",
        inputs={"text": "hola"},
        confirmed=True,
        approved_permissions=[],
        manager=None,
    )
    assert result["ok"] is True
    assert result["receipt"]["status"] == "succeeded"
    assert result["receipt"]["result"]["steps"]["echo"]["result"] == {"seen": "hola"}
    assert result["receipt"]["steps"][2]["receipt_id"]
    assert packages.list_receipts()[0]["pipeline_id"] == "local.compose-pipeline"


def test_nested_pipeline_executes_and_enforces_declared_dependency():
    inner_definition = {
        "id": "local.inner-pipeline",
        "steps": [{"id": "inner", "type": "noop", "with": {"value": "${inputs.value}"}}],
        "input_schema": {
            "type": "object",
            "properties": {"value": {"type": "string"}},
            "required": ["value"],
        },
    }
    import_bytes(
        "local.inner-pipeline",
        package_bytes(
            "local.inner-pipeline",
            kind="pipeline",
            execution_mode="declarative",
            definition=inner_definition,
        ),
    )
    packages.set_enabled("local.inner-pipeline", True, confirm_trust=True)

    outer_definition = {
        "id": "local.outer-pipeline",
        "steps": [
            {
                "id": "nested",
                "type": "pipeline",
                "uses": "local.inner-pipeline",
                "with": {"value": "${inputs.value}"},
            }
        ],
        "input_schema": {
            "type": "object",
            "properties": {"value": {"type": "string"}},
            "required": ["value"],
        },
    }
    undeclared_archive = package_bytes(
        "local.outer-pipeline",
        kind="pipeline",
        execution_mode="declarative",
        definition=outer_definition,
    )
    import_bytes("local.outer-pipeline", undeclared_archive)
    packages.set_enabled("local.outer-pipeline", True, confirm_trust=True)
    with pytest.raises(packages.CapabilityPackageError) as error:
        packages.execute_pipeline_package(
            "local.outer-pipeline",
            inputs={"value": "nested"},
            confirmed=True,
            approved_permissions=[],
            manager=None,
        )
    assert error.value.code == "undeclared_dependency"

    # A new version is not needed: isolate the corrected outer package under a second id.
    corrected_definition = {
        **outer_definition,
        "id": "local.outer-pipeline-ok",
    }
    import_bytes(
        "local.outer-pipeline-ok",
        package_bytes(
            "local.outer-pipeline-ok",
            kind="pipeline",
            execution_mode="declarative",
            definition=corrected_definition,
            dependencies=[{"id": "local.inner-pipeline", "version": "1.0.0"}],
        ),
    )
    packages.set_enabled("local.outer-pipeline-ok", True, confirm_trust=True)
    result = packages.execute_pipeline_package(
        "local.outer-pipeline-ok",
        inputs={"value": "nested"},
        confirmed=True,
        approved_permissions=[],
        manager=None,
    )
    assert result["ok"] is True
    nested = result["receipt"]["result"]["steps"]["nested"]
    assert nested["result"]["output"] == {"value": "nested"}


def test_executable_pipeline_requires_confirmation_and_permissions():
    definition = {
        "contract_version": "bago.pipeline/v1",
        "schema_version": "1.0",
        "id": "local.executable-pipeline",
        "runtime": {"kind": "python", "timeout_s": 10},
        "input_schema": {
            "type": "object",
            "properties": {"value": {"type": "string"}},
            "required": ["value"],
        },
        "steps": [],
    }
    runner = (
        b"import json, sys\n"
        b"payload=json.load(sys.stdin)\n"
        b"print(json.dumps({'executed': payload['input']['value']}))\n"
    )
    imported = import_bytes(
        "local.executable-pipeline",
        package_bytes(
            "local.executable-pipeline",
            kind="pipeline",
            execution_mode="executable",
            definition=definition,
            runner=runner,
            permissions=["filesystem.read"],
        ),
    )
    assert imported["package"]["trust_state"] == "untrusted"
    with pytest.raises(packages.CapabilityPackageError) as activation:
        packages.set_enabled("local.executable-pipeline", True)
    assert activation.value.code == "trust_confirmation_required"
    packages.set_enabled("local.executable-pipeline", True, confirm_trust=True)
    with pytest.raises(packages.CapabilityPackageError) as confirmation:
        packages.execute_pipeline_package(
            "local.executable-pipeline",
            inputs={"value": "ok"},
            confirmed=False,
            approved_permissions=["filesystem.read"],
            manager=None,
        )
    assert confirmation.value.code == "confirmation_required"
    with pytest.raises(packages.CapabilityPackageError) as permission:
        packages.execute_pipeline_package(
            "local.executable-pipeline",
            inputs={"value": "ok"},
            confirmed=True,
            approved_permissions=[],
            manager=None,
        )
    assert permission.value.code == "permission_approval_required"
    result = packages.execute_pipeline_package(
        "local.executable-pipeline",
        inputs={"value": "ok"},
        confirmed=True,
        approved_permissions=["filesystem.read"],
        manager=None,
    )
    assert result["ok"] is True
    assert result["receipt"]["result"] == {"executed": "ok"}


def test_schedule_defaults_are_validated_but_never_activated():
    archive = canonical_bytes(schedule_defaults=[{
        "name": "Cada hora",
        "schedule_type": "interval",
        "interval_s": 3600,
        "timezone": "UTC",
    }])
    inspected = packages.inspect_package(content_base64=encode(archive), file_name="scheduled.zip")
    assert inspected["ok"] is True
    imported = packages.import_package(content_base64=encode(archive), file_name="scheduled.zip", confirm_trust=True)
    assert imported["package"]["schedule_defaults"][0]["interval_s"] == 3600

    invalid = canonical_bytes(schedule_defaults=[{
        "name": "Demasiado frecuente",
        "schedule_type": "interval",
        "interval_s": 1,
        "timezone": "UTC",
    }])
    rejected = packages.inspect_package(content_base64=encode(invalid), file_name="invalid-schedule.zip")
    assert rejected["ok"] is False
    assert "interval_s" in rejected["errors"][0]["message"]


def test_example_catalog_routes_are_exposed():
    import api_dispatch

    assert "/api/v1/capability-packages/examples" in api_dispatch.GET_ROUTES
    matched, install = api_dispatch.resolve_post(
        object(),
        "/api/v1/capability-packages/local.scheduled-report/install-example",
        {},
    )
    assert matched is True
    assert callable(install)

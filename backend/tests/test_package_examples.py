from __future__ import annotations

import base64
import io
import json
from pathlib import Path
import zipfile

import capability_packages as packages


EXAMPLES_ROOT = Path(__file__).resolve().parents[2] / "examples" / "packages"


def example_archive(name: str) -> bytes:
    root = EXAMPLES_ROOT / name
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(item for item in root.rglob("*") if item.is_file()):
            archive.writestr(path.relative_to(root).as_posix(), path.read_bytes())
    return buffer.getvalue()


def encode(content: bytes) -> str:
    return base64.b64encode(content).decode("ascii")


def test_productivity_examples_satisfy_the_package_contract():
    expected = {
        "text-stats": "local.text-stats-v1",
        "text-transform": "local.text-transform",
        "file-batch": "local.file-batch",
        "report-builder": "local.report-builder",
        "scheduled-report": "local.scheduled-report",
    }

    for name, package_id in expected.items():
        inspected = packages.inspect_package(
            content_base64=encode(example_archive(name)),
            file_name=f"{name}.bago.zip",
        )
        assert inspected["ok"] is True, inspected
        assert inspected["identity"]["id"] == package_id
        assert inspected["digest_state"] == "verified"
        assert inspected["signature_state"] == "unsigned"


def test_text_transform_and_report_examples_execute(tmp_path, monkeypatch):
    monkeypatch.setattr(packages, "state_root", lambda: tmp_path / "state")
    for name in ("text-transform", "report-builder"):
        packages.import_package(
            content_base64=encode(example_archive(name)),
            file_name=f"{name}.bago.zip",
            confirm_trust=True,
        )

    packages.set_enabled("local.text-transform", True, confirm_trust=True)
    transformed = packages.execute_package(
        "local.text-transform",
        inputs={"text": "  BAGO   local  "},
        confirmed=True,
        approved_permissions=[],
    )
    assert transformed["receipt"]["status"] == "succeeded"
    assert transformed["receipt"]["result"]["text"] == "BAGO local"

    packages.set_enabled("local.report-builder", True, confirm_trust=True)
    report = packages.execute_package(
        "local.report-builder",
        inputs={
            "title": "Estado",
            "summary": "Semana",
            "sections_json": json.dumps([{"title": "Hecho", "content": "Tres tareas."}]),
        },
        confirmed=True,
        approved_permissions=[],
    )
    assert report["receipt"]["status"] == "succeeded"
    assert "# Estado" in report["receipt"]["result"]["content"]


def test_scheduled_report_is_inert_on_import_and_executes_when_enabled(tmp_path, monkeypatch):
    monkeypatch.setattr(packages, "state_root", lambda: tmp_path / "state")
    for name in ("file-batch", "report-builder", "scheduled-report"):
        packages.import_package(
            content_base64=encode(example_archive(name)),
            file_name=f"{name}.bago.zip",
            confirm_trust=True,
        )
        package_id = {
            "file-batch": "local.file-batch",
            "report-builder": "local.report-builder",
            "scheduled-report": "local.scheduled-report",
        }[name]
        packages.set_enabled(package_id, True, confirm_trust=True)

    pipeline = packages.get_package("local.scheduled-report")
    assert pipeline["schedule_defaults"] == [{
        "name": "Informe diario del workspace",
        "schedule_type": "cron",
        "cron_expr": "0 9 * * 1-5",
        "timezone": "UTC",
    }]
    assert not (tmp_path / "state" / "schedules.json").exists()

    result = packages.execute_pipeline_package(
        "local.scheduled-report",
        inputs={"root": str(tmp_path), "title": "Informe de prueba"},
        confirmed=True,
        approved_permissions=["filesystem.read"],
        manager=None,
    )
    assert result["ok"] is True
    assert result["receipt"]["status"] == "succeeded"
    assert result["receipt"]["steps"][-1]["status"] == "succeeded"
    assert "# Informe de prueba" in result["receipt"]["result"]["output"]["content"]


def test_bundled_examples_can_be_listed_and_installed_without_activation(tmp_path, monkeypatch):
    monkeypatch.setattr(packages, "state_root", lambda: tmp_path / "state")
    examples = packages.list_example_packages()
    ids = {item["id"] for item in examples}
    assert {"local.text-transform", "local.file-batch", "local.report-builder", "local.scheduled-report"} <= ids

    installed = packages.install_example_package("local.scheduled-report")
    assert installed["package"]["id"] == "local.scheduled-report"
    assert installed["package"]["enabled"] is False
    assert installed["package"]["trust_state"] == "untrusted"

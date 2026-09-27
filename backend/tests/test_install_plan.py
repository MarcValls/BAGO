from __future__ import annotations

import hashlib
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend" / ".bago" / "core"))

from install_plan import InstallPlanError, build_install_plan, configuration_digest, plan_digest, source_tree_digest  # noqa: E402


def _sha(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _configuration(label: str) -> dict:
    return {
        "providers": {
            "ollama-local": {"enabled": True, "base_url": "http://127.0.0.1:11434", "model": "llama3.2:3b"},
            "codex": {"enabled": False, "base_url": "https://api.openai.com/v1", "api_key": f"secret-{label}", "model": "gpt-5.4-mini"},
            "copilot": {"enabled": False, "base_url": "https://api.githubcopilot.com", "api_key": "", "auth_mode": "device-flow", "model": "gpt-4o-copilot"},
            "ollama-cloud": {"enabled": False, "base_url": "", "api_key": "", "auth_mode": "signin", "model": "llama3.2:3b"},
        },
        "knowledge": {"mode": "none", "path": "", "visibility": "private", "git_init": False},
        "credential_store": {"mode": "session", "path": "", "encrypted": False, "scope": "session"},
    }


def _fixture(tmp_path: Path):
    source = tmp_path / "source"
    source.mkdir()
    helper = source / "install-v4.ps1"
    helper.write_bytes(b"Write-Output ready\n")
    target = tmp_path / "installed" / "BAGO"
    return source, helper, target


def test_install_plan_binds_source_helper_target_configuration_and_options(tmp_path: Path) -> None:
    source, helper, target = _fixture(tmp_path)
    first = build_install_plan(
        action="install", source_root=source, helper_path=helper,
        install_dir=target, mode="Express", options={"skip_tests": True},
        configuration=_configuration("a"),
    )
    second = build_install_plan(
        action="install", source_root=source, helper_path=helper,
        install_dir=target, mode="Express", options={"skip_tests": True},
        configuration=_configuration("a"),
    )

    assert first == second
    assert first["source_tree_sha256"] == source_tree_digest(source)
    assert first["helper_sha256"] == _sha("Write-Output ready\n")
    assert first["operation_sha256"] == plan_digest(first)
    assert first["configuration_digest"] == configuration_digest(_configuration("a"))
    assert "secret-a" not in repr(first)


@pytest.mark.parametrize("changed", ["mode", "configuration", "target", "source", "helper"])
def test_install_plan_digest_changes_when_authorized_operation_changes(tmp_path: Path, changed: str) -> None:
    source, helper, target = _fixture(tmp_path)
    base = build_install_plan(
        action="install", source_root=source, helper_path=helper,
        install_dir=target, mode="Express", options={},
        configuration=_configuration("a"),
    )
    arguments = {
        "action": "install", "source_root": source, "helper_path": helper,
        "install_dir": target, "mode": "Express", "options": {},
        "configuration": _configuration("a"),
    }
    if changed == "mode":
        arguments["mode"] = "Advanced"
    elif changed == "configuration":
        arguments["configuration"] = _configuration("b")
    elif changed == "target":
        arguments["install_dir"] = tmp_path / "other-target"
    elif changed == "helper":
        helper.write_bytes(b"Write-Output changed\n")
    else:
        (source / "runtime.py").write_text("different\n", encoding="utf-8")
    changed_plan = build_install_plan(**arguments)

    assert changed_plan["operation_sha256"] != base["operation_sha256"]


def test_install_plan_rejects_unselected_mode_unknown_options_and_external_helper(tmp_path: Path) -> None:
    source, helper, target = _fixture(tmp_path)
    base = {
        "action": "install", "source_root": source, "helper_path": helper,
        "install_dir": target, "mode": "", "options": {},
        "configuration": _configuration("a"),
    }
    with pytest.raises(InstallPlanError, match="mode must be selected"):
        build_install_plan(**base)
    with pytest.raises(InstallPlanError, match="unsupported installer switches"):
        build_install_plan(**{**base, "mode": "Express", "options": {"force": True}})
    outside = tmp_path / "outside.ps1"
    outside.write_text("exit 0\n", encoding="utf-8")
    with pytest.raises(InstallPlanError, match="inside source_root"):
        build_install_plan(**{**base, "mode": "Express", "helper_path": outside})


def test_source_tree_digest_rejects_symlinks(tmp_path: Path) -> None:
    source, _, _ = _fixture(tmp_path)
    link = source / "linked.txt"
    target = tmp_path / "external.txt"
    target.write_text("outside", encoding="utf-8")
    try:
        link.symlink_to(target)
    except (OSError, NotImplementedError):
        pytest.skip("symlink creation is unavailable")

    with pytest.raises(InstallPlanError, match="Linked source entry"):
        source_tree_digest(source)

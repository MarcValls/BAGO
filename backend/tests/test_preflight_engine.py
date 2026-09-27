from __future__ import annotations

import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / ".bago" / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import preflight_engine


def test_preflight_file_env_command_and_warning_behavior(tmp_path, monkeypatch) -> None:
    (tmp_path / "present.txt").write_text("ok\n", encoding="utf-8")
    monkeypatch.setenv("BAGO_PREFLIGHT_TEST_ENV", "1")

    files = preflight_engine.Preflight("sample", root=tmp_path)
    files.require_file("present.txt")
    assert files.passed

    missing = preflight_engine.Preflight("sample", root=tmp_path)
    missing.require_file("missing.txt")
    assert not missing.passed
    assert missing.run(exit_on_fail=False, silent=True) is False

    environment = preflight_engine.Preflight("sample")
    environment.require_env("BAGO_PREFLIGHT_TEST_ENV")
    assert environment.passed

    command = preflight_engine.Preflight("sample")
    monkeypatch.setattr(preflight_engine.shutil, "which", lambda _name: "python")
    command.require_cmd("python")
    assert command.passed

    warning = preflight_engine.Preflight("sample", root=tmp_path)
    warning.require_file("missing-warning.txt", severity="warning")
    assert warning.run(exit_on_fail=False, silent=True)


def test_preflight_json_shape_is_stable(tmp_path) -> None:
    preflight = preflight_engine.Preflight("sample", root=tmp_path)
    preflight.require_file("missing.txt")

    checks = preflight.to_json_checks()

    assert len(checks) == 1
    assert set(checks[0]) == {"name", "passed", "message", "severity"}
    assert checks[0]["passed"] is False


def test_removed_selftest_switch_is_rejected() -> None:
    with pytest.raises(SystemExit) as exc:
        preflight_engine.main(["--test"])

    assert exc.value.code == 2

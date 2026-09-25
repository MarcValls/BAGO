from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parents[1] / ".bago" / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import doctor


def test_check_python_syntax_reports_invalid_source(tmp_path: Path) -> None:
    (tmp_path / "broken.py").write_text("def bad(:\n pass\n", encoding="utf-8")

    findings = doctor.check_python_syntax(tmp_path, set())

    assert [item["code"] for item in findings] == ["DR-E001"]


def test_check_json_files_reports_invalid_document(tmp_path: Path) -> None:
    (tmp_path / "bad.json").write_text("{bad json}\n", encoding="utf-8")

    findings = doctor.check_json_files(tmp_path, set())

    assert [item["code"] for item in findings] == ["DR-E002"]


def test_check_encoding_reports_invalid_utf8(tmp_path: Path) -> None:
    (tmp_path / "bad.txt").write_bytes(b"abc\xff\n")

    findings = doctor.check_encoding(tmp_path)

    assert findings[0]["code"] == "DR-E003"


def test_check_large_files_reports_large_artifact(tmp_path: Path) -> None:
    (tmp_path / "large.bin").write_bytes(b"0" * (doctor.LARGE_FILE_BYTES + 1))

    findings = doctor.check_large_files(tmp_path)

    assert findings[0]["code"] == "DR-W001"


def test_check_orphans_reports_temporary_artifact(tmp_path: Path) -> None:
    (tmp_path / "notes.tmp").write_text("temp\n", encoding="utf-8")

    findings = doctor.check_orphans(tmp_path)

    assert findings[0]["code"] == "DR-W002"


def test_main_emits_json_and_clean_exit(tmp_path: Path, capsys) -> None:
    (tmp_path / "ok.py").write_text("value = 2\n", encoding="utf-8")

    result = doctor.main(["--root", str(tmp_path), "--json"])

    assert result == 0
    assert json.loads(capsys.readouterr().out)["errors"] == 0


def test_self_test_cli_switch_was_removed() -> None:
    with pytest.raises(SystemExit) as exit_info:
        doctor.main(["--test"])

    assert exit_info.value.code == 2

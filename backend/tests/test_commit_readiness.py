from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parents[1] / ".bago" / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import commit_readiness


def test_check_syntax_flags_invalid_source(tmp_path: Path) -> None:
    source = tmp_path / "sample.py"
    source.write_text("def bad(:\n pass\n", encoding="utf-8")

    assert commit_readiness.check_syntax(source, tmp_path)[0]["code"] == "CR-E001"


def test_check_secrets_flags_password_fixture(tmp_path: Path) -> None:
    source = tmp_path / "sample.py"
    source.write_text('password = "supersecret123"\n', encoding="utf-8")

    assert commit_readiness.check_secrets(source, tmp_path)[0]["code"] == "CR-E002"


def test_check_merge_conflicts_flags_markers(tmp_path: Path) -> None:
    source = tmp_path / "sample.py"
    source.write_text("<<<<<<< HEAD\nfoo=1\n=======\nfoo=2\n>>>>>>> branch\n", encoding="utf-8")

    assert commit_readiness.check_merge_conflicts(source, tmp_path)[0]["code"] == "CR-E003"


def test_check_debug_prints_flags_unmarked_print(tmp_path: Path) -> None:
    source = tmp_path / "sample.py"
    source.write_text("def f():\n    print('debug')\n", encoding="utf-8")

    assert commit_readiness.check_debug_prints(source, tmp_path)[0]["code"] == "CR-W001"


def test_check_new_todos_flags_added_todo() -> None:
    assert commit_readiness.check_new_todos("+ # TODO: fix me\n")[0]["code"] == "CR-W002"


def test_new_task_marker_does_not_copy_staged_source_into_report() -> None:
    secret = "sk-" + "A" * 24
    marker = "TO" + "DO"
    findings = commit_readiness.check_new_todos(f"+ # {marker}: rotate credential {secret}\n")

    assert findings[0]["code"] == "CR-W002"
    assert "task marker" in findings[0]["message"]
    assert secret not in findings[0]["message"]


def test_cli_report_outputs_only_safe_finding_projection(capsys: pytest.CaptureFixture[str]) -> None:
    secret = "sk-" + "A" * 24
    result = {
        "root": "C:/private/" + secret,
        "mode": "standard",
        "files": ["C:/private/" + secret + "/module.py"],
        "total": 1,
        "errors": 1,
        "warnings": 0,
        "findings": [{
            "code": "CR-E002",
            "severity": "error",
            "path": "C:/private/" + secret + "/module.py",
            "line": 7,
            "message": "secret found: " + secret,
        }],
    }

    commit_readiness.print_report(result)
    human = capsys.readouterr().out
    payload = json.dumps(commit_readiness._safe_json_result(result))

    assert secret not in human + payload
    assert "C:/private" not in human + payload
    assert "CR-E002:7" in human
    assert json.loads(payload)["findings"][0]["label"] == "secret pattern detected; value withheld"


def test_check_docstrings_strict_and_clean_evaluation(tmp_path: Path) -> None:
    source = tmp_path / "sample.py"
    source.write_text("def public():\n    return 1\n", encoding="utf-8")
    assert commit_readiness.check_docstrings(source, tmp_path)

    source.write_text('"""module doc"""\n\n\ndef public():\n    """doc"""\n    return 1\n', encoding="utf-8")
    assert commit_readiness.evaluate([source], tmp_path, None, strict=True)["total"] == 0


def test_find_git_root_walks_marker_without_running_process(tmp_path: Path, monkeypatch) -> None:
    root = tmp_path / "repo"
    nested = root / "src" / "module"
    (root / ".git").mkdir(parents=True)
    nested.mkdir(parents=True)
    monkeypatch.setattr(commit_readiness, "execute_cli_effect", lambda *_args, **_kwargs: pytest.fail("no process expected"))

    assert commit_readiness.find_git_root(nested) == root.resolve()


def test_git_helper_uses_only_registered_staged_operations(tmp_path: Path, monkeypatch) -> None:
    captured = []
    monkeypatch.setattr(
        commit_readiness,
        "execute_cli_effect",
        lambda request, **_kwargs: captured.append(request) or ({"ok": True, "returncode": 0, "stdout": "src/a.py\0"}, {}),
    )

    result = commit_readiness.git(["diff", "--cached", "--name-only", "-z", "--diff-filter=ACMR"], tmp_path)

    assert result.stdout == "src/a.py\0"
    assert captured[0].effect_id == "repository.inspect"
    assert captured[0].target["operation"] == "staged_files"
    with pytest.raises(ValueError):
        commit_readiness.git(["status", "--short"], tmp_path)


def test_internal_self_test_cli_switch_was_removed() -> None:
    with pytest.raises(SystemExit) as exit_info:
        commit_readiness.main(["--test"])

    assert exit_info.value.code == 2

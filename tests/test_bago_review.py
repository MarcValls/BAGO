"""Tests focalizados para `bago review`."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / ".bago" / "tools"))
import code_review  # noqa: E402


def test_run_reviews_emits_stable_schema(tmp_path, monkeypatch):
    """El reporte JSON mantiene un esquema estable y canónico."""
    target = tmp_path / "sample.py"
    target.write_text("print('ok')\n", encoding="utf-8")

    def fake_run_tool(tool: str, args: list[str], cwd: str, timeout: int = 60):  # noqa: ARG001
        findings = {
            "scan.py": [],
            "complexity.py": [],
            "secret_scan.py": [],
            "dead_code.py": [],
            "duplicate_check.py": [],
        }
        return 0, json.dumps(findings.get(tool, [])), ""

    monkeypatch.setattr(code_review, "_run_tool", fake_run_tool)

    report = code_review.run_reviews(str(tmp_path))

    assert report["schema_version"] == 1
    assert report["command"] == "bago review"
    assert report["summary"]["max_score"] == 100
    assert report["summary"]["min_score"] == code_review.DEFAULT_MIN_SCORE
    assert report["verdict"]["id"] == "mergeable"
    assert report["verdict"]["mergeable"] is True
    assert "lint" in report["sections"]


def test_changed_only_limits_scope_to_files_since_base(tmp_path, monkeypatch):
    """`--changed-only --base` filtra findings al diff contra la base."""
    repo = tmp_path
    (repo / "clean.py").write_text("print('base')\n", encoding="utf-8")

    assert code_review._git(["init"], str(repo))[0] == 0
    code_review._git(["config", "user.email", "test@example.com"], str(repo))
    code_review._git(["config", "user.name", "BAGO Test"], str(repo))
    code_review._git(["add", "clean.py"], str(repo))
    code_review._git(["commit", "-m", "base"], str(repo))

    (repo / "changed.py").write_text("print('first')\n", encoding="utf-8")
    code_review._git(["add", "changed.py"], str(repo))
    code_review._git(["commit", "-m", "add changed"], str(repo))
    (repo / "changed.py").write_text("print('second')\n", encoding="utf-8")

    def fake_run_tool(tool: str, args: list[str], cwd: str, timeout: int = 60):  # noqa: ARG001
        findings = {
            "scan.py": [
                {"file": "clean.py", "line": 1, "severity": "warning", "rule": "X1", "message": "old"},
                {"file": "changed.py", "line": 1, "severity": "warning", "rule": "X2", "message": "new"},
            ],
            "complexity.py": [],
            "secret_scan.py": [],
            "dead_code.py": [],
            "duplicate_check.py": [],
        }
        return 0, json.dumps(findings.get(tool, [])), ""

    monkeypatch.setattr(code_review, "_run_tool", fake_run_tool)

    report = code_review.run_reviews(str(repo), changed_only=True, base_ref="HEAD~1", min_score=40)

    assert report["scope"]["files"] == ["changed.py"]
    assert report["scope"]["file_count"] == 1
    assert report["total_findings"] == 1
    assert report["verdict"]["id"] == "review-required"


def test_markdown_and_ci_mode_use_bago_review_name(tmp_path, monkeypatch):
    """Markdown y CI usan el nombre canónico `bago review`."""
    report = {
        "schema_version": 1,
        "command": "bago review",
        "score": 80,
        "total_lines": 10,
        "total_findings": 1,
        "elapsed_s": 0.1,
        "mode": {"ci": True, "changed_only": False, "base_ref": "", "sarif_inputs": []},
        "scope": {"root": str(tmp_path), "kind": "directory", "files": [], "file_count": 1},
        "summary": {
            "score": 80,
            "max_score": 100,
            "min_score": 80,
            "weighted_findings": 2,
            "total_findings": 1,
            "by_severity": {"error": 0, "warning": 1, "info": 0, "hint": 0},
            "checks": {"ok": 0, "warn": 1, "fail": 0, "skipped": 0},
        },
        "checks": [
            {
                "id": "lint",
                "name": "BAGO Lint",
                "tool": "scan.py",
                "status": "warn",
                "findings": 1,
                "by_severity": {"error": 0, "warning": 1, "info": 0, "hint": 0},
                "details": [{"file": "sample.py", "line": 1, "severity": "warning", "rule": "X1", "message": "warn"}],
                "error": "",
            }
        ],
        "sections": {},
        "verdict": {
            "id": "review-required",
            "label": "REVIEW REQUIRED",
            "mergeable": False,
            "reason": "1 warning finding(s)",
            "score": 80,
            "min_score": 80,
            "total_findings": 1,
        },
        "verdict_label": "REVIEW REQUIRED",
    }

    markdown = code_review.generate_markdown(report)

    monkeypatch.setattr(code_review, "run_reviews", lambda *args, **kwargs: report)

    assert "bago review" in markdown
    assert "bago code-review" not in markdown
    assert code_review.main([str(tmp_path), "--ci"]) == 1

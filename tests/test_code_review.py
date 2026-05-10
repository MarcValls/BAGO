from __future__ import annotations

import code_review


def test_run_reviews_exposes_explicit_scanner_statuses(monkeypatch, tmp_path):
    (tmp_path / "clean.py").write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")

    outputs = {
        "scan.py": "[]",
        "complexity.py": '[{"rule": "CX001"}]',
        "secret_scan.py": "[]",
        "dead_code.py": "[]",
        "duplicate_check.py": "[]",
    }

    monkeypatch.setattr(code_review, "_count_py_lines", lambda _: 100)
    monkeypatch.setattr(
        code_review,
        "_run_tool",
        lambda tool, args, cwd, timeout=60: (0, outputs[tool], ""),
    )

    report = code_review.run_reviews(str(tmp_path))

    assert report["scanner_failures"] == 0
    assert report["sections"]["complexity"]["scanner_status"] == "findings"
    assert report["sections"]["complexity"]["status"] == "warn"
    assert report["sections"]["complexity"]["exit_code"] == 0
    assert report["sections"]["complexity"]["error"] == ""
    assert "Scanner status" in code_review.generate_markdown(report)


def test_run_reviews_fails_closed_when_scanner_is_unavailable(monkeypatch, tmp_path):
    (tmp_path / "clean.py").write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")

    def fake_run_tool(tool, args, cwd, timeout=60):
        if tool == "complexity.py":
            return -1, "", "tool not found: complexity.py"
        return 0, "[]", ""

    monkeypatch.setattr(code_review, "_count_py_lines", lambda _: 100)
    monkeypatch.setattr(code_review, "_run_tool", fake_run_tool)

    report = code_review.run_reviews(str(tmp_path))

    assert report["score"] == 0
    assert report["verdict"] == "❌ NO MERGE (scanner error)"
    assert report["scanner_failures"] == 1
    assert report["scanner_errors"] == {"complexity": "complexity.py: tool not found: complexity.py"}
    assert report["sections"]["complexity"]["scanner_status"] == "error"
    assert report["sections"]["complexity"]["status"] == "fail"


def test_run_reviews_fails_closed_when_scanner_json_is_invalid(monkeypatch, tmp_path):
    (tmp_path / "clean.py").write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")

    def fake_run_tool(tool, args, cwd, timeout=60):
        if tool == "secret_scan.py":
            return 0, "{not-json", ""
        return 0, "[]", ""

    monkeypatch.setattr(code_review, "_count_py_lines", lambda _: 100)
    monkeypatch.setattr(code_review, "_run_tool", fake_run_tool)

    report = code_review.run_reviews(str(tmp_path))

    assert report["score"] == 0
    assert report["scanner_failures"] == 1
    assert report["sections"]["secrets"]["scanner_status"] == "error"
    assert report["sections"]["secrets"]["status"] == "fail"
    assert "secret_scan.py" in report["sections"]["secrets"]["error"]

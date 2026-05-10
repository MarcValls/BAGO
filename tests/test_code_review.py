from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / ".bago" / "tools"))
import code_review  # noqa: E402


@pytest.fixture
def scanner_defs():
    return (
        {
            "key": "fixture",
            "name": "Fixture Scanner",
            "tool": "fixture.py",
            "args": ["{directory}"],
            "parser": "json",
            "critical": True,
            "warn_threshold": 2,
            "fail_threshold": 5,
            "detail_limit": 5,
            "score_multiplier": 1,
            "score_divisor": 1,
            "block_on_statuses": {code_review.STATUS_ERROR},
        },
    )


def test_missing_scanner_is_reported_as_error(monkeypatch, tmp_path, scanner_defs):
    monkeypatch.setattr(code_review, "SCANNER_DEFS", scanner_defs)
    monkeypatch.setattr(code_review, "_run_tool", lambda *args, **kwargs: (-1, "", "tool not found: fixture.py"))

    report = code_review.run_reviews(str(tmp_path))
    section = report["sections"]["fixture"]

    assert section["status"] == "error"
    assert section["return_code"] == -1
    assert section["parse_status"] == "not_attempted"
    assert report["blocker_count"] == 1
    assert report["verdict"] == "❌ NO MERGE"


def test_timeout_is_reported_as_error(monkeypatch, tmp_path, scanner_defs):
    monkeypatch.setattr(code_review, "SCANNER_DEFS", scanner_defs)
    monkeypatch.setattr(code_review, "_run_tool", lambda *args, **kwargs: (-2, "", "timeout after 60s"))

    report = code_review.run_reviews(str(tmp_path))
    section = report["sections"]["fixture"]

    assert section["status"] == "error"
    assert section["return_code"] == -2
    assert section["parse_status"] == "not_attempted"
    assert report["blocker_count"] == 1


def test_invalid_json_blocks_instead_of_counting_zero_findings(monkeypatch, tmp_path, scanner_defs):
    monkeypatch.setattr(code_review, "SCANNER_DEFS", scanner_defs)
    monkeypatch.setattr(code_review, "_run_tool", lambda *args, **kwargs: (0, "not-json", "broken output"))

    report = code_review.run_reviews(str(tmp_path))
    section = report["sections"]["fixture"]
    text = code_review.generate_text(report)

    assert section["status"] == "error"
    assert section["findings"] == 0
    assert section["parse_status"] == "invalid_json"
    assert report["blocker_count"] == 1
    assert report["verdict"] == "❌ NO MERGE"
    assert "status=error" in text


def test_strict_sarif_parse_failure_is_a_blocker(monkeypatch, tmp_path, scanner_defs):
    sarif_defs = ({**scanner_defs[0], "parser": "sarif"},)
    monkeypatch.setattr(code_review, "SCANNER_DEFS", sarif_defs)
    monkeypatch.setattr(code_review, "_run_tool", lambda *args, **kwargs: (0, json.dumps({"version": "2.1.0"}), ""))

    report = code_review.run_reviews(str(tmp_path))
    section = report["sections"]["fixture"]

    assert section["status"] == "error"
    assert section["parse_status"] == "invalid_sarif"
    assert report["blocker_count"] == 1
    assert report["verdict"] == "❌ NO MERGE"


def test_ci_mode_exits_non_zero_on_critical_scanner_error(monkeypatch, tmp_path, scanner_defs):
    monkeypatch.setattr(code_review, "SCANNER_DEFS", scanner_defs)
    monkeypatch.setattr(code_review, "_run_tool", lambda *args, **kwargs: (-1, "", "tool not found: fixture.py"))

    rc = code_review.main([str(tmp_path), "--ci"])

    assert rc == 1


def test_valid_non_zero_return_code_with_findings_is_not_treated_as_execution_error(monkeypatch, tmp_path, scanner_defs):
    monkeypatch.setattr(code_review, "SCANNER_DEFS", scanner_defs)
    payload = json.dumps({"total": 3, "findings": [{"id": 1}, {"id": 2}, {"id": 3}]})
    monkeypatch.setattr(code_review, "_run_tool", lambda *args, **kwargs: (1, payload, "scanner reported findings"))

    report = code_review.run_reviews(str(tmp_path))
    section = report["sections"]["fixture"]

    assert section["status"] == "warn"
    assert section["return_code"] == 1
    assert section["parse_status"] == "ok"
    assert report["blocker_count"] == 0

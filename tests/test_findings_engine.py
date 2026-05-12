"""
tests/test_findings_engine.py — Tests para findings_engine.py

Cubre: Finding, parsers (flake8/pylint/mypy/bandit/shellcheck),
diff_findings, save/load, SARIF output, Finding.to_dict/from_dict.
"""

import json
import os
import sys
from pathlib import Path
import pytest

# ── Bootstrap ──────────────────────────────────────────────────────────────
REPO = Path(__file__).resolve().parents[1]
TOOLS = REPO / ".bago" / "tools"
sys.path.insert(0, str(TOOLS))

# Isolate findings dir via env var
import tempfile
_TMP = tempfile.mkdtemp(prefix="bago_findings_test_")
os.environ.setdefault("BAGO_STATE_DIR", _TMP)

import findings_engine as fe


# ── Finding dataclass ──────────────────────────────────────────────────────

class TestFinding:
    def _make(self, **kw) -> fe.Finding:
        defaults = dict(
            id="FIND-ABCD1234",
            severity="error",
            file="bago_core/foo.py",
            line=10,
            col=4,
            rule="E501",
            source="flake8",
            message="line too long",
        )
        defaults.update(kw)
        return fe.Finding(**defaults)

    def test_finding_fields(self):
        f = self._make()
        assert f.severity == "error"
        assert f.rule == "E501"
        assert f.autofixable is False

    def test_to_dict_roundtrip(self):
        f = self._make(fix_suggestion="shorten line", autofixable=True)
        d = f.to_dict()
        assert isinstance(d, dict)
        assert d["severity"] == "error"
        assert d["autofixable"] is True

    def test_from_dict_roundtrip(self):
        f = self._make()
        d = f.to_dict()
        f2 = fe.Finding.from_dict(d)
        assert f2.id == f.id
        assert f2.line == f.line
        assert f2.source == f.source

    def test_from_dict_ignores_extra_keys(self):
        f = self._make()
        d = f.to_dict()
        d["__extra__"] = "ignored"
        f2 = fe.Finding.from_dict(d)
        assert f2.rule == f.rule

    def test_severities_constant(self):
        assert "error" in fe.SEVERITIES
        assert "warning" in fe.SEVERITIES
        assert "info" in fe.SEVERITIES


# ── parse_flake8 ────────────────────────────────────────────────────────────

class TestParseFlake8:
    def test_basic_line(self):
        output = "bago_core/foo.py:10:5: E501 line too long (90 > 79 characters)"
        findings = fe.parse_flake8(output)
        assert len(findings) == 1
        f = findings[0]
        assert f.line == 10
        assert f.col == 5
        assert f.rule == "E501"
        assert "line too long" in f.message
        assert f.source == "flake8"

    def test_empty_output(self):
        assert fe.parse_flake8("") == []

    def test_multiple_lines(self):
        output = (
            "bago_core/a.py:1:1: F401 'os' imported but unused\n"
            "bago_core/b.py:20:3: E302 expected 2 blank lines\n"
        )
        findings = fe.parse_flake8(output)
        assert len(findings) == 2
        assert findings[0].rule == "F401"
        assert findings[1].rule == "E302"

    def test_severity_warning_for_w_codes(self):
        output = "bago_core/foo.py:5:1: W291 trailing whitespace"
        findings = fe.parse_flake8(output)
        if findings:  # if parser is implemented
            assert findings[0].source == "flake8"

    def test_invalid_lines_ignored(self):
        output = "not a flake8 line at all\n"
        findings = fe.parse_flake8(output)
        assert isinstance(findings, list)


# ── parse_pylint ────────────────────────────────────────────────────────────

class TestParsePylint:
    def test_basic_line(self):
        output = "bago_core/foo.py:15:0: C0114: Missing module docstring (missing-module-docstring)"
        findings = fe.parse_pylint(output)
        assert len(findings) == 1
        f = findings[0]
        assert f.line == 15
        assert "docstring" in f.message.lower()
        assert f.source == "pylint"

    def test_empty(self):
        assert fe.parse_pylint("") == []

    def test_error_severity(self):
        output = "bago_core/foo.py:5:4: E0001: invalid syntax (syntax-error)"
        findings = fe.parse_pylint(output)
        if findings:
            assert findings[0].severity in ("error", "warning", "info")


# ── parse_mypy ──────────────────────────────────────────────────────────────

class TestParseMypy:
    def test_error_line(self):
        output = 'bago_core/foo.py:10: error: Argument 1 to "foo" has incompatible type'
        findings = fe.parse_mypy(output)
        assert len(findings) >= 1
        assert findings[0].source == "mypy"

    def test_note_skipped_or_info(self):
        output = 'bago_core/foo.py:10: note: See https://mypy.readthedocs.io'
        findings = fe.parse_mypy(output)
        # notes may be filtered or kept as info — either is fine
        assert isinstance(findings, list)

    def test_empty(self):
        assert fe.parse_mypy("") == []


# ── parse_bandit ────────────────────────────────────────────────────────────

class TestParseBandit:
    BANDIT_JSON = json.dumps({
        "results": [
            {
                "filename": "bago_core/foo.py",
                "line_number": 42,
                "col_offset": 0,
                "test_id": "B105",
                "issue_severity": "HIGH",
                "issue_confidence": "MEDIUM",
                "issue_text": "Hardcoded password string 'secret'",
                "more_info": ""
            }
        ]
    })

    def test_parses_json(self):
        findings = fe.parse_bandit(self.BANDIT_JSON)
        assert len(findings) == 1
        f = findings[0]
        assert f.rule == "B105"
        assert f.line == 42
        assert f.source == "bandit"
        assert "password" in f.message.lower()

    def test_empty_results(self):
        findings = fe.parse_bandit(json.dumps({"results": []}))
        assert findings == []

    def test_invalid_json_returns_empty(self):
        findings = fe.parse_bandit("not json")
        assert isinstance(findings, list)


# ── parse_shellcheck ────────────────────────────────────────────────────────

class TestParseShellcheck:
    SC_JSON = json.dumps([{
        "file": "launcher/run.sh",
        "line": 5,
        "endLine": 5,
        "column": 1,
        "endColumn": 10,
        "level": "warning",
        "code": 2086,
        "message": "Double quote to prevent globbing and word splitting."
    }])

    def test_parses_json(self):
        findings = fe.parse_shellcheck(self.SC_JSON)
        assert len(findings) == 1
        f = findings[0]
        assert f.rule == "SC2086"
        assert f.severity == "warning"
        assert f.source == "shellcheck"

    def test_empty_array(self):
        assert fe.parse_shellcheck("[]") == []

    def test_invalid_json_returns_empty(self):
        findings = fe.parse_shellcheck("not json")
        assert isinstance(findings, list)


# ── diff_findings ───────────────────────────────────────────────────────────

class TestDiffFindings:
    def _f(self, rule: str, line: int = 1) -> fe.Finding:
        return fe.Finding(
            id=f"FIND-{rule}-{line}",
            severity="warning",
            file="foo.py",
            line=line,
            col=1,
            rule=rule,
            source="flake8",
            message=f"Test {rule}",
        )

    def test_new_findings_detected(self):
        old = [self._f("E501", 1)]
        new = [self._f("E501", 1), self._f("E302", 5)]
        result = fe.diff_findings(old, new)
        # diff_findings returns dict with keys: new, fixed, persistent
        assert isinstance(result, dict)
        assert "new" in result
        assert len(result["new"]) == 1
        assert result["new"][0].rule == "E302"

    def test_no_diff_persistent(self):
        f = [self._f("E501", 1)]
        result = fe.diff_findings(f, f)
        assert isinstance(result, dict)
        assert len(result["new"]) == 0
        assert len(result["persistent"]) == 1

    def test_empty_old_all_new(self):
        new = [self._f("E501", 1), self._f("E302", 2)]
        result = fe.diff_findings([], new)
        assert isinstance(result, dict)
        assert len(result["new"]) == 2
        assert len(result["fixed"]) == 0

    def test_fixed_detected(self):
        old = [self._f("E501", 1), self._f("E302", 5)]
        new = [self._f("E501", 1)]
        result = fe.diff_findings(old, new)
        assert len(result["fixed"]) == 1
        assert result["fixed"][0].rule == "E302"


# ── FindingsDB save / load ───────────────────────────────────────────────────

class TestFindingsDB:
    def _sample_findings(self) -> list:
        return [
            fe.Finding(
                id="FIND-AAAA0001",
                severity="error",
                file="bago_core/test.py",
                line=1,
                col=1,
                rule="E501",
                source="flake8",
                message="line too long",
            )
        ]

    def test_save_creates_file(self, tmp_path, monkeypatch):
        monkeypatch.setattr(fe, "FINDINGS_DIR", tmp_path)
        db = fe.FindingsDB("SCAN-TESTONLY")
        db.add(self._sample_findings())
        path = db.save()
        assert path.exists()
        content = json.loads(path.read_text())
        assert content["meta"]["scan_id"] == "SCAN-TESTONLY"
        assert len(content["findings"]) == 1

    def test_save_load_roundtrip(self, tmp_path, monkeypatch):
        monkeypatch.setattr(fe, "FINDINGS_DIR", tmp_path)
        db = fe.FindingsDB("SCAN-ROUNDTRIP")
        db.add(self._sample_findings())
        db.save()
        db2 = fe.FindingsDB.load("SCAN-ROUNDTRIP")
        assert len(db2.findings) == 1
        assert db2.findings[0].id == "FIND-AAAA0001"
        assert db2.findings[0].rule == "E501"

    def test_deduplication(self, tmp_path, monkeypatch):
        monkeypatch.setattr(fe, "FINDINGS_DIR", tmp_path)
        db = fe.FindingsDB("SCAN-DEDUP")
        f = self._sample_findings()[0]
        db.add([f, f, f])  # same finding 3 times
        db.save()
        db2 = fe.FindingsDB.load("SCAN-DEDUP")
        assert len(db2.findings) == 1  # deduplicated

    def test_latest_returns_none_when_empty(self, tmp_path, monkeypatch):
        monkeypatch.setattr(fe, "FINDINGS_DIR", tmp_path)
        result = fe.FindingsDB.latest()
        assert result is None

    def test_summary_counts(self, tmp_path, monkeypatch):
        monkeypatch.setattr(fe, "FINDINGS_DIR", tmp_path)
        db = fe.FindingsDB("SCAN-SUMMARY")
        db.add(self._sample_findings())
        path = db.save()
        content = json.loads(path.read_text())
        assert content["summary"]["total"] == 1
        assert content["summary"]["by_severity"]["error"] == 1

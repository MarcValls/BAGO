"""test_sarif_parser.py — Tests para parse_sarif() en findings_engine.py.

Casos cubiertos:
  1. SARIF vacío → []
  2. CodeQL warning con file/line → Finding(source="codeql")
  3. SARIF sin location → finding global (file="", line=0), no crash
  4. Severity mapping correcto (error/warning/note/none)
  5. ID canónico estable para misma ubicación/regla
  6. Múltiples runs (herramientas distintas) se parsean correctamente
  7. JSON inválido → [] sin crash
  8. URI file:// prefix se elimina del filepath
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / ".bago" / "tools"))
from findings_engine import Finding, SARIF_VERSION, parse_sarif  # noqa: E402


# ─── Helpers ────────────────────────────────────────────────────────────────

def _sarif(results: list, tool: str = "CodeQL") -> str:
    """Construye un SARIF mínimo serializado."""
    return json.dumps({
        "version": SARIF_VERSION,
        "runs": [
            {"tool": {"driver": {"name": tool}}, "results": results}
        ],
    })


def _loc_result(
    rule: str = "py/sql-injection",
    message: str = "SQL injection",
    level: str = "error",
    filepath: str = "app/db.py",
    line: int = 42,
    col: int = 5,
) -> dict:
    """Construye un SARIF result con physicalLocation."""
    return {
        "ruleId": rule,
        "message": {"text": message},
        "level": level,
        "locations": [
            {
                "physicalLocation": {
                    "artifactLocation": {"uri": filepath},
                    "region": {"startLine": line, "startColumn": col},
                }
            }
        ],
    }


# ─── Tests ──────────────────────────────────────────────────────────────────

def test_empty_sarif_returns_empty_list():
    """SARIF sin resultados → lista vacía."""
    assert parse_sarif(_sarif([])) == []


def test_codeql_finding_with_file_and_line():
    """CodeQL error con file/line → Finding canónico con source='codeql'."""
    sarif = _sarif(
        [_loc_result(
            rule="py/sql-injection",
            message="User-controlled data in SQL query",
            level="error",
            filepath="app/db.py",
            line=42,
            col=5,
        )],
        tool="CodeQL",
    )
    findings = parse_sarif(sarif)

    assert len(findings) == 1
    f = findings[0]
    assert isinstance(f, Finding)
    assert f.source == "codeql"
    assert f.rule == "py/sql-injection"
    assert f.file == "app/db.py"
    assert f.line == 42
    assert f.col == 5
    assert f.severity == "error"
    assert "SQL" in f.message


def test_sarif_without_location_does_not_crash():
    """SARIF result sin locations → finding global (file='', line=0), no crash."""
    result_no_loc = {
        "ruleId": "py/global-issue",
        "message": {"text": "Global analysis result"},
        "level": "warning",
        "locations": [],
    }
    findings = parse_sarif(_sarif([result_no_loc]))

    assert len(findings) == 1
    f = findings[0]
    assert f.file == ""
    assert f.line == 0
    assert f.severity == "warning"
    assert f.rule == "py/global-issue"


@pytest.mark.parametrize("sarif_level,expected_severity", [
    ("error",   "error"),
    ("warning", "warning"),
    ("note",    "info"),
    ("none",    "hint"),
])
def test_severity_mapping(sarif_level: str, expected_severity: str):
    """Severity SARIF se mapea correctamente al modelo Finding."""
    sarif = _sarif([_loc_result(rule=f"rule-{sarif_level}", level=sarif_level, filepath="x.py", line=1)])
    findings = parse_sarif(sarif)

    assert len(findings) == 1, f"Expected 1 finding for level={sarif_level}"
    assert findings[0].severity == expected_severity


def test_stable_canonical_id():
    """El mismo source/file/line/rule produce el mismo ID (estabilidad de deduplicación)."""
    result = _loc_result(rule="py/injection", filepath="app.py", line=10)
    id_first  = parse_sarif(_sarif([result]))[0].id
    id_second = parse_sarif(_sarif([result]))[0].id

    assert id_first == id_second
    assert id_first.startswith("FIND-")


def test_multiple_runs_multiple_tools():
    """Múltiples runs (herramientas distintas) se parsean en findings separados."""
    sarif = json.dumps({
        "version": SARIF_VERSION,
        "runs": [
            {
                "tool": {"driver": {"name": "CodeQL"}},
                "results": [_loc_result(rule="py/injection", filepath="a.py", line=1)],
            },
            {
                "tool": {"driver": {"name": "Bandit"}},
                "results": [_loc_result(rule="B101", filepath="b.py", line=5)],
            },
        ],
    })
    findings = parse_sarif(sarif)

    assert len(findings) == 2
    sources = {f.source for f in findings}
    assert sources == {"codeql", "bandit"}


@pytest.mark.parametrize("bad_input", [
    "not json at all",
    "",
    "{}",
    json.dumps({"version": SARIF_VERSION}),
])
def test_invalid_input_returns_empty(bad_input: str):
    """Entrada inválida o vacía → [] sin crash."""
    assert parse_sarif(bad_input) == []


def test_file_uri_prefix_stripped():
    """URI file:// prefix se elimina del filepath resultante."""
    result = {
        "ruleId": "py/test",
        "message": {"text": "test message"},
        "level": "warning",
        "locations": [
            {
                "physicalLocation": {
                    "artifactLocation": {"uri": "file:///repo/src/main.py"},
                    "region": {"startLine": 10, "startColumn": 1},
                }
            }
        ],
    }
    findings = parse_sarif(_sarif([result]))

    assert len(findings) == 1
    assert findings[0].file == "/repo/src/main.py"


def test_root_prefix_stripped():
    """Si root es proporcionado, se elimina el prefijo del filepath."""
    result = _loc_result(filepath="/workspace/src/app.py", line=7)
    findings = parse_sarif(_sarif([result]), root="/workspace")

    assert len(findings) == 1
    assert findings[0].file == "src/app.py"


def test_missing_rule_id_defaults_gracefully():
    """result sin ruleId → Finding con rule='sarif-rule' (no crash)."""
    result = {
        "message": {"text": "anonymous finding"},
        "level": "note",
        "locations": [_loc_result()["locations"][0]],
    }
    findings = parse_sarif(_sarif([result]))

    assert len(findings) == 1
    assert findings[0].rule == "sarif-rule"
    assert findings[0].severity == "info"

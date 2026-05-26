#!/usr/bin/env python3
"""
findings_engine.py — Motor de hallazgos unificado para BAGO.

Modelo canónico de Finding:
  id, severity, file, line, col, rule, source, message,
  fix_suggestion, autofixable, fix_patch, context_lines

Parsea salida de: flake8, pylint, mypy, pyflakes, bandit, custom-bago,
  checkstyle (Java), dotnet build (C#), rubocop (Ruby), phpcs/phpstan (PHP),
  swiftlint (Swift), ktlint (Kotlin), shellcheck (Shell),
  tflint (Terraform), yamllint (YAML)
Persiste en state/findings/SCAN-{timestamp}.json
"""
from __future__ import annotations
import os
import sys

os.environ.setdefault("PYTHONUTF8", "1")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import json
import sys
from pathlib import Path

# Ensure private modules are importable
_HERE = Path(__file__).parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

import _findings_model as _findings_model

# Re-exports from private modules (backward compatibility)
from _findings_model import (
    Finding, diff_findings,
    SEVERITIES, SARIF_VERSION, BAGO_ROOT,
    _make_id, _read_context,
)
from _findings_parsers import (
    parse_flake8, parse_pylint, parse_mypy, parse_bandit, parse_bago_custom,
    parse_eslint, parse_ast_js, run_js_ast_scan,
    parse_golangci, parse_clippy, parse_checkstyle, parse_dotnet_build,
    parse_rubocop, parse_phpcs, parse_phpstan, parse_swiftlint, parse_ktlint,
    parse_shellcheck, parse_tflint, parse_yamllint, parse_sarif,
    run_linter,
)
from _findings_bago_lint import (
    run_bago_lint, _make_bare_except_patch, _make_utcnow_patch,
)

FINDINGS_DIR = _findings_model.FINDINGS_DIR


class FindingsDB(_findings_model.FindingsDB):
    def __init__(self, scan_id: str | None = None):
        _findings_model.FINDINGS_DIR = FINDINGS_DIR
        super().__init__(scan_id)

    @classmethod
    def load(cls, scan_id: str) -> "FindingsDB":
        _findings_model.FINDINGS_DIR = FINDINGS_DIR
        return super().load(scan_id)

    @classmethod
    def latest(cls) -> "FindingsDB | None":
        _findings_model.FINDINGS_DIR = FINDINGS_DIR
        scans = sorted(FINDINGS_DIR.glob("SCAN-*.json"))
        if not scans:
            return None
        scan_id = scans[-1].stem
        return cls.load(scan_id)


def run_tests():
    print("Ejecutando tests de findings_engine.py...")
    errors = 0
    def ok(n): print(f"  OK: {n}")
    def fail(n, m):
        nonlocal errors; errors += 1; print(f"  FAIL: {n} — {m}")

    # T1: parse_flake8
    sample_flake8 = ".bago/tools/test.py:10:1: E302 expected 2 blank lines, found 1\n.bago/tools/test.py:20:5: W291 trailing whitespace\n"
    fs = parse_flake8(sample_flake8)
    if len(fs) == 2 and fs[0].rule == "E302" and fs[0].severity == "error":
        ok("engine:parse_flake8")
    else:
        fail("engine:parse_flake8", str([(f.rule,f.severity) for f in fs]))

    # T2: parse_mypy
    sample_mypy = '.bago/tools/x.py:5: error: Incompatible return value type  [return-value]\n.bago/tools/x.py:8: note: hint here\n'
    fs2 = parse_mypy(sample_mypy)
    if len(fs2) == 2 and fs2[0].severity == "error" and fs2[1].severity == "info":
        ok("engine:parse_mypy")
    else:
        fail("engine:parse_mypy", str([(f.severity,f.rule) for f in fs2]))

    # T3: Finding autofixable flag
    f = Finding(id="X",severity="warning",file="a.py",line=1,col=0,
                rule="E302",source="flake8",message="test",autofixable=True)
    if f.autofixable:
        ok("engine:autofixable_flag")
    else:
        fail("engine:autofixable_flag", str(f))

    # T4: FindingsDB save/load roundtrip
    import tempfile, shutil
    tmp = Path(tempfile.mkdtemp())
    orig_dir = FindingsDB.__init__.__globals__["FINDINGS_DIR"]
    # Monkeypatch via module-level
    import importlib.util
    spec = importlib.util.spec_from_file_location("fe", Path(__file__))
    m    = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    m.FINDINGS_DIR = tmp
    db = m.FindingsDB("SCAN-TEST")
    db.add([m.Finding(id="F1",severity="error",file="a.py",line=1,col=0,
                      rule="E001",source="flake8",message="test")])
    db.save()
    db2 = m.FindingsDB.load("SCAN-TEST")
    if len(db2.findings) == 1 and db2.findings[0].id == "F1":
        ok("engine:db_roundtrip")
    else:
        fail("engine:db_roundtrip", str(db2.findings))
    shutil.rmtree(tmp)

    # T5: run_bago_lint detects utcnow
    import tempfile as tf
    tmp2 = Path(tf.mkdtemp())
    py_file = tmp2 / "sample.py"
    py_file.write_text("import datetime\nts = datetime.datetime.utcnow()\nprint(ts)\n")  # noqa: BAGO-W001
    findings = run_bago_lint(str(tmp2))
    utcnow_f = [f for f in findings if f.rule == "BAGO-W001"]
    if utcnow_f:
        ok("engine:bago_lint_utcnow")
    else:
        fail("engine:bago_lint_utcnow", str(findings))
    shutil.rmtree(tmp2)

    # T6: _make_utcnow_patch generates valid diff
    patch = _make_utcnow_patch("a.py", 5, "    ts = datetime.datetime.utcnow()")  # noqa: BAGO-W001
    if "BAGO-W001" not in patch and "datetime.timezone.utc" in patch and "@@ -5" in patch:
        ok("engine:utcnow_patch")
    else:
        fail("engine:utcnow_patch", repr(patch[:100]))

    # T7: parse_bandit JSON
    bandit_json = json.dumps({"results":[
        {"filename":"a.py","line_number":3,"test_id":"B101",
         "issue_text":"assert used","issue_severity":"LOW","more_info":""}
    ]})
    fb = parse_bandit(bandit_json)
    if len(fb)==1 and fb[0].source=="bandit" and fb[0].rule=="B101":
        ok("engine:parse_bandit")
    else:
        fail("engine:parse_bandit", str(fb))

    # T8a: bago_lint new rules (BAGO-E001, BAGO-W002, BAGO-W003, BAGO-I002)
    tmp3 = Path(tf.mkdtemp())
    py3 = tmp3 / "mixed.py"
    py3.write_text(
        "import os\n"
        "try:\n"
        "    pass\n"
        "except Exception:  # BAGO-E001\n"
        "    pass\n"
        "result = eval('1+1')  # BAGO-W002\n" # noqa: BAGO-W002
        "os.system('ls')  # BAGO-W003\n"  # noqa: BAGO-W003
        "# TODO: fix this  # BAGO-I002\n"  # noqa: BAGO-I002
    )
    f3 = run_bago_lint(str(tmp3))
    rules3 = {f.rule for f in f3}
    if "BAGO-E001" in rules3 and "BAGO-W002" in rules3 and "BAGO-W003" in rules3 and "BAGO-I002" in rules3:
        ok("engine:bago_lint_new_rules")
    else:
        fail("engine:bago_lint_new_rules", f"found rules: {rules3}")
    # Verify bare_except patch
    patch_e = _make_bare_except_patch("b.py", 4, "    except Exception:")
    if "except Exception:" in patch_e and "@@ -4" in patch_e:
        ok("engine:bare_except_patch")
    else:
        fail("engine:bare_except_patch", repr(patch_e[:80]))
    # T8b: BAGO-W004 hardcoded paths
    tmp4 = Path(tf.mkdtemp())
    py4 = tmp4 / "paths_config.py"
    py4.write_text("DATA_DIR = '/Users/john/data/file.txt'\n") # noqa: BAGO-W004
    f4 = run_bago_lint(str(tmp4))
    rules4 = {f.rule for f in f4}
    if "BAGO-W004" in rules4:
        ok("engine:bago_lint_w004")
    else:
        fail("engine:bago_lint_w004", f"found rules: {rules4}")
    shutil.rmtree(tmp4)
    shutil.rmtree(tmp3)

    # T8c: # noqa suppression
    tmp5 = Path(tf.mkdtemp())
    py5 = tmp5 / "noqa_sample.py"
    py5.write_text(
        "import os\n"
        "os.system('ls')  # noqa: BAGO-W003\n"
        "x = eval('1+1')\n"  # W002 NOT suppressed # noqa: BAGO-W002
    )
    f5 = run_bago_lint(str(tmp5))
    rules5 = {f.rule for f in f5}
    w003_suppressed = "BAGO-W003" not in rules5
    w002_present    = "BAGO-W002" in rules5
    if w003_suppressed and w002_present:
        ok("engine:noqa_suppression")
    else:
        fail("engine:noqa_suppression", f"rules: {rules5}, expected W003 gone + W002 present")
    shutil.rmtree(tmp5)

    # T8d: diff_findings
    f_before = [
        Finding("id1", "warning", "a.py", 10, 0, "BAGO-W001", "bago_lint", "old utcnow"),
        Finding("id2", "error",   "a.py", 20, 0, "BAGO-E001", "bago_lint", "bare except", autofixable=True),
    ]
    f_after = [
        Finding("id1", "warning", "a.py", 10, 0, "BAGO-W001", "bago_lint", "old utcnow"),
        Finding("id3", "warning", "a.py", 30, 0, "BAGO-W004", "bago_lint", "hardcoded path"),
    ]
    diff = diff_findings(f_before, f_after)
    ok_diff = (
        len(diff["new"]) == 1 and diff["new"][0].rule == "BAGO-W004" and
        len(diff["fixed"]) == 1 and diff["fixed"][0].rule == "BAGO-E001" and
        len(diff["persistent"]) == 1 and diff["persistent"][0].rule == "BAGO-W001"
    )
    if ok_diff:
        ok("engine:diff_findings")
    else:
        fail("engine:diff_findings", str(diff))

    total = 12; passed = total - errors
    print(f"\n  {passed}/{total} tests pasaron")
    if errors: raise SystemExit(1)

    # ── Extended tests for new parsers ─────────────────────────────────────
    errors2 = 0
    print("\nTests de parsers multi-lenguaje...")

    # T8: parse_eslint
    eslint_json = json.dumps([{
        "filePath": "/repo/src/app.js",
        "messages": [
            {"ruleId": "no-unused-vars", "severity": 2, "message": "'x' is defined but never used.", "line": 5, "column": 7, "fix": {"range": [0,1],"text":""}},
            {"ruleId": "semi", "severity": 1, "message": "Missing semicolon.", "line": 10, "column": 20},
        ]
    }])
    fe_list = parse_eslint(eslint_json)
    if (len(fe_list) == 2 and fe_list[0].rule == "no-unused-vars"
            and fe_list[0].severity == "error" and fe_list[0].autofixable
            and fe_list[1].severity == "warning"):
        print("  OK: engine:parse_eslint")
    else:
        errors2 += 1; print(f"  FAIL: engine:parse_eslint — {[(f.rule,f.severity,f.autofixable) for f in fe_list]}")

    # T9: parse_golangci
    gc_json = json.dumps({"Issues": [
        {"FromLinter": "errcheck", "Text": "Error return value of x not checked.",
         "Pos": {"Filename": "main.go", "Line": 15, "Column": 3}},
        {"FromLinter": "golint", "Text": "exported function Foo should have comment",
         "Pos": {"Filename": "foo.go", "Line": 7, "Column": 1}},
    ]})
    gc_list = parse_golangci(gc_json)
    if (len(gc_list) == 2 and gc_list[0].source == "golangci"
            and gc_list[0].severity == "error" and gc_list[1].severity == "warning"):
        print("  OK: engine:parse_golangci")
    else:
        errors2 += 1; print(f"  FAIL: engine:parse_golangci — {[(f.rule,f.severity) for f in gc_list]}")

    # T10: parse_clippy
    clippy_line = json.dumps({
        "reason": "compiler-message",
        "message": {
            "level": "warning",
            "code": {"code": "clippy::needless_return"},
            "message": "needless return",
            "rendered": "warning: needless return",
            "spans": [{"file_name": "src/lib.rs", "line_start": 42, "column_start": 5}],
        }
    })
    cl_list = parse_clippy(clippy_line)
    if (cl_list and cl_list[0].rule == "clippy::needless_return"
            and cl_list[0].source == "clippy"):
        print("  OK: engine:parse_clippy")
    else:
        errors2 += 1; print(f"  FAIL: engine:parse_clippy — {cl_list}")

    total2 = 3; passed2 = total2 - errors2
    print(f"\n  {passed2}/{total2} tests de parsers multi-lenguaje pasaron")
    if errors2: raise SystemExit(1)

    # ── Tests for Phase 1-3 parsers ───────────────────────────────────────
    errors3 = 0
    print("\nTests de parsers Fase 1-3...")

    # T11: parse_checkstyle (Java)
    cs_xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<checkstyle version="10.0">'
        '<file name="/repo/src/Main.java">'
        '<error line="5" column="1" severity="error" message="Missing a Javadoc comment." source="com.puppycrawl.tools.checkstyle.checks.javadoc.MissingJavadocMethodCheck"/>'
        '<error line="12" column="3" severity="warning" message="Line is too long (110 > 100)." source="com.puppycrawl.tools.checkstyle.checks.sizes.LineLengthCheck"/>'
        '</file>'
        '</checkstyle>'
    )
    cs_list = parse_checkstyle(cs_xml)
    if (len(cs_list) == 2 and cs_list[0].source == "checkstyle"
            and cs_list[0].severity == "error" and cs_list[1].severity == "warning"
            and cs_list[0].rule == "MissingJavadocMethodCheck"):
        print("  OK: engine:parse_checkstyle")
    else:
        errors3 += 1; print(f"  FAIL: engine:parse_checkstyle — {[(f.rule, f.severity) for f in cs_list]}")

    # T12: parse_dotnet_build (C#)
    dotnet_out = (
        "Build FAILED.\n"
        "  /repo/Src/Program.cs(10,5): error CS0103: The name 'foo' does not exist [App.csproj]\n"
        "  /repo/Src/Program.cs(15,1): warning CS0219: Variable 'x' assigned but never used [App.csproj]\n"
    )
    dn_list = parse_dotnet_build(dotnet_out)
    if (len(dn_list) == 2 and dn_list[0].rule == "CS0103" and dn_list[0].severity == "error"
            and dn_list[1].rule == "CS0219" and dn_list[1].severity == "warning"):
        print("  OK: engine:parse_dotnet_build")
    else:
        errors3 += 1; print(f"  FAIL: engine:parse_dotnet_build — {[(f.rule, f.severity) for f in dn_list]}")

    # T13: parse_rubocop (Ruby)
    rubocop_json = json.dumps({"files": [{"path": "/repo/lib/app.rb", "offenses": [
        {"severity": "convention", "message": "Line is too long. [110/100]",
         "cop_name": "Layout/LineLength", "correctable": False,
         "location": {"line": 5, "column": 101}},
        {"severity": "error", "message": "Use snake_case for method names.",
         "cop_name": "Naming/MethodName", "correctable": True,
         "location": {"line": 12, "column": 7}},
    ]}], "summary": {"offense_count": 2}})
    rb_list = parse_rubocop(rubocop_json)
    if (len(rb_list) == 2 and rb_list[0].source == "rubocop"
            and rb_list[0].severity == "info" and rb_list[1].severity == "error"
            and rb_list[1].autofixable):
        print("  OK: engine:parse_rubocop")
    else:
        errors3 += 1; print(f"  FAIL: engine:parse_rubocop — {[(f.severity, f.autofixable) for f in rb_list]}")

    # T14: parse_phpcs (PHP)
    phpcs_json = json.dumps({"files": {"/repo/src/App.php": {"errors": 1, "warnings": 1, "messages": [
        {"message": "Missing function doc comment", "source": "PEAR.Commenting.FunctionComment.Missing",
         "severity": 5, "type": "ERROR", "line": 8, "column": 1},
        {"message": "Line exceeds 120 characters", "source": "Generic.Files.LineLength.TooLong",
         "severity": 5, "type": "WARNING", "line": 20, "column": 121},
    ]}}})
    pc_list = parse_phpcs(phpcs_json)
    if (len(pc_list) == 2 and pc_list[0].source == "phpcs"
            and pc_list[0].severity == "error" and pc_list[1].severity == "warning"):
        print("  OK: engine:parse_phpcs")
    else:
        errors3 += 1; print(f"  FAIL: engine:parse_phpcs — {[(f.severity, f.rule) for f in pc_list]}")

    # T15: parse_phpstan (PHP)
    phpstan_json = json.dumps({"totals": {"errors": 1, "file_errors": 1},
                               "files": {"/repo/src/Foo.php": {"errors": 1, "messages": [
                                   {"message": "Call to undefined method Bar::baz()", "line": 14, "ignorable": True}
                               ]}}, "errors": []})
    ps_list = parse_phpstan(phpstan_json)
    if (len(ps_list) == 1 and ps_list[0].source == "phpstan"
            and ps_list[0].severity == "error" and ps_list[0].line == 14):
        print("  OK: engine:parse_phpstan")
    else:
        errors3 += 1; print(f"  FAIL: engine:parse_phpstan — {ps_list}")

    # T16: parse_swiftlint (Swift)
    sl_json = json.dumps([
        {"file": "/repo/Sources/App.swift", "line": 7, "character": 5,
         "severity": "Error", "reason": "Force cast is not allowed.", "rule_id": "force_cast", "type": "Force Cast"},
        {"file": "/repo/Sources/App.swift", "line": 22, "character": 1,
         "severity": "Warning", "reason": "Line should be 120 characters or less.", "rule_id": "line_length", "type": "Line Length"},
    ])
    sw_list = parse_swiftlint(sl_json)
    if (len(sw_list) == 2 and sw_list[0].source == "swiftlint"
            and sw_list[0].severity == "error" and sw_list[1].severity == "warning"
            and sw_list[0].rule == "force_cast"):
        print("  OK: engine:parse_swiftlint")
    else:
        errors3 += 1; print(f"  FAIL: engine:parse_swiftlint — {[(f.severity, f.rule) for f in sw_list]}")

    # T17: parse_ktlint (Kotlin)
    kt_json = json.dumps([{"file": "/repo/src/main/kotlin/App.kt", "errors": [
        {"line": 3, "column": 1, "message": "Unnecessary semicolon", "rule": "no-semi"},
        {"line": 10, "column": 5, "message": "Missing newline after '{'", "rule": "brace-style"},
    ]}])
    kt_list = parse_ktlint(kt_json)
    if (len(kt_list) == 2 and kt_list[0].source == "ktlint"
            and kt_list[0].rule == "no-semi" and kt_list[1].rule == "brace-style"):
        print("  OK: engine:parse_ktlint")
    else:
        errors3 += 1; print(f"  FAIL: engine:parse_ktlint — {[(f.rule,) for f in kt_list]}")

    # T18: parse_shellcheck (Shell)
    sc_json = json.dumps([
        {"file": "deploy.sh", "line": 5, "column": 3, "level": "error",
         "code": 2086, "message": "Double quote to prevent globbing and word splitting.", "fix": {"replacements": []}},
        {"file": "deploy.sh", "line": 12, "column": 1, "level": "warning",
         "code": 2034, "message": "foo appears unused.", "fix": None},
    ])
    sh_list = parse_shellcheck(sc_json)
    if (len(sh_list) == 2 and sh_list[0].source == "shellcheck"
            and sh_list[0].severity == "error" and sh_list[0].rule == "SC2086"
            and sh_list[0].autofixable and not sh_list[1].autofixable):
        print("  OK: engine:parse_shellcheck")
    else:
        errors3 += 1; print(f"  FAIL: engine:parse_shellcheck — {[(f.rule, f.severity, f.autofixable) for f in sh_list]}")

    # T19: parse_tflint (Terraform)
    tf_json = json.dumps({"issues": [
        {"rule": {"name": "terraform_deprecated_interpolation", "severity": "warning"},
         "message": "Interpolation-only expressions are deprecated.",
         "range": {"filename": "main.tf", "start": {"line": 8, "column": 3}}},
        {"rule": {"name": "aws_instance_invalid_type", "severity": "error"},
         "message": "\"t1.micro\" is an invalid value as instance_type.",
         "range": {"filename": "main.tf", "start": {"line": 15, "column": 5}}},
    ], "errors": []})
    tfl_list = parse_tflint(tf_json)
    if (len(tfl_list) == 2 and tfl_list[0].source == "tflint"
            and tfl_list[0].severity == "warning" and tfl_list[1].severity == "error"):
        print("  OK: engine:parse_tflint")
    else:
        errors3 += 1; print(f"  FAIL: engine:parse_tflint — {[(f.severity,) for f in tfl_list]}")

    # T20: parse_yamllint (YAML)
    yl_out = (
        "./config.yml:3:3: [warning] wrong indentation: expected 4 but found 2 (indentation)\n"
        "./config.yml:7:1: [error] too many blank lines (2 > 1) (empty-lines)\n"
    )
    yl_list = parse_yamllint(yl_out)
    if (len(yl_list) == 2 and yl_list[0].source == "yamllint"
            and yl_list[0].severity == "warning" and yl_list[0].rule == "indentation"
            and yl_list[1].severity == "error" and yl_list[1].rule == "empty-lines"):
        print("  OK: engine:parse_yamllint")
    else:
        errors3 += 1; print(f"  FAIL: engine:parse_yamllint — {[(f.severity, f.rule) for f in yl_list]}")

    total3 = 10; passed3 = total3 - errors3
    print(f"\n  {passed3}/{total3} tests de parsers Fase 1-3 pasaron")
    if errors3: raise SystemExit(1)

    # ── Tests SARIF/CodeQL ────────────────────────────────────────────────
    errors4 = 0
    print("\nTests de parse_sarif...")

    def _sarif(results, tool="CodeQL"):
        return json.dumps({"version": SARIF_VERSION, "runs": [
            {"tool": {"driver": {"name": tool}}, "results": results}
        ]})

    def _loc_result(rule, msg, level, filepath, line, col=0):
        return {"ruleId": rule, "message": {"text": msg}, "level": level,
                "locations": [{"physicalLocation": {
                    "artifactLocation": {"uri": filepath},
                    "region": {"startLine": line, "startColumn": col},
                }}]}

    # T21: SARIF vacío → []
    if parse_sarif(_sarif([])) == []:
        print("  OK: engine:parse_sarif_empty")
    else:
        errors4 += 1; print("  FAIL: engine:parse_sarif_empty")

    # T22: CodeQL error con file/line → Finding(source="codeql")
    sarif22 = _sarif([_loc_result("py/sql-injection", "SQL injection", "error", "app/db.py", 42, 5)])
    fs22 = parse_sarif(sarif22)
    if (len(fs22) == 1 and fs22[0].source == "codeql" and fs22[0].rule == "py/sql-injection"
            and fs22[0].file == "app/db.py" and fs22[0].line == 42 and fs22[0].severity == "error"):
        print("  OK: engine:parse_sarif_codeql_finding")
    else:
        errors4 += 1; print(f"  FAIL: engine:parse_sarif_codeql_finding — {fs22}")

    # T23: SARIF sin location → finding global, no crash
    sarif23 = _sarif([{"ruleId": "py/global", "message": {"text": "global"}, "level": "warning", "locations": []}])
    fs23 = parse_sarif(sarif23)
    if len(fs23) == 1 and fs23[0].file == "" and fs23[0].line == 0:
        print("  OK: engine:parse_sarif_no_location")
    else:
        errors4 += 1; print(f"  FAIL: engine:parse_sarif_no_location — {fs23}")

    # T24: severity mapping (error→error, warning→warning, note→info, none→hint)
    sev_cases = [("error","error"),("warning","warning"),("note","info"),("none","hint")]
    sev_ok = all(
        parse_sarif(_sarif([_loc_result(f"r-{sl}", "m", sl, "f.py", 1)]))[0].severity == es
        for sl, es in sev_cases
    )
    if sev_ok:
        print("  OK: engine:parse_sarif_severity_mapping")
    else:
        errors4 += 1; print("  FAIL: engine:parse_sarif_severity_mapping")

    # T25: ID estable para misma ubicación/regla
    r25 = _loc_result("py/injection", "msg", "error", "x.py", 10)
    id_a = parse_sarif(_sarif([r25]))[0].id
    id_b = parse_sarif(_sarif([r25]))[0].id
    if id_a == id_b and id_a.startswith("FIND-"):
        print("  OK: engine:parse_sarif_stable_id")
    else:
        errors4 += 1; print(f"  FAIL: engine:parse_sarif_stable_id — {id_a} vs {id_b}")

    # T26: strict=True hace observable un SARIF inválido
    try:
        parse_sarif("{}", strict=True)
        errors4 += 1; print("  FAIL: engine:parse_sarif_strict_invalid")
    except ValueError:
        print("  OK: engine:parse_sarif_strict_invalid")

    total4 = 6; passed4 = total4 - errors4
    print(f"\n  {passed4}/{total4} tests SARIF pasaron")
    if errors4: raise SystemExit(1)


if __name__ == "__main__":
    if "--test" in sys.argv:
        run_tests()
    else:
        print("findings_engine.py — importable module. Usa scan.py o 'bago scan'.")

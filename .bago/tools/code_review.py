#!/usr/bin/env python3
"""code_review.py — BAGO review report with fail-closed scanner status.

Aggregates local BAGO scanners into a merge-oriented report. Scanner execution
errors are explicit blockers: a missing scanner, timeout, invalid JSON, or
invalid SARIF must never be interpreted as zero findings.
"""code_review.py — Herramienta #116: reporte canónico de `bago review`.

Agrega findings de scanners BAGO y, opcionalmente, resultados SARIF/CodeQL
para producir un reporte confiable tanto en local como en CI.

Usage:
    bago review [DIR] [--branch BRANCH] [--format text|md|json]
                [--out FILE] [--min-score N] [--ci] [--test]

Exit codes:
    0  Mergeable review
    1  Score below threshold, blocker, scanner error, or invalid target
    0  Veredicto mergeable, o review-required fuera de CI
    1  Veredicto not-mergeable, error crítico o, en CI, cualquier veredicto
       distinto de mergeable
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

try:
    import findings_engine as fe
except Exception:  # pragma: no cover - SARIF is optional for this runner path
    fe = None

_GRN = "\033[0;32m"
_YEL = "\033[0;33m"
_RED = "\033[0;31m"
_RST = "\033[0m"
_BOLD = "\033[1m"

TOOLS_DIR = Path(__file__).parent

STATUS_OK = "ok"
STATUS_WARN = "warn"
STATUS_FAIL = "fail"
STATUS_ERROR = "error"
STATUS_SKIPPED = "skipped"

PARSE_OK = "ok"
PARSE_NOT_ATTEMPTED = "not_attempted"
PARSE_INVALID_JSON = "invalid_json"
PARSE_INVALID_SARIF = "invalid_sarif"

SCANNER_DEFS = (
    {
        "key": "lint",
        "name": "BAGO Lint",
        "tool": "scan.py",
        "args": ["{directory}", "--quiet", "--format", "json"],
        "parser": "json",
        "critical": True,
        "warn_threshold": 10,
        "fail_threshold": 10,
        "detail_limit": 5,
        "score_multiplier": 1,
        "score_divisor": 1,
        "block_on_statuses": {STATUS_ERROR},
    },
    {
        "key": "complexity",
        "name": "Complexity (high)",
        "tool": "complexity.py",
        "args": ["{directory}", "--min", "11", "--format", "json"],
        "parser": "json",
        "critical": True,
        "warn_threshold": 5,
        "fail_threshold": 5,
        "detail_limit": 5,
        "score_multiplier": 1,
        "score_divisor": 1,
        "block_on_statuses": {STATUS_ERROR},
    },
    {
        "key": "secrets",
        "name": "Secret Scan",
        "tool": "secret_scan.py",
        "args": ["{directory}", "--json"],
        "parser": "json",
        "critical": True,
        "warn_threshold": 1,
        "fail_threshold": 1,
        "detail_limit": 3,
        "score_multiplier": 3,
        "score_divisor": 1,
        "block_on_statuses": {STATUS_FAIL, STATUS_ERROR},
    },
    {
        "key": "dead_code",
        "name": "Dead Code",
        "tool": "dead_code.py",
        "args": ["{directory}", "--json"],
        "parser": "json",
        "critical": True,
        "warn_threshold": 10,
        "fail_threshold": 10,
        "detail_limit": 3,
        "score_multiplier": 1,
        "score_divisor": 2,
        "block_on_statuses": {STATUS_ERROR},
    },
    {
        "key": "duplicates",
        "name": "Duplicate Check",
        "tool": "duplicate_check.py",
        "args": ["{directory}", "--format", "json"],
        "parser": "json",
        "critical": True,
        "warn_threshold": 3,
        "fail_threshold": 3,
        "detail_limit": 3,
        "score_multiplier": 1,
        "score_divisor": 1,
        "block_on_statuses": {STATUS_ERROR},
    },
)


def _run_tool(tool: str, args: list[str], cwd: str, timeout: int = 60) -> tuple[int, str, str]:
    tool_path = TOOLS_DIR / tool
    if not tool_path.exists():
        return -1, "", f"tool not found: {tool}"
    try:
        result = subprocess.run(
            ["python3", str(tool_path)] + args,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=cwd,
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return -2, "", f"timeout after {timeout}s"
    except Exception as exc:  # noqa: BAGO-W002
        return -3, "", str(exc)
    except Exception as exc:  # pragma: no cover - defensive wrapper
        return -3, "", str(exc)


def _git(args: list[str], cwd: str) -> tuple[int, str, str]:
    try:
        result = subprocess.run(
            ["git"] + args,
            capture_output=True,
            text=True,
            timeout=30,
            cwd=cwd,
        )
        return result.returncode, result.stdout.strip(), result.stderr.strip()
    except Exception as exc:  # pragma: no cover - defensive wrapper
        return -1, "", str(exc)


def _scanner_specs(directory: str) -> list[dict]:
    specs: list[dict] = []
    for spec in SCANNER_DEFS:
        specs.append({
            **spec,
            "args": [directory if arg == "{directory}" else arg for arg in spec["args"]],
        })
    return specs


def _summarize_stderr(stderr: str, limit: int = 200) -> str:
    summary = " | ".join(line.strip() for line in stderr.splitlines() if line.strip())
    return summary[:limit]


def _parse_json_output(output: str) -> tuple[int, list[dict]]:
    if not output.strip():
        raise ValueError("empty output")
    data = json.loads(output)
    if isinstance(data, list):
        return len(data), data
    if not isinstance(data, dict):
        raise ValueError("JSON root must be a list or object")

    findings = data.get("findings")
    if findings is None:
        findings = data.get("results")
    if findings is None:
        findings = [] if data.get("total") == 0 else None
    if not isinstance(findings, list):
        raise ValueError("JSON payload missing findings list")

    summary = data.get("summary", {})
    count = data.get("total")
    if not isinstance(count, int) and isinstance(summary, dict):
        count = summary.get("total")
    if not isinstance(count, int):
        count = len(findings)
    return count, findings


def _parse_sarif_output(output: str, root: str) -> tuple[int, list[dict]]:
    if fe is None or not hasattr(fe, "parse_sarif"):
        raise ValueError("SARIF parser unavailable")
    findings = fe.parse_sarif(output, root=root, strict=True)
    return len(findings), [finding.to_dict() for finding in findings]


def _status_from_findings(count: int, spec: dict) -> str:
    if count <= 0:
        return STATUS_OK
    if count >= spec["fail_threshold"]:
        return STATUS_FAIL
    return STATUS_WARN


def _scanner_status_from_review_status(status: str) -> str:
    if status == STATUS_ERROR:
        return STATUS_ERROR
    return "passed" if status == STATUS_OK else "findings"


def _error_section(spec: dict, rc: int, err: str, elapsed_s: float, parse_status: str) -> dict:
    error = f"{spec['tool']}: {err}" if err else f"{spec['tool']}: scanner error"
    return {
        "name": spec["name"],
        "tool": spec["tool"],
        "critical": spec["critical"],
        "findings": 0,
        "status": STATUS_FAIL,
        "scanner_status": STATUS_ERROR,
        "exit_code": rc,
        "error": error,
        "details": [],
        "return_code": rc,
        "stderr_summary": _summarize_stderr(err),
        "elapsed_s": elapsed_s,
        "parse_status": parse_status,
    }


def _run_scanner(spec: dict, cwd: str) -> tuple[dict, int, bool]:
    started = time.time()
    rc, out, err = _run_tool(spec["tool"], spec["args"], cwd)
    elapsed_s = round(time.time() - started, 3)

    if rc in (-1, -2, -3):
        return _error_section(spec, rc, err, elapsed_s, PARSE_NOT_ATTEMPTED), 0, True

    try:
        if spec["parser"] == "sarif":
            findings_count, details = _parse_sarif_output(out, root=cwd)
        else:
            findings_count, details = _parse_json_output(out)
        parse_status = PARSE_OK
    except json.JSONDecodeError as exc:
        return _error_section(spec, rc, f"{err} {exc}".strip(), elapsed_s, PARSE_INVALID_JSON), 0, True
    except ValueError as exc:
        parse_status = PARSE_INVALID_SARIF if spec["parser"] == "sarif" else PARSE_INVALID_JSON
        return _error_section(spec, rc, f"{err} {exc}".strip(), elapsed_s, parse_status), 0, True

    if rc not in (0, 1):
        return _error_section(spec, rc, err or f"unexpected return code: {rc}", elapsed_s, parse_status), 0, True

    status = _status_from_findings(findings_count, spec)
    weighted_findings = (findings_count * spec["score_multiplier"]) // spec["score_divisor"]
    section = {
        "name": spec["name"],
        "tool": spec["tool"],
        "critical": spec["critical"],
        "findings": findings_count,
        "status": status,
        "scanner_status": _scanner_status_from_review_status(status),
        "exit_code": rc,
        "error": "",
        "details": details[:spec["detail_limit"]],
        "return_code": rc,
        "stderr_summary": _summarize_stderr(err),
        "elapsed_s": elapsed_s,
        "parse_status": parse_status,
    }
    blocked = spec["critical"] and status in spec["block_on_statuses"]
    return section, weighted_findings, blocked


def _score_from_findings(findings_count: int, total_lines: int) -> int:
    """Convert finding density into a 0-100 score."""
    if total_lines <= 0:
        return 80
    """Convierte densidad de findings ponderados en puntuación 0-100."""
    if total_lines <= 0:
        return 100 if findings_count == 0 else 80
    density = findings_count / max(1, total_lines / 100)
    if density == 0:
        return 100
    if density < 0.5:
        return 90
    if density < 1:
        return 75
    if density < 2:
        return 60
    if density < 5:
        return 40
    return 20


def _count_py_lines(directory: str) -> int:
    root = Path(directory)
    total = 0
    for file in root.rglob("*.py"):
        if "__pycache__" in str(file):
def _normalize_scope_path(filepath: str, scope_root: Path) -> str:
    if not filepath:
        return ""
    raw = filepath.replace("\\", "/")
    candidate = Path(raw)
    if candidate.is_absolute():
        try:
            return candidate.resolve().relative_to(scope_root.resolve()).as_posix()
        except Exception:
            return candidate.as_posix()
    return candidate.as_posix().lstrip("./")


def _read_text_file(filepath: Path) -> str:
    return filepath.read_text(encoding="utf-8", errors="ignore")


def _iter_scope_files(scope_root: Path, scope_files: list[str] | None = None):
    if scope_files is not None:
        for rel_path in scope_files:
            candidate = (scope_root / rel_path).resolve()
            if candidate.is_file():
                yield candidate
        return

    if scope_root.is_file():
        yield scope_root
        return

    skip_dirs = {".git", "__pycache__", "node_modules", ".venv", "venv", "dist", "build"}
    for candidate in scope_root.rglob("*"):
        if not candidate.is_file():
            continue
        if skip_dirs.intersection(candidate.parts):
            continue
        yield candidate


def _count_lines(scope_root: Path, scope_files: list[str] | None = None) -> int:
    total = 0
    for candidate in _iter_scope_files(scope_root, scope_files):
        try:
            total += len(file.read_text(encoding="utf-8", errors="ignore").splitlines())
        except Exception:  # noqa: BAGO-W002
            pass
            total += len(_read_text_file(candidate).splitlines())
        except Exception:
            continue
    return total


def run_reviews(directory: str, branch: str = "") -> dict:
    """Run all scanners and aggregate their results into one review report."""
    start = time.time()
    sections: dict[str, dict] = {}
    total_findings = 0
    blocker_count = 0

    for spec in _scanner_specs(directory):
        section, weighted_findings, blocked = _run_scanner(spec, directory)
        sections[spec["key"]] = section
        total_findings += weighted_findings
        if blocked:
            blocker_count += 1

    total_lines = _count_py_lines(directory)
    score = _score_from_findings(total_findings, total_lines)
    scanner_errors = {
        key: section["error"]
        for key, section in sections.items()
        if section["scanner_status"] == STATUS_ERROR
    }

    if sections.get("secrets", {}).get("findings", 0) > 0:
        score = min(score, 30)
    if scanner_errors:
        score = 0

    if scanner_errors:
        verdict = "❌ NO MERGE (scanner error)"
    elif blocker_count > 0 or score < 60:
        verdict = "❌ NO MERGE"
    else:
        verdict = "✅ MERGE OK"

    elapsed = round(time.time() - start, 1)
    return {
        "directory": directory,
        "branch": branch,
        "timestamp": int(time.time()),
        "elapsed_s": elapsed,
        "score": score,
        "blocker_count": blocker_count,
        "total_lines": total_lines,
        "total_findings": total_findings,
        "scanner_failures": len(scanner_errors),
        "scanner_errors": scanner_errors,
        "sections": sections,
        "verdict": verdict,
    }


def generate_text(report: dict) -> str:
    score = report["score"]
    color = _GRN if score >= 80 else (_YEL if score >= 60 else _RED)
    return report


def _verdict_icon(verdict: dict[str, Any]) -> str:
    if verdict["id"] == "mergeable":
        return "🟢"
    if verdict["id"] == "review-required":
        return "🟡"
    return "🔴"


def generate_text(report: dict[str, Any]) -> str:
    verdict = report["verdict"]
    score = report["score"]
    color = _GRN if verdict["id"] == "mergeable" else (_YEL if verdict["id"] == "review-required" else _RED)
    scope = report["scope"]
    mode = report["mode"]
    scope_note = (
        f"{scope['file_count']} file(s) changed since {mode['base_ref']}"
        if mode["changed_only"]
        else f"{scope['file_count']} file(s) in scope"
    )
    lines = [
        f"{_BOLD}╔══ BAGO Code Review ══╗{_RST}",
        f"  Score:   {color}{score}/100{_RST}",
        f"  Verdict: {_BOLD}{report['verdict']}{_RST}",
        f"  Lines:   {report['total_lines']}  |  Findings: {report['total_findings']}  |  Blockers: {report['blocker_count']}  |  Scanner failures: {report['scanner_failures']}  |  Time: {report['elapsed_s']}s",
        "",
    ]
    for section in report["sections"].values():
        icon = "✅" if section["status"] == STATUS_OK else ("⚠️" if section["status"] == STATUS_WARN else "❌")
        lines.append(
            f"  {icon} {section['name']:20s}  {section['findings']} finding(s)  "
            f"[scanner={section['scanner_status']}, rc={section['exit_code']}, parse={section['parse_status']}]"
        )
        if section["error"]:
            lines.append(f"      ↳ {section['error']}")
    lines += ["", f"  {_BOLD}{'-' * 40}{_RST}"]
    return "\n".join(lines)


def generate_markdown(report: dict) -> str:
    score = report["score"]
    badge = "🟢" if score >= 80 else ("🟡" if score >= 60 else "🔴")
def generate_markdown(report: dict[str, Any]) -> str:
    verdict = report["verdict"]
    scope = report["scope"]
    mode = report["mode"]
    lines = [
        "# BAGO Code Review",
        "",
        f"**Score:** {badge} {score}/100  |  **Verdict:** {report['verdict']}  |  **Blockers:** {report['blocker_count']}",
        "",
        "| Scanner | Findings | Review status | Scanner status | Parse |",
        "|---------|----------|---------------|----------------|-------|",
    ]
    for section in report["sections"].values():
        icon = "✅" if section["status"] == STATUS_OK else ("⚠️" if section["status"] == STATUS_WARN else "❌")
        scanner_status = section["scanner_status"]
        if section["error"]:
            scanner_status = f"{scanner_status} (`rc={section['exit_code']}`)"
        lines.append(
            f"| {section['name']} | {section['findings']} | {icon} {section['status']} | {scanner_status} | {section['parse_status']} |"
        )
    lines += [
        "",
        f"**Lines analyzed:** {report['total_lines']}  | **Time:** {report['elapsed_s']}s  | **Scanner failures:** {report['scanner_failures']}",
        "",
        "---",
        f"*Generated with `{REVIEW_COMMAND}` · schema v{report['schema_version']}*",
    ]
    for key, error in report["scanner_errors"].items():
        lines.append(f"- `{key}`: {error}")
    lines += ["", "---", "*Generated with `bago review`*"]
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    directory = "./"
    branch = ""
    fmt = "text"
    out_file: str | None = None
    min_score = 60
    ci_mode = False

    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg == "--branch" and i + 1 < len(argv):
            branch = argv[i + 1]
            i += 2
        elif arg == "--format" and i + 1 < len(argv):
            fmt = argv[i + 1]
            i += 2
        elif arg == "--out" and i + 1 < len(argv):
            out_file = argv[i + 1]
            i += 2
        elif arg == "--min-score" and i + 1 < len(argv):
            min_score = int(argv[i + 1])
            i += 2
        elif arg == "--ci":
            ci_mode = True
            i += 1
        elif not arg.startswith("--"):
            directory = arg
            i += 1
        else:
            i += 1

    if not Path(directory).exists():
        print(f"No existe: {directory}", file=sys.stderr)
        return 1

    print(f"Analizando {directory}...", file=sys.stderr)
    report = run_reviews(directory, branch)

    if fmt == "json":
        content = json.dumps(report, indent=2, ensure_ascii=False)
    elif fmt == "md":

def main(argv: list[str]) -> int:
    args = _parse_args(argv)
    if args.test:
        _self_test()
        return 0

    scope_root = Path(args.directory).resolve()
    if not scope_root.exists():
        print(f"No existe: {args.directory}", file=sys.stderr)
        return 1

    min_score = args.min_score
    if args.ci and min_score < CI_MIN_SCORE:
        min_score = CI_MIN_SCORE

    print(f"Analizando {scope_root} con {REVIEW_COMMAND}…", file=sys.stderr)
    report = run_reviews(
        str(scope_root),
        args.branch,
        min_score=min_score,
        changed_only=args.changed_only,
        base_ref=args.base,
        ci=args.ci,
        sarif_paths=args.sarif,
    )

    if args.format == "json":
        content = json.dumps(report, indent=2, sort_keys=True)
    elif args.format == "md":
        content = generate_markdown(report)
    else:
        content = generate_text(report)

    if args.out:
        Path(args.out).write_text(content, encoding="utf-8")
        print(f"Guardado: {args.out}", file=sys.stderr)
    else:
        print(content)

    if report["blocker_count"] > 0:
        return 1
    if report["score"] < min_score:
        return 1
    if ci_mode and report["verdict"] != "✅ MERGE OK":
        return 1
    return 0


def _self_test() -> None:
    import tempfile

    print("Tests de code_review.py...")
    fails: list[str] = []

    def ok(name: str) -> None:
        print(f"  OK: {name}")

        original_run_tool = _run_tool

        def fake_run_tool(tool: str, args: list[str], cwd: str, timeout: int = 60) -> tuple[int, str, str]:
            outputs = {
                "scan.py": (0, json.dumps({"summary": {"total": 0}, "findings": []}), ""),
                "complexity.py": (0, "[]", ""),
                "secret_scan.py": (0, json.dumps({"total": 0, "findings": []}), ""),
                "dead_code.py": (0, json.dumps({"total": 0, "findings": []}), ""),
                "duplicate_check.py": (0, "[]", ""),
            }
            return outputs[tool]

    print("Tests de code_review.py...")
    failures: list[str] = []

    def ok(name: str) -> None:
        print(f"  OK: {name}")

    def fail(name: str, message: str) -> None:
        failures.append(name)
        print(f"  FAIL: {name}: {message}")

    original_run_tool = globals()["_run_tool"]
    original_count_py_lines = globals()["_count_py_lines"]
    try:
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "clean.py").write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")
            globals()["_run_tool"] = lambda tool, args, cwd, timeout=60: (0, "[]", "")
            globals()["_count_py_lines"] = lambda _: 100
            report = run_reviews(tmp)
            if report["score"] == 100 and report["verdict"] == "✅ MERGE OK":
                ok("clean_review_mergeable")
            else:
                fail("clean_review_mergeable", str(report))

            globals()["_run_tool"] = lambda tool, args, cwd, timeout=60: (-1, "", "missing") if tool == "complexity.py" else (0, "[]", "")
            broken = run_reviews(tmp)
            if broken["scanner_failures"] == 1 and broken["score"] == 0:
                ok("scanner_error_blocks")
            else:
                fail("scanner_error_blocks", str(broken))
    finally:
        globals()["_run_tool"] = original_run_tool
        globals()["_count_py_lines"] = original_count_py_lines

    total = 2
    passed = total - len(failures)
    print(f"\n  {passed}/{total} tests pasaron")
    if failures:
        def fake_run_tool(tool: str, args: list[str], cwd: str, timeout: int = 60):  # noqa: ARG001
            findings = {
                "scan.py": [],
                "complexity.py": [],
                "secret_scan.py": [],
                "dead_code.py": [],
                "duplicate_check.py": [],
            }
            return 0, json.dumps(findings.get(tool, [])), ""

        original = globals()["_run_tool"]
        globals()["_run_tool"] = fake_run_tool
        try:
            report = run_reviews(str(root))

            if report["schema_version"] == 1 and report["command"] == REVIEW_COMMAND:
                ok("code_review:schema")
            else:
                fail("code_review:schema", json.dumps(report, ensure_ascii=False)[:120])

            if 0 <= report["score"] <= 100:
                ok("code_review:score_range")
            else:
                fail("code_review:score_range", str(report.get("score")))

            if report["verdict"]["id"] == "mergeable":
                ok("code_review:verdict_model")
            else:
                fail("code_review:verdict_model", str(report.get("verdict")))

            expected = {"lint", "complexity", "secrets", "dead_code", "duplicates"}
            if expected <= set(report["sections"]):
                ok("code_review:sections_complete")
            else:
                fail("code_review:sections_complete", f"missing={expected - set(report['sections'])}")

            md = generate_markdown(report)
            if "BAGO Review" in md and REVIEW_COMMAND in md:
                ok("code_review:markdown_generated")
            else:
                fail("code_review:markdown_generated", md[:80])

            assert _score_from_findings(0, 1000) == 100
            assert _score_from_findings(100, 100) <= 40
            ok("code_review:score_function")

            rc_init, _, err_init = _git(["init"], td)
            _git(["config", "user.email", "test@example.com"], td)
            _git(["config", "user.name", "BAGO Test"], td)
            if rc_init != 0:
                fail("code_review:git_setup", err_init)
            else:
                _git(["add", "clean.py"], td)
                _git(["commit", "-m", "base"], td)
                (root / "changed.py").write_text("print('changed')\n", encoding="utf-8")
                _git(["add", "changed.py"], td)
                _git(["commit", "-m", "add changed"], td)
                (root / "changed.py").write_text("print('changed again')\n", encoding="utf-8")

                def diff_run_tool(tool: str, args: list[str], cwd: str, timeout: int = 60):  # noqa: ARG001
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

                globals()["_run_tool"] = diff_run_tool
                scoped = run_reviews(str(root), changed_only=True, base_ref="HEAD~1")
                if scoped["scope"]["files"] == ["changed.py"] and scoped["total_findings"] == 1:
                    ok("code_review:changed_only")
                else:
                    fail("code_review:changed_only", json.dumps(scoped["scope"]))
        finally:
            globals()["_run_tool"] = original

    total = 7
    passed = total - len(fails)
    print(f"\n  {passed}/{total} tests pasaron")
    if fails:
        raise SystemExit(1)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

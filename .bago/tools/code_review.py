#!/usr/bin/env python3
"""code_review.py — Herramienta #116: reporte canónico de `bago review`.

Agrega findings de scanners BAGO y, opcionalmente, resultados SARIF/CodeQL
para producir un reporte confiable tanto en local como en CI.

Uso:
    bago code-review [DIR] [--branch BRANCH] [--format text|md|html]
                     [--out FILE] [--min-score N] [--ci] [--test]

Exit codes:
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

import findings_engine as fe

_GRN  = "\033[0;32m"
_YEL  = "\033[0;33m"
_RED  = "\033[0;31m"
_RST  = "\033[0m"
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
    specs = []
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
    findings = fe.parse_sarif(output, root=root, strict=True)
    return len(findings), [f.to_dict() for f in findings]


def _status_from_findings(count: int, spec: dict) -> str:
    if count <= 0:
        return STATUS_OK
    if count >= spec["fail_threshold"]:
        return STATUS_FAIL
    return STATUS_WARN


def _error_section(spec: dict, rc: int, err: str, elapsed_s: float, parse_status: str) -> dict:
    return {
        "name": spec["name"],
        "tool": spec["tool"],
        "critical": spec["critical"],
        "findings": 0,
        "status": STATUS_ERROR,
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
            parse_status = PARSE_OK
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
        "details": details[:spec["detail_limit"]],
        "return_code": rc,
        "stderr_summary": _summarize_stderr(err),
        "elapsed_s": elapsed_s,
        "parse_status": parse_status,
    }
    blocked = spec["critical"] and status in spec["block_on_statuses"]
    return section, weighted_findings, blocked


def _score_from_findings(findings_count: int, total_lines: int) -> int:
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
            total += len(_read_text_file(candidate).splitlines())
        except Exception:
            continue
    return total


def run_reviews(directory: str, branch: str = "") -> dict:
    """Ejecuta todos los scanners y agrega resultados."""
    start     = time.time()
    sections  = {}
    total_findings = 0
    blocker_count = 0

    for spec in _scanner_specs(directory):
        section, weighted_findings, blocked = _run_scanner(spec, directory)
        sections[spec["key"]] = section
        total_findings += weighted_findings
        blocker_count += 1 if blocked else 0


    # Penalizar si hay secretos (crítico)
    if sections.get("secrets", {}).get("findings", 0) > 0:
        score = min(score, 30)

    elapsed = round(time.time() - start, 1)
    verdict = "❌ NO MERGE" if blocker_count > 0 or score < 60 else "✅ MERGE OK"

    return {
        "directory":    directory,
        "branch":       branch,
        "timestamp":    int(time.time()),
        "elapsed_s":    elapsed,
        "score":        score,
        "blocker_count": blocker_count,
        "total_lines":  total_lines,
        "total_findings": total_findings,
        "sections":     sections,
        "verdict":      verdict,
    }
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
        f"  Score:   {color}{sc}/100{_RST}",
        f"  Verdict: {_BOLD}{report['verdict']}{_RST}",
        f"  Lines:   {report['total_lines']}  |  Findings: {report['total_findings']}  |  Blockers: {report['blocker_count']}  |  Time: {report['elapsed_s']}s",
        "",
    ]
    for key, sec in report["sections"].items():
        icon = "✅" if sec["status"] == STATUS_OK else ("⚠️" if sec["status"] == STATUS_WARN else ("⏭️" if sec["status"] == STATUS_SKIPPED else "❌"))
        lines.append(
            f"  {icon} {sec['name']:20s} findings={sec['findings']} status={sec['status']} "
            f"rc={sec['return_code']} parse={sec['parse_status']} time={sec['elapsed_s']}s"
        )
    lines += ["", f"  {_BOLD}{'─'*40}{_RST}"]
    return "\n".join(lines)


def generate_markdown(report: dict[str, Any]) -> str:
    verdict = report["verdict"]
    scope = report["scope"]
    mode = report["mode"]
    lines = [
        f"# BAGO Code Review",
        f"",
        f"**Score:** {badge} {sc}/100  |  **Verdict:** {report['verdict']}  |  **Blockers:** {report['blocker_count']}",
        f"",
        f"| Scanner | Findings | Status | RC | Parse |",
        f"|---------|----------|--------|----|-------|",
    ]
    for sec in report["sections"].values():
        icon = "✅" if sec["status"] == STATUS_OK else ("⚠️" if sec["status"] == STATUS_WARN else ("⏭️" if sec["status"] == STATUS_SKIPPED else "❌"))
        lines.append(f"| {sec['name']} | {sec['findings']} | {sec['status']} {icon} | {sec['return_code']} | {sec['parse_status']} |")
    lines += [
        "",
        "---",
        f"*Generated with `{REVIEW_COMMAND}` · schema v{report['schema_version']}*",
    ]
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    directory  = "./"
    branch     = ""
    fmt        = "text"
    out_file   = None
    min_score  = 60
    ci_mode    = False

    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--branch" and i + 1 < len(argv):
            branch = argv[i + 1]; i += 2
        elif a == "--format" and i + 1 < len(argv):
            fmt = argv[i + 1]; i += 2
        elif a == "--out" and i + 1 < len(argv):
            out_file = argv[i + 1]; i += 2
        elif a == "--min-score" and i + 1 < len(argv):
            min_score = int(argv[i + 1]); i += 2
        elif a == "--ci":
            ci_mode = True; i += 1
        elif not a.startswith("--"):
            directory = a; i += 1
        else:
            i += 1


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

        globals()["_run_tool"] = fake_run_tool

        try:
            # T1 — run_reviews retorna score
            report = run_reviews(td)
            if "score" in report and 0 <= report["score"] <= 100:
                ok("code_review:score_range")
            else:
                fail("code_review:score_range", str(report.get("score")))

            # T2 — verdict presente
            if "verdict" in report and ("MERGE" in report["verdict"] or "NO" in report["verdict"]):
                ok("code_review:verdict_present")
            else:
                fail("code_review:verdict_present", str(report.get("verdict")))

            # T3 — sections contiene los 5 scanners
            secs = set(report.get("sections", {}).keys())
            expected = {"lint", "complexity", "secrets", "dead_code", "duplicates"}
            if expected <= secs:
                ok("code_review:sections_complete")
            else:
                fail("code_review:sections_complete", f"missing={expected - secs}")

            # T4 — clean code da score alto
            if report["score"] >= 60 and report["blocker_count"] == 0:
                ok("code_review:clean_code_score")
            else:
                fail("code_review:clean_code_score", f"score={report['score']} blockers={report['blocker_count']}")

            # T5 — markdown generado
            md = generate_markdown(report)
            if "BAGO Code Review" in md and "Blockers" in md:
                ok("code_review:markdown_generated")
            else:
                fail("code_review:markdown_generated", md[:80])

            # T6 — _score_from_findings lógica
            assert _score_from_findings(0, 1000) == 100
            assert _score_from_findings(100, 100) <= 40
            ok("code_review:score_function")
        finally:
            globals()["_run_tool"] = original_run_tool

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

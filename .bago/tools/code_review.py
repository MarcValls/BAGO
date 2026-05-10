#!/usr/bin/env python3
"""code_review.py — Herramienta #116: reporte canónico de `bago review`.

Agrega findings de scanners BAGO y, opcionalmente, resultados SARIF/CodeQL
para producir un reporte confiable tanto en local como en CI.

Uso:
    bago review [TARGET] [--branch BRANCH] [--format text|md|json]
                [--out FILE] [--min-score N] [--changed-only] [--base REF]
                [--ci] [--sarif FILE] [--test]

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

from findings_engine import parse_sarif

_GRN = "\033[0;32m"
_YEL = "\033[0;33m"
_RED = "\033[0;31m"
_DIM = "\033[2m"
_RST = "\033[0m"
_BOLD = "\033[1m"

TOOLS_DIR = Path(__file__).parent
REVIEW_COMMAND = "bago review"
SCHEMA_VERSION = 1
DEFAULT_MIN_SCORE = 60
CI_MIN_SCORE = 80
MAX_SCORE = 100
SEVERITY_WEIGHTS = {"error": 3, "warning": 2, "info": 1, "hint": 1}
TEXT_STATUS = {"ok": "OK", "warn": "WARN", "fail": "FAIL", "skipped": "SKIP"}
CHECK_SPECS = [
    {"id": "lint", "name": "BAGO Lint", "tool": "scan.py", "args": ["--format", "json"]},
    {"id": "complexity", "name": "Complexity (high)", "tool": "complexity.py", "args": ["--min", "11", "--format", "json"]},
    {"id": "secrets", "name": "Secret Scan", "tool": "secret_scan.py", "args": ["--json"]},
    {"id": "dead_code", "name": "Dead Code", "tool": "dead_code.py", "args": ["--json"]},
    {"id": "duplicates", "name": "Duplicate Check", "tool": "duplicate_check.py", "args": ["--format", "json"]},
]


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


def _severity_counts(findings: list[dict[str, Any]]) -> dict[str, int]:
    counts = {"error": 0, "warning": 0, "info": 0, "hint": 0}
    for finding in findings:
        severity = str(finding.get("severity", "warning")).lower()
        if severity not in counts:
            severity = "warning"
        counts[severity] += 1
    return counts


def _weighted_findings(findings: list[dict[str, Any]]) -> int:
    counts = _severity_counts(findings)
    return sum(counts[severity] * SEVERITY_WEIGHTS[severity] for severity in counts)


def _filter_findings_to_scope(
    findings: list[dict[str, Any]],
    scope_root: Path,
    scope_files: list[str] | None,
) -> list[dict[str, Any]]:
    if scope_files is None:
        normalized = []
        for finding in findings:
            item = dict(finding)
            item["file"] = _normalize_scope_path(str(item.get("file", "")), scope_root)
            normalized.append(item)
        return normalized

    allowed = set(scope_files)
    filtered: list[dict[str, Any]] = []
    for finding in findings:
        item = dict(finding)
        rel_path = _normalize_scope_path(str(item.get("file", "")), scope_root)
        item["file"] = rel_path
        if rel_path in allowed:
            filtered.append(item)
    return filtered


def _make_check(
    *,
    check_id: str,
    name: str,
    tool: str,
    findings: list[dict[str, Any]],
    error: str = "",
    detail_limit: int = 5,
) -> dict[str, Any]:
    sev = _severity_counts(findings)
    if sev["error"] > 0:
        status = "fail"
    elif findings:
        status = "warn"
    elif error:
        status = "skipped"
    else:
        status = "ok"

    return {
        "id": check_id,
        "name": name,
        "tool": tool,
        "status": status,
        "findings": len(findings),
        "by_severity": _severity_counts(findings),
        "details": findings[:detail_limit],
        "error": error,
    }


def _collect_tool_check(
    spec: dict[str, Any],
    scope_root: Path,
    scope_files: list[str] | None = None,
) -> dict[str, Any]:
    target = str(scope_root)
    cwd = str(scope_root if scope_root.is_dir() else scope_root.parent)
    rc, out, err = _run_tool(spec["tool"], [target] + spec["args"], cwd)
    if rc < 0:
        return _make_check(
            check_id=spec["id"],
            name=spec["name"],
            tool=spec["tool"],
            findings=[],
            error=err or f"failed to execute {spec['tool']}",
        )
    try:
        raw_payload = json.loads(out) if out.strip() else []
        if isinstance(raw_payload, dict):
            raw_findings = raw_payload.get("findings", [])
        else:
            raw_findings = raw_payload
        if not isinstance(raw_findings, list):
            raise TypeError("JSON output does not contain a findings list")
    except Exception as exc:
        return _make_check(
            check_id=spec["id"],
            name=spec["name"],
            tool=spec["tool"],
            findings=[],
            error=err or f"invalid JSON output: {exc}",
        )

    filtered = _filter_findings_to_scope(raw_findings, scope_root, scope_files)
    return _make_check(
        check_id=spec["id"],
        name=spec["name"],
        tool=spec["tool"],
        findings=filtered,
        error="" if rc == 0 else (err or f"rc={rc}"),
    )


def _collect_sarif_check(
    scope_root: Path,
    sarif_paths: list[str],
    scope_files: list[str] | None = None,
) -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    errors: list[str] = []
    for sarif_path in sarif_paths:
        candidate = Path(sarif_path)
        if not candidate.exists():
            errors.append(f"missing SARIF file: {sarif_path}")
            continue
        try:
            parsed = parse_sarif(candidate.read_text(encoding="utf-8"), root=str(scope_root))
            findings.extend([finding.to_dict() for finding in parsed])
        except Exception as exc:
            errors.append(f"{sarif_path}: {exc}")
    filtered = _filter_findings_to_scope(findings, scope_root, scope_files)
    return _make_check(
        check_id="sarif",
        name="SARIF / CodeQL",
        tool="sarif",
        findings=filtered,
        error="; ".join(errors),
    )


def _resolve_scope_files(scope_root: Path, base_ref: str) -> list[str]:
    git_cwd = str(scope_root if scope_root.is_dir() else scope_root.parent)
    rc_root, repo_root_out, repo_root_err = _git(["rev-parse", "--show-toplevel"], git_cwd)
    if rc_root != 0 or not repo_root_out:
        raise ValueError(repo_root_err or "git root not found")

    repo_root = Path(repo_root_out)
    target_abs = scope_root.resolve()
    if target_abs == repo_root:
        rel_target = "."
    else:
        try:
            rel_target = target_abs.relative_to(repo_root).as_posix()
        except ValueError as exc:
            raise ValueError(f"target fuera del repo git: {target_abs}") from exc

    diff_args = ["diff", "--name-only", "--diff-filter=ACMR", f"{base_ref}...HEAD"]
    if rel_target != ".":
        diff_args.extend(["--", rel_target])
    rc_diff, out_diff, err_diff = _git(diff_args, str(repo_root))
    if rc_diff != 0:
        raise ValueError(err_diff or f"no se pudo calcular diff contra {base_ref}")

    scope_files: list[str] = []
    for line in out_diff.splitlines():
        changed = line.strip()
        if not changed:
            continue
        changed_abs = (repo_root / changed).resolve()
        if scope_root.is_file():
            if changed_abs == target_abs:
                scope_files.append(target_abs.name)
            continue
        try:
            rel_path = changed_abs.relative_to(target_abs).as_posix()
        except ValueError:
            continue
        if rel_path and changed_abs.exists():
            scope_files.append(rel_path)
    return sorted(set(scope_files))


def _detect_branch(scope_root: Path, branch: str) -> str:
    if branch:
        return branch
    git_cwd = str(scope_root if scope_root.is_dir() else scope_root.parent)
    rc, out, _ = _git(["rev-parse", "--abbrev-ref", "HEAD"], git_cwd)
    return out if rc == 0 else ""


def _build_verdict(
    *,
    score: int,
    min_score: int,
    checks: list[dict[str, Any]],
    total_findings: int,
) -> dict[str, Any]:
    blocking = sum(check["by_severity"]["error"] for check in checks)
    warnings = sum(check["by_severity"]["warning"] for check in checks)
    skipped = sum(1 for check in checks if check["status"] == "skipped")

    if blocking > 0 or score < min_score:
        verdict_id = "not-mergeable"
        label = "NOT MERGEABLE"
        mergeable = False
        if blocking > 0:
            reason = f"{blocking} blocking finding(s)"
        else:
            reason = f"score {score} below min-score {min_score}"
    elif warnings > 0 or skipped > 0:
        verdict_id = "review-required"
        label = "REVIEW REQUIRED"
        mergeable = False
        if warnings > 0:
            reason = f"{warnings} warning finding(s)"
        else:
            reason = f"{skipped} check(s) skipped"
    else:
        verdict_id = "mergeable"
        label = "MERGEABLE"
        mergeable = True
        reason = "No blocking findings"

    return {
        "id": verdict_id,
        "label": label,
        "mergeable": mergeable,
        "reason": reason,
        "score": score,
        "min_score": min_score,
        "total_findings": total_findings,
    }


def run_reviews(
    directory: str,
    branch: str = "",
    *,
    min_score: int = DEFAULT_MIN_SCORE,
    changed_only: bool = False,
    base_ref: str = "origin/main",
    ci: bool = False,
    sarif_paths: list[str] | None = None,
) -> dict[str, Any]:
    """Ejecuta checks y construye un reporte estable para `bago review`."""
    start = time.time()
    scope_root = Path(directory).resolve()
    scope_files: list[str] | None = None
    scope_error = ""

    if changed_only:
        try:
            scope_files = _resolve_scope_files(scope_root, base_ref)
        except ValueError as exc:
            scope_error = str(exc)
            scope_files = []

    checks = [_collect_tool_check(spec, scope_root, scope_files) for spec in CHECK_SPECS]
    if sarif_paths:
        checks.append(_collect_sarif_check(scope_root, sarif_paths, scope_files))

    total_lines = _count_lines(scope_root, scope_files)
    total_findings = sum(check["findings"] for check in checks)
    weighted = sum(
        check["by_severity"]["error"] * SEVERITY_WEIGHTS["error"]
        + check["by_severity"]["warning"] * SEVERITY_WEIGHTS["warning"]
        + check["by_severity"]["info"] * SEVERITY_WEIGHTS["info"]
        + check["by_severity"]["hint"] * SEVERITY_WEIGHTS["hint"]
        for check in checks
    )
    score = _score_from_findings(weighted, total_lines)
    verdict = _build_verdict(score=score, min_score=min_score, checks=checks, total_findings=total_findings)

    if scope_error:
        verdict = {
            "id": "not-mergeable",
            "label": "NOT MERGEABLE",
            "mergeable": False,
            "reason": scope_error,
            "score": score,
            "min_score": min_score,
            "total_findings": total_findings,
        }

    elapsed = round(time.time() - start, 1)
    by_severity = {
        "error": sum(check["by_severity"]["error"] for check in checks),
        "warning": sum(check["by_severity"]["warning"] for check in checks),
        "info": sum(check["by_severity"]["info"] for check in checks),
        "hint": sum(check["by_severity"]["hint"] for check in checks),
    }
    check_counts = {
        "ok": sum(1 for check in checks if check["status"] == "ok"),
        "warn": sum(1 for check in checks if check["status"] == "warn"),
        "fail": sum(1 for check in checks if check["status"] == "fail"),
        "skipped": sum(1 for check in checks if check["status"] == "skipped"),
    }
    scope_file_count = len(scope_files) if scope_files is not None else sum(1 for _ in _iter_scope_files(scope_root))

    report = {
        "schema_version": SCHEMA_VERSION,
        "command": REVIEW_COMMAND,
        "target": str(scope_root),
        "branch": _detect_branch(scope_root, branch),
        "timestamp": int(time.time()),
        "elapsed_s": elapsed,
        "score": score,
        "total_lines": total_lines,
        "total_findings": total_findings,
        "mode": {
            "ci": ci,
            "changed_only": changed_only,
            "base_ref": base_ref if changed_only else "",
            "sarif_inputs": sarif_paths or [],
        },
        "scope": {
            "root": str(scope_root),
            "kind": "file" if scope_root.is_file() else "directory",
            "files": scope_files or [],
            "file_count": scope_file_count,
        },
        "summary": {
            "score": score,
            "max_score": MAX_SCORE,
            "min_score": min_score,
            "weighted_findings": weighted,
            "total_findings": total_findings,
            "by_severity": by_severity,
            "checks": check_counts,
        },
        "checks": checks,
        "sections": {check["id"]: check for check in checks},
        "verdict": verdict,
        "verdict_label": verdict["label"],
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
        f"{_BOLD}╔══ BAGO Review ══╗{_RST}",
        f"  Command: {REVIEW_COMMAND}",
        f"  Score:   {color}{score}/{MAX_SCORE}{_RST}",
        f"  Verdict: {_BOLD}{verdict['label']}{_RST} {_DIM}({verdict['reason']}){_RST}",
        f"  Scope:   {scope_note}",
        f"  Lines:   {report['total_lines']}  |  Findings: {report['total_findings']}  |  Time: {report['elapsed_s']}s",
        "",
    ]
    for check in report["checks"]:
        sev = check["by_severity"]
        color = _GRN if check["status"] == "ok" else (_YEL if check["status"] == "warn" else (_RED if check["status"] == "fail" else _DIM))
        lines.append(
            f"  {color}{TEXT_STATUS[check['status']]:4s}{_RST} {check['name']:18s} "
            f"findings={check['findings']} errors={sev['error']} warnings={sev['warning']}"
        )
        if check["error"]:
            lines.append(f"       {_DIM}{check['error']}{_RST}")
    lines += ["", f"  {_BOLD}{'─' * 48}{_RST}"]
    return "\n".join(lines)


def generate_markdown(report: dict[str, Any]) -> str:
    verdict = report["verdict"]
    scope = report["scope"]
    mode = report["mode"]
    lines = [
        "# BAGO Review",
        "",
        f"**Command:** `{REVIEW_COMMAND}`",
        "",
        f"**Verdict:** {_verdict_icon(verdict)} {verdict['label']}  |  **Score:** {report['score']}/{MAX_SCORE}  |  **Threshold:** {report['summary']['min_score']}",
        "",
        f"**Reason:** {verdict['reason']}",
        "",
        f"**Scope:** `{scope['root']}` · {scope['file_count']} file(s)"
        + (f" changed since `{mode['base_ref']}`" if mode["changed_only"] else ""),
        "",
        "| Check | Status | Findings | Errors | Warnings | Notes |",
        "|-------|--------|----------|--------|----------|-------|",
    ]
    for check in report["checks"]:
        note = check["error"] or "—"
        lines.append(
            f"| {check['name']} | {TEXT_STATUS[check['status']]} | {check['findings']} | "
            f"{check['by_severity']['error']} | {check['by_severity']['warning']} | {note} |"
        )

    interesting = []
    for check in report["checks"]:
        for finding in check["details"]:
            interesting.append((finding.get("severity", "warning"), finding, check["name"]))

    if interesting:
        lines += [
            "",
            "## Top findings",
            "",
            "| Severity | Check | Rule | File | Line | Message |",
            "|----------|-------|------|------|------|---------|",
        ]
        for severity, finding, check_name in interesting[:10]:
            lines.append(
                f"| {severity} | {check_name} | {finding.get('rule', '')} | "
                f"{finding.get('file', '')} | {finding.get('line', 0)} | {finding.get('message', '')} |"
            )

    lines += [
        "",
        "---",
        f"*Generated with `{REVIEW_COMMAND}` · schema v{report['schema_version']}*",
    ]
    return "\n".join(lines)


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("directory", nargs="?", default="./")
    parser.add_argument("--branch", default="")
    parser.add_argument("--format", choices=["text", "md", "json"], default="text")
    parser.add_argument("--out", default=None)
    parser.add_argument("--min-score", type=int, default=DEFAULT_MIN_SCORE)
    parser.add_argument("--changed-only", action="store_true")
    parser.add_argument("--base", default="origin/main")
    parser.add_argument("--ci", action="store_true")
    parser.add_argument("--sarif", action="append", default=[])
    parser.add_argument("--test", action="store_true")
    parser.add_argument("-h", "--help", action="help")
    return parser.parse_args(argv)


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

    if args.ci:
        return 0 if report["verdict"]["mergeable"] else 1
    return 0 if report["verdict"]["id"] != "not-mergeable" else 1


def _self_test() -> None:
    import tempfile

    print("Tests de code_review.py...")
    fails: list[str] = []

    def ok(name: str) -> None:
        print(f"  OK: {name}")

    def fail(name: str, message: str) -> None:
        fails.append(name)
        print(f"  FAIL: {name}: {message}")

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "clean.py").write_text(
            '"""Módulo limpio."""\ndef add(a, b):\n    """Suma."""\n    return a + b\n',
            encoding="utf-8",
        )

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

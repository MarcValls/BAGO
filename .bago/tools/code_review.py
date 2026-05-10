#!/usr/bin/env python3
"""code_review.py — canonical `bago review` report generator."""

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
except Exception:  # pragma: no cover
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

REVIEW_COMMAND = "bago review"
DEFAULT_MIN_SCORE = 60
CI_MIN_SCORE = 80

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
        "supports_changed_only": True,
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
        "supports_changed_only": True,
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
        "supports_changed_only": True,
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
        "supports_changed_only": True,
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
        "supports_changed_only": True,
    },
)


class Verdict(dict):
    """Dict-like verdict that remains backward-compatible with string checks."""

    def __eq__(self, other: object) -> bool:  # type: ignore[override]
        if isinstance(other, str):
            return self.get("label") == other
        return dict.__eq__(self, other)



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
    except Exception as exc:  # pragma: no cover
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
    except Exception as exc:  # pragma: no cover
        return -1, "", str(exc)



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



def _severity(value: str | None) -> str:
    raw = (value or "warning").lower().strip()
    if raw in {"error", "critical", "high"}:
        return "error"
    if raw in {"warning", "warn", "medium"}:
        return "warning"
    if raw in {"info", "note", "low"}:
        return "info"
    return "hint"



def _summarize_stderr(stderr: str, limit: int = 200) -> str:
    summary = " | ".join(line.strip() for line in stderr.splitlines() if line.strip())
    return summary[:limit]



def _status_from_findings(count: int, spec: dict[str, Any]) -> str:
    if count <= 0:
        return STATUS_OK
    if count >= int(spec["fail_threshold"]):
        return STATUS_FAIL
    return STATUS_WARN



def _scanner_status_from_review_status(status: str) -> str:
    if status == STATUS_ERROR:
        return STATUS_ERROR
    if status == STATUS_SKIPPED:
        return STATUS_SKIPPED
    return "passed" if status == STATUS_OK else "findings"



def _error_section(spec: dict[str, Any], rc: int, err: str, elapsed_s: float, parse_status: str) -> dict[str, Any]:
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
        "by_severity": {"error": 0, "warning": 0, "info": 0, "hint": 0},
    }



def _parse_json_output(output: str) -> tuple[int, list[dict[str, Any]]]:
    if not output.strip():
        raise ValueError("empty output")
    data = json.loads(output)
    if isinstance(data, list):
        findings = data
    elif isinstance(data, dict):
        findings = data.get("findings")
        if findings is None:
            findings = data.get("results")
        if findings is None:
            findings = [] if data.get("total") == 0 else None
        if not isinstance(findings, list):
            raise ValueError("JSON payload missing findings list")
    else:
        raise ValueError("JSON root must be a list or object")
    return len(findings), findings



def _parse_sarif_output(output: str, root: str, strict: bool) -> tuple[int, list[dict[str, Any]]]:
    if fe is None or not hasattr(fe, "parse_sarif"):
        raise ValueError("SARIF parser unavailable")
    findings = fe.parse_sarif(output, root=root, strict=strict)
    return len(findings), [finding.to_dict() for finding in findings]



def _scanner_specs(directory: str, sarif_paths: list[str] | None) -> list[dict[str, Any]]:
    specs: list[dict[str, Any]] = []
    for spec in SCANNER_DEFS:
        specs.append({
            **spec,
            "args": [directory if arg == "{directory}" else arg for arg in spec["args"]],
        })

    for index, sarif in enumerate(sarif_paths or []):
        specs.append({
            "key": f"codeql_{index + 1}",
            "name": "CodeQL SARIF",
            "tool": "sarif",
            "args": [sarif],
            "parser": "sarif_file",
            "critical": True,
            "warn_threshold": 1,
            "fail_threshold": 1,
            "detail_limit": 20,
            "score_multiplier": 2,
            "score_divisor": 1,
            "block_on_statuses": {STATUS_FAIL, STATUS_ERROR},
            "supports_changed_only": True,
        })
    return specs



def _severity_counts(details: list[dict[str, Any]]) -> dict[str, int]:
    counts = {"error": 0, "warning": 0, "info": 0, "hint": 0}
    for detail in details:
        counts[_severity(detail.get("severity"))] += 1
    return counts



def _normalize_detail(detail: dict[str, Any], scope_root: Path) -> dict[str, Any]:
    normalized = dict(detail)
    normalized["severity"] = _severity(normalized.get("severity"))
    normalized["file"] = _normalize_scope_path(str(normalized.get("file", "")), scope_root)
    return normalized



def _run_scanner(spec: dict[str, Any], cwd: str, ci: bool) -> tuple[dict[str, Any], int, bool]:
    started = time.time()

    if spec["parser"] == "sarif_file":
        sarif_path = Path(spec["args"][0])
        if not sarif_path.is_absolute():
            sarif_path = Path(cwd) / sarif_path
        try:
            raw = sarif_path.read_text(encoding="utf-8")
            findings_count, details = _parse_sarif_output(raw, root=cwd, strict=ci)
            rc = 0
            err = ""
            parse_status = PARSE_OK
        except FileNotFoundError:
            elapsed = round(time.time() - started, 3)
            return _error_section(spec, -1, f"file not found: {sarif_path}", elapsed, PARSE_NOT_ATTEMPTED), 0, True
        except json.JSONDecodeError as exc:
            elapsed = round(time.time() - started, 3)
            return _error_section(spec, 1, str(exc), elapsed, PARSE_INVALID_SARIF), 0, True
        except ValueError as exc:
            elapsed = round(time.time() - started, 3)
            return _error_section(spec, 1, str(exc), elapsed, PARSE_INVALID_SARIF), 0, True
    else:
        rc, out, err = _run_tool(spec["tool"], spec["args"], cwd)
        elapsed = round(time.time() - started, 3)

        if rc in (-1, -2, -3):
            return _error_section(spec, rc, err, elapsed, PARSE_NOT_ATTEMPTED), 0, True

        try:
            findings_count, details = _parse_json_output(out)
            parse_status = PARSE_OK
        except json.JSONDecodeError as exc:
            return _error_section(spec, rc, f"{err} {exc}".strip(), elapsed, PARSE_INVALID_JSON), 0, True
        except ValueError as exc:
            return _error_section(spec, rc, f"{err} {exc}".strip(), elapsed, PARSE_INVALID_JSON), 0, True

        if rc not in (0, 1):
            return _error_section(spec, rc, err or f"unexpected return code: {rc}", elapsed, parse_status), 0, True

    elapsed_s = round(time.time() - started, 3)
    status = _status_from_findings(findings_count, spec)
    weighted_findings = (findings_count * int(spec["score_multiplier"])) // int(spec["score_divisor"])
    section = {
        "name": spec["name"],
        "tool": spec["tool"],
        "critical": spec["critical"],
        "findings": findings_count,
        "status": status,
        "scanner_status": _scanner_status_from_review_status(status),
        "exit_code": rc,
        "error": "",
        "details": details[: int(spec["detail_limit"])],
        "return_code": rc,
        "stderr_summary": _summarize_stderr(err),
        "elapsed_s": elapsed_s,
        "parse_status": parse_status,
    }
    section["by_severity"] = _severity_counts(section["details"])
    blocked = bool(spec["critical"]) and status in set(spec["block_on_statuses"])
    return section, weighted_findings, blocked



def _count_py_lines(directory: str) -> int:
    root = Path(directory)
    total = 0
    for file in root.rglob("*.py"):
        if "__pycache__" in str(file):
            continue
        try:
            total += len(file.read_text(encoding="utf-8", errors="ignore").splitlines())
        except Exception:
            continue
    return total



def _count_lines(scope_root: Path, scope_files: list[str] | None = None) -> int:
    if scope_files is None:
        return _count_py_lines(str(scope_root))

    total = 0
    for rel in scope_files:
        file_path = (scope_root / rel).resolve()
        if not file_path.exists() or not file_path.is_file():
            continue
        try:
            total += len(file_path.read_text(encoding="utf-8", errors="ignore").splitlines())
        except Exception:
            continue
    return total



def _score_from_findings(findings_count: int, total_lines: int) -> int:
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



def _resolve_changed_files(scope_root: Path, base_ref: str) -> list[str]:
    rc, out, _ = _git(["diff", "--name-only", base_ref, "--"], str(scope_root))
    if rc != 0:
        return []
    files: list[str] = []
    for line in out.splitlines():
        rel = _normalize_scope_path(line.strip(), scope_root)
        if rel:
            files.append(rel)
    return sorted(set(files))



def _apply_scope_filter(
    section: dict[str, Any],
    spec: dict[str, Any],
    scope_root: Path,
    scope_files: set[str] | None,
) -> tuple[dict[str, Any], int, bool]:
    if scope_files is None or section["scanner_status"] == STATUS_ERROR:
        findings = int(section["findings"])
        weighted = (findings * int(spec["score_multiplier"])) // int(spec["score_divisor"])
        blocked = bool(spec["critical"]) and section["status"] in set(spec["block_on_statuses"])
        return section, weighted, blocked

    details = [_normalize_detail(item, scope_root) for item in section.get("details", [])]

    if not spec.get("supports_changed_only", True):
        section["status"] = STATUS_SKIPPED
        section["scanner_status"] = STATUS_SKIPPED
        section["details"] = []
        section["findings"] = 0
        section["by_severity"] = {"error": 0, "warning": 0, "info": 0, "hint": 0}
        return section, 0, False

    filtered = [item for item in details if item.get("file") in scope_files]
    count = len(filtered)
    section["details"] = filtered
    section["findings"] = count
    section["status"] = _status_from_findings(count, spec)
    section["scanner_status"] = _scanner_status_from_review_status(section["status"])
    section["by_severity"] = _severity_counts(filtered)

    weighted = (count * int(spec["score_multiplier"])) // int(spec["score_divisor"])
    blocked = bool(spec["critical"]) and section["status"] in set(spec["block_on_statuses"])
    return section, weighted, blocked



def _make_verdict(score: int, min_score: int, blocker_count: int, scanner_errors: dict[str, str], total_findings: int) -> Verdict:
    if scanner_errors:
        label = "❌ NO MERGE (scanner error)"
        verdict_id = "no-merge"
        mergeable = False
        reason = "scanner error"
    elif blocker_count > 0:
        label = "❌ NO MERGE"
        verdict_id = "no-merge"
        mergeable = False
        reason = "blocker findings"
    elif score < min_score:
        label = "❌ NO MERGE"
        verdict_id = "fail"
        mergeable = False
        reason = "score below threshold"
    elif total_findings > 0:
        label = "⚠️ REVIEW REQUIRED"
        verdict_id = "review-required"
        mergeable = False
        reason = f"{total_findings} finding(s)"
    else:
        label = "✅ MERGE OK"
        verdict_id = "mergeable"
        mergeable = True
        reason = "clean"

    return Verdict(
        {
            "id": verdict_id,
            "label": label,
            "mergeable": mergeable,
            "reason": reason,
            "score": score,
            "min_score": min_score,
            "total_findings": total_findings,
        }
    )



def run_reviews(
    directory: str,
    branch: str = "",
    *,
    min_score: int = DEFAULT_MIN_SCORE,
    changed_only: bool = False,
    base_ref: str = "",
    ci: bool = False,
    sarif_paths: list[str] | None = None,
) -> dict[str, Any]:
    start = time.time()
    scope_root = Path(directory).resolve()

    effective_base = base_ref
    if changed_only and not effective_base:
        effective_base = "origin/main" if ci else "HEAD"

    scope_files: list[str] | None = None
    if changed_only:
        scope_files = _resolve_changed_files(scope_root, effective_base)

    sections: dict[str, dict[str, Any]] = {}
    checks: list[dict[str, Any]] = []
    total_findings = 0
    blocker_count = 0

    for spec in _scanner_specs(str(scope_root), sarif_paths):
        section, _, _ = _run_scanner(spec, str(scope_root), ci=ci)
        section, weighted, blocked = _apply_scope_filter(
            section,
            spec,
            scope_root,
            set(scope_files) if scope_files is not None else None,
        )

        sections[spec["key"]] = section
        checks.append(
            {
                "id": spec["key"],
                "name": section["name"],
                "tool": section["tool"],
                "status": section["status"],
                "findings": section["findings"],
                "scanner_status": section["scanner_status"],
                "exit_code": section["exit_code"],
                "return_code": section["return_code"],
                "parse_status": section["parse_status"],
                "stderr_summary": section["stderr_summary"],
                "elapsed_s": section["elapsed_s"],
                "error": section["error"],
                "by_severity": section.get("by_severity", {"error": 0, "warning": 0, "info": 0, "hint": 0}),
                "details": section.get("details", []),
            }
        )
        total_findings += weighted
        blocker_count += 1 if blocked else 0

    total_lines = _count_lines(scope_root, scope_files)
    score = _score_from_findings(total_findings, total_lines)

    scanner_errors = {
        key: section["error"]
        for key, section in sections.items()
        if section.get("scanner_status") == STATUS_ERROR
    }

    if sections.get("secrets", {}).get("findings", 0) > 0:
        score = min(score, 30)
    if scanner_errors:
        score = 0

    verdict = _make_verdict(score, min_score, blocker_count, scanner_errors, total_findings)

    summary_by_severity = {"error": 0, "warning": 0, "info": 0, "hint": 0}
    check_counts = {"ok": 0, "warn": 0, "fail": 0, "skipped": 0}
    for section in sections.values():
        check_counts[section["status"]] = check_counts.get(section["status"], 0) + 1
        for key, value in section.get("by_severity", {}).items():
            summary_by_severity[key] = summary_by_severity.get(key, 0) + int(value)

    elapsed = round(time.time() - start, 3)
    report = {
        "schema_version": 1,
        "command": REVIEW_COMMAND,
        "directory": str(scope_root),
        "branch": branch,
        "timestamp": int(time.time()),
        "elapsed_s": elapsed,
        "score": score,
        "blocker_count": blocker_count,
        "total_lines": total_lines,
        "total_findings": total_findings,
        "scanner_failures": len(scanner_errors),
        "scanner_errors": scanner_errors,
        "mode": {
            "ci": ci,
            "changed_only": changed_only,
            "base_ref": effective_base if changed_only else "",
            "sarif_inputs": list(sarif_paths or []),
        },
        "scope": {
            "root": str(scope_root),
            "kind": "file" if scope_root.is_file() else "directory",
            "files": scope_files or [],
            "file_count": len(scope_files) if scope_files is not None else 1,
        },
        "summary": {
            "score": score,
            "max_score": 100,
            "min_score": min_score,
            "weighted_findings": total_findings,
            "total_findings": total_findings,
            "by_severity": summary_by_severity,
            "checks": check_counts,
        },
        "checks": checks,
        "sections": sections,
        "verdict": verdict,
        "verdict_label": verdict["label"],
    }
    return report



def _verdict_id(verdict: Any) -> str:
    if isinstance(verdict, dict):
        return str(verdict.get("id", ""))
    if isinstance(verdict, str):
        if "MERGE OK" in verdict:
            return "mergeable"
        if "REVIEW REQUIRED" in verdict:
            return "review-required"
        return "no-merge"
    return "no-merge"



def _verdict_label(verdict: Any) -> str:
    if isinstance(verdict, dict):
        return str(verdict.get("label", ""))
    return str(verdict)



def _verdict_icon(verdict: Any) -> str:
    verdict_id = _verdict_id(verdict)
    if verdict_id == "mergeable":
        return "🟢"
    if verdict_id == "review-required":
        return "🟡"
    return "🔴"



def generate_text(report: dict[str, Any]) -> str:
    verdict = report["verdict"]
    verdict_id = _verdict_id(verdict)
    score = report["score"]
    color = _GRN if verdict_id == "mergeable" else (_YEL if verdict_id == "review-required" else _RED)
    blocker_count = report.get("blocker_count", 0)
    scanner_failures = report.get("scanner_failures", 0)

    lines = [
        f"{_BOLD}╔══ BAGO Review ══╗{_RST}",
        f"  Score:   {color}{score}/100{_RST}",
        f"  Verdict: {_BOLD}{_verdict_label(verdict)}{_RST}",
        f"  Lines:   {report['total_lines']}  |  Findings: {report['total_findings']}  |  Blockers: {blocker_count}  |  Scanner failures: {scanner_failures}  |  Time: {report['elapsed_s']}s",
        "",
    ]
    for section in report["sections"].values():
        icon = "✅" if section["status"] == STATUS_OK else ("⚠️" if section["status"] == STATUS_WARN else ("⏭️" if section["status"] == STATUS_SKIPPED else "❌"))
        lines.append(
            f"  {icon} {section['name']:20s}  {section['findings']} finding(s)  [scanner={section['scanner_status']}, rc={section['exit_code']}, parse={section['parse_status']}]"
        )
        if section["error"]:
            lines.append(f"      ↳ {section['error']}")

    lines += ["", f"  {_BOLD}{'-' * 40}{_RST}"]
    return "\n".join(lines)



def generate_markdown(report: dict[str, Any]) -> str:
    verdict = report["verdict"]
    badge = _verdict_icon(verdict)
    blocker_count = report.get("blocker_count", 0)
    schema_version = report.get("schema_version", 1)
    scanner_failures = report.get("scanner_failures", 0)
    scanner_errors = report.get("scanner_errors", {})
    lines = [
        "# BAGO Review",
        "",
        f"**Score:** {badge} {report['score']}/100  |  **Verdict:** {_verdict_label(verdict)}  |  **Blockers:** {blocker_count}",
        "",
        "| Scanner | Findings | Review status | Scanner status | Parse |",
        "|---------|----------|---------------|----------------|-------|",
    ]
    for section in report["sections"].values():
        icon = "✅" if section["status"] == STATUS_OK else ("⚠️" if section["status"] == STATUS_WARN else ("⏭️" if section["status"] == STATUS_SKIPPED else "❌"))
        scanner_status = section["scanner_status"]
        if section["error"]:
            scanner_status = f"{scanner_status} (`rc={section['exit_code']}`)"
        lines.append(
            f"| {section['name']} | {section['findings']} | {icon} {section['status']} | {scanner_status} | {section['parse_status']} |"
        )

    lines += [
        "",
        "**Scanner status legend:** passed/findings/error/skipped",
        f"**Lines analyzed:** {report['total_lines']}  | **Time:** {report['elapsed_s']}s  | **Scanner failures:** {scanner_failures}",
        "",
        "---",
        f"*Generated with `{REVIEW_COMMAND}` · schema v{schema_version}*",
    ]

    if scanner_errors:
        lines.append("")
        lines.append("## Scanner errors")
        for key, error in scanner_errors.items():
            lines.append(f"- `{key}`: {error}")

    return "\n".join(lines)



def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog=REVIEW_COMMAND)
    parser.add_argument("directory", nargs="?", default=".")
    parser.add_argument("--branch", default="")
    parser.add_argument("--format", choices=("text", "md", "json"), default="text")
    parser.add_argument("--out", default="")
    parser.add_argument("--min-score", type=int, default=DEFAULT_MIN_SCORE)
    parser.add_argument("--ci", action="store_true")
    parser.add_argument("--changed-only", action="store_true")
    parser.add_argument("--base", default="")
    parser.add_argument("--sarif", action="append", default=[])
    parser.add_argument("--test", action="store_true")
    return parser.parse_args(argv)



def main(argv: list[str]) -> int:
    args = _parse_args(argv)
    if args.test:
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

    if report.get("blocker_count", 0) > 0:
        return 1
    if report["score"] < min_score:
        return 1
    if args.ci and _verdict_id(report["verdict"]) != "mergeable":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

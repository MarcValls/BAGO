#!/usr/bin/env python3
"""Portable pre-commit readiness checker for BAGO 4.x.

Usage:
    python commit_readiness.py [--root DIR] [--staged|--all|--file FILE] [--strict] [--json] [--test]

Exit codes:
    0 = clean
    1 = findings detected
    2 = runtime error
"""
from __future__ import annotations

import argparse
import ast
import json
import os
import re
import subprocess
import sys
from pathlib import Path

SKIP_DIRS = {
    ".git", "node_modules", "__pycache__", ".venv", "venv", "dist", "build",
    ".pytest_cache", ".mypy_cache",
}
ALLOWLIST_MARKERS = (
    "# noqa: test fixture",
    "# pragma: allowlist secret",
    "# nosec: test fixture",
)
SECRET_PATTERNS = [
    ("CR-E002", re.compile(r'(?i)(password|passwd|pwd)\s*[=:]\s*["\'](?!.*placeholder|.*example|.*changeme|.*your)[^"\']{6,}["\']'), "hardcoded password"),
    ("CR-E002", re.compile(r'(?i)(api[_-]?key|apikey|secret[_-]?key)\s*[=:]\s*["\'][A-Za-z0-9+/\-_]{16,}["\']'), "hardcoded api key"),
    ("CR-E002", re.compile(r'(AKIA|AGPA|AROA|AIDA|ANPA|ANVA|ASIA)[A-Z0-9]{16}'), "aws access key"),
    ("CR-E002", re.compile(r'ghp_[A-Za-z0-9]{36}|github_pat_[A-Za-z0-9_]{82}'), "github token"),
    ("CR-E002", re.compile(r'sk-[A-Za-z0-9]{20,}'), "openai key"),
    ("CR-E002", re.compile(r'-----BEGIN (RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----'), "private key"),
    ("CR-E002", re.compile(r'(?i)mongodb(\+srv)?://[^:]+:[^@]{6,}@'), "connection string with creds"),
    ("CR-E002", re.compile(r'(?i)(token|auth[_-]?token|access[_-]?token)\s*[=:]\s*["\'][A-Za-z0-9+/\-_\.]{20,}["\']'), "hardcoded token"),
]
MERGE_CONFLICT_RE = re.compile(r'^(<{7}|={7}|>{7})( |$)', re.MULTILINE)
TODO_ADDED_RE = re.compile(r'^\+.*\b(TODO|FIXME|HACK|XXX)\b', re.MULTILINE)
PUBLIC_FUNC_RE = re.compile(r'^[A-Za-z_][A-Za-z0-9_]*$')
MAX_FILE_SIZE = 500 * 1024


def resolve_root(root_arg: str) -> Path:
    return Path(root_arg).resolve() if root_arg else Path.cwd().resolve()


def git(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args], cwd=str(cwd), capture_output=True, text=True, check=False
    )


def find_git_root(start: Path) -> Path | None:
    current = start.resolve()
    while True:
        probe = git(["rev-parse", "--show-toplevel"], current)
        if probe.returncode == 0 and probe.stdout.strip():
            return Path(probe.stdout.strip())
        if current.parent == current:
            return None
        current = current.parent


def iter_python_files(root: Path):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        base = Path(dirpath)
        for name in filenames:
            if name.endswith(".py"):
                yield base / name


def get_staged_files(git_root: Path, scan_root: Path) -> list[Path]:
    result = git(["diff", "--cached", "--name-only", "--diff-filter=ACMR"], git_root)
    if result.returncode != 0:
        return []
    files: list[Path] = []
    for raw in result.stdout.splitlines():
        raw = raw.strip()
        if not raw.endswith(".py"):
            continue
        path = (git_root / raw).resolve()
        try:
            path.relative_to(scan_root)
        except ValueError:
            continue
        files.append(path)
    return sorted(set(files))


def get_staged_diff(git_root: Path) -> str:
    result = git(["diff", "--cached"], git_root)
    return result.stdout if result.returncode == 0 else ""


def make_finding(code: str, severity: str, path: Path | str, line: int, message: str, root: Path) -> dict[str, object]:
    if isinstance(path, Path):
        try:
            rel = str(path.relative_to(root))
        except ValueError:
            rel = str(path)
    else:
        rel = path
    return {"code": code, "severity": severity, "path": rel, "line": line, "message": message}


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def check_syntax(path: Path, root: Path) -> list[dict[str, object]]:
    try:
        ast.parse(read_text(path), filename=str(path))
        return []
    except SyntaxError as exc:
        return [make_finding("CR-E001", "error", path, exc.lineno or 0, exc.msg, root)]
    except OSError as exc:
        return [make_finding("CR-E001", "error", path, 0, str(exc), root)]


def check_secrets(path: Path, root: Path) -> list[dict[str, object]]:
    findings: list[dict[str, object]] = []
    try:
        lines = read_text(path).splitlines()
    except OSError:
        return findings
    for line_no, line in enumerate(lines, start=1):
        if any(marker in line for marker in ALLOWLIST_MARKERS):
            continue
        low = line.lower()
        if any(token in low for token in ("example", "placeholder", "changeme", "your_", "your-", "<your", "${", "%(")):
            continue
        for code, pattern, label in SECRET_PATTERNS:
            if pattern.search(line):
                findings.append(make_finding(code, "error", path, line_no, label, root))
                break
    return findings


def check_merge_conflicts(path: Path, root: Path) -> list[dict[str, object]]:
    try:
        if MERGE_CONFLICT_RE.search(read_text(path)):
            return [make_finding("CR-E003", "error", path, 0, "merge conflict markers found", root)]
    except OSError:
        return []
    return []


def check_debug_prints(path: Path, root: Path) -> list[dict[str, object]]:
    findings: list[dict[str, object]] = []
    try:
        for line_no, line in enumerate(read_text(path).splitlines(), start=1):
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            if (stripped.startswith("print(") or stripped.startswith("print (")) and "# keep" not in line.lower():
                findings.append(make_finding("CR-W001", "warning", path, line_no, "debug print found", root))
    except OSError:
        return findings
    return findings


def check_new_todos(diff_text: str) -> list[dict[str, object]]:
    findings: list[dict[str, object]] = []
    for match in TODO_ADDED_RE.finditer(diff_text):
        snippet = match.group(0)[1:].strip()[:120]
        findings.append({
            "code": "CR-W002", "severity": "warning", "path": "git-diff", "line": 0,
            "message": f"new todo in staged diff: {snippet}",
        })
    return findings


def check_file_size(path: Path, root: Path) -> list[dict[str, object]]:
    try:
        size = path.stat().st_size
    except OSError:
        return []
    if size > MAX_FILE_SIZE:
        return [make_finding("CR-W003", "warning", path, 0, f"file too large: {size} bytes", root)]
    return []


def check_docstrings(path: Path, root: Path) -> list[dict[str, object]]:
    findings: list[dict[str, object]] = []
    try:
        tree = ast.parse(read_text(path), filename=str(path))
    except Exception:
        return findings
    if ast.get_docstring(tree) is None:
        findings.append(make_finding("CR-W004", "warning", path, 1, "module docstring missing", root))
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name.startswith("_"):
                continue
            if not PUBLIC_FUNC_RE.match(node.name):
                continue
            if ast.get_docstring(node) is None:
                findings.append(make_finding("CR-W004", "warning", path, node.lineno, f"docstring missing for {node.name}", root))
    return findings


def evaluate(files: list[Path], scan_root: Path, git_root: Path | None, strict: bool) -> dict[str, object]:
    findings: list[dict[str, object]] = []
    for path in files:
        if not path.exists():
            continue
        findings.extend(check_syntax(path, scan_root))
        findings.extend(check_secrets(path, scan_root))
        findings.extend(check_merge_conflicts(path, scan_root))
        findings.extend(check_debug_prints(path, scan_root))
        if strict:
            findings.extend(check_file_size(path, scan_root))
            findings.extend(check_docstrings(path, scan_root))
    if git_root is not None:
        findings.extend(check_new_todos(get_staged_diff(git_root)))
    errors = [item for item in findings if item["severity"] == "error"]
    warnings = [item for item in findings if item["severity"] == "warning"]
    return {
        "root": str(scan_root),
        "mode": "strict" if strict else "standard",
        "files": [str(p) for p in files],
        "total": len(findings),
        "errors": len(errors),
        "warnings": len(warnings),
        "findings": findings,
    }


def print_report(result: dict[str, object]) -> None:
    print(f"Commit readiness root: {result['root']}")
    print(f"Mode: {result['mode']}")
    for item in result["findings"]:
        sev = item["severity"].upper()
        line = f":{item['line']}" if item["line"] else ""
        print(f"[{sev}] {item['code']} {item['path']}{line} - {item['message']}")
    print(
        f"Summary: total={result['total']} errors={result['errors']} warnings={result['warnings']}"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Portable pre-commit readiness checker")
    parser.add_argument("--root", default="", help="Project root to scan")
    parser.add_argument("--all", action="store_true", help="Scan all Python files in root")
    parser.add_argument("--staged", action="store_true", help="Scan staged Python files (default)")
    parser.add_argument("--file", default="", help="Scan one specific file")
    parser.add_argument("--strict", action="store_true", help="Enable extra checks")
    parser.add_argument("--json", dest="as_json", action="store_true", help="JSON output")
    parser.add_argument("--test", action="store_true", help="Run self-tests")
    args = parser.parse_args(argv)

    if args.test:
        return run_self_tests()

    scan_root = resolve_root(args.root)
    if not scan_root.exists() or not scan_root.is_dir():
        print(f"[ERROR] invalid root: {scan_root}", file=sys.stderr)
        return 2

    try:
        git_root = find_git_root(scan_root)
        if args.file:
            file_path = Path(args.file)
            if not file_path.is_absolute():
                file_path = (scan_root / file_path).resolve()
            files = [file_path]
        elif args.all:
            files = list(iter_python_files(scan_root))
        else:
            if git_root is None:
                print("[ERROR] no git repository found for staged mode", file=sys.stderr)
                return 2
            files = get_staged_files(git_root, scan_root)
        result = evaluate(files, scan_root, git_root, args.strict)
    except Exception as exc:  # noqa: BLE001
        print(f"[ERROR] commit_readiness failed: {exc}", file=sys.stderr)
        return 2

    if args.as_json:
        print(json.dumps(result, indent=2, ensure_ascii=True))
    else:
        print_report(result)
    return 1 if result["findings"] else 0


def run_self_tests() -> int:
    import tempfile

    results: list[tuple[str, bool, str]] = []

    def record(name: str, ok: bool, detail: str) -> None:
        results.append((name, ok, detail))

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        sample = root / "sample.py"

        sample.write_text("def bad(:\n    pass\n", encoding="utf-8")
        record("commit:syntax", bool(check_syntax(sample, root)), "syntax flagged")

        sample.write_text('password = "supersecret123"\n', encoding="utf-8")  # nosec: test fixture
        record("commit:secret", bool(check_secrets(sample, root)), "secret flagged")

        sample.write_text("<<<<<<< HEAD\nfoo = 1\n=======\nfoo = 2\n>>>>>>> branch\n", encoding="utf-8")
        record("commit:merge", bool(check_merge_conflicts(sample, root)), "merge flagged")

        sample.write_text("def f():\n    print('debug')\n", encoding="utf-8")
        record("commit:print", bool(check_debug_prints(sample, root)), "print flagged")

        todo_findings = check_new_todos("+ # TODO: fix me\n")
        record("commit:todo", bool(todo_findings), "todo diff flagged")

        sample.write_text("def public():\n    return 1\n", encoding="utf-8")
        strict_findings = check_docstrings(sample, root)
        record("commit:strict_docstring", bool(strict_findings), "docstring flagged")

        sample.write_text('"""module doc"""\n\n\ndef public():\n    """doc"""\n    return 1\n', encoding="utf-8")
        clean = evaluate([sample], root, None, strict=True)
        record("commit:clean", clean["total"] == 0, f"total={clean['total']}")

    passed = sum(1 for _, ok, _ in results if ok)
    for name, ok, detail in results:
        print(f"{'OK' if ok else 'FAIL'}: {name} - {detail}")
    print(f"{passed}/{len(results)} tests passed")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())

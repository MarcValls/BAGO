#!/usr/bin/env python3
"""Portable project doctor for BAGO 4.x.

Usage:
    python doctor.py [--root DIR] [--fix] [--quiet] [--json] [--test]

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
import sys
from pathlib import Path

TEXT_EXTS = {
    ".py", ".json", ".md", ".txt", ".toml", ".ini", ".cfg", ".conf",
    ".yaml", ".yml", ".xml", ".html", ".css", ".js", ".ts", ".tsx",
    ".jsx", ".env", ".ps1", ".cmd", ".bat", ".csv",
}
SKIP_DIRS = {
    ".git", "node_modules", "__pycache__", ".venv", "venv", "dist", "build",
    ".pytest_cache", ".mypy_cache",
}
ORPHAN_SUFFIXES = (".orig", ".rej", ".bak", ".tmp", ".old")
LARGE_FILE_BYTES = 200 * 1024


class Finding(dict):
    pass


def resolve_root(root_arg: str) -> Path:
    return Path(root_arg).resolve() if root_arg else Path.cwd().resolve()


def iter_files(root: Path):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        base = Path(dirpath)
        for name in filenames:
            yield base / name


def is_probably_binary(path: Path) -> bool:
    try:
        raw = path.read_bytes()[:4096]
    except OSError:
        return True
    if b"\x00" in raw:
        return True
    if path.suffix.lower() in TEXT_EXTS or path.name.startswith(".env"):
        return False
    if not raw:
        return False
    bad = sum(1 for b in raw if b < 9 or (13 < b < 32 and b not in (26, 27)))
    return bad > max(8, len(raw) // 8)


def read_utf8(path: Path) -> tuple[str | None, str | None]:
    try:
        data = path.read_bytes()
    except OSError as exc:
        return None, f"read failed: {exc}"
    try:
        return data.decode("utf-8"), None
    except UnicodeDecodeError as exc:
        return None, f"not utf-8 at byte {exc.start}"


def make_finding(code: str, severity: str, path: Path, detail: str, root: Path) -> Finding:
    try:
        rel = str(path.relative_to(root))
    except ValueError:
        rel = str(path)
    return Finding(code=code, severity=severity, path=rel, detail=detail)


def check_encoding(root: Path) -> list[Finding]:
    findings: list[Finding] = []
    for path in iter_files(root):
        if is_probably_binary(path):
            continue
        _, err = read_utf8(path)
        if err:
            findings.append(make_finding("DR-E003", "error", path, err, root))
    return findings


def check_python_syntax(root: Path, bad_utf8: set[str]) -> list[Finding]:
    findings: list[Finding] = []
    for path in iter_files(root):
        if path.suffix.lower() != ".py":
            continue
        rel = str(path.relative_to(root))
        if rel in bad_utf8:
            continue
        text, err = read_utf8(path)
        if err:
            continue
        try:
            ast.parse(text or "", filename=rel)
        except SyntaxError as exc:
            detail = f"line {exc.lineno or 0}: {exc.msg}"
            findings.append(make_finding("DR-E001", "error", path, detail, root))
    return findings


def check_json_files(root: Path, bad_utf8: set[str]) -> list[Finding]:
    findings: list[Finding] = []
    for path in iter_files(root):
        if path.suffix.lower() != ".json":
            continue
        rel = str(path.relative_to(root))
        if rel in bad_utf8:
            continue
        text, err = read_utf8(path)
        if err:
            continue
        try:
            json.loads(text or "")
        except json.JSONDecodeError as exc:
            detail = f"line {exc.lineno} col {exc.colno}: {exc.msg}"
            findings.append(make_finding("DR-E002", "error", path, detail, root))
    return findings


def check_large_files(root: Path) -> list[Finding]:
    findings: list[Finding] = []
    for path in iter_files(root):
        try:
            size = path.stat().st_size
        except OSError:
            continue
        if size > LARGE_FILE_BYTES:
            findings.append(make_finding(
                "DR-W001", "warning", path, f"large file: {size} bytes", root
            ))
    return findings


def check_orphans(root: Path) -> list[Finding]:
    findings: list[Finding] = []
    for path in iter_files(root):
        name_low = path.name.lower()
        if name_low.endswith(ORPHAN_SUFFIXES) or name_low in {"thumbs.db", ".ds_store"}:
            findings.append(make_finding("DR-W002", "warning", path, "orphan-like file", root))
    return findings


def run_checks(root: Path) -> dict[str, object]:
    encoding_findings = check_encoding(root)
    bad_utf8 = {item["path"] for item in encoding_findings}
    findings = []
    findings.extend(check_python_syntax(root, bad_utf8))
    findings.extend(check_json_files(root, bad_utf8))
    findings.extend(encoding_findings)
    findings.extend(check_large_files(root))
    findings.extend(check_orphans(root))
    errors = [item for item in findings if item["severity"] == "error"]
    warnings = [item for item in findings if item["severity"] == "warning"]
    return {
        "root": str(root),
        "total": len(findings),
        "errors": len(errors),
        "warnings": len(warnings),
        "findings": sorted(findings, key=lambda x: (x["severity"], x["path"], x["code"])),
    }


def print_fix_hints(result: dict[str, object]) -> None:
    hints = {
        "DR-E001": "Fix Python syntax errors and re-run the tool.",
        "DR-E002": "Repair invalid JSON with a JSON formatter or parser.",
        "DR-E003": "Re-save the file as UTF-8 without invalid bytes.",
        "DR-W001": "Move large artifacts out of source tree or add them to ignore rules.",
        "DR-W002": "Delete leftover backup or conflict files if they are no longer needed.",
    }
    seen = []
    for item in result["findings"]:
        code = item["code"]
        if code not in seen:
            seen.append(code)
    if not seen:
        return
    print("Fix hints:")
    for code in seen:
        print(f"  {code}: {hints.get(code, 'Review the file and fix the issue.')}")


def print_text(result: dict[str, object], quiet: bool) -> None:
    print(f"Doctor scan root: {result['root']}")
    if not quiet:
        for item in result["findings"]:
            sev = item["severity"].upper()
            print(f"[{sev}] {item['code']} {item['path']} - {item['detail']}")
    else:
        for item in result["findings"]:
            if item["severity"] == "error":
                print(f"[ERROR] {item['code']} {item['path']} - {item['detail']}")
    print(
        f"Summary: total={result['total']} errors={result['errors']} warnings={result['warnings']}"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Portable project doctor")
    parser.add_argument("--root", default="", help="Project root to scan")
    parser.add_argument("--fix", action="store_true", help="Show fix hints")
    parser.add_argument("--quiet", action="store_true", help="Show only errors")
    parser.add_argument("--json", dest="as_json", action="store_true", help="JSON output")
    parser.add_argument("--test", action="store_true", help="Run self-tests")
    args = parser.parse_args(argv)

    if args.test:
        return run_self_tests()

    root = resolve_root(args.root)
    if not root.exists() or not root.is_dir():
        print(f"[ERROR] invalid root: {root}", file=sys.stderr)
        return 2

    try:
        result = run_checks(root)
    except Exception as exc:  # noqa: BLE001
        print(f"[ERROR] doctor failed: {exc}", file=sys.stderr)
        return 2

    if args.as_json:
        print(json.dumps(result, indent=2, ensure_ascii=True))
    else:
        print_text(result, args.quiet)
        if args.fix and result["findings"]:
            print_fix_hints(result)
    return 1 if result["findings"] else 0


def run_self_tests() -> int:
    import io
    import tempfile
    from contextlib import redirect_stdout

    results: list[tuple[str, bool, str]] = []

    def record(name: str, ok: bool, detail: str) -> None:
        results.append((name, ok, detail))

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)

        good = root / "good.py"
        good.write_text("x = 1\n", encoding="utf-8")
        record("doctor:clean_python", not check_python_syntax(root, set()), "valid file")

        bad_py = root / "broken.py"
        bad_py.write_text("def bad(:\n    pass\n", encoding="utf-8")
        record("doctor:syntax_error", bool(check_python_syntax(root, set())), "syntax flagged")

        bad_json = root / "bad.json"
        bad_json.write_text("{bad json}\n", encoding="utf-8")
        record("doctor:json_error", bool(check_json_files(root, set())), "json flagged")

        bad_utf8 = root / "bad.txt"
        bad_utf8.write_bytes(b"abc\xff\n")
        enc = check_encoding(root)
        record("doctor:utf8_error", any(item["path"] == "bad.txt" for item in enc), "encoding flagged")

        big = root / "big.bin"
        big.write_bytes(b"0" * (LARGE_FILE_BYTES + 1))
        large = check_large_files(root)
        record("doctor:large_file", any(item["path"] == "big.bin" for item in large), "large flagged")

        orphan = root / "notes.tmp"
        orphan.write_text("temp\n", encoding="utf-8")
        orphans = check_orphans(root)
        record("doctor:orphan_file", any(item["path"] == "notes.tmp" for item in orphans), "orphan flagged")

        clean_root = root / "clean"
        clean_root.mkdir()
        (clean_root / "ok.py").write_text("value = 2\n", encoding="utf-8")
        out = io.StringIO()
        with redirect_stdout(out):
            rc = main(["--root", str(clean_root), "--json"])
        record("doctor:clean_exit", rc == 0, f"rc={rc}")

    passed = sum(1 for _, ok, _ in results if ok)
    for name, ok, detail in results:
        print(f"{'OK' if ok else 'FAIL'}: {name} - {detail}")
    print(f"{passed}/{len(results)} tests passed")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ast
import json
import shutil
import sys
from pathlib import Path

RULE_R001 = "R001"
RULE_R004 = "R004"
RULE_RGEN = "RGEN"
RULE_RLARGE = "RLARGE"
MAX_LARGE_SIZE = 500 * 1024


def _iter_tool_files(root: Path) -> list[Path]:
    candidates: list[Path] = []
    for candidate in (root / ".bago" / "tools", root / "tools"):
        if candidate.exists():
            candidates.extend(sorted(candidate.glob("*.py")))
    seen: set[Path] = set()
    out: list[Path] = []
    for path in candidates:
        if path not in seen:
            seen.add(path)
            out.append(path)
    return out


def _display(root: Path, path: Path) -> str:
    try:
        return str(path.relative_to(root)).replace("\\", "/")
    except Exception:
        return str(path)


def _json_fix_replacement(text: str) -> str | None:
    stripped = text.strip()
    if not stripped:
        return "{}\n"
    if stripped.startswith("["):
        if stripped in {"[", "[,]"} or stripped[-1] in "[,":
            return "[]\n"
        if stripped.count("[") > stripped.count("]") and not stripped.endswith("]"):
            return "[]\n"
    if stripped.startswith("{"):
        if stripped in {"{", "{,}"} or stripped[-1] in "{,:":
            return "{}\n"
        if stripped.count("{") > stripped.count("}") and not stripped.endswith("}"):
            return "{}\n"
    return None


def scan_missing_test_flag(root: Path) -> list[dict]:
    findings = []
    for path in _iter_tool_files(root):
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if "--test" not in text:
            findings.append({"rule": RULE_R001, "file": _display(root, path), "detail": "Python tool without --test flag", "fixable": False})
    return findings


def scan_invalid_json(root: Path) -> list[dict]:
    findings = []
    for path in root.rglob("*.json"):
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
            json.loads(text)
        except json.JSONDecodeError:
            findings.append({"rule": RULE_R004, "file": _display(root, path), "detail": "Invalid JSON", "fixable": _json_fix_replacement(text) is not None})
        except OSError:
            continue
    return findings


def scan_invalid_python(root: Path) -> list[dict]:
    findings = []
    for path in root.rglob("*.py"):
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
            ast.parse(text, filename=str(path))
        except SyntaxError as exc:
            findings.append({"rule": RULE_RGEN, "file": _display(root, path), "detail": f"Invalid Python syntax at line {exc.lineno}", "fixable": False})
        except OSError:
            continue
    return findings


def scan_large_files(root: Path) -> list[dict]:
    findings = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        try:
            size = path.stat().st_size
        except OSError:
            continue
        if size > MAX_LARGE_SIZE:
            findings.append({"rule": RULE_RLARGE, "file": _display(root, path), "detail": f"Large file: {size} bytes", "fixable": False})
    return findings


def collect_findings(root: Path) -> list[dict]:
    findings = []
    findings.extend(scan_missing_test_flag(root))
    findings.extend(scan_invalid_json(root))
    findings.extend(scan_invalid_python(root))
    findings.extend(scan_large_files(root))
    findings.sort(key=lambda item: (item["rule"], item["file"]))
    return findings


def apply_fixes(root: Path, findings: list[dict], dry_run: bool) -> list[dict]:
    actions = []
    for item in findings:
        if item["rule"] != RULE_R004 or not item.get("fixable"):
            continue
        path = root / Path(item["file"])
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        replacement = _json_fix_replacement(text)
        if replacement is None:
            continue
        actions.append({"file": item["file"], "action": "rewrite_json", "applied": not dry_run})
        if not dry_run:
            path.write_text(replacement, encoding="utf-8")
    return actions


def _print_report(findings: list[dict], actions: list[dict], as_json: bool) -> None:
    if as_json:
        print(json.dumps({"findings": findings, "actions": actions}, indent=2, ensure_ascii=True))
        return
    print("AUTO HEAL")
    print(f"Findings: {len(findings)}")
    for item in findings:
        suffix = " [fixable]" if item.get("fixable") else ""
        print(f"[{item['rule']}] {item['file']} - {item['detail']}{suffix}")
    if actions:
        print("Actions:")
        for action in actions:
            state = "applied" if action["applied"] else "planned"
            print(f"  {action['file']} - {action['action']} ({state})")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Portable immune scanner for project inconsistencies.")
    parser.add_argument("--root", default="", help="Project root to scan. Default: cwd")
    parser.add_argument("--fix", action="store_true", help="Apply safe fixes")
    parser.add_argument("--dry-run", action="store_true", help="Show safe fixes without writing")
    parser.add_argument("--json", action="store_true", help="Emit JSON output")
    parser.add_argument("--test", action="store_true", help="Run self tests")
    return parser


def _selftest_dir() -> Path:
    return Path(__file__).resolve().parent / ".selftest_auto_heal"


def run_self_tests() -> int:
    base = _selftest_dir()
    if base.exists():
        shutil.rmtree(base)
    (base / ".bago" / "tools").mkdir(parents=True)
    try:
        (base / ".bago" / "tools" / "bad_tool.py").write_text("print('x')\n", encoding="utf-8")
        (base / "bad.json").write_text("{", encoding="utf-8")
        (base / "empty.json").write_text("", encoding="utf-8")
        (base / "broken.py").write_text("def x(:\n    pass\n", encoding="utf-8")
        (base / "large.bin").write_bytes(b"0" * (MAX_LARGE_SIZE + 1))

        ok1 = len(scan_missing_test_flag(base)) == 1
        ok2 = _json_fix_replacement("") == "{}\n"
        ok3 = _json_fix_replacement("[") == "[]\n"
        ok4 = len(scan_invalid_python(base)) == 1
        ok5 = len(scan_large_files(base)) == 1
        apply_fixes(base, scan_invalid_json(base), dry_run=False)
        ok6 = json.loads((base / "bad.json").read_text(encoding="utf-8")) == {}

        results = [ok1, ok2, ok3, ok4, ok5, ok6]
        passed = sum(1 for ok in results if ok)
        print(f"{passed}/{len(results)} tests passed")
        return 0 if passed == len(results) else 1
    finally:
        shutil.rmtree(base, ignore_errors=True)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.test:
        return run_self_tests()
    root = Path(args.root or Path.cwd()).resolve()
    if not root.exists() or not root.is_dir():
        print(f"Error: invalid root {root}", file=sys.stderr)
        return 2
    findings = collect_findings(root)
    actions = apply_fixes(root, findings, dry_run=args.dry_run) if args.fix or args.dry_run else []
    _print_report(findings, actions, args.json)
    fixed_files = {action["file"] for action in actions if action["applied"]}
    unresolved = [item for item in findings if not (item["rule"] == RULE_R004 and item["file"] in fixed_files)]
    return 1 if unresolved or (args.dry_run and actions) else 0


if __name__ == "__main__":
    sys.exit(main())

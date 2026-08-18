#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from pathlib import Path

TOKEN_PATTERNS = {
    "github_pat": re.compile(r"(?:ghp_[A-Za-z0-9]{36}|github_pat_[A-Za-z0-9_]{40,})"),
    "openai": re.compile(r"sk-[A-Za-z0-9_-]{20,}"),
    "anthropic": re.compile(r"sk-ant-[A-Za-z0-9_-]{16,}"),
    "telegram": re.compile(r"[0-9]{8,10}:[A-Za-z0-9_-]{30,}"),
    "bearer": re.compile(r"Bearer\s+[A-Za-z0-9._-]{16,}", re.IGNORECASE),
    "api_key": re.compile(r"(?i)(?:api[_-]?key|apikey)\s*[:=]\s*(?:['\"][A-Za-z0-9._-]{16,}['\"]|[A-Za-z0-9._-]{24,})"),
}
EXCLUDE_DIRS = {".git", "node_modules", "dist", "build", ".venv", "venv", "__pycache__", ".bago", ".vercel"}
EXCLUDE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".ico", ".zip", ".7z", ".exe", ".dll", ".bin", ".pyc", ".mp3", ".mp4"}
MAX_SCAN_SIZE = 500_000
SEVERITY_DEDUCTIONS = {"CRITICAL": 30, "HIGH": 15, "MEDIUM": 8, "LOW": 3}


def _display(root: Path, path: Path) -> str:
    try:
        return str(path.relative_to(root)).replace("\\", "/")
    except Exception:
        return str(path)


def _iter_files(root: Path):
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(root)
        if any(part in EXCLUDE_DIRS for part in rel.parts):
            continue
        if path.suffix.lower() in EXCLUDE_EXTS:
            continue
        try:
            if path.stat().st_size > MAX_SCAN_SIZE:
                continue
        except OSError:
            continue
        yield path


def _should_skip_line(line: str) -> bool:
    low = line.lower()
    markers = ("example", "fixture", "dummy", "placeholder", "xxxx", "your_", "<token", "<api", "test")
    if any(marker in low for marker in markers):
        return True
    if "read-inputordefault" in low or "$env:" in low or "process.env" in low or "os.environ" in low:
        return True
    return False


def scan_tokens(root: Path) -> list[dict]:
    findings = []
    for path in _iter_files(root):
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for lineno, line in enumerate(text.splitlines(), start=1):
            if _should_skip_line(line):
                continue
            for name, pattern in TOKEN_PATTERNS.items():
                if not pattern.search(line):
                    continue
                findings.append({
                    "severity": "CRITICAL",
                    "kind": "token_exposed",
                    "token_type": name,
                    "file": _display(root, path),
                    "line": lineno,
                    "excerpt": line.strip()[:160],
                })
    return findings


def _permission_flags(mode: int) -> list[str]:
    flags = []
    if mode & 0o111:
        flags.append("executable")
    if mode & 0o002:
        flags.append("world_writable")
    return flags


def _env_files(root: Path) -> list[Path]:
    return [path for path in root.rglob(".env*") if path.is_file() and not any(part in EXCLUDE_DIRS for part in path.relative_to(root).parts)]


def scan_env_permissions(root: Path) -> list[dict]:
    findings = []
    for path in _env_files(root):
        try:
            flags = _permission_flags(path.stat().st_mode)
        except OSError:
            continue
        for flag in flags:
            findings.append({
                "severity": "HIGH",
                "kind": "env_permissions",
                "token_type": "",
                "file": _display(root, path),
                "line": 0,
                "excerpt": flag,
            })
    return findings


def _gitignore_text(root: Path) -> str:
    gitignore = root / ".gitignore"
    if not gitignore.exists():
        return ""
    try:
        return gitignore.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _env_is_ignored(rel: str, gitignore_text: str) -> bool:
    if not gitignore_text:
        return False
    rel = rel.replace("\\", "/")
    name = Path(rel).name
    for raw in gitignore_text.splitlines():
        entry = raw.strip()
        if not entry or entry.startswith("#"):
            continue
        if entry in {".env", ".env.*", ".env*", name, rel, f"/{rel}"}:
            return True
    return False


def scan_env_gitignore(root: Path) -> list[dict]:
    findings = []
    gitignore_text = _gitignore_text(root)
    for path in _env_files(root):
        rel = _display(root, path)
        if not _env_is_ignored(rel, gitignore_text):
            findings.append({
                "severity": "MEDIUM",
                "kind": "env_gitignore",
                "token_type": "",
                "file": rel,
                "line": 0,
                "excerpt": ".env file not ignored by git",
            })
    return findings


def compute_score(findings: list[dict]) -> int:
    score = 100
    for item in findings:
        score -= SEVERITY_DEDUCTIONS.get(item.get("severity", ""), 0)
    return max(0, min(100, score))


def remediation_steps(findings: list[dict]) -> list[str]:
    steps = []
    for item in findings:
        if item["kind"] == "token_exposed":
            steps.append(f"Rotate {item['token_type']} secret found in {item['file']} line {item['line']}")
        elif item["kind"] == "env_permissions":
            steps.append(f"Remove dangerous permissions from {item['file']} ({item['excerpt']})")
        elif item["kind"] == "env_gitignore":
            steps.append(f"Add {item['file']} or .env* to .gitignore")
    out = []
    seen = set()
    for step in steps:
        if step not in seen:
            seen.add(step)
            out.append(step)
    return out


def scan(root: Path) -> dict:
    findings = []
    findings.extend(scan_tokens(root))
    findings.extend(scan_env_permissions(root))
    findings.extend(scan_env_gitignore(root))
    findings.sort(key=lambda item: (item["severity"], item["file"], item["line"], item["kind"]))
    return {"root": str(root), "findings": findings, "score": compute_score(findings)}


def _print_report(report: dict, show_fix: bool, as_json: bool) -> None:
    payload = dict(report)
    if show_fix:
        payload["remediation"] = remediation_steps(report["findings"])
    if as_json:
        print(json.dumps(payload, indent=2, ensure_ascii=True))
        return
    print("BAGO SECURITY AUDIT")
    print(f"Root: {report['root']}")
    print(f"Score: {report['score']}/100")
    print(f"Findings: {len(report['findings'])}")
    for item in report["findings"]:
        location = f"{item['file']}:{item['line']}" if item["line"] else item["file"]
        extra = f" [{item['token_type']}]" if item.get("token_type") else ""
        print(f"[{item['severity']}] {item['kind']}{extra} {location} - {item['excerpt']}")
    if show_fix:
        print("Remediation:")
        for step in payload["remediation"]:
            print(f"  - {step}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Portable security audit for tokens, env permissions and unsafe config.")
    parser.add_argument("--root", default="", help="Project root to scan. Default: cwd")
    parser.add_argument("--json", action="store_true", help="Emit JSON output")
    parser.add_argument("--fix", action="store_true", help="Show remediation instructions")
    parser.add_argument("--test", action="store_true", help="Run self tests")
    return parser


def _selftest_dir() -> Path:
    return Path(__file__).resolve().parent / ".selftest_bago_security_audit"


def run_self_tests() -> int:
    base = _selftest_dir()
    if base.exists():
        shutil.rmtree(base)
    base.mkdir(parents=True)
    try:
        token_line = "github_pat_" + "abcdefghijklmnopqrstuvwxyz_" + "ABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890\n"
        (base / "token.txt").write_text(token_line, encoding="utf-8")
        (base / ".env").write_text("OPENAI_KEY=test\n", encoding="utf-8")
        (base / "example.txt").write_text("example github_pat_placeholder_token\n", encoding="utf-8")
        (base / "prompt.ps1").write_text('$cfg.api_key = Read-InputOrDefault -Default $env:OPENAI_API_KEY\n', encoding="utf-8")

        ok1 = any(item["token_type"] == "github_pat" for item in scan_tokens(base))
        ok2 = _permission_flags(0o777) == ["executable", "world_writable"]
        ok3 = any(item["kind"] == "env_gitignore" for item in scan_env_gitignore(base))
        (base / ".gitignore").write_text(".env\n", encoding="utf-8")
        ok4 = not scan_env_gitignore(base)
        ok5 = compute_score([{"severity": "CRITICAL"}] * 10) == 0
        ok6 = not any(item["file"] == "example.txt" for item in scan_tokens(base))
        ok7 = not any(item["file"] == "prompt.ps1" for item in scan_tokens(base))

        results = [ok1, ok2, ok3, ok4, ok5, ok6, ok7]
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
    report = scan(root)
    _print_report(report, args.fix, args.json)
    return 1 if report["findings"] else 0


if __name__ == "__main__":
    sys.exit(main())

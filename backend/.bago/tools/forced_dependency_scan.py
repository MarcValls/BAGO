#!/usr/bin/env python3
"""Detecta dependencias forzadas, pins raros y patrones de instalacion directa."""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

EXCLUDE_DIRS = {".git", "node_modules", "dist", "build", ".venv", "venv", "__pycache__", "site-dist"}
TARGET_EXTS = {".py", ".ps1", ".cmd", ".cjs", ".js", ".json", ".toml", ".cfg", ".yml", ".yaml", ".txt"}

FORCED_PATTERNS: list[tuple[str, str, str]] = [
    ("FDEP-001", "error", r"\bpip\s+install\b.*"),
    ("FDEP-001", "error", r"\bpython\s+-m\s+pip\s+install\b.*"),
    ("FDEP-001", "error", r"\bnpm\s+install\b.*"),
    ("FDEP-001", "error", r"\bpnpm\s+add\b.*"),
    ("FDEP-001", "error", r"\byarn\s+add\b.*"),
    ("FDEP-001", "error", r"\bwinget\s+install\b.*"),
    ("FDEP-001", "error", r"\bInstall-Module\b.*"),
    ("FDEP-001", "error", r"\bInvoke-WebRequest\b.*\biex\b"),
    ("FDEP-001", "error", r"\biex\b.*Invoke-WebRequest"),
    ("FDEP-001", "error", r"\bcurl\b.*\|\s*(bash|sh|iex)"),
    ("FDEP-002", "warning", r"sys\.path\.insert\("),
    ("FDEP-002", "warning", r"site\.addsitedir\("),
    ("FDEP-003", "warning", r'"overrides"\s*:'),
    ("FDEP-003", "warning", r'"resolutions"\s*:'),
    ("FDEP-003", "warning", r'"file:[^"]+"'),
    ("FDEP-003", "warning", r'"link:[^"]+"'),
    ("FDEP-003", "warning", r'"workspace:[^"]+"'),
]


def _resolve_root(root_arg: str) -> Path:
    return Path(root_arg).resolve() if root_arg else Path.cwd().resolve()


def _should_skip(path: Path) -> bool:
    if any(part in EXCLUDE_DIRS for part in path.parts):
        return True
    return path.name == "forced_dependency_scan.py"


def _display(root: Path, path: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return str(path)


def _is_command_definition(line: str) -> bool:
    low = line.lower()
    return any(token in low for token in (
        "installcommand",
        "wingetid",
        "cmd:pscommand",
        "label:",
        "desc:",
    ))


def _is_workflow_line(path: Path, line: str) -> bool:
    rel = path.as_posix().lower()
    return "/.github/workflows/" in rel and line.strip().lower().startswith("run:")


def _is_routine_repo_path_mutation(line: str) -> bool:
    low = line.lower()
    routine_tokens = (
        "path(__file__)",
        "path(__file__).",
        "__file__",
        "parents[",
        "bago_root",
        "repo_root",
        "root_dir",
        "project_root",
        "runtime_root",
        "repo",
        "core_dir",
        "core_path",
        "_path_s",
        "_this_dir",
        "script_dir",
        "tools_dir",
        "path.cwd()",
        "root /",
        "base /",
        "bago_dir /",
        "str(root",
        "str(repo",
        "str(base",
        "str(core",
        "str(tools",
        "str(bago",
    )
    return "sys.path.insert(" in low and any(token in low for token in routine_tokens)


def _classify_forced_command(path: Path, line: str) -> tuple[str, str, str] | None:
    low = line.lower()
    if "invoke-webrequest" in low:
        if "iex" in low or "invoke-expression" in low:
            return "FDEP-001", "error", "ejecucion remota directa"
        if "-outfile" in low:
            return "FDEP-001", "warning", "descarga a fichero; verificar checksum/firma"
    if "curl" in low and re.search(r"\|\s*(bash|sh|iex)", low):
        return "FDEP-001", "error", "pipe remoto a shell"
    if any(tok in low for tok in ("pip install", "python -m pip install", "npm install", "pnpm add", "yarn add", "winget install", "install-module")):
        if _is_workflow_line(path, line):
            return "FDEP-001", "warning", "instalacion declarada en CI"
        return "FDEP-001", "error", "instalacion directa"
    if "site.addsitedir(" in low:
        return "FDEP-002", "warning", "mutacion site.addsitedir"
    if "sys.path.insert(" in low:
        if _is_routine_repo_path_mutation(line):
            return None
        return "FDEP-002", "warning", "mutacion sys.path"
    return None


def _iter_targets(root: Path) -> list[Path]:
    files: list[Path] = []
    for path in sorted(root.rglob("*")):
        if path.is_dir() or _should_skip(path):
            continue
        if path.suffix.lower() in TARGET_EXTS or path.name in {"package.json", "package-lock.json", "pyproject.toml", "requirements.txt", "requirements-dev.txt"}:
            files.append(path)
    return files


def _scan_text(path: Path) -> list[dict[str, object]]:
    findings: list[dict[str, object]] = []
    manifest_like = (
        path.name == "package.json"
        or path.name == "package-lock.json"
        or path.name == "pyproject.toml"
        or path.name.startswith("requirements")
        or path.suffix in {".txt", ".toml", ".cfg", ".json"}
    )
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception as exc:  # noqa: BLE001
        return [{
            "rule": "FDEP-000",
            "severity": "warning",
            "file": str(path),
            "line": 0,
            "message": f"No se pudo leer: {exc}",
        }]

    lower = text.lower()
    for idx, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line:
            continue
        if _is_command_definition(line):
            continue
        if _is_routine_repo_path_mutation(line):
            continue
        low = line.lower()
        classified = _classify_forced_command(path, line)
        if classified:
            rule, severity, reason = classified
            findings.append({
                "rule": rule,
                "severity": severity,
                "file": _display(root_global, path) if "root_global" in globals() else str(path),
                "line": idx,
                "message": f"{reason}: {line[:220]}",
            })
            continue
        for rule, severity, pattern in FORCED_PATTERNS:
            if not manifest_like and rule in {"FDEP-003", "FDEP-004"}:
                continue
            if re.search(pattern, line, re.IGNORECASE):
                findings.append({
                    "rule": rule,
                    "severity": severity,
                    "file": _display(root_global, path) if "root_global" in globals() else str(path),
                    "line": idx,
                    "message": line[:220],
                })
                break

    if path.name == "package.json":
        try:
            data = json.loads(text)
        except Exception:
            data = {}
        if isinstance(data, dict):
            for field in ("overrides", "resolutions"):
                if field in data:
                    findings.append({
                        "rule": "FDEP-003",
                        "severity": "warning",
                        "file": _display(root_global, path) if "root_global" in globals() else str(path),
                        "line": 1,
                        "message": f"{field} presente en package.json",
                    })
            for dep_group in ("dependencies", "devDependencies", "optionalDependencies", "peerDependencies"):
                deps = data.get(dep_group, {})
                if isinstance(deps, dict):
                    for dep, version in deps.items():
                        if isinstance(version, str) and (version.startswith("file:") or version.startswith("link:") or version.startswith("workspace:")):
                            findings.append({
                                "rule": "FDEP-003",
                                "severity": "warning",
                                "file": _display(root_global, path) if "root_global" in globals() else str(path),
                                "line": 1,
                                "message": f"{dep_group}.{dep} usa {version}",
                            })
                        if isinstance(version, str) and version.startswith("^") is False and version.startswith("~") is False and version not in {"*", "latest"} and re.fullmatch(r"\d+\.\d+\.\d+", version):
                            findings.append({
                                "rule": "FDEP-004",
                                "severity": "warning",
                                "file": _display(root_global, path) if "root_global" in globals() else str(path),
                                "line": 1,
                                "message": f"{dep_group}.{dep} fijada a {version}",
                            })

    if manifest_like and (path.name.startswith("requirements") or path.suffix == ".txt"):
        for idx, raw in enumerate(text.splitlines(), 1):
            stripped = raw.strip()
            if not stripped or stripped.startswith("#") or stripped.startswith("-"):
                continue
            if "==" in stripped and "===" not in stripped:
                findings.append({
                    "rule": "FDEP-004",
                    "severity": "warning",
                    "file": _display(root_global, path) if "root_global" in globals() else str(path),
                    "line": idx,
                    "message": f"Pin exacto en requirements: {stripped}",
                })
            elif ">=" in stripped and "<" not in stripped:
                findings.append({
                    "rule": "FDEP-004",
                    "severity": "warning",
                    "file": _display(root_global, path) if "root_global" in globals() else str(path),
                    "line": idx,
                    "message": f"Rango abierto en requirements: {stripped}",
                })
    elif manifest_like and path.name in {"pyproject.toml", "package-lock.json", "package.json"}:
        for idx, raw in enumerate(text.splitlines(), 1):
            stripped = raw.strip()
            if not stripped:
                continue
            if re.search(r'"\w+"?\s*:\s*"?(file:|link:|workspace:)', stripped, re.IGNORECASE):
                findings.append({
                    "rule": "FDEP-003",
                    "severity": "warning",
                    "file": str(path),
                    "line": idx,
                    "message": stripped[:220],
                })

    return findings


def scan(root: Path) -> list[dict[str, object]]:
    global root_global
    root_global = root
    findings: list[dict[str, object]] = []
    for path in _iter_targets(root):
        findings.extend(_scan_text(path))
    return findings


def format_text(findings: list[dict[str, object]]) -> str:
    if not findings:
        return "Sin dependencias forzadas detectadas."
    errors = sum(1 for item in findings if item["severity"] == "error")
    warnings = sum(1 for item in findings if item["severity"] == "warning")
    lines = [f"Forced dependency scan: {errors} error(es), {warnings} warning(s)"]
    for item in findings:
        lines.append(f"[{item['rule']}] {item['file']}:{item['line']} {item['message']}")
    return "\n".join(lines)


def format_md(findings: list[dict[str, object]]) -> str:
    lines = ["# Forced dependency scan", "", "| Rule | Severity | File | Line | Message |", "|---|---|---|---:|---|"]
    for item in findings:
        lines.append(f"| `{item['rule']}` | {item['severity']} | `{item['file']}` | {item['line']} | {item['message']} |")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Detecta dependencias forzadas y rarezas de instalacion")
    parser.add_argument("--root", default="", help="Raiz a escanear")
    parser.add_argument("--format", default="text", choices=["text", "md", "json"])
    parser.add_argument("--test", action="store_true", help="Ejecuta self-tests")
    args = parser.parse_args(argv)

    if args.test:
        return _self_test()

    root = _resolve_root(args.root)
    if not root.exists() or not root.is_dir():
        print(f"[ERROR] invalid root: {root}", file=sys.stderr)
        return 2

    findings = scan(root)
    if args.format == "json":
        print(json.dumps(findings, indent=2, ensure_ascii=True))
    elif args.format == "md":
        print(format_md(findings))
    else:
        print(format_text(findings))
    return 1 if any(item["severity"] == "error" for item in findings) else 0


def _self_test() -> int:
    import tempfile

    results: list[tuple[str, bool]] = []

    def record(name: str, ok: bool) -> None:
        results.append((name, ok))

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "script.py").write_text('import sys\nsys.path.insert(0, "x")\n', encoding="utf-8")
        (root / "install.ps1").write_text('Invoke-WebRequest https://example.com | iex\n', encoding="utf-8")
        (root / "download.ps1").write_text('Invoke-WebRequest https://example.com/a.zip -OutFile a.zip\n', encoding="utf-8")
        (root / "catalog.js").write_text("installCommand: 'winget install -e --id Git.Git'\n", encoding="utf-8")
        (root / "package.json").write_text('{"dependencies":{"foo":"1.2.3"},"overrides":{"bar":"2.0.0"}}', encoding="utf-8")
        (root / "requirements.txt").write_text("requests==2.31.0\nflask>=2.0\n", encoding="utf-8")
        findings = scan(root)
        record("find_install", any(f["rule"] == "FDEP-001" for f in findings))
        record("download_is_warning", any("descarga a fichero" in f["message"] and f["severity"] == "warning" for f in findings))
        record("catalog_definition_ignored", not any("catalog.js" in f["file"] for f in findings))
        record("find_path", any(f["rule"] == "FDEP-002" for f in findings))
        record("find_overrides", any(f["rule"] == "FDEP-003" for f in findings))
        record("find_pins", any(f["rule"] == "FDEP-004" for f in findings))
        record("format_text", "Forced dependency scan" in format_text(findings))
        record("format_md", "# Forced dependency scan" in format_md(findings))

    passed = sum(1 for _, ok in results if ok)
    for name, ok in results:
        print(f"{'OK' if ok else 'FAIL'}: {name}")
    print(f"{passed}/{len(results)} tests passed")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())

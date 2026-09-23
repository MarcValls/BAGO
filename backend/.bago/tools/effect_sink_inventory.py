#!/usr/bin/env python3
"""Static inventory of BAGO effect sinks.

This is an audit tool, not an authorization mechanism. It answers:

    Where can BAGO currently cause observable effects?
    Which canonical effect_id best describes each sink?
    Is that sink already behind the ExecutionGateway?

Default mode is report-only so the existing migration can be measured without
breaking CI. --strict is the future closure gate: it exits non-zero while
unbound or unknown sinks remain.

The scanner covers Python plus high-signal PowerShell/JS process/filesystem
patterns. It intentionally prefers false-positive audit candidates over silent
effect sinks.
"""

from __future__ import annotations

import argparse
import ast
import json
import re
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable


SCRIPT_PATH = Path(__file__).resolve()
REPO_ROOT = SCRIPT_PATH.parents[3]

DEFAULT_ROOTS = (
    REPO_ROOT / "backend",
    REPO_ROOT / "scripts",
    REPO_ROOT / "electron-viewer",
)
EXCLUDED_DIRS = {
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    "node_modules",
    "dist",
    "build",
    "coverage",
}

# The first materialized gateway owns its own authorization ledger. This is an
# authority-internal persistence sink, not a bypass around itself.
INTERNAL_AUTHORITY_PATHS = {
    "backend/.bago/core/authorization_boundary.py",
}

# These implementations are reached only through registered, server-owned
# ExecutionGateway adapters. They remain inventory findings; their binding is
# evidence of that ownership, not an exclusion from the audit.
GATEWAY_OWNED_PATHS = {
    "backend/.bago/core/filesystem_effects.py",
}
EXECUTION_GATEWAY_PATH = "backend/.bago/core/execution_gateway.py"

# High-signal Python call suffixes. Suffix matching is intentional because Path
# instances are often local variables, not literal pathlib.Path expressions.
PYTHON_SUFFIX_RULES: tuple[tuple[str, str, str], ...] = (
    (".write_text", "filesystem.write", "high"),
    (".write_bytes", "filesystem.write", "high"),
    (".unlink", "filesystem.delete", "high"),
    (".rmdir", "filesystem.delete", "high"),
    (".mkdir", "filesystem.write", "medium"),
    (".rename", "filesystem.write", "medium"),
    ("os.remove", "filesystem.delete", "high"),
    ("os.unlink", "filesystem.delete", "high"),
    ("os.rmdir", "filesystem.delete", "high"),
    ("os.removedirs", "filesystem.delete", "high"),
    ("os.rename", "filesystem.write", "high"),
    ("os.replace", "filesystem.write", "high"),
    ("os.mkdir", "filesystem.write", "high"),
    ("os.makedirs", "filesystem.write", "high"),
    ("shutil.rmtree", "filesystem.delete", "high"),
    ("shutil.move", "filesystem.write", "high"),
    ("shutil.copy", "filesystem.write", "high"),
    ("shutil.copy2", "filesystem.write", "high"),
    ("shutil.copyfile", "filesystem.write", "high"),
    ("shutil.copytree", "filesystem.write", "high"),
    ("subprocess.run", "process.execute", "high"),
    ("subprocess.Popen", "process.execute", "high"),
    ("subprocess.call", "process.execute", "high"),
    ("subprocess.check_call", "process.execute", "high"),
    ("subprocess.check_output", "process.execute", "high"),
    ("os.system", "process.execute", "high"),
    ("urllib.request.urlopen", "network.read", "medium"),
    ("requests.get", "network.read", "high"),
    ("requests.head", "network.read", "high"),
    ("requests.post", "network.external_write", "high"),
    ("requests.put", "network.external_write", "high"),
    ("requests.patch", "network.external_write", "high"),
    ("requests.delete", "network.external_write", "high"),
    ("httpx.get", "network.read", "high"),
    ("httpx.post", "network.external_write", "high"),
    ("httpx.put", "network.external_write", "high"),
    ("httpx.patch", "network.external_write", "high"),
    ("httpx.delete", "network.external_write", "high"),
)

POWERSHELL_RULES: tuple[tuple[re.Pattern[str], str, str], ...] = (
    (re.compile(r"\bRemove-Item\b", re.I), "filesystem.delete", "high"),
    (re.compile(r"\b(?:Set-Content|Add-Content|Out-File|Copy-Item|Move-Item|New-Item)\b", re.I), "filesystem.write", "medium"),
    (re.compile(r"\bStart-Process\b", re.I), "process.execute", "high"),
    (re.compile(r"\b(?:Invoke-WebRequest|Invoke-RestMethod)\b.*\b-Method\s+(?:POST|PUT|PATCH|DELETE)\b", re.I), "network.external_write", "high"),
    (re.compile(r"\b(?:Invoke-WebRequest|Invoke-RestMethod)\b", re.I), "network.read", "medium"),
)

JS_RULES: tuple[tuple[re.Pattern[str], str, str], ...] = (
    (re.compile(r"\b(?:child_process\.)?(?:spawn|spawnSync|exec|execSync|execFile|execFileSync|fork)\s*\("), "process.execute", "high"),
    (re.compile(r"\b(?:fs\.)?(?:writeFile|writeFileSync|appendFile|appendFileSync|mkdir|mkdirSync|copyFile|copyFileSync|rename|renameSync)\s*\("), "filesystem.write", "medium"),
    (re.compile(r"\b(?:fs\.)?(?:unlink|unlinkSync|rm|rmSync|rmdir|rmdirSync)\s*\("), "filesystem.delete", "high"),
)


@dataclass(frozen=True, slots=True)
class SinkFinding:
    path: str
    line: int
    column: int
    language: str
    sink: str
    effect_id: str
    confidence: str
    binding: str
    excerpt: str


def _relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def _binding_for(path: Path, *, gateway_owned_adapter: bool = False) -> str:
    rel = _relative(path)
    if rel in INTERNAL_AUTHORITY_PATHS:
        return "authority_internal"
    if rel in GATEWAY_OWNED_PATHS or gateway_owned_adapter:
        return "gateway_owned"
    # P1 intentionally has no effect adapters yet. Every other sink remains
    # visible as unbound until a later migration step registers an adapter.
    return "unbound"


def _qualified_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        left = _qualified_name(node.value)
        return f"{left}.{node.attr}" if left else node.attr
    if isinstance(node, ast.Call):
        return _qualified_name(node.func)
    return ""


def _literal_open_effect(call: ast.Call) -> tuple[str, str] | None:
    name = _qualified_name(call.func)
    if name not in {"open", "io.open", "Path.open", "pathlib.Path.open"} and not name.endswith(".open"):
        return None
    mode: str | None = None
    if len(call.args) >= 2 and isinstance(call.args[1], ast.Constant) and isinstance(call.args[1].value, str):
        mode = call.args[1].value
    for keyword in call.keywords:
        if keyword.arg == "mode" and isinstance(keyword.value, ast.Constant) and isinstance(keyword.value.value, str):
            mode = keyword.value.value
    if mode and any(flag in mode for flag in ("w", "a", "x", "+")):
        return ("filesystem.write", "medium")
    return None


def _classify_python_call(call: ast.Call) -> tuple[str, str] | None:
    opened = _literal_open_effect(call)
    if opened is not None:
        return opened
    name = _qualified_name(call.func)
    for suffix, effect_id, confidence in PYTHON_SUFFIX_RULES:
        if name == suffix or name.endswith(suffix):
            return (effect_id, confidence)
    return None


def _line_excerpt(lines: list[str], line: int) -> str:
    if 1 <= line <= len(lines):
        return " ".join(lines[line - 1].strip().split())[:240]
    return ""


def _gateway_owned_adapter_ranges(path: Path, tree: ast.AST) -> tuple[tuple[int, int], ...]:
    """Return concrete adapter class spans in the server-owned gateway module."""
    if _relative(path) != EXECUTION_GATEWAY_PATH:
        return ()
    return tuple(
        (
            int(getattr(node, "lineno", 0) or 0),
            int(getattr(node, "end_lineno", 0) or 0),
        )
        for node in ast.walk(tree)
        if isinstance(node, ast.ClassDef)
        and node.name != "EffectAdapter"
        and node.name.endswith("EffectAdapter")
    )


def _is_in_ranges(line: int, ranges: Iterable[tuple[int, int]]) -> bool:
    return any(start <= line <= end for start, end in ranges)


def scan_python(path: Path) -> list[SinkFinding]:
    try:
        source = path.read_text(encoding="utf-8", errors="replace")
        tree = ast.parse(source, filename=str(path))
    except (OSError, SyntaxError):
        return []
    lines = source.splitlines()
    gateway_owned_adapter_ranges = _gateway_owned_adapter_ranges(path, tree)
    findings: list[SinkFinding] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        classification = _classify_python_call(node)
        if classification is None:
            continue
        effect_id, confidence = classification
        findings.append(
            SinkFinding(
                path=_relative(path),
                line=int(getattr(node, "lineno", 0) or 0),
                column=int(getattr(node, "col_offset", 0) or 0),
                language="python",
                sink=_qualified_name(node.func) or "<call>",
                effect_id=effect_id,
                confidence=confidence,
                binding=_binding_for(
                    path,
                    gateway_owned_adapter=_is_in_ranges(
                        int(getattr(node, "lineno", 0) or 0),
                        gateway_owned_adapter_ranges,
                    ),
                ),
                excerpt=_line_excerpt(lines, int(getattr(node, "lineno", 0) or 0)),
            )
        )
    return findings


def _scan_text(path: Path, language: str, rules: Iterable[tuple[re.Pattern[str], str, str]]) -> list[SinkFinding]:
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []
    findings: list[SinkFinding] = []
    for number, line in enumerate(lines, start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith(("#", "//")):
            continue
        for pattern, effect_id, confidence in rules:
            match = pattern.search(line)
            if not match:
                continue
            findings.append(
                SinkFinding(
                    path=_relative(path),
                    line=number,
                    column=match.start(),
                    language=language,
                    sink=match.group(0)[:120],
                    effect_id=effect_id,
                    confidence=confidence,
                    binding=_binding_for(path),
                    excerpt=" ".join(stripped.split())[:240],
                )
            )
            # One highest-value finding per rule on the line is sufficient.
    return findings


def _iter_files(roots: Iterable[Path]) -> Iterable[Path]:
    for root in roots:
        if not root.exists():
            continue
        if root.is_file():
            yield root
            continue
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            if any(part in EXCLUDED_DIRS for part in path.parts):
                continue
            if path.suffix.lower() in {".py", ".ps1", ".js", ".cjs", ".mjs"}:
                yield path


def scan_paths(roots: Iterable[Path]) -> list[SinkFinding]:
    findings: list[SinkFinding] = []
    for path in _iter_files(roots):
        suffix = path.suffix.lower()
        if suffix == ".py":
            findings.extend(scan_python(path))
        elif suffix == ".ps1":
            findings.extend(_scan_text(path, "powershell", POWERSHELL_RULES))
        elif suffix in {".js", ".cjs", ".mjs"}:
            findings.extend(_scan_text(path, "javascript", JS_RULES))
    return sorted(findings, key=lambda item: (item.path, item.line, item.column, item.effect_id))


def build_inventory(roots: Iterable[Path] | None = None) -> dict[str, Any]:
    selected = tuple(roots or DEFAULT_ROOTS)
    findings = scan_paths(selected)
    by_effect = Counter(item.effect_id for item in findings)
    by_binding = Counter(item.binding for item in findings)
    high_confidence_unbound = [
        item for item in findings
        if item.binding == "unbound" and item.confidence == "high"
    ]
    return {
        "schema": "bago.effect-sink-inventory.v1",
        "repo_root": str(REPO_ROOT),
        "roots": [_relative(path) for path in selected],
        "summary": {
            "total_sinks": len(findings),
            "unbound_sinks": sum(1 for item in findings if item.binding == "unbound"),
            "authority_internal_sinks": sum(1 for item in findings if item.binding == "authority_internal"),
            "high_confidence_unbound_sinks": len(high_confidence_unbound),
            "by_effect": dict(sorted(by_effect.items())),
            "by_binding": dict(sorted(by_binding.items())),
        },
        "findings": [asdict(item) for item in findings],
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Inventory BAGO material effect sinks")
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="fail while any unbound sink remains (future UNIQUE_EXECUTION_BOUNDARY gate)",
    )
    parser.add_argument(
        "--root",
        action="append",
        default=[],
        help="override scan roots relative to repository root; may be repeated",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    roots = tuple((REPO_ROOT / raw).resolve() for raw in args.root) if args.root else DEFAULT_ROOTS
    inventory = build_inventory(roots)
    if args.json:
        print(json.dumps(inventory, ensure_ascii=False, indent=2))
    else:
        summary = inventory["summary"]
        print("BAGO effect-sink inventory")
        print(f"  total_sinks: {summary['total_sinks']}")
        print(f"  unbound_sinks: {summary['unbound_sinks']}")
        print(f"  high_confidence_unbound_sinks: {summary['high_confidence_unbound_sinks']}")
        for effect_id, count in summary["by_effect"].items():
            print(f"  {effect_id}: {count}")
    if args.strict and inventory["summary"]["unbound_sinks"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

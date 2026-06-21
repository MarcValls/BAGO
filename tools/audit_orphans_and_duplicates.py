#!/usr/bin/env python3
"""Audit orphaned and duplicated BAGO pieces.

This is a repo-level report generator. It classifies:
- source-facing tools that are wired, support-only, or orphan candidates
- generated mirrors such as manager/ vs site-dist/manager/
- absent source roots for agents/skills

Usage:
    python tools/audit_orphans_and_duplicates.py [--root DIR] [--json]
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import hashlib
from pathlib import Path

SKIP_DIRS = {
    ".git",
    "node_modules",
    "__pycache__",
    ".venv",
    "venv",
    "dist",
    "build",
    "release",
    "site-dist",
}

TEXT_EXTS = {
    ".py", ".js", ".cjs", ".mjs", ".jsx", ".ts", ".tsx",
    ".ps1", ".cmd", ".bat", ".md", ".json", ".toml", ".yml", ".yaml", ".txt",
}


def _load_inventory_module(root: Path):
    module_path = root / ".bago" / "tools" / "bago_inventory.py"
    spec = importlib.util.spec_from_file_location("bago_inventory", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load inventory module: {module_path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _iter_text_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if path.name.startswith("ORPHAN_DUPLICATE_"):
            continue
        if path.suffix.lower() not in TEXT_EXTS:
            continue
        files.append(path)
    return files


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _rel(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def _refs_for_name(root: Path, name: str, files: list[Path]) -> list[str]:
    hits: list[str] = []
    for path in files:
        if path.name == f"{name}.py":
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        if name in text:
            hits.append(_rel(path, root))
    return hits


def _manager_mirror(root: Path) -> dict[str, object]:
    manager = root / "manager"
    site = root / "site-dist" / "manager"
    if not manager.exists() or not site.exists():
        return {"present": False}
    pairs = 0
    equal = 0
    diffs: list[str] = []
    for src in manager.rglob("*"):
        if not src.is_file():
            continue
        rel = src.relative_to(manager)
        dst = site / rel
        if not dst.exists() or not dst.is_file():
            diffs.append(f"missing:{_rel(dst, root)}")
            continue
        pairs += 1
        if _hash(src) == _hash(dst):
            equal += 1
        else:
            diffs.append(_rel(src, root))
    return {
        "present": True,
        "pairs": pairs,
        "equal": equal,
        "different": pairs - equal,
        "fully_mirrored": pairs > 0 and pairs == equal and not diffs,
        "diffs": diffs[:20],
    }


def scan(root: Path) -> dict[str, object]:
    inventory_mod = _load_inventory_module(root)
    inventory = inventory_mod.gather_inventory(root)
    text_files = _iter_text_files(root)

    cmd_tools = (root / "bago_core" / "commands" / "cmd_tools.py").read_text(encoding="utf-8", errors="replace")
    launcher = (root / "bago_core" / "launcher.py").read_text(encoding="utf-8", errors="replace")
    parsers = (root / "bago_core" / "parsers_sections.py").read_text(encoding="utf-8", errors="replace")
    tool_readme = (root / ".bago" / "tools" / "README.md").read_text(encoding="utf-8", errors="replace")

    tool_rows: list[dict[str, object]] = []
    for tool in sorted((root / ".bago" / "tools").glob("*.py")):
        if tool.name == "__init__.py":
            continue
        stem = tool.stem
        code_hits = []
        doc_hits = []
        if stem in cmd_tools:
            code_hits.append(_rel(root / "bago_core" / "commands" / "cmd_tools.py", root))
        if stem in launcher:
            code_hits.append(_rel(root / "bago_core" / "launcher.py", root))
        if stem in parsers:
            code_hits.append(_rel(root / "bago_core" / "parsers_sections.py", root))
        if stem in tool_readme:
            doc_hits.append(_rel(root / ".bago" / "tools" / "README.md", root))
        support_refs = _refs_for_name(root, stem, text_files)
        support_refs = [ref for ref in support_refs if ref not in code_hits and ref not in doc_hits]
        if code_hits:
            status = "wired"
        elif support_refs:
            status = "support-only"
        elif doc_hits:
            status = "doc-only"
        else:
            status = "orphan-candidate"
        tool_rows.append({
            "tool": _rel(tool, root),
            "status": status,
            "wired_refs": code_hits,
            "doc_refs": doc_hits,
            "support_refs": support_refs[:8],
        })

    orphan_candidates = [row for row in tool_rows if row["status"] == "orphan-candidate"]
    doc_only = [row for row in tool_rows if row["status"] == "doc-only"]
    support_only = [row for row in tool_rows if row["status"] == "support-only"]

    return {
        "root": str(root),
        "inventory": inventory,
        "tool_rows": tool_rows,
        "orphan_candidates": orphan_candidates,
        "doc_only": doc_only,
        "support_only": support_only,
        "manager_mirror": _manager_mirror(root),
        "agents_root_exists": (root / "agents").exists(),
        "skills_root_exists": (root / "skills").exists(),
        "summary": {
            "tool_files": len(tool_rows),
            "orphan_candidates": len(orphan_candidates),
            "doc_only": len(doc_only),
            "support_only": len(support_only),
        },
    }


def format_text(report: dict[str, object]) -> str:
    lines = [
        f"Orphan/duplicate audit for {report['root']}",
        f"Tools scanned: {report['summary']['tool_files']}",
        f"Orphan candidates: {report['summary']['orphan_candidates']}",
        f"Doc-only candidates: {report['summary']['doc_only']}",
        f"Support-only engines: {report['summary']['support_only']}",
        f"agents/ exists: {report['agents_root_exists']}",
        f"skills/ exists: {report['skills_root_exists']}",
        "",
        "Manager mirror:",
    ]
    mm = report["manager_mirror"]
    if not mm.get("present"):
        lines.append("  - absent")
    else:
        lines.append(
            f"  - pairs={mm['pairs']} equal={mm['equal']} different={mm['different']} fully_mirrored={mm['fully_mirrored']}"
        )
        for diff in mm.get("diffs", []):
            lines.append(f"    - diff {diff}")

    lines.append("")
    lines.append("Tool rows:")
    for row in report["tool_rows"]:
        lines.append(
            f"  - {row['tool']} [{row['status']}] wired={len(row['wired_refs'])} doc={len(row.get('doc_refs', []))} support={len(row['support_refs'])}"
        )
        if row["wired_refs"]:
            lines.append(f"    wired: {', '.join(row['wired_refs'])}")
        if row.get("doc_refs"):
            lines.append(f"    doc: {', '.join(row['doc_refs'])}")
        if row["support_refs"]:
            lines.append(f"    support: {', '.join(row['support_refs'])}")

    return "\n".join(lines)


def format_md(report: dict[str, object]) -> str:
    lines = [
        f"# Orphan and duplicate audit for `{report['root']}`",
        "",
        f"- Tools scanned: {report['summary']['tool_files']}",
        f"- Orphan candidates: {report['summary']['orphan_candidates']}",
        f"- Support-only engines: {report['summary']['support_only']}",
        f"- `agents/` exists: {report['agents_root_exists']}",
        f"- `skills/` exists: {report['skills_root_exists']}",
        "",
        "## Manager Mirror",
    ]
    mm = report["manager_mirror"]
    if not mm.get("present"):
        lines.append("- absent")
    else:
        lines.append(
            f"- pairs={mm['pairs']} equal={mm['equal']} different={mm['different']} fully_mirrored={mm['fully_mirrored']}"
        )
        for diff in mm.get("diffs", []):
            lines.append(f"  - diff `{diff}`")

    lines.append("")
    lines.append("## Tool Rows")
    for row in report["tool_rows"]:
        lines.append(f"- `{row['tool']}`: **{row['status']}**")
        if row["wired_refs"]:
            lines.append(f"  - wired: {', '.join(f'`{x}`' for x in row['wired_refs'])}")
        if row.get("doc_refs"):
            lines.append(f"  - doc: {', '.join(f'`{x}`' for x in row['doc_refs'])}")
        if row["support_refs"]:
            lines.append(f"  - support: {', '.join(f'`{x}`' for x in row['support_refs'])}")

    return "\n".join(lines)


def build_plan(report: dict[str, object]) -> str:
    orphan_tools = [row["tool"] for row in report["orphan_candidates"]]
    doc_only_tools = [row["tool"] for row in report["doc_only"]]
    support_tools = [row["tool"] for row in report["support_only"]]
    lines = [
        "# Plan de limpieza y conexión",
        "",
        "## 1. Mantener como canónico",
        "- `manager/` como fuente editable del manager.",
        "- `.bago/tools/bago_utils.py` como helper compartido.",
        "- `debt_scanner.py` y `skill_engine.py` como motores internos si siguen siendo dependencias de otras piezas.",
        "",
        "## 2. Mantener como generado",
        "- `site-dist/manager/` como espejo de publicación, no como fuente manual.",
        "- No editar a mano `site-dist/manager.html` si es solo alias del build.",
        "",
        "## 3. Conectar o archivar",
    ]
    if orphan_tools:
        for tool in orphan_tools:
            lines.append(f"- Revisar `{tool}`: si tiene ruta real, exponerla en CLI/docs; si no, archivarla.")
    else:
        lines.append("- No hay huérfanos claros en `.bago/tools` con esta heurística.")
    if doc_only_tools:
        lines.extend([
            "",
            "## 4. Doc-only que merece decisión",
        ])
        for tool in doc_only_tools:
            lines.append(f"- Revisar `{tool}`: si debe vivir, cablearlo; si no, archivarlo.")
    lines.extend([
        "",
        "## 5. Eliminar duplicidades",
        "- Eliminar duplicación manual entre `manager/` y `site-dist/manager/` solo si el build las regenera al vuelo.",
        "- Si ambos deben existir, documentar que `site-dist/` es salida y nunca fuente.",
        "",
        "## 6. Regla de cierre",
        "- Un tool nuevo debe tener un solo camino: CLI, docs y una dependencia clara; si no, se queda como soporte interno.",
    ])
    mm = report.get("manager_mirror", {})
    if mm.get("present") and not mm.get("fully_mirrored"):
        lines.extend([
            "",
            "## 7. Drift detectado",
            "- `site-dist/manager/` no está exactamente alineado con `manager/`.",
        ])
        for diff in mm.get("diffs", []):
            lines.append(f"- Revisar {diff}")
    if support_tools:
        heading = "## 7. Soporte interno que no se debe borrar a ciegas"
        if mm.get("present") and not mm.get("fully_mirrored"):
            heading = "## 8. Soporte interno que no se debe borrar a ciegas"
        lines.extend([
            "",
            heading,
        ])
        for tool in support_tools:
            lines.append(f"- `{tool}`")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Audit orphaned and duplicated BAGO pieces")
    parser.add_argument("--root", default="", help="Repo root")
    parser.add_argument("--json", action="store_true", help="Emit JSON")
    parser.add_argument("--md", action="store_true", help="Emit markdown")
    parser.add_argument("--plan-out", default="", help="Write plan markdown to this path")
    args = parser.parse_args(argv)

    root = Path(args.root).resolve() if args.root else Path.cwd().resolve()
    if not root.exists() or not root.is_dir():
        print(f"[ERROR] invalid root: {root}")
        return 2

    report = scan(root)
    if args.plan_out:
        Path(args.plan_out).write_text(build_plan(report), encoding="utf-8")

    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    elif args.md:
        print(format_md(report))
    else:
        print(format_text(report))
        print()
        print(build_plan(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

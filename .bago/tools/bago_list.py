#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
bago_list.py — Lista todos los archivos del directorio de trabajo con metadatos.

Uso:
    python .bago/tools/bago_list.py [directorio] [opciones]

Opciones:
    --all               Incluye archivos ocultos y directorios excluidos
    --tree              Salida en formato árbol jerárquico
    --size              Muestra tamaño human-readable
    --modified          Muestra fecha de última modificación
    --ext               Agrupa por extensión
    --git               Marca archivos según estado git (M, A, ?, etc.)
    --json              Salida JSON
    --max-depth N       Límite de profundidad (default: sin límite)
    --filter EXT        Filtra por extensión (ej: --filter py,ts)

Códigos de salida: 0 = OK, 1 = directorio no existe, 2 = error
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Iterable

from bago_utils import get_repo_root

ROOT = get_repo_root()

EXCLUDE_DIRS = {"node_modules", "dist", "build", ".next", ".git", ".bago", "out",
                "coverage", ".turbo", "__pycache__", ".pytest_cache", ".mypy_cache",
                "venv", ".venv", "env", ".env", ".idea", ".vscode", ".vs"}

def _human_size(size: int) -> str:
    for unit in ["B", "KB", "MB", "GB"]:
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"

def _git_status_map(root: Path) -> dict[str, str]:
    """Returns {relative_path: status_code} using git status --porcelain."""
    git_map: dict[str, str] = {}
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain", "-uall"],
            cwd=str(root),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if result.returncode == 0:
            for line in result.stdout.splitlines():
                if len(line) >= 3:
                    code = line[:2].strip()
                    path_str = line[3:].strip()
                    git_map[path_str] = code
    except Exception:
        pass
    return git_map

def _collect_files(root: Path, max_depth: int | None, include_hidden: bool,
                   filter_exts: set[str] | None) -> Iterable[tuple[Path, int]]:
    if root.is_file():
        yield (root, 0)
        return
    for dirpath, dirnames, filenames in os.walk(root):
        current = Path(dirpath)
        # Compute depth
        try:
            depth = len(current.relative_to(root).parts)
        except ValueError:
            depth = 0
        if max_depth is not None and depth > max_depth:
            del dirnames[:]
            continue
        # Exclude directories
        if not include_hidden:
            dirnames[:] = [d for d in dirnames if not d.startswith(".")]
            dirnames[:] = [d for d in dirnames if d not in EXCLUDE_DIRS]
        for fname in filenames:
            if not include_hidden and fname.startswith("."):
                continue
            fpath = current / fname
            if filter_exts and fpath.suffix.lower().lstrip(".") not in filter_exts:
                continue
            yield (fpath, depth)

def _color(code: int, s: str) -> str:
    return f"\033[{code}m{s}\033[0m"

GREEN = lambda s: _color(32, s)
YELLOW = lambda s: _color(33, s)
CYAN = lambda s: _color(36, s)
DIM = lambda s: _color(2, s)
BOLD = lambda s: _color(1, s)
MAGENTA = lambda s: _color(35, s)
RED = lambda s: _color(31, s)

def main() -> int:
    args = sys.argv[1:]
    if args and args[0] in ("-h", "--help"):
        print(__doc__)
        return 0

    target = ROOT
    show_all = "--all" in args
    tree_mode = "--tree" in args
    show_size = "--size" in args
    show_modified = "--modified" in args
    group_ext = "--ext" in args
    git_mode = "--git" in args
    json_out = "--json" in args
    max_depth = None
    filter_exts: set[str] | None = None

    # Parse positional directory
    for arg in args:
        if arg.startswith("-"):
            continue
        candidate = Path(arg)
        if candidate.exists():
            target = candidate.resolve()
            break

    # Parse flags with values
    for i, arg in enumerate(args):
        if arg == "--max-depth" and i + 1 < len(args):
            try:
                max_depth = int(args[i + 1])
            except ValueError:
                pass
        if arg == "--filter" and i + 1 < len(args):
            filter_exts = set(e.lstrip(".") for e in args[i + 1].split(","))

    if not target.exists():
        print(RED(f"Directorio no existe: {target}"))
        return 1

    git_map = _git_status_map(target) if git_mode else {}

    files = list(_collect_files(target, max_depth, show_all, filter_exts))
    if not files:
        if not json_out:
            print(DIM("Sin archivos."))
        else:
            print(json.dumps({"files": []}, ensure_ascii=False))
        return 0

    if json_out:
        output = []
        for fpath, depth in files:
            entry = {
                "path": str(fpath.relative_to(target)),
                "absolute": str(fpath),
                "depth": depth,
                "extension": fpath.suffix.lower().lstrip("."),
            }
            if show_size:
                entry["size"] = fpath.stat().st_size
                entry["size_human"] = _human_size(fpath.stat().st_size)
            if show_modified:
                mtime = datetime.fromtimestamp(fpath.stat().st_mtime)
                entry["modified"] = mtime.isoformat()
            if git_mode:
                rel = str(fpath.relative_to(target)).replace("\\", "/")
                entry["git_status"] = git_map.get(rel, "")
            output.append(entry)
        print(json.dumps({"root": str(target), "count": len(output), "files": output},
                         ensure_ascii=False, indent=2))
        return 0

    if group_ext:
        by_ext: dict[str, list[Path]] = {}
        for fpath, _ in files:
            ext = fpath.suffix.lower() or "(sin extensión)"
            by_ext.setdefault(ext, []).append(fpath)
        print(BOLD(f"📁 {target}") + DIM(f"  ({len(files)} archivos)"))
        for ext in sorted(by_ext):
            print(f"\n{BOLD(ext)} {DIM(f'({len(by_ext[ext])})')}")
            for fpath in sorted(by_ext[ext]):
                rel = fpath.relative_to(target)
                line = f"  {CYAN(rel)}"
                if show_size:
                    line += DIM(f"  {_human_size(fpath.stat().st_size)}")
                if show_modified:
                    mtime = datetime.fromtimestamp(fpath.stat().st_mtime)
                    line += DIM(f"  {mtime.strftime('%Y-%m-%d %H:%M')}")
                if git_mode:
                    rel_str = str(rel).replace("\\", "/")
                    status = git_map.get(rel_str, "")
                    if status:
                        color = YELLOW if status == "M" else GREEN if status == "A" else RED if status == "D" else MAGENTA
                        line += f"  [{color(status)}]"
                print(line)
        return 0

    if tree_mode:
        # Build tree structure
        tree: dict = {}
        for fpath, depth in files:
            parts = list(fpath.relative_to(target).parts)
            node = tree
            for part in parts[:-1]:
                node = node.setdefault(part, {})
            node[parts[-1]] = None  # leaf

        def print_tree(node: dict, prefix: str = ""):
            items = sorted(node.items(), key=lambda x: (x[1] is not None, x[0]))
            for i, (name, child) in enumerate(items):
                is_last = i == len(items) - 1
                connector = "└── " if is_last else "├── "
                line = prefix + connector + name
                if git_mode:
                    rel = str(Path(prefix.replace("│   ", "").replace("    ", "") / name)).replace("\\", "/").lstrip("/")
                    status = git_map.get(rel, "")
                    if status:
                        color = YELLOW if status == "M" else GREEN if status == "A" else RED if status == "D" else MAGENTA
                        line += f" [{color(status)}]"
                print(line)
                if child is not None:
                    extension = "    " if is_last else "│   "
                    print_tree(child, prefix + extension)

        print(BOLD(f"📁 {target}"))
        print_tree(tree)
        return 0

    # Default flat list
    print(BOLD(f"📁 {target}") + DIM(f"  ({len(files)} archivos)"))
    for fpath, depth in files:
        rel = fpath.relative_to(target)
        indent = "  " * depth if max_depth is not None else "  "
        line = f"{indent}{CYAN(rel)}"
        if show_size:
            line += DIM(f"  {_human_size(fpath.stat().st_size)}")
        if show_modified:
            mtime = datetime.fromtimestamp(fpath.stat().st_mtime)
            line += DIM(f"  {mtime.strftime('%Y-%m-%d %H:%M')}")
        if git_mode:
            rel_str = str(rel).replace("\\", "/")
            status = git_map.get(rel_str, "")
            if status:
                color = YELLOW if status == "M" else GREEN if status == "A" else RED if status == "D" else MAGENTA
                line += f"  [{color(status)}]"
        print(line)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())

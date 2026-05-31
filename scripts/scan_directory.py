#!/usr/bin/env python3
"""
scan_directory.py - BAGO filesystem battery script.

Prints a compact tree for a directory and is safe to run by default.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class TreeOptions:
    path: Path
    max_depth: int
    show_hidden: bool
    dirs_only: bool


def _visible_entries(path: Path, show_hidden: bool) -> list[Path]:
    items = []
    for item in sorted(path.iterdir(), key=lambda p: (p.is_file(), p.name.lower())):
        if not show_hidden and item.name.startswith("."):
            continue
        items.append(item)
    return items


def _render_tree(path: Path, options: TreeOptions, depth: int = 0) -> list[str]:
    prefix = "  " * depth
    marker = "[D]" if path.is_dir() else "[F]"
    lines = [f"{prefix}{marker} {path.name if depth else path}"]
    if not path.is_dir() or depth >= options.max_depth:
        return lines

    for child in _visible_entries(path, options.show_hidden):
        if options.dirs_only and child.is_file():
            continue
        lines.extend(_render_tree(child, options, depth + 1))
    return lines


def scan_directory(path: str, max_depth: int = 2, show_hidden: bool = False, dirs_only: bool = False) -> str:
    target = Path(path).expanduser().resolve()
    if not target.exists():
        raise FileNotFoundError(f"No existe: {target}")
    if not target.is_dir():
        raise NotADirectoryError(f"No es directorio: {target}")
    options = TreeOptions(path=target, max_depth=max_depth, show_hidden=show_hidden, dirs_only=dirs_only)
    lines = [f"Directory: {target}", f"Max depth: {max_depth}", ""]
    lines.extend(_render_tree(target, options))
    return "\n".join(lines)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Scan a directory tree for the filesystem battery.")
    parser.add_argument("path", nargs="?", default=".", help="Directory to inspect")
    parser.add_argument("--max-depth", type=int, default=2, help="Maximum recursion depth")
    parser.add_argument("--hidden", action="store_true", help="Include hidden files")
    parser.add_argument("--dirs-only", action="store_true", help="Show only directories")
    return parser


def _run_tests() -> int:
    from tempfile import TemporaryDirectory

    with TemporaryDirectory() as td:
        root = Path(td)
        (root / "alpha").mkdir()
        (root / "alpha" / "beta.txt").write_text("ok", encoding="utf-8")
        (root / "root.txt").write_text("root", encoding="utf-8")
        output = scan_directory(td, max_depth=3)
        assert "Directory:" in output
        assert "alpha" in output
        assert "beta.txt" in output
    print("scan_directory.py --test: ALL PASS")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        print(scan_directory(args.path, max_depth=args.max_depth, show_hidden=args.hidden, dirs_only=args.dirs_only))
        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    if "--test" in sys.argv:
        raise SystemExit(_run_tests())
    raise SystemExit(main())

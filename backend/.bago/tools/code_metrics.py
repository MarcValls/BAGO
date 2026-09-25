#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

EXCLUDE_DIRS = {"node_modules", ".git", "dist", "build", ".next", ".vite", "coverage", "__pycache__", ".venv", "venv", ".bago"}
EXCLUDE_NAMES = {"package-lock.json", "pnpm-lock.yaml", "yarn.lock"}
DEFAULT_SOURCE_EXTS = {
    ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".py", ".json",
    ".css", ".scss", ".html", ".vue", ".md", ".yaml", ".yml",
    ".toml", ".sh", ".mts", ".rst", ".txt",
}


def _normalize_exts(raw: str) -> set[str]:
    if not raw:
        return set()
    exts = set()
    for item in raw.split(","):
        part = item.strip().lower()
        if not part:
            continue
        if not part.startswith("."):
            part = f".{part}"
        exts.add(part)
    return exts


def _should_skip(path: Path) -> bool:
    return any(part in EXCLUDE_DIRS for part in path.parts) or path.name in EXCLUDE_NAMES


def analyze(root: Path, only_exts: set[str] | None = None) -> dict:
    metrics: dict[str, dict[str, int]] = defaultdict(lambda: {"files": 0, "lines": 0, "size": 0})
    scanned_files = 0
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(root)
        if _should_skip(rel):
            continue
        ext = path.suffix.lower()
        if only_exts:
            if ext not in only_exts:
                continue
        elif ext not in DEFAULT_SOURCE_EXTS:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
            size = path.stat().st_size
        except OSError:
            continue
        metrics[ext]["files"] += 1
        metrics[ext]["lines"] += len(text.splitlines())
        metrics[ext]["size"] += size
        scanned_files += 1
    total = {
        "files": sum(item["files"] for item in metrics.values()),
        "lines": sum(item["lines"] for item in metrics.values()),
        "size": sum(item["size"] for item in metrics.values()),
    }
    return {"root": str(root), "scanned_files": scanned_files, "total": total, "extensions": dict(metrics)}


def _sorted_extensions(metrics: dict[str, dict[str, int]], sort_by: str) -> list[tuple[str, dict[str, int]]]:
    key_name = "size" if sort_by == "size" else sort_by
    return sorted(metrics.items(), key=lambda item: (-item[1][key_name], item[0]))


def _print_report(report: dict, sort_by: str) -> None:
    print("CODE METRICS")
    print(f"Root: {report['root']}")
    print(f"Files: {report['total']['files']}")
    print(f"Lines: {report['total']['lines']}")
    print(f"Bytes: {report['total']['size']}")
    print(f"{'Ext':<8} {'Files':>8} {'Lines':>10} {'Bytes':>12}")
    for ext, data in _sorted_extensions(report["extensions"], sort_by):
        print(f"{ext or '[none]':<8} {data['files']:>8} {data['lines']:>10} {data['size']:>12}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Code metrics for any project.")
    parser.add_argument("--root", default="", help="Project root to scan. Default: cwd")
    parser.add_argument("--ext", default="", help="Comma separated extension filter, ex: ts,py")
    parser.add_argument("--json", action="store_true", help="Emit JSON output")
    parser.add_argument("--sort", choices=["size", "files", "lines"], default="lines", help="Sort key")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = Path(args.root or Path.cwd()).resolve()
    if not root.exists() or not root.is_dir():
        print(f"Error: invalid root {root}", file=sys.stderr)
        return 2
    report = analyze(root, _normalize_exts(args.ext) or None)
    if args.json:
        payload = dict(report)
        payload["extensions"] = [{"ext": ext, **data} for ext, data in _sorted_extensions(report["extensions"], args.sort)]
        print(json.dumps(payload, indent=2, ensure_ascii=True))
    else:
        _print_report(report, args.sort)
    return 0


if __name__ == "__main__":
    sys.exit(main())

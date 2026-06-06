#!/usr/bin/env python3
"""Portable backup vault for BAGO 4.x.

Usage:
    python bago_backup_vault.py [--root DIR] create [--max N]
    python bago_backup_vault.py [--root DIR] list
    python bago_backup_vault.py [--root DIR] restore --index N
    python bago_backup_vault.py --test

Exit codes:
    0 = ok
    2 = runtime error
"""
from __future__ import annotations

import argparse
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

EXCLUDE_DIRS = {".git", "node_modules", "__pycache__", "dist", "build", ".venv", "venv"}


def resolve_root(root_arg: str) -> Path:
    return Path(root_arg).resolve() if root_arg else Path.cwd().resolve()


def backup_dir(root: Path) -> Path:
    path = root / ".bago" / "backups"
    path.mkdir(parents=True, exist_ok=True)
    return path


def list_backup_files(root: Path) -> list[Path]:
    return sorted(backup_dir(root).glob("backup_*.zip"), reverse=True)


def should_skip(path: Path, root: Path) -> bool:
    parts = path.relative_to(root).parts
    if not parts:
        return False
    if parts[0] in EXCLUDE_DIRS:
        return True
    if parts[:2] == (".bago", "backups"):
        return True
    return False


def create_backup(root: Path, max_backups: int) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
    target = backup_dir(root) / f"backup_{stamp}.zip"
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(root.rglob("*")):
            if path.is_dir() or should_skip(path, root):
                continue
            zf.write(path, arcname=str(path.relative_to(root)))
    rotate_backups(root, max_backups)
    return target


def rotate_backups(root: Path, max_backups: int) -> None:
    files = list_backup_files(root)
    for stale in files[max(1, max_backups):]:
        stale.unlink(missing_ok=True)


def list_backups(root: Path) -> list[dict[str, object]]:
    items = []
    for idx, path in enumerate(list_backup_files(root), start=1):
        items.append({
            "index": idx,
            "name": path.name,
            "size": path.stat().st_size,
        })
    return items


def restore_backup(root: Path, index: int) -> Path:
    files = list_backup_files(root)
    if index < 1 or index > len(files):
        raise IndexError(f"backup index out of range: {index}")
    source = files[index - 1]
    with zipfile.ZipFile(source, "r") as zf:
        zf.extractall(root)
    return source


def print_list(items: list[dict[str, object]]) -> None:
    if not items:
        print("No backups found")
        return
    print("Backups:")
    for item in items:
        print(f"  [{item['index']}] {item['name']} {item['size']} bytes")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Portable backup vault")
    parser.add_argument("--root", default="", help="Project root")
    parser.add_argument("--test", action="store_true", help="Run self-tests")
    sub = parser.add_subparsers(dest="command")
    create_parser = sub.add_parser("create", help="Create backup zip")
    create_parser.add_argument("--max", type=int, default=10)
    sub.add_parser("list", help="List backups")
    restore_parser = sub.add_parser("restore", help="Restore backup by list index")
    restore_parser.add_argument("--index", type=int, default=1)
    args = parser.parse_args(argv)

    if args.test:
        return run_self_tests()

    root = resolve_root(args.root)
    if not root.exists() or not root.is_dir():
        print(f"[ERROR] invalid root: {root}", file=sys.stderr)
        return 2

    try:
        if args.command == "create":
            target = create_backup(root, max(1, args.max))
            print(f"Created backup: {target.name}")
            return 0
        if args.command == "restore":
            source = restore_backup(root, args.index)
            print(f"Restored backup: {source.name}")
            return 0
        print_list(list_backups(root))
        return 0
    except Exception as exc:  # noqa: BLE001
        print(f"[ERROR] bago_backup_vault failed: {exc}", file=sys.stderr)
        return 2


def run_self_tests() -> int:
    import tempfile

    results: list[tuple[str, bool, str]] = []

    def record(name: str, ok: bool, detail: str) -> None:
        results.append((name, ok, detail))

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "src").mkdir()
        (root / "src" / "app.py").write_text("print('ok')\n", encoding="utf-8")
        (root / "node_modules").mkdir()
        (root / "node_modules" / "skip.js").write_text("skip\n", encoding="utf-8")

        created = create_backup(root, 2)
        record("backup:create", created.exists(), f"file={created.name}")

        items = list_backups(root)
        record("backup:list", len(items) == 1, f"count={len(items)}")

        with zipfile.ZipFile(created, "r") as zf:
            names = set(zf.namelist())
        record("backup:exclude_dirs", "node_modules/skip.js" not in names and "src/app.py" in names, "filters ok")

        (root / "src" / "app.py").write_text("changed\n", encoding="utf-8")
        restore_backup(root, 1)
        restored = (root / "src" / "app.py").read_text(encoding="utf-8")
        record("backup:restore", restored == "print('ok')\n", "restore ok")

        create_backup(root, 2)
        create_backup(root, 2)
        record("backup:rotate", len(list_backups(root)) == 2, f"count={len(list_backups(root))}")

    passed = sum(1 for _, ok, _ in results if ok)
    for name, ok, detail in results:
        print(f"{'OK' if ok else 'FAIL'}: {name} - {detail}")
    print(f"{passed}/{len(results)} tests passed")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())

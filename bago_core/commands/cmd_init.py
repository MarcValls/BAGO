#!/usr/bin/env python3
"""cmd_init.py -- Initialize a BAGO project by seeding .bago/ from the canonical template."""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

BAGO_ROOT = Path(__file__).resolve().parents[2]

# Canonical files and directories that must be present in every BAGO project.
DOT_BAGO_SEED_DIRS = [
    "AGENT_START.md",
    "BOOTSTRAP.md",
    "START_AGENT.md",
    "agents",
    "api",
    "chat",
    "core",
    "keybinds.json",
    "mcp",
    "prompts",
    "providers",
    "roles",
    "templates",
    "tools",
    "workflows",
]

# Optional project-specific overrides that are only seeded when requested.
OPTIONAL_SEED_DIRS = [
    "knowledge",
    "extensions",
]

# Patterns that must never be copied from a live .bago/ tree into a new project.
SEED_SKIP_NAMES = {
    "__pycache__",
    "state",
    "logs",
    "launch",
    "credentials.json",
    "config.json",
    "session-credentials.json",
    "monitor",
}
SEED_SKIP_SUFFIXES = (".pyc", ".pyo", ".db", ".sqlite", ".sqlite3", ".tmp", ".bak")


def _resolve_source() -> Path:
    """Find the canonical seed source.

    Preferred order:
      1. bago_core/templates/dot-bago (future master template)
      2. .bago in the source/install tree (current fallback)
    """
    template = BAGO_ROOT / "bago_core" / "templates" / "dot-bago"
    if template.exists():
        return template
    runtime = BAGO_ROOT / ".bago"
    if runtime.exists():
        return runtime
    raise RuntimeError("No se encontro la semilla canonica de .bago")


def _should_copy(path: Path) -> bool:
    if path.name in SEED_SKIP_NAMES:
        return False
    if path.suffix in SEED_SKIP_SUFFIXES:
        return False
    return True


def _copy_tree_filtered(
    src: Path,
    dst: Path,
    target_root: Path,
    dry_run: bool,
) -> tuple[list[str], list[str]]:
    """Copy a directory tree while skipping runtime/compiled artifacts.

    Returns (created_dirs, created_files) relative to the project target.
    """
    created_dirs: list[str] = []
    created_files: list[str] = []

    for root, dirs, files in src.resolve().walk(top_down=True):
        rel_root = root.relative_to(src)
        dst_root = dst / rel_root

        # Filter directories in-place so os.walk does not descend into skipped paths
        dirs[:] = [d for d in dirs if _should_copy(Path(d))]

        for d in dirs:
            d_dst = dst_root / d
            rel = d_dst.relative_to(target_root)
            if dry_run or not d_dst.exists():
                created_dirs.append(str(rel))
            if not dry_run:
                d_dst.mkdir(parents=True, exist_ok=True)

        for f in files:
            src_file = root / f
            if not _should_copy(src_file):
                continue
            dst_file = dst_root / f
            rel = dst_file.relative_to(target_root)
            if dst_file.exists():
                continue
            created_files.append(str(rel))
            if not dry_run:
                dst_file.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src_file, dst_file)

    return created_dirs, created_files


def _seed_project(
    target: Path,
    source: Path,
    dry_run: bool = False,
    force: bool = False,
    with_knowledge: bool = False,
) -> dict[str, list[str]]:
    target = target.resolve()
    bago_dir = target / ".bago"
    if not dry_run:
        bago_dir.mkdir(parents=True, exist_ok=True)

    created_dirs: list[str] = []
    created_files: list[str] = []
    skipped: list[str] = []

    seed_list = list(DOT_BAGO_SEED_DIRS)
    if with_knowledge:
        seed_list += OPTIONAL_SEED_DIRS

    for seed_name in seed_list:
        src = source / seed_name
        if not src.exists():
            continue
        dst = bago_dir / seed_name

        if dst.exists() and not force:
            skipped.append(str(dst.relative_to(target)))
            continue

        if src.is_dir():
            dirs, files = _copy_tree_filtered(src, dst, target, dry_run)
            created_dirs.extend(dirs)
            created_files.extend(files)
        else:
            rel = dst.relative_to(target)
            created_files.append(str(rel))
            if not dry_run:
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)

    # Runtime state: prefer state.example if it exists; otherwise create empty dirs.
    state_example = source / "state.example"
    state_dst = bago_dir / "state"
    if state_example.exists() and (force or not state_dst.exists()):
        if dry_run:
            created_dirs.append(str(state_dst.relative_to(target)))
        else:
            if state_dst.exists():
                shutil.rmtree(state_dst)
            shutil.copytree(state_example, state_dst)
            created_dirs.append(str(state_dst.relative_to(target)))
    elif not state_dst.exists():
        rel = state_dst.relative_to(target)
        created_dirs.append(str(rel))
        if not dry_run:
            state_dst.mkdir(parents=True, exist_ok=True)
            (state_dst / "sessions").mkdir(exist_ok=True)
            (state_dst / "evidences").mkdir(exist_ok=True)
            (state_dst / "changes").mkdir(exist_ok=True)

    logs_dst = bago_dir / "logs"
    if not logs_dst.exists():
        rel = logs_dst.relative_to(target)
        created_dirs.append(str(rel))
        if not dry_run:
            logs_dst.mkdir(parents=True, exist_ok=True)

    return {
        "created_dirs": sorted(set(created_dirs)),
        "created_files": sorted(set(created_files)),
        "skipped": sorted(set(skipped)),
    }


def cmd_init(args: argparse.Namespace) -> int:
    target = Path(getattr(args, "target", "") or Path.cwd()).resolve()
    source = _resolve_source()
    report = _seed_project(
        target,
        source,
        dry_run=getattr(args, "dry_run", False),
        force=getattr(args, "force", False),
        with_knowledge=getattr(args, "with_knowledge", False),
    )

    mode = "[DRY-RUN] " if getattr(args, "dry_run", False) else ""
    print(f"{mode}BAGO project seed")
    print(f"  source: {source}")
    print(f"  target: {target / '.bago'}")
    print(f"  created directories: {len(report['created_dirs'])}")
    for d in report["created_dirs"]:
        print(f"    + {d}")
    print(f"  created files: {len(report['created_files'])}")
    for f in report["created_files"]:
        print(f"    + {f}")
    if report["skipped"]:
        print(f"  skipped (already exist, use --force to overwrite): {len(report['skipped'])}")
        for s in report["skipped"]:
            print(f"    ~ {s}")
    return 0

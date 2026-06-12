#!/usr/bin/env python3
"""
publish_release.py - BAGO release battery script.

Produces a local release summary by default and can build a zip artifact on demand.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import zipfile
from pathlib import Path

from package_v4 import build_package


EXCLUDE_DIRS = {
    ".git",
    "__pycache__",
    ".pytest_cache",
    "node_modules",
    "dist",
}

EXCLUDE_PATH_PARTS = {
    ".bago/state",
    ".bago\\state",
}


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _git_output(*args: str, cwd: Path | None = None) -> str:
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=str(cwd or _repo_root()),
            capture_output=True,
            text=True,
            shell=False,
            timeout=15,
        )
    except Exception:
        return ""
    if result.returncode != 0:
        return ""
    return (result.stdout or "").strip()


def _is_excluded(relative_path: Path) -> bool:
    parts = [part.lower() for part in relative_path.parts]
    if any(part in EXCLUDE_DIRS for part in parts):
        return True
    rel_text = str(relative_path).replace("/", "\\")
    return any(part.lower() in rel_text.lower() for part in EXCLUDE_PATH_PARTS)


def build_release_bundle(output_dir: str | None = None, repo_root: str | Path | None = None) -> Path:
    root = Path(repo_root).resolve() if repo_root is not None else _repo_root()
    out_dir = Path(output_dir).resolve() if output_dir else root / "dist"
    version = (root / "release_version.txt").read_text(encoding="utf-8").strip()
    return Path(build_package(root, out_dir, release_version=version)["zip"])


def release_summary(repo_root: str | Path | None = None) -> str:
    root = Path(repo_root).resolve() if repo_root is not None else _repo_root()
    branch = _git_output("rev-parse", "--abbrev-ref", "HEAD", cwd=root) or "(no git)"
    commit = _git_output("rev-parse", "--short", "HEAD", cwd=root) or "(no commit)"
    status = _git_output("status", "--short", cwd=root)
    dirty_lines = [line for line in status.splitlines() if line.strip()] if status else []
    lines = [
        f"Repo: {root}",
        f"Branch: {branch}",
        f"Commit: {commit}",
        f"Working tree: {'dirty' if dirty_lines else 'clean'}",
        f"Dirty files: {len(dirty_lines)}",
    ]
    if dirty_lines:
        lines.append("Changes:")
        lines.extend(f"  {line}" for line in dirty_lines[:20])
    return "\n".join(lines)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Prepare or build a local release bundle.")
    parser.add_argument("--mode", choices=("summary", "build"), default="summary")
    parser.add_argument("--output-dir", default="", help="Where to place the zip bundle")
    return parser


def _run_tests() -> int:
    from tempfile import TemporaryDirectory

    with TemporaryDirectory() as td:
        root = Path(td)
        (root / "README.md").write_text("BAGO 4.5.0", encoding="utf-8")
        (root / "release_version.txt").write_text("4.5.0\n", encoding="utf-8")
        (root / "versions.json").write_text('{"current":"4.5.0"}', encoding="utf-8")
        (root / "package.json").write_text('{"version":"4.5.0"}', encoding="utf-8")
        (root / "bago_core" / "tags").mkdir(parents=True)
        (root / "bago_core" / "tags" / "v4.5.0.json").write_text(
            '{"version":"4.5.0"}', encoding="utf-8"
        )
        (root / ".git").mkdir()
        (root / ".bago").mkdir()
        (root / ".bago" / "state").mkdir(parents=True)
        bundle = build_release_bundle(output_dir=str(root / "dist"), repo_root=root)
        assert bundle.exists()
        with zipfile.ZipFile(bundle, "r") as zf:
            names = zf.namelist()
            assert "README.md" in names
            assert ".bago/state" not in "\n".join(names)
    print("publish_release.py --test: ALL PASS")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        if args.mode == "summary":
            print(release_summary())
            return 0
        bundle = build_release_bundle(output_dir=args.output_dir or None)
        print(release_summary())
        print(f"Bundle: {bundle}")
        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    if "--test" in sys.argv:
        raise SystemExit(_run_tests())
    raise SystemExit(main())

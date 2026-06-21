#!/usr/bin/env python3
"""
publish_release.py - BAGO release battery script.

Produces a local release summary by default and can build a zip artifact on demand.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import subprocess
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path


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


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 16), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_release_bundle(output_dir: str | None = None, repo_root: str | Path | None = None) -> Path:
    root = Path(repo_root).resolve() if repo_root is not None else _repo_root()
    out_dir = Path(output_dir).resolve() if output_dir else root / "dist"
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    zip_path = out_dir / f"bago-release-{stamp}.zip"

    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for file_path in root.rglob("*"):
            if not file_path.is_file():
                continue
            relative = file_path.relative_to(root)
            if _is_excluded(relative):
                continue
            zf.write(file_path, arcname=str(relative))
    zip_sha256 = _sha256_file(zip_path)
    zip_path.with_suffix(zip_path.suffix + ".sha256").write_text(
        f"{zip_sha256}  {zip_path.name}\n",
        encoding="utf-8",
    )
    return zip_path


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
        (root / "keep.txt").write_text("ok", encoding="utf-8")
        (root / ".git").mkdir()
        (root / ".bago").mkdir()
        (root / ".bago" / "state").mkdir(parents=True)
        old_cwd = Path.cwd()
        try:
            os.chdir(root)
            bundle = build_release_bundle(output_dir=str(root / "dist"), repo_root=root)
            assert bundle.exists()
            assert (bundle.with_suffix(bundle.suffix + ".sha256")).exists()
            with zipfile.ZipFile(bundle, "r") as zf:
                names = zf.namelist()
                assert "keep.txt" in names
                assert ".bago/state" not in "\n".join(names)
        finally:
            os.chdir(old_cwd)
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

#!/usr/bin/env python3
"""knowledge_sync.py — sincroniza la memoria canónica de BAGO con su repo Git.

Contrato:
  - runtime:  .bago/knowledge
  - repo:     clon local de MarcValls/bago-knowledge
  - layout:   README.md, manifest.json, topics/, examples/, schemas/, assets/

Uso:
  python knowledge_sync.py status
  python knowledge_sync.py pull
  python knowledge_sync.py sync
  python knowledge_sync.py sync --repo C:\\path\\to\\bago-knowledge

Por defecto, `sync` hace pull si el runtime no tiene knowledge montado; si ya
existe un runtime con manifest, copia runtime -> repo y hace commit/push.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess as sp
import sys
from pathlib import Path
from typing import Iterable

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

_HERE = Path(__file__).resolve()
_TOOLS = _HERE.parent
_BAGO = _TOOLS.parent
_RUNTIME_KNOWLEDGE = _BAGO / "knowledge"
_DEFAULT_REPO_NAME = "bago-knowledge"

_DEFAULT_CANONICAL = [
    "README.md",
    "manifest.json",
    "topics/index.md",
    "topics/image-generation.md",
    "topics/transposition.md",
    "topics/knowledge-curation.md",
    "topics/release-gates.md",
    "topics/project-patterns.md",
    "topics/learned-lessons.md",
    "topics/sync-protocol.md",
    "examples/",
    "schemas/",
    "assets/",
]


def _read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _manifest_roots() -> list[Path]:
    roots = [_RUNTIME_KNOWLEDGE]
    repo_candidate = _find_repo_root(None)
    if repo_candidate and repo_candidate not in roots:
        roots.append(repo_candidate)
    return roots


def _canonical_entries() -> list[str]:
    for root in _manifest_roots():
        manifest = _read_json(root / "manifest.json")
        sync = manifest.get("sync", {})
        paths = sync.get("canonical_paths")
        if paths:
            return [str(p).replace("\\", "/").strip() for p in paths if str(p).strip()]
        knowledge = manifest.get("knowledge", {})
        layout = knowledge.get("canonical_layout")
        if layout:
            return [str(p).replace("\\", "/").strip() for p in layout if str(p).strip()]
    return list(_DEFAULT_CANONICAL)


def _find_repo_root(explicit: str | None) -> Path | None:
    candidates: list[Path] = []
    if explicit:
        candidates.append(Path(explicit).expanduser())

    env_repo = os.environ.get("BAGO_KNOWLEDGE_REPO", "").strip()
    if env_repo:
        candidates.append(Path(env_repo).expanduser())

    candidates.extend([
        Path.home() / _DEFAULT_REPO_NAME,
        _BAGO.parent / _DEFAULT_REPO_NAME,
        Path.cwd() / _DEFAULT_REPO_NAME,
    ])

    seen: set[str] = set()
    for cand in candidates:
        try:
            resolved = cand.resolve()
        except Exception:
            resolved = cand
        key = str(resolved).lower()
        if key in seen:
            continue
        seen.add(key)
        if (resolved / ".git").exists() and (resolved / "manifest.json").exists():
            return resolved
    return None


def _git(repo: Path, args: list[str], *, check: bool = False) -> sp.CompletedProcess[str]:
    return sp.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=check,
    )


def _current_branch(repo: Path) -> str:
    result = _git(repo, ["rev-parse", "--abbrev-ref", "HEAD"])
    branch = result.stdout.strip()
    return branch if branch and branch != "HEAD" else "main"


def _copy_file(src: Path, dst: Path) -> int:
    if not src.exists() or not src.is_file():
        return 0
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    return 1


def _copy_tree(src: Path, dst: Path) -> int:
    if not src.exists():
        return 0
    copied = 0
    if src.is_file():
        return _copy_file(src, dst)
    for item in src.rglob("*"):
        rel = item.relative_to(src)
        target = dst / rel
        if item.is_dir():
            target.mkdir(parents=True, exist_ok=True)
            continue
        copied += _copy_file(item, target)
    return copied


def _copy_canonical(src_root: Path, dst_root: Path, entries: Iterable[str]) -> int:
    copied = 0
    for rel in entries:
        rel_path = Path(rel)
        src = src_root / rel_path
        dst = dst_root / rel_path
        if rel.endswith("/") or src.is_dir():
            copied += _copy_tree(src, dst)
        else:
            copied += _copy_file(src, dst)
    return copied


def _collect_present(root: Path, entries: Iterable[str]) -> set[str]:
    found: set[str] = set()
    for rel in entries:
        rel_path = Path(rel)
        src = root / rel_path
        if rel.endswith("/") or src.is_dir():
            if not src.exists():
                continue
            for item in src.rglob("*"):
                if item.is_file():
                    found.add(item.relative_to(root).as_posix())
        elif src.is_file():
            found.add(rel_path.as_posix())
    return found


def _status(runtime_root: Path, repo_root: Path) -> int:
    entries = _canonical_entries()
    runtime_files = _collect_present(runtime_root, entries)
    repo_files = _collect_present(repo_root, entries)

    missing_in_repo = sorted(runtime_files - repo_files)
    missing_in_runtime = sorted(repo_files - runtime_files)

    print(f"Runtime knowledge: {runtime_root}")
    print(f"Repo knowledge:    {repo_root}")
    print(f"Canonical entries: {len(entries)}")
    print(f"Runtime files:     {len(runtime_files)}")
    print(f"Repo files:        {len(repo_files)}")
    print(f"Missing in repo:   {len(missing_in_repo)}")
    print(f"Missing in runtime:{len(missing_in_runtime)}")

    if missing_in_repo:
        print("\nMissing in repo:")
        for rel in missing_in_repo[:20]:
            print(f"  - {rel}")
    if missing_in_runtime:
        print("\nMissing in runtime:")
        for rel in missing_in_runtime[:20]:
            print(f"  - {rel}")

    return 0


def _git_sync(repo_root: Path, *, commit_prefix: str) -> int:
    branch = _current_branch(repo_root)
    remote = _git(repo_root, ["remote", "get-url", "origin"])
    has_origin = remote.returncode == 0 and bool(remote.stdout.strip())

    if has_origin:
        _git(repo_root, ["pull", "--rebase", "--autostash", "origin", branch])

    status = _git(repo_root, ["status", "--porcelain"])
    if not status.stdout.strip():
        print("Repo clean: no hay cambios para commit/push.")
        return 0

    _git(repo_root, ["add", "-A"])
    msg = f"{commit_prefix} {branch}".strip()
    commit = _git(repo_root, ["commit", "-m", msg])
    if commit.returncode != 0 and "nothing to commit" not in (commit.stdout + commit.stderr).lower():
        print(commit.stdout or commit.stderr)
        return commit.returncode

    if has_origin:
        push = _git(repo_root, ["push", "origin", branch])
        if push.returncode != 0:
            print(push.stdout or push.stderr)
            return push.returncode
        print(f"Push OK -> origin/{branch}")
    else:
        print("Repositorio sin origin: commit local realizado.")
    return 0


def cmd_pull(runtime_root: Path, repo_root: Path) -> int:
    entries = _canonical_entries()
    copied = _copy_canonical(repo_root, runtime_root, entries)
    print(f"Pulled {copied} archivos desde repo -> runtime")
    return 0


def cmd_push(runtime_root: Path, repo_root: Path) -> int:
    entries = _canonical_entries()
    copied = _copy_canonical(runtime_root, repo_root, entries)
    print(f"Pushed {copied} archivos desde runtime -> repo")
    return _git_sync(repo_root, commit_prefix="sync: bago-knowledge")


def cmd_sync(runtime_root: Path, repo_root: Path) -> int:
    if not (runtime_root / "manifest.json").exists() and (repo_root / "manifest.json").exists():
        return cmd_pull(runtime_root, repo_root)
    return cmd_push(runtime_root, repo_root)


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else list(argv)
    parser = argparse.ArgumentParser(description="Sincroniza el knowledge canónico de BAGO")
    parser.add_argument("action", nargs="?", default="sync", choices=["status", "pull", "push", "sync"])
    parser.add_argument("--repo", dest="repo_root", default="", help="Ruta local al repo bago-knowledge")
    parsed = parser.parse_args(args)

    repo_root = _find_repo_root(parsed.repo_root)
    if repo_root is None:
        print("No se encontró el repo local bago-knowledge.")
        print("Define BAGO_KNOWLEDGE_REPO o usa --repo <ruta>.")
        return 1

    runtime_root = _RUNTIME_KNOWLEDGE
    runtime_root.mkdir(parents=True, exist_ok=True)

    if parsed.action == "status":
        return _status(runtime_root, repo_root)
    if parsed.action == "pull":
        return cmd_pull(runtime_root, repo_root)
    if parsed.action == "push":
        return cmd_push(runtime_root, repo_root)
    if parsed.action == "sync":
        return cmd_sync(runtime_root, repo_root)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())


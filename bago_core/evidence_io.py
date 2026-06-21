#!/usr/bin/env python3
"""FASE 9.2: file IO helpers for the contract evidence bundle.

This module owns every filesystem operation the bundle generator needs.
Everything here is pure IO + digest + path manipulation. Nothing here
should ever import the model, the orchestrator, or the REPL executor.

R0-R10:
- R0: <250 lines, no business logic.
- R1: low layer. Imported by `bago_core.evidence_generator`.
- R8: no `print()`; only `_write_*` side-effects.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def now_iso() -> str:
    """UTC ISO8601 timestamp used in manifest + objective files (R5 SSoT)."""
    return datetime.now(timezone.utc).isoformat()


def write_json(path: Path, payload: Any) -> None:
    """Write a JSON file with UTF-8 + indent=2 + ensure_ascii=False (R0)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
        newline="\n",
    )


def write_text(path: Path, content: str) -> None:
    """Write a plain-text file with UTF-8 (R0)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="\n")


def sha256(path: Path) -> str:
    """Hex SHA-256 of a file, streamed in 64 KiB chunks."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def copy_if_exists(source: Path, target: Path) -> bool:
    """Copy a file only if the source exists; return whether it was copied."""
    if not source.exists():
        return False
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    return True


def prepare_output_dir(output_dir: Path, overwrite: bool) -> None:
    """Reset the output dir if requested; raise if it exists and not overwriting."""
    if output_dir.exists():
        if not overwrite:
            raise FileExistsError(
                f"El directorio ya existe: {output_dir}"
            )
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)


def _relative_posix(path: Path, base: Path) -> str:
    """Return `path` relative to `base` using portable POSIX separators."""
    return path.relative_to(base).as_posix()


def collect_file_digests(
    output_dir: Path,
    *,
    exclude: set[str] | frozenset[str] = frozenset(),
) -> list[dict[str, Any]]:
    """SHA-256 + size for every file under `output_dir` (R8)."""
    files: list[dict[str, Any]] = []
    for path in sorted(output_dir.rglob("*")):
        if not path.is_file():
            continue
        relative = _relative_posix(path, output_dir)
        if relative in exclude:
            continue
        files.append({
            "path": relative,
            "sha256": sha256(path),
            "size_bytes": path.stat().st_size,
        })
    return files


def write_checksums(output_dir: Path, files: list[dict[str, Any]]) -> None:
    """Write the `checksums.sha256` file in sha256sum format (R8)."""
    lines = [
        f"{entry['sha256']} *{entry['path']}"
        for entry in files
        if entry["path"] != "checksums.sha256"
    ]
    write_text(
        output_dir / "checksums.sha256",
        "\n".join(lines) + ("\n" if lines else ""),
    )


def copy_session_artifacts(
    base_path: Path, session_id: str, output_dir: Path,
) -> list[str]:
    """Copy the persistent session artifacts into the bundle (R1, R8)."""
    override = os.environ.get("BAGO_STATE_ROOT", "").strip()
    state_root = Path(override).expanduser().resolve() if override else None
    candidates = [
        state_root if state_root is not None else base_path / ".bago" / "state",
        base_path / ".bago" / "state",
        Path.home() / ".bago" / "state",
    ]
    copied: list[str] = []

    for candidate in candidates:
        state_dir = candidate / "sessions"
        session_dir = state_dir / session_id
        for name in ("context.jsonl", "timeline.jsonl", "tokens.json", "meta.json"):
            target = output_dir / "session" / name
            if copy_if_exists(session_dir / name, target):
                copied.append(_relative_posix(target, output_dir))

        session_meta = state_dir / f"{session_id}.json"
        target = output_dir / "session" / "session.json"
        if copy_if_exists(session_meta, target):
            copied.append(_relative_posix(target, output_dir))
        if copied:
            break

    return copied

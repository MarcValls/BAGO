"""Shared, side-effect-free primitives for BAGO release packaging."""

from __future__ import annotations

import hashlib
from pathlib import Path


def rel_posix(path: Path) -> str:
    return path.as_posix()


def normalize_release_version(value: str) -> str:
    normalized = str(value or "").strip().lower().removeprefix("v")
    if not normalized:
        raise ValueError("release_version vacío")
    allowed = set("abcdefghijklmnopqrstuvwxyz0123456789.-")
    if any(ch not in allowed for ch in normalized):
        raise ValueError(f"release_version inválido: {value}")
    return normalized


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()

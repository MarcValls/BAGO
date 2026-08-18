from __future__ import annotations

from pathlib import Path
from typing import Iterable

from .roots import framework_root


def resolve_candidates(candidates: Iterable[str]) -> tuple[Path, str]:
    base = framework_root()
    first_path: Path | None = None
    first_candidate = ""
    for raw in candidates:
        candidate = _resolve_candidate(base, raw)
        if first_path is None:
            first_path = candidate
            first_candidate = raw
        if candidate.exists():
            return candidate, raw
    if first_path is None:
        raise FileNotFoundError("resolver received no candidates")
    return first_path, first_candidate


def _resolve_candidate(base: Path, raw: str) -> Path:
    candidate = Path(raw)
    if candidate.is_absolute():
        return candidate
    text = raw.strip()
    if text.startswith("~"):
        return Path(text).expanduser().resolve()
    return (base / candidate).resolve()

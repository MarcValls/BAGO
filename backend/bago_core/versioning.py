from __future__ import annotations

import json
from datetime import date
from pathlib import Path


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _candidate_release_files(root: Path) -> list[Path]:
    return [
        root / "release_version.txt",
        root / ".gabo" / "release_version.txt",
    ]


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def _load_versions_json(root: Path) -> dict:
    versions_path = root / "versions.json"
    try:
        return json.loads(versions_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def read_release_version(root: Path | None = None) -> str:
    resolved = (root or repo_root()).resolve()
    for candidate in _candidate_release_files(resolved):
        value = _read_text(candidate)
        if value:
            return value.lstrip("vV").strip()
    data = _load_versions_json(resolved)
    current = data.get("current", "")
    return current.strip() if isinstance(current, str) else ""


def current(root: Path | None = None) -> str:
    return read_release_version(root)


def history(root: Path | None = None) -> list[dict]:
    data = _load_versions_json((root or repo_root()).resolve())
    history_data = data.get("history", [])
    return history_data if isinstance(history_data, list) else []


def at_date(date_str: str, root: Path | None = None) -> str:
    target = date.fromisoformat(date_str)
    history_data = history(root)
    for entry in reversed(history_data):
        try:
            released = date.fromisoformat(str(entry.get("released", "")))
        except ValueError:
            continue
        if target >= released:
            version = entry.get("version", "")
            if isinstance(version, str) and version.strip():
                return version.strip()
    if history_data:
        version = history_data[0].get("version", "")
        if isinstance(version, str) and version.strip():
            return version.strip()
    return current(root)

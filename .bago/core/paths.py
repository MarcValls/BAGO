"""Central path helpers for BAGO."""

from __future__ import annotations

import sys
from pathlib import Path


def is_frozen_app() -> bool:
    """Return True when the process runs as a frozen app."""
    return bool(getattr(sys, "frozen", False))


def source_base_dir() -> Path:
    """Return the repository root when running from source."""
    return Path(__file__).resolve().parents[2]


def app_base_dir() -> Path:
    """Return the operational app root."""
    if is_frozen_app():
        return Path(sys.executable).resolve().parent
    return source_base_dir()


def bundle_base_dir() -> Path:
    """Return the bundled resource root when available."""
    if is_frozen_app():
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            return Path(str(meipass)).resolve()
    return source_base_dir()


def resource_path(*parts: object) -> Path:
    """Build a path to a bundled resource or source-tree asset."""
    cleaned = [str(part) for part in parts if str(part)]
    return bundle_base_dir().joinpath(*cleaned)


def external_program_path(source_name: str, frozen_name: str | None = None) -> Path:
    """Build the path to a helper program next to the app."""
    if is_frozen_app():
        return app_base_dir() / str(frozen_name or source_name)
    return app_base_dir() / str(source_name)

"""Resolucion de la carpeta externa de modelos Ollama."""

from __future__ import annotations

import os
import string
import sys
from pathlib import Path
from typing import Iterable

os.environ.setdefault("PYTHONUTF8", "1")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from .constants import BAGO_DIR, BAGO_REPO_ROOT


_MODEL_DIR_NAMES = (".models", "models")
_DEFAULT_OLLAMA_MODELS_DIR_ENV = "BAGO_OLLAMA_MODELS_DIR"


def _is_framework_path(path: Path) -> bool:
    try:
        resolved = path.resolve()
    except Exception:
        resolved = path
    try:
        return resolved.is_relative_to(BAGO_DIR) or resolved.is_relative_to(BAGO_REPO_ROOT)
    except Exception:
        text = str(resolved).lower()
        return str(BAGO_DIR).lower() in text or str(BAGO_REPO_ROOT).lower() in text


def _looks_like_ollama_store(path: Path) -> bool:
    blobs = path / "blobs"
    manifests = path / "manifests"
    if not blobs.exists() and not manifests.exists():
        return False
    for section in (blobs, manifests):
        try:
            for item in section.iterdir():
                if item.is_file():
                    return True
                if item.is_dir():
                    for nested in item.rglob("*"):
                        if nested.is_file():
                            return True
        except Exception:
            continue
    return False


def _default_ollama_models_dir() -> Path:
    raw = os.environ.get(_DEFAULT_OLLAMA_MODELS_DIR_ENV, "").strip()
    if raw:
        try:
            return Path(raw).expanduser().resolve()
        except Exception:
            return Path(raw).expanduser()
    return (Path.home() / ".ollama" / "models").expanduser()


def _windows_drive_type(path: Path) -> int | None:
    if os.name != "nt":
        return None
    try:
        import ctypes

        anchor = path.anchor or ""
        if not anchor and path.drive:
            anchor = f"{path.drive}\\"
        if anchor and not anchor.endswith("\\"):
            anchor += "\\"
        if not anchor:
            return None
        return int(ctypes.windll.kernel32.GetDriveTypeW(anchor))
    except Exception:
        return None


def _is_removable_path(path: Path) -> bool:
    return _windows_drive_type(path) == 2


def _copy_file_if_needed(source: Path, target: Path) -> bool:
    import shutil

    try:
        src_stat = source.stat()
    except Exception:
        return False
    try:
        dst_stat = target.stat()
    except Exception:
        dst_stat = None
    if dst_stat is not None and src_stat.st_size == dst_stat.st_size and int(src_stat.st_mtime) <= int(dst_stat.st_mtime):
        return False
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    return True


def sync_ollama_models_to_disk(source_dir: Path, target_dir: Path | None = None) -> Path:
    """Copia la tienda Ollama a una ruta fija en disco duro fuera del framework."""
    source = Path(source_dir).expanduser()
    target = Path(target_dir).expanduser() if target_dir is not None else _default_ollama_models_dir()
    try:
        source = source.resolve()
    except Exception:
        pass
    try:
        target = target.resolve()
    except Exception:
        pass
    if source == target:
        return target
    if not source.exists():
        return target

    target.mkdir(parents=True, exist_ok=True)
    for item in source.rglob("*"):
        try:
            rel = item.relative_to(source)
        except Exception:
            continue
        dst = target / rel
        if item.is_dir():
            dst.mkdir(parents=True, exist_ok=True)
            continue
        if not item.is_file():
            continue
        _copy_file_if_needed(item, dst)
    return target


def _candidate_dirs_for_root(root: Path) -> list[Path]:
    return [root / name for name in _MODEL_DIR_NAMES]


def _filesystem_roots() -> list[Path]:
    roots: list[Path] = []
    if os.name == "nt":
        for letter in string.ascii_uppercase:
            root = Path(f"{letter}:/")
            if root.exists():
                roots.append(root)
        return roots
    roots.extend([Path("/Volumes"), Path.home(), Path("/media"), Path("/run/media")])
    return [root for root in roots if root.exists()]


def _ordered_roots(root_paths: Iterable[Path] | None = None) -> list[Path]:
    roots = list(root_paths) if root_paths is not None else _filesystem_roots()
    primary: list[Path] = []
    secondary: list[Path] = []
    for root in roots:
        if not root:
            continue
        try:
            resolved = root.resolve()
        except Exception:
            resolved = root
        if _is_framework_path(resolved):
            secondary.append(resolved)
        else:
            primary.append(resolved)
    return primary + secondary


def resolve_ollama_models_dir(root_paths: Iterable[Path] | None = None) -> Path | None:
    """Devuelve una carpeta externa de modelos, fuera del framework.

    Prioridad:
    1. Ruta Ollama estándar en disco duro si ya tiene tienda válida.
    2. `OLLAMA_MODELS` si apunta a una ruta externa válida.
    3. Siblings `.models` / `models` junto a las raices del sistema.
    4. Ruta externa con estructura real de Ollama (`blobs` / `manifests`).
    """
    disk_target = _default_ollama_models_dir()
    if disk_target.exists() and _looks_like_ollama_store(disk_target):
        return disk_target.resolve()

    env = os.environ.get("OLLAMA_MODELS", "").strip()
    if env:
        try:
            env_path = Path(env).expanduser()
            if env_path.exists() and not _is_framework_path(env_path):
                if _is_removable_path(env_path):
                    return sync_ollama_models_to_disk(env_path, disk_target)
                return env_path.resolve()
        except Exception:
            pass

    fallback: Path | None = None
    for root in _ordered_roots(root_paths):
        for candidate in _candidate_dirs_for_root(root):
            if not candidate.exists() or _is_framework_path(candidate):
                continue
            try:
                resolved = candidate.resolve()
            except Exception:
                resolved = candidate
            if _looks_like_ollama_store(candidate):
                if _is_removable_path(resolved):
                    return sync_ollama_models_to_disk(resolved, disk_target)
                return resolved
            if fallback is None:
                fallback = resolved

    return fallback


def ensure_ollama_models_env(root_paths: Iterable[Path] | None = None) -> Path | None:
    """Fija `OLLAMA_MODELS` si se encuentra una ruta externa válida."""
    resolved = resolve_ollama_models_dir(root_paths=root_paths)
    if resolved is not None:
        os.environ["OLLAMA_MODELS"] = str(resolved)
    return resolved

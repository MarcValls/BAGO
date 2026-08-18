"""scope_validator.py — validación de rutas contra `workspace_scope_root`.

Reglas:
    - Toda ruta debe resolver bajo `workspace_scope_root` (canónico).
    - Symlinks, junctions, ADS y rutas UNC son rechazadas si escapan
      del scope o si la plataforma no permite resolverlas de forma
      segura.
    - En Windows se aplica `os.path.normcase` para evitar escapes por
      cambio de mayúsculas.
    - Se detecta TOCTOU re-`stat` antes de cualquier uso.

Esta es la versión Python del sidecar. El sidecar Node/TS debe
replicar exactamente la misma lógica; la paridad se cubre con el test
`test_sidecar_contract`.
"""
from __future__ import annotations

import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from .errors import (
    ScopeLinkEscapeDenied,
    ScopePathDenied,
    ScopeReadDenied,
    ScopeToctouDetected,
)


_DRIVE_LETTER_RE = re.compile(r"^[A-Za-z]:[\\/]")
_UNC_RE = re.compile(r"^[/\\]{2}[^\\/]+[/\\]")


@dataclass(frozen=True)
class ResolvedPath:
    raw: str
    canonical: str
    inside_scope: bool
    is_symlink: bool
    on_ancestor_symlink: bool
    exists: bool

    def to_dict(self) -> dict[str, str | bool]:
        return {
            "raw": self.raw,
            "canonical": self.canonical,
            "inside_scope": self.inside_scope,
            "is_symlink": self.is_symlink,
            "on_ancestor_symlink": self.on_ancestor_symlink,
            "exists": self.exists,
        }


def _is_windows() -> bool:
    return sys.platform.startswith("win")


def _norm_case(path: str) -> str:
    if _is_windows():
        return os.path.normcase(path)
    return path


def _detect_symlink_ancestor(absolute: Path) -> bool:
    current = absolute
    while True:
        if current.is_symlink():
            return True
        parent = current.parent
        if parent == current:
            return False
        current = parent


def _looks_unc_or_drive(value: str) -> bool:
    return bool(_DRIVE_LETTER_RE.match(value) or _UNC_RE.match(value))


def resolve_path(raw: str, scope_root: str) -> ResolvedPath:
    """Resuelve una ruta y determina si está dentro de `scope_root`.

    Nunca lanza `FileNotFoundError`: una ruta inexistente se reporta con
    `exists=False`. Las violaciones de scope sí lanzan excepciones.
    """
    if not raw or not isinstance(raw, str):
        raise ScopePathDenied("empty path", details={"raw": str(raw)})
    if not scope_root:
        raise ScopePathDenied("scope_root is empty")
    if os.path.isabs(raw) and _looks_unc_or_drive(raw) and not _is_windows():
        # En sistemas no-Windows, una ruta tipo `C:\` o `\\server\share`
        # sólo puede ser una inyección.
        raise ScopePathDenied("unc/drive on non-windows", details={"raw": raw})

    scope = Path(scope_root).expanduser().resolve(strict=False)
    try:
        candidate = Path(raw).expanduser()
    except (OSError, ValueError) as exc:
        raise ScopePathDenied(
            "path expansion failed",
            details={"raw": raw, "error": str(exc)},
        ) from exc

    is_absolute = candidate.is_absolute()
    if not is_absolute:
        candidate = (scope / candidate).resolve(strict=False)
    else:
        candidate = candidate.resolve(strict=False)

    canonical_scope = _norm_case(str(scope))
    canonical_candidate = _norm_case(str(candidate))
    inside = canonical_candidate == canonical_scope or canonical_candidate.startswith(
        canonical_scope + os.sep
    )

    is_symlink = candidate.is_symlink()
    on_ancestor = _detect_symlink_ancestor(candidate)

    return ResolvedPath(
        raw=raw,
        canonical=str(candidate),
        inside_scope=inside,
        is_symlink=is_symlink,
        on_ancestor_symlink=on_ancestor,
        exists=candidate.exists(),
    )


def assert_within_scope(raw: str, scope_root: str) -> ResolvedPath:
    """Resuelve y exige que la ruta esté dentro de scope.

    Lanza `ScopePathDenied` si la ruta está fuera de scope, si
    contiene un symlink/junction que escapa, o si su forma no es
    admitida.
    """
    resolved = resolve_path(raw, scope_root)
    if not resolved.inside_scope:
        raise ScopePathDenied(
            "path outside scope",
            details={"raw": resolved.raw, "scope": scope_root},
        )
    if resolved.is_symlink or resolved.on_ancestor_symlink:
        # Verificamos también el target.
        try:
            target = Path(resolved.canonical).resolve(strict=True)
        except (OSError, RuntimeError) as exc:
            raise ScopeLinkEscapeDenied(
                "symlink target unresolvable",
                details={"raw": resolved.raw, "error": str(exc)},
            ) from exc
        target_norm = _norm_case(str(target))
        if not (
            target_norm == _norm_case(scope_root)
            or target_norm.startswith(_norm_case(scope_root) + os.sep)
        ):
            raise ScopeLinkEscapeDenied(
                "symlink target escapes scope",
                details={"raw": resolved.raw, "target": str(target)},
            )
    return resolved


def verify_toctou(resolved: ResolvedPath, expected_stat: os.stat_result) -> None:
    """Re-stat del path tras la resolución; falla si cambia identidad."""
    if not resolved.exists:
        return
    try:
        current = os.stat(resolved.canonical)
    except OSError as exc:
        raise ScopeToctouDetected(
            "path disappeared after resolution",
            details={"path": resolved.canonical, "error": str(exc)},
        ) from exc
    if (current.st_dev, current.st_ino) != (expected_stat.st_dev, expected_stat.st_ino):
        raise ScopeToctouDetected(
            "path identity changed after resolution",
            details={"path": resolved.canonical},
        )


def find_violations(scope_root: str, candidates: Iterable[str]) -> list[str]:
    """Devuelve la lista de paths que caen fuera de scope."""
    bad: list[str] = []
    for raw in candidates:
        try:
            resolved = resolve_path(raw, scope_root)
        except ScopePathDenied:
            bad.append(raw)
            continue
        if not resolved.inside_scope:
            bad.append(raw)
    return bad


def deny_implicit_pi_sources(scope_root: str) -> list[str]:
    """Detecta presencia de fuentes implícitas PI dentro de scope.

    Devuelve la lista de paths prohibidos encontrados.
    """
    forbidden_names = {".pi", ".agents", ".pi-skills", "skills", "extensions"}
    forbidden: list[str] = []
    try:
        scope = Path(scope_root).resolve()
    except (OSError, RuntimeError):
        return forbidden
    if not scope.exists():
        return forbidden
    for name in forbidden_names:
        candidate = scope / name
        if candidate.exists():
            forbidden.append(str(candidate))
    return forbidden


__all__ = [
    "ResolvedPath",
    "resolve_path",
    "assert_within_scope",
    "verify_toctou",
    "find_violations",
    "deny_implicit_pi_sources",
]

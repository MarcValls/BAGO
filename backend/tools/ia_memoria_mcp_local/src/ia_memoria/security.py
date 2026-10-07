from __future__ import annotations

import os
import re
from pathlib import Path, PurePath

_PROJECT_RE = re.compile(r"^[A-Z0-9][A-Z0-9_-]{1,63}$")

class SecurityError(ValueError):
    """La ruta o el identificador viola la frontera de memoria."""

def normalize_project_id(value: str) -> str:
    project_id = value.strip().upper().replace(" ", "_")
    if not _PROJECT_RE.fullmatch(project_id):
        raise SecurityError("project_id inválido: usa 2-64 caracteres A-Z, 0-9, guion o guion bajo.")
    return project_id

def safe_resolve(root: Path, relative_path: str, *, must_exist: bool = True) -> Path:
    if not isinstance(relative_path, str) or not relative_path.strip():
        raise SecurityError("La ruta relativa no puede estar vacía.")
    text = relative_path.strip().replace("\\", "/")
    pure = PurePath(text)
    if pure.is_absolute() or re.match(r"^[A-Za-z]:", text):
        raise SecurityError("No se permiten rutas absolutas ni letras de unidad.")
    if any(part in {"..", ""} for part in pure.parts):
        raise SecurityError("No se permiten segmentos '..' ni rutas vacías.")
    root_resolved = root.resolve()
    target = (root_resolved / Path(*pure.parts)).resolve(strict=False)
    try:
        common = Path(os.path.commonpath([str(root_resolved), str(target)]))
    except ValueError as exc:
        raise SecurityError("La ruta apunta a otra raíz o unidad.") from exc
    if common != root_resolved:
        raise SecurityError("La ruta sale de la raíz autorizada.")
    if must_exist and not target.exists():
        raise FileNotFoundError(f"No existe: {relative_path}")
    return target

def ensure_allowed_extension(path: Path, allowed_extensions: frozenset[str]) -> None:
    if path.suffix.lower() not in allowed_extensions:
        raise SecurityError(f"Extensión no permitida: {path.suffix or '(sin extensión)'}")

def ensure_managed_write_location(root: Path, path: Path) -> None:
    relative = path.resolve(strict=False).relative_to(root.resolve())
    allowed = {"10_GLOBAL", "20_PROJECTS", "30_LINKS", "40_INBOX", "50_INDEX", "90_EVENTS", "99_ARCHIVE"}
    if not relative.parts or relative.parts[0] not in allowed:
        raise SecurityError("La escritura no está permitida en esa zona.")

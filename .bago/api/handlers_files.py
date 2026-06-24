"""handlers_files.py \u2014 file listing + read endpoints for the BAGO HTTP bridge.

GET /files/list              \u2014 walk the project's base_path
GET /files/read/<path>       \u2014 read a single file (UTF-8 with replace)

Both endpoints are sandboxed to `session_mgr.base_path`; the read
endpoint rejects any path that escapes that root.
"""

from __future__ import annotations
import os
from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import unquote

if TYPE_CHECKING:
    from http.server import BaseHTTPRequestHandler


_SKIP_DIRS = {"node_modules", ".git", "__pycache__", "dist", "build"}


def _mgr(handler):
    return getattr(handler, "session_mgr", None)


def handle_list(handler):
    from api_serializers import send_json
    mgr = _mgr(handler)
    if mgr is None:
        send_json(handler, 503, {"error": "SessionManager no disponible"})
        return
    base = Path(mgr.base_path).resolve()
    try:
        entries = []
        for root, dirs, files in os.walk(base):
            rel_root = Path(root).relative_to(base)
            for d in sorted(dirs):
                entries.append({
                    "path": str(rel_root / d).replace("\\", "/"),
                    "name": d,
                    "type": "directory",
                })
            for f in sorted(files):
                entries.append({
                    "path": str(rel_root / f).replace("\\", "/"),
                    "name": f,
                    "type": "file",
                })
            dirs[:] = [d for d in dirs if d not in _SKIP_DIRS]
        send_json(handler, 200, {"base_path": str(base), "entries": entries})
    except Exception as exc:
        send_json(handler, 500, {"error": f"Error listando archivos: {exc}"})


def handle_read(handler, file_path: str):
    from api_serializers import send_json
    mgr = _mgr(handler)
    if mgr is None:
        send_json(handler, 503, {"error": "SessionManager no disponible"})
        return
    base = Path(mgr.base_path).resolve()
    try:
        target = (base / unquote(file_path)).resolve()
        target.relative_to(base)
    except (ValueError, Exception):
        send_json(handler, 403, {"error": "Ruta de archivo invalida"})
        return
    if not target.is_file():
        send_json(handler, 404, {"error": "Archivo no encontrado"})
        return
    try:
        content = target.read_text(encoding="utf-8", errors="replace")
        send_json(handler, 200, {
            "path": file_path,
            "name": target.name,
            "content": content,
            "size": target.stat().st_size,
        })
    except Exception as exc:
        send_json(handler, 500, {"error": f"Error leyendo archivo: {exc}"})

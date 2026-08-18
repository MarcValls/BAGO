#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
legacy_aliases.py -- Aliases para rutas legacy/obsoletas del frontend.

Este modulo provee aliases de URLs que el bundle del frontend puede
invocar (por drift o por compatibilidad hacia atras) hacia las URLs
canonicas que el backend si implementa.

CANON[LA-001]: Mantener backwards-compatibility sin tocar el bundle.
"""

from __future__ import annotations

import re
from typing import Optional, Tuple


# Mapa de alias: (method, path_legacy) -> (method, path_canonical)
# Las redirecciones se hacen a nivel de aplicacion (no HTTP 302) para
# mantener el mismo Content-Type y los mismos headers CORS.
LEGACY_ALIASES = [
    # (method_legacy, path_legacy, method_canonical, path_canonical)

    # Audit: el frontend a veces llama /audit, debe ir a /audit/ledger
    ("GET", "/audit", "GET", "/audit/ledger"),

    # Auto-config: el frontend a veces llama /auto-config
    ("GET", "/auto-config", "GET", "/configure/auto/status"),
    ("POST", "/auto-config", "POST", "/configure/auto/status"),

    # Blacklist: el frontend a veces llama /blacklist
    ("GET", "/blacklist", "GET", "/providers/blacklist"),
    ("POST", "/blacklist", "POST", "/providers/blacklist"),

    # Contexto: el frontend a veces llama /context
    ("GET", "/context", "GET", "/workspace/status"),

    # GitHub setup: el codigo viejo usa /github/setup-git
    ("POST", "/github/setup-git", "POST", "/github/setup"),

    # Project: el frontend a veces llama /project, debe ir a /project/status
    ("GET", "/project", "GET", "/project/status"),

    # Workspace: el frontend a veces llama /workspace directo
    ("GET", "/workspace", "GET", "/workspace/status"),

    # Workspace actions: rutas duplicadas eliminadas de ROUTE_META;
    # se redirigen a los endpoints de projecto canonical.
    ("POST", "/workspace/init", "POST", "/project/init"),
    ("POST", "/workspace/link", "POST", "/project/link"),
    ("POST", "/workspace/seed", "POST", "/project/seed"),
    ("POST", "/workspace/sync", "POST", "/project/sync"),

    # Command: el endpoint legacy /command se elimino; el canonical es /api/v1/commands.
    ("POST", "/command", "POST", "/api/v1/commands"),

    # Workspaces list: /workspaces era un duplicado de /workspace/list.
    ("GET", "/workspaces", "GET", "/workspace/list"),

    # Provider buffer: /providers/buffer era un duplicado de /providers/buffer/status.
    ("GET", "/providers/buffer", "GET", "/providers/buffer/status"),

    # Interpretations: el frontend tiene 4 metodos que llaman a /interpretations/*
    # pero el backend solo tiene /interpret (POST) y /interpret/history (GET).
    # Mapeamos para mantener compat.
    ("GET", "/interpretations", "GET", "/interpret/history"),
    ("POST", "/interpretations", "POST", "/interpret"),
    ("GET", "/interpretations/{id}", "GET", "/interpret/history"),
    ("POST", "/interpretations/{id}/cancel", "POST", "/interpret"),

    # Provider buffer: el frontend usa /provider/ (singular), el backend
    # expone /providers/ (plural). Mapeamos para mantener compat.
    ("GET", "/provider/buffer/status", "GET", "/providers/buffer/status"),
    ("POST", "/provider/buffer/prepare", "POST", "/providers/buffer/prepare"),
    ("POST", "/provider/buffer/unload", "POST", "/providers/buffer/unload"),
    ("POST", "/provider/buffer/unload/{id}", "POST", "/providers/buffer/unload/{id}"),
]


def resolve_legacy_alias(method: str, path: str) -> Optional[Tuple[str, str]]:
    """Si (method, path) tiene un alias, devuelve (method_canonical, path_canonical).
    Si no, devuelve None.
    Las paths con {id} se matchean con un valor cualquiera entre /.
    """
    for m_leg, p_leg, m_can, p_can in LEGACY_ALIASES:
        if m_leg != method:
            continue
        # Convertir {id} a regex
        regex = re.escape(p_leg).replace(r"\{id\}", "[^/]+")
        if re.fullmatch(regex, path):
            return (m_can, p_can)
    return None


def handle_legacy_alias(handler, method: str, path: str, body: Optional[dict] = None) -> bool:
    """Si la ruta es un alias, hace proxy al endpoint canonico.
    Devuelve True si la ruta era un alias (y se proceso).
    Devuelve False si no era un alias (dejar que otro handler lo procese).

    CANON[LA-002]: Para POST, el body ya viene leido por do_POST().
    Para GET, simplemente cambiamos el path y re-dispatchamos.
    """
    resolved = resolve_legacy_alias(method, path)
    if resolved is None:
        return False

    m_can, p_can = resolved

    if method == "GET":
        # Re-dispatch GET: solo cambiamos el path
        original_path = handler.path
        try:
            from urllib.parse import urlparse
            parsed = urlparse(original_path)
            query = f"?{parsed.query}" if parsed.query else ""
            handler.path = f"{p_can}{query}"
            handler.do_GET()
        finally:
            handler.path = original_path
        return True

    # Para POST: el body ya fue leido por do_POST(), lo recibimos como parametro.
    # Solo necesitamos dispatchar al path canonico.
    if body is None:
        # Fallback: leer el body (no deberia pasar si do_POST() nos llamo)
        body = {}
        try:
            length = int(handler.headers.get("Content-Length", "0"))
            if length > 0 and hasattr(handler, "rfile"):
                import json
                body_bytes = handler.rfile.read(length)
                body = json.loads(body_bytes.decode("utf-8", errors="replace"))
        except Exception:
            pass

    try:
        import sys
        api_dispatch = sys.modules.get("api_dispatch")
        if api_dispatch is None:
            handler._send_json(501, {"error": "api_dispatch not loaded"})
            return True

        resolve_post = getattr(api_dispatch, "resolve_post", None)
        resolve_router = getattr(api_dispatch, "resolve_router", None)
        if resolve_post is None:
            handler._send_json(501, {"error": "resolve_post not found"})
            return True

        # Cambiar el path temporalmente
        original_path = handler.path
        try:
            from urllib.parse import urlparse
            parsed = urlparse(original_path)
            query = f"?{parsed.query}" if parsed.query else ""
            handler.path = f"{p_can}{query}"

            matched, call = resolve_post(handler, p_can, body)
            if matched:
                call(handler, body)
                return True

            if resolve_router is not None:
                matched, call = resolve_router(handler, p_can, body)
                if matched:
                    call(handler, body)
                    return True

            handler._send_json(404, {"error": f"Ruta canonica no encontrada: {p_can}"})
        finally:
            handler.path = original_path
        return True
    except Exception as exc:
        handler._send_json(502, {"error": f"Legacy alias proxy error: {exc}"})
        return True

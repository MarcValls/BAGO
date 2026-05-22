#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
workspace_selector.py — Selector de espacio de trabajo BAGO

Presenta tres opciones al iniciar:
  1. Framework (self)      — el propio directorio BAGO
  2. Directorio padre      — el directorio que contiene la instalación BAGO
  3. Ruta o repo concreto  — texto libre con ruta o URL de repo

El resultado se persiste en repo_context.json para que toda la sesión
opere sobre el workspace elegido.

Uso:
  python3 .bago/tools/workspace_selector.py
  python3 .bago/tools/workspace_selector.py --json   (salida estructurada)
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# ─── Rutas base ───────────────────────────────────────────────────────────────
BAGO_ROOT  = Path(__file__).resolve().parent.parent          # .bago/
TOOLS      = BAGO_ROOT / "tools"
HOST_ROOT  = BAGO_ROOT.parent                                # directorio raíz
STATE_PATH = BAGO_ROOT / "state" / "repo_context.json"

# ─── Colores ANSI ─────────────────────────────────────────────────────────────
USE_COLOR = sys.stdout.isatty() and "--plain" not in sys.argv

def _c(code: str, text: str) -> str:
    return f"\033[{code}m{text}\033[0m" if USE_COLOR else text

CYAN   = lambda t: _c("1;36", t)
GREEN  = lambda t: _c("1;32", t)
YELLOW = lambda t: _c("1;33", t)
BOLD   = lambda t: _c("1",    t)
DIM    = lambda t: _c("2",    t)
RED    = lambda t: _c("1;31", t)

# ─── Helpers ──────────────────────────────────────────────────────────────────

def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _load_context() -> dict:
    if STATE_PATH.exists():
        try:
            return json.loads(STATE_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _save_context(repo_root: Path, working_mode: str, note: str = "") -> dict:
    import hashlib
    try:
        top_entries = sorted(p.name for p in repo_root.iterdir() if p.name != ".bago")
    except Exception:
        top_entries = []
    payload = "\n".join([str(repo_root), str(HOST_ROOT.resolve())] + top_entries[:200])
    fingerprint = hashlib.sha256(payload.encode("utf-8")).hexdigest()

    existing = _load_context()
    ctx = {
        "bago_host_root": str(HOST_ROOT.resolve()),
        "note": note or existing.get("note", ""),
        "recorded_at": _now_iso(),
        "repo_fingerprint": fingerprint,
        "repo_root": str(repo_root),
        "role": existing.get("role", "workspace_pointer"),
        "working_mode": working_mode,
    }
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(ctx, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return ctx


def _current_label() -> str:
    """Devuelve descripción legible del workspace activo."""
    ctx = _load_context()
    mode = ctx.get("working_mode", "?")
    root = ctx.get("repo_root", "?")
    if mode == "self":
        return f"framework  ({root})"
    if mode == "parent":
        return f"padre      ({root})"
    if mode == "external":
        return f"externo    ({root})"
    return f"{mode} ({root})"


# ─── Selector interactivo ─────────────────────────────────────────────────────

MENU = """\
╔══════════════════════════════════════════════════════╗
║       BAGO · ¿Sobre qué quieres trabajar?            ║
╠══════════════════════════════════════════════════════╣
║  1. 🏠  Framework (self)                             ║
║  2. 📂  Directorio padre de esta instalación         ║
║  3. 🔗  Ruta o repositorio concreto…                 ║
║  0. ⬅  Mantener workspace actual                    ║
╚══════════════════════════════════════════════════════╝"""


def select(skip_if_set: bool = False) -> dict | None:
    """
    Muestra el selector y persiste la elección.

    Parámetros:
      skip_if_set — si True y ya hay un workspace configurado, retorna sin preguntar.

    Retorna el dict de contexto persistido, o None si el usuario eligió mantener el actual.
    """
    ctx = _load_context()

    if skip_if_set and ctx.get("working_mode") in ("self", "external", "parent"):
        return ctx

    print()
    print(CYAN(MENU))

    if ctx.get("working_mode"):
        print(DIM(f"  Workspace actual: {_current_label()}"))
        print()

    choice = input(DIM("Tu elección") + " → ").strip()

    if choice == "0":
        print(DIM("  Manteniendo workspace actual."))
        return ctx if ctx else None

    if choice == "1":
        root = HOST_ROOT.resolve()
        ctx = _save_context(root, "self", "BAGO operando en su propio directorio host (self).")
        print(GREEN("✓") + f" Workspace: {BOLD('framework')}  {DIM(str(root))}")
        return ctx

    if choice == "2":
        parent = HOST_ROOT.resolve().parent
        if not parent.exists():
            print(RED("❌") + f" El directorio padre no existe: {parent}")
            return None
        ctx = _save_context(parent, "parent",
                            "BAGO operando sobre el directorio padre de su instalación.")
        print(GREEN("✓") + f" Workspace: {BOLD('padre')}  {DIM(str(parent))}")
        return ctx

    if choice == "3":
        print()
        raw = input(CYAN("  Ruta o URL del repo") + " → ").strip()
        if not raw:
            print(YELLOW("⚠") + "  Ruta vacía. Manteniendo workspace actual.")
            return ctx if ctx else None

        target = Path(raw).expanduser().resolve()
        if not target.exists():
            print(RED("❌") + f" Ruta no encontrada: {target}")
            print(DIM("  Verifica la ruta e intenta de nuevo con:") +
                  " " + CYAN("bago repo-on <ruta>"))
            return None

        ctx = _save_context(target, "external",
                            "BAGO operando como herramienta sobre un proyecto externo.")
        print(GREEN("✓") + f" Workspace: {BOLD('externo')}  {DIM(str(target))}")
        return ctx

    print(YELLOW("⚠") + f"  Opción no válida: '{choice}'. Manteniendo workspace actual.")
    return ctx if ctx else None


def main() -> int:
    as_json = "--json" in sys.argv
    result = select()
    if as_json:
        print(json.dumps(result or {}, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

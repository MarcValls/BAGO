#!/usr/bin/env python3
"""_bago_paths.py — Resolver de rutas universal para el ecosistema BAGO.

Este archivo es el ANCLA del sistema de paths. Funciona desde CUALQUIER
ubicación dentro de .bago/ (tools/, tools/neural/, core/, etc.) y siempre
resuelve correctamente TOOLS_DIR, BAGO_ROOT y REPO_ROOT.

Uso en cualquier herramienta BAGO:
    from _bago_paths import TOOLS_DIR, BAGO_ROOT, REPO_ROOT, find_tool

    # En vez de:
    scanner = TOOLS_DIR / "secret_scan.py"          # ← se rompe si se mueve
    # Usa:
    scanner = find_tool("secret_scan")               # ← siempre funciona

Funciona aunque el archivo que lo importa esté en una subcarpeta de tools/.
No tiene dependencias externas. Python stdlib puro.
"""
from __future__ import annotations

import sys
from functools import lru_cache
from pathlib import Path

# ── Localización del anchor ──────────────────────────────────────────────────
# Este archivo vive en tools/ (o en una subcarpeta de tools/).
# Caminamos hacia arriba hasta encontrar tool_registry.py, que es el marcador
# canónico de la raíz de tools/.

def _locate_tools_root() -> Path:
    """Encuentra el directorio tools/ buscando tool_registry.py hacia arriba."""
    here = Path(__file__).resolve().parent
    candidate = here
    for _ in range(5):  # máximo 5 niveles arriba
        if (candidate / "tool_registry.py").exists():
            return candidate
        parent = candidate.parent
        if parent == candidate:
            break
        candidate = parent
    # Fallback: asumimos que estamos directamente en tools/
    return here


TOOLS_DIR: Path = _locate_tools_root()
BAGO_ROOT:  Path = TOOLS_DIR.parent          # .bago/
REPO_ROOT:  Path = BAGO_ROOT.parent          # raíz del repositorio
CORE_DIR:   Path = BAGO_ROOT / "core"        # .bago/core/
STATE_DIR:  Path = BAGO_ROOT / "state"       # .bago/state/
AGENTS_DIR: Path = BAGO_ROOT / "agents"      # .bago/agents/

PYTHON = sys.executable


# ── Buscador recursivo de herramientas ────────────────────────────────────────

@lru_cache(maxsize=256)
def find_tool(stem: str) -> Path:
    """Encuentra un archivo .py por su nombre (sin extensión) de forma recursiva.

    Busca en este orden:
      1. TOOLS_DIR/ (raíz, lookup rápido sin rglob)
      2. Subdirectorios de TOOLS_DIR/ (rglob)
      3. CORE_DIR/ (para módulos como autonomous_loop)
      4. Fallback: devuelve la ruta canónica aunque no exista

    Resultados cacheados (lru_cache) — sin overhead en llamadas repetidas.

    Ejemplo:
        path = find_tool("secret_scan")        # → tools/scanners/secret_scan.py
        path = find_tool("bago_neural")        # → tools/neural/bago_neural.py
        path = find_tool("autonomous_loop")    # → core/autonomous_loop.py
    """
    # 1. Lookup directo en raíz (más común, más rápido)
    direct = TOOLS_DIR / f"{stem}.py"
    if direct.exists():
        return direct

    # 2. Búsqueda recursiva en subdirectorios
    for match in TOOLS_DIR.rglob(f"{stem}.py"):
        return match

    # 3. core/ (e.g. autonomous_loop, agent_dispatcher, bago_context)
    core = CORE_DIR / f"{stem}.py"
    if core.exists():
        return core

    # 4. Fallback: ruta en raíz (no existe — fallará al ejecutar, con mensaje claro)
    return direct


def find_tool_str(stem: str) -> str:
    """Versión str de find_tool — para usar en subprocess.run y PreflightCheck."""
    return str(find_tool(stem))


def resolve_tools(*stems: str) -> dict[str, Path]:
    """Resuelve múltiples stems de una vez.

    Ejemplo:
        paths = resolve_tools("secret_scan", "dep_audit", "type_check")
        # → {"secret_scan": Path(...), "dep_audit": Path(...), ...}
    """
    return {stem: find_tool(stem) for stem in stems}


def invalidate_cache() -> None:
    """Limpia el caché de find_tool (necesario si se mueven archivos en runtime)."""
    find_tool.cache_clear()


# ── Diagnóstico ───────────────────────────────────────────────────────────────

def diagnose() -> dict:
    """Devuelve un dict con el estado del sistema de paths (para bago doctor)."""
    return {
        "tools_dir":  str(TOOLS_DIR),
        "bago_root":  str(BAGO_ROOT),
        "repo_root":  str(REPO_ROOT),
        "core_dir":   str(CORE_DIR),
        "state_dir":  str(STATE_DIR),
        "tools_dir_exists": TOOLS_DIR.exists(),
        "bago_root_exists": BAGO_ROOT.exists(),
        "tool_registry_found": (TOOLS_DIR / "tool_registry.py").exists(),
    }


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import json
    import argparse

    ap = argparse.ArgumentParser(description="BAGO Path Resolver — diagnóstico de rutas")
    ap.add_argument("--find", metavar="STEM", help="Busca un módulo por stem")
    ap.add_argument("--diagnose", action="store_true", help="Muestra estado de rutas base")
    ap.add_argument("--test", action="store_true", help="Ejecuta self-tests")
    args = ap.parse_args()

    if args.find:
        p = find_tool(args.find)
        exists = "✅" if p.exists() else "❌"
        print(f"  {exists} {args.find}  →  {p}")
        sys.exit(0 if p.exists() else 1)

    if args.diagnose:
        info = diagnose()
        for k, v in info.items():
            icon = "✅" if v is True else ("❌" if v is False else "  ")
            print(f"  {icon} {k}: {v}")
        sys.exit(0)

    if args.test:
        tests = []

        # Test 1: TOOLS_DIR contiene tool_registry.py
        t1 = (TOOLS_DIR / "tool_registry.py").exists()
        tests.append(("tools_dir_anchor", t1, str(TOOLS_DIR)))

        # Test 2: BAGO_ROOT es el padre
        t2 = BAGO_ROOT == TOOLS_DIR.parent
        tests.append(("bago_root_is_parent", t2, str(BAGO_ROOT)))

        # Test 3: find_tool encuentra tool_registry mismo
        t3 = find_tool("tool_registry").exists()
        tests.append(("find_tool_registry", t3, str(find_tool("tool_registry"))))

        # Test 4: find_tool con stem inexistente devuelve Path (no lanza)
        ghost = find_tool("__nonexistent_xyz__")
        t4 = isinstance(ghost, Path)
        tests.append(("find_tool_ghost_returns_path", t4, str(ghost)))

        # Test 5: find_tool_str devuelve string
        t5 = isinstance(find_tool_str("tool_registry"), str)
        tests.append(("find_tool_str_type", t5, ""))

        # Test 6: diagnose tiene las claves esperadas
        d = diagnose()
        t6 = all(k in d for k in ("tools_dir", "bago_root", "tool_registry_found"))
        tests.append(("diagnose_keys", t6, ""))

        # Test 7: cache funciona (mismo objeto devuelto)
        p1, p2 = find_tool("tool_registry"), find_tool("tool_registry")
        t7 = p1 is p2
        tests.append(("lru_cache_same_object", t7, ""))

        passed = sum(1 for _, ok, _ in tests if ok)
        print(f"\n  _bago_paths — Self-tests ({passed}/{len(tests)} pasaron)\n")
        for name, ok, detail in tests:
            print(f"  {'✅' if ok else '❌'}  {name}  {detail}")
        sys.exit(0 if passed == len(tests) else 1)

    # Default: mostrar info básica
    print(f"\n  🗂  BAGO Path Resolver")
    print(f"  TOOLS_DIR : {TOOLS_DIR}")
    print(f"  BAGO_ROOT : {BAGO_ROOT}")
    print(f"  REPO_ROOT : {REPO_ROOT}")
    print(f"\n  Uso: python3 _bago_paths.py --find <stem>")
    print(f"       python3 _bago_paths.py --diagnose")
    print(f"       python3 _bago_paths.py --test\n")

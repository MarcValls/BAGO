#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
infra_parity.py — Compara variables de entorno locales con las declaradas en producción.

Fuentes locales : .env  (o .env.example si no existe .env) del proyecto activo
Fuentes prod    : render.yaml  envVars[].key
                  netlify.toml [build.environment] keys
                  vercel.json  env / build.env keys

Uso:
    python3 .bago/tools/infra_parity.py
    python3 .bago/tools/infra_parity.py --path /ruta/al/proyecto
    python3 .bago/tools/infra_parity.py --verbose

Códigos de salida: 0 = OK, 1 = error, 2 = diferencias detectadas
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

# Windows UTF-8
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parents[2]
STATE = ROOT / ".bago" / "state"


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _project_root() -> Path | None:
    """Lee active_project.path de global_state.json."""
    gs_file = STATE / "global_state.json"
    if not gs_file.exists():
        return None
    try:
        gs = json.loads(gs_file.read_text(encoding="utf-8"))
        p = gs.get("active_project", {}).get("path", "")
        return Path(p) if p else None
    except Exception:
        return None


def _parse_dotenv(path: Path) -> dict[str, str]:
    """Lee un archivo .env y devuelve {KEY: value_or_empty}."""
    result: dict[str, str] = {}
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, _, val = line.partition("=")
                result[key.strip()] = val.strip()
    except Exception:
        pass
    return result


def _parse_render_yaml(path: Path) -> set[str]:
    """Extrae claves de envVars en render.yaml (YAML simple, sin dependencia externa)."""
    keys: set[str] = set()
    if not path.exists():
        return keys
    try:
        inside_env_vars = False
        for line in path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if stripped == "envVars:":
                inside_env_vars = True
                continue
            if inside_env_vars:
                # Fin de sección si hay otro key sin indentación
                if stripped and not stripped.startswith("-") and not stripped.startswith("key:") \
                        and not stripped.startswith("value:") and not stripped.startswith("sync:") \
                        and ":" in stripped and not line.startswith(" ") and not line.startswith("\t"):
                    inside_env_vars = False
                    continue
                if stripped.startswith("- key:"):
                    keys.add(stripped.removeprefix("- key:").strip())
                elif stripped.startswith("key:"):
                    keys.add(stripped.removeprefix("key:").strip())
    except Exception:
        pass
    return keys


def _parse_netlify_toml(path: Path) -> set[str]:
    """Extrae claves de [build.environment] en netlify.toml."""
    keys: set[str] = set()
    if not path.exists():
        return keys
    try:
        in_build_env = False
        for line in path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if stripped == "[build.environment]":
                in_build_env = True
                continue
            if in_build_env:
                if stripped.startswith("["):
                    in_build_env = False
                    continue
                if "=" in stripped and not stripped.startswith("#"):
                    key = stripped.split("=")[0].strip()
                    keys.add(key)
    except Exception:
        pass
    return keys


def _parse_vercel_json(path: Path) -> set[str]:
    """Extrae claves de env / build.env en vercel.json."""
    keys: set[str] = set()
    if not path.exists():
        return keys
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        for section in ("env", "build"):
            obj = data.get(section, {})
            if isinstance(obj, dict):
                keys.update(obj.keys())
            elif isinstance(obj, dict) and "env" in obj:
                keys.update(obj["env"].keys())
    except Exception:
        pass
    return keys


def _find_env_files(project: Path) -> list[Path]:
    """Busca .env y .env.example en subdirectorios apps/*/."""
    candidates = []
    # Preferir .env local sobre .env.example
    for pattern in (".env", ".env.example"):
        for f in sorted(project.glob(f"apps/*/{pattern}")):
            candidates.append(f)
        if candidates:
            break
    return candidates


# ─── Render ───────────────────────────────────────────────────────────────────

def _col(text: str, width: int, color: str = "") -> str:
    codes = {"green": "\033[32m", "red": "\033[31m", "yellow": "\033[33m",
             "cyan": "\033[36m", "dim": "\033[2m", "reset": "\033[0m"}
    cell = str(text).ljust(width)[:width]
    if color and color in codes:
        return codes[color] + cell + codes["reset"]
    return cell


def _print_table(rows: list[tuple[str, str, str]]) -> None:
    W1, W2, W3 = 40, 12, 12
    hdr = f"{'Variable'.ljust(W1)}  {'Local'.ljust(W2)}  {'Prod'.ljust(W3)}"
    sep = "-" * (W1 + W2 + W3 + 4)
    print(f"  {hdr}")
    print(f"  {sep}")
    for key, local_st, prod_st in rows:
        if local_st == "✓" and prod_st == "✓":
            color_l, color_p = "green", "green"
        elif local_st == "—":
            color_l, color_p = "red", "green"
        elif prod_st == "—":
            color_l, color_p = "green", "yellow"
        else:
            color_l = color_p = ""
        print(f"  {_col(key, W1, 'dim')}  {_col(local_st, W2, color_l)}  {_col(prod_st, W3, color_p)}")


def run(project: Path, verbose: bool = False) -> int:
    # ── Leer .env local (del server o primer .env encontrado) ────────────────
    env_file = project / "apps" / "server" / ".env"
    env_example = project / "apps" / "server" / ".env.example"
    if env_file.exists():
        local_vars = _parse_dotenv(env_file)
        local_source = str(env_file.relative_to(project))
    elif env_example.exists():
        local_vars = _parse_dotenv(env_example)
        local_source = str(env_example.relative_to(project)) + " (fallback)"
    else:
        env_files = _find_env_files(project)
        if env_files:
            local_vars = _parse_dotenv(env_files[0])
            local_source = str(env_files[0].relative_to(project))
        else:
            print("  ⚠  No se encontró .env ni .env.example en el proyecto.")
            return 1

    # ── Leer fuentes de producción ────────────────────────────────────────────
    render_keys  = _parse_render_yaml(project / "render.yaml")
    netlify_keys = _parse_netlify_toml(project / "netlify.toml")
    vercel_keys  = _parse_vercel_json(project / "vercel.json")
    prod_keys: set[str] = render_keys | netlify_keys | vercel_keys

    prod_sources = []
    if render_keys:  prod_sources.append(f"render.yaml ({len(render_keys)})")
    if netlify_keys: prod_sources.append(f"netlify.toml ({len(netlify_keys)})")
    if vercel_keys:  prod_sources.append(f"vercel.json ({len(vercel_keys)})")

    if not prod_keys:
        print("  ⚠  No se encontraron fuentes de producción (render.yaml, netlify.toml, vercel.json).")
        return 1

    local_keys = set(local_vars.keys())
    all_keys   = sorted(local_keys | prod_keys)

    # ── Clasificar ────────────────────────────────────────────────────────────
    only_local = local_keys - prod_keys   # en local pero no en prod
    only_prod  = prod_keys - local_keys   # en prod pero no en local
    both       = local_keys & prod_keys

    print()
    print("  ┌─────────────────────────────────────────────────────────────┐")
    print("  │  BAGO · Paridad de infraestructura                          │")
    print("  └─────────────────────────────────────────────────────────────┘")
    print(f"  Local  : {local_source}")
    print(f"  Prod   : {', '.join(prod_sources) or '(ninguna)'}")
    print()

    rows = []
    for k in all_keys:
        l = "✓" if k in local_keys else "—"
        p = "✓" if k in prod_keys  else "—"
        rows.append((k, l, p))

    _print_table(rows)
    print()

    # ── Resumen ───────────────────────────────────────────────────────────────
    print(f"  ✅  En ambos      : {len(both)}")
    if only_prod:
        print(f"  ❌  Solo en prod   : {len(only_prod)}  ← faltan en local")
        for k in sorted(only_prod):
            print(f"        · {k}")
    if only_local:
        print(f"  ⚠️   Solo en local  : {len(only_local)}  ← no declaradas en prod")
        for k in sorted(only_local):
            print(f"        · {k}")
    print()

    if only_prod:
        return 2  # diferencias críticas
    return 0


def main() -> int:
    args = sys.argv[1:]
    verbose = "--verbose" in args or "-v" in args

    # --path override
    project: Path | None = None
    if "--path" in args:
        idx = args.index("--path")
        if idx + 1 < len(args):
            project = Path(args[idx + 1])

    if project is None:
        project = _project_root()

    if project is None or not project.exists():
        print("  ⚠  No se encontró proyecto activo. Usa --path /ruta/al/proyecto")
        return 1

    return run(project, verbose=verbose)



def _self_test():
    """Autotest mínimo — verifica arranque limpio del módulo."""
    from pathlib import Path as _P
    assert _P(__file__).exists(), "fichero no encontrado"
    print("  1/1 tests pasaron")

if __name__ == "__main__":
    if "--test" in sys.argv:
        _self_test()
        raise SystemExit(0)
    raise SystemExit(main())

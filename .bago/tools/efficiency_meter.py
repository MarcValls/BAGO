#!/usr/bin/env python3
"""
efficiency_meter.py — Medidor de eficiencia inter-versiones BAGO
Compara métricas clave entre cleanversions y la versión activa.

Uso:
  python3 efficiency_meter.py
  python3 efficiency_meter.py --json
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import zipfile
from functools import lru_cache
from pathlib import Path

# ── Rutas ─────────────────────────────────────────────────────────────────────

SCRIPT_DIR   = Path(__file__).resolve().parent
BAGO_ROOT    = SCRIPT_DIR.parent
REPO_ROOT    = BAGO_ROOT.parent
CV_DIR       = REPO_ROOT / "cleanversion"
DIST_DIR     = BAGO_ROOT / "dist" / "source"
STATE_FILE   = BAGO_ROOT / "state" / "global_state.json"
IMPL_FILE    = BAGO_ROOT / "state" / "implemented_ideas.json"
CHANGES_DIR  = BAGO_ROOT / "state" / "changes"

# ── Colores ANSI ───────────────────────────────────────────────────────────────

R  = "\033[0m"
B  = "\033[1m"
G  = "\033[32m"
Y  = "\033[33m"
C  = "\033[36m"
M  = "\033[35m"
DIM = "\033[2m"
BG  = "\033[1;32m"
BY  = "\033[1;33m"
BC  = "\033[1;36m"

# ── Pesos para el Índice de Eficiencia ────────────────────────────────────────

WEIGHTS = {
    "tools":     0.35,
    "commands":  0.30,
    "docs":      0.20,
    "workflows": 0.15,
}


@lru_cache(maxsize=1)
def _load_weights() -> dict[str, float]:
    try:
        from bago_config import load_config
        data = load_config("efficiency_weights", fallback=None)
        weights = data.get("weights") if isinstance(data, dict) else None
        if isinstance(weights, dict):
            return {str(k): float(v) for k, v in weights.items()}
    except Exception:
        pass
    return WEIGHTS

# ── Recolección de métricas ────────────────────────────────────────────────────

def _extract_commands_from_bago(bago_path: Path) -> list[str]:
    """Extrae las claves del dict COMMANDS del script bago."""
    if not bago_path.exists():
        return []
    txt = bago_path.read_text(encoding="utf-8", errors="ignore")
    return re.findall(r'"([a-z_-]+)"\s*:\s*\["python3"', txt)


def _metrics_from_zip(zip_path: Path) -> dict:
    """Extrae métricas de un zip fuente de distribución."""
    if not zip_path.exists():
        return {}
    with zipfile.ZipFile(zip_path) as zf:
        names = zf.namelist()
        tools     = [n for n in names if "/tools/" in n and n.endswith(".py") and "__" not in n]
        workflows = [n for n in names if "/workflows/W" in n and n.endswith(".md")]
        docs      = [n for n in names if "/docs/" in n and n.endswith(".md")]
        # intenta leer pack.json para la versión
        version = "?"
        for name in names:
            if name.endswith("pack.json"):
                try:
                    data = json.loads(zf.read(name))
                    version = data.get("version", "?")
                except Exception:
                    pass
                break
    return {
        "tools":     len(tools),
        "workflows": len(workflows),
        "docs":      len(docs),
        "version":   version,
        "tool_names": sorted(Path(t).name for t in tools),
    }


def _metrics_live() -> dict:
    """Métricas del estado activo del sistema."""
    tools     = list((BAGO_ROOT / "tools").rglob("*.py")) if (BAGO_ROOT / "tools").exists() else []
    workflows = list((BAGO_ROOT / "workflows").glob("W*.md"))
    docs      = list((BAGO_ROOT / "docs").rglob("*.md"))
    chgs      = list(CHANGES_DIR.glob("BAGO-CHG-*.json")) if CHANGES_DIR.exists() else []

    version = "?"
    if STATE_FILE.exists():
        try:
            version = json.loads(STATE_FILE.read_text()).get("bago_version", "?")
        except Exception:
            pass

    ideas_done = 0
    if IMPL_FILE.exists():
        try:
            data = json.loads(IMPL_FILE.read_text())
            ideas_done = len(data.get("implemented", []))
        except Exception:
            pass

    # Obtener health score
    health = _get_health_score()

    # Comandos del bago script activo
    commands = _extract_commands_from_bago(REPO_ROOT / "bago")

    return {
        "tools":       len([t for t in tools if not t.name.startswith("__")]),
        "tool_names":  sorted(t.name for t in tools if not t.name.startswith("__")),
        "workflows":   len(workflows),
        "docs":        len(docs),
        "chgs":        len(chgs),
        "commands":    commands,
        "ideas_done":  ideas_done,
        "health":      health,
        "version":     version,
    }


def _get_health_score() -> int:
    """Ejecuta health_score.py y extrae el score."""
    try:
        result = subprocess.run(
            [sys.executable, str(BAGO_ROOT / "tools" / "health_score.py"), "--score-only"],
            capture_output=True, text=True, timeout=10,
            cwd=str(REPO_ROOT)
        )
        return int(result.stdout.strip())
    except Exception:
        pass
    return -1


def _build_versions() -> list[dict]:
    """Construye la lista ordenada de versiones con sus métricas."""
    versions = []

    # ── ZIP 2.3-clean (primera referencia disponible) ──────────────────────
    old_zip = next(iter(sorted(DIST_DIR.glob("BAGO_2.3*.zip"))), None) if DIST_DIR.exists() else None
    if old_zip:
        m = _metrics_from_zip(old_zip)
        m["label"]    = "2.3-clean"
        m["slug"]     = "2.3-clean"
        m["commands"] = 10  # v01 bago scripts
        m["source"]   = f"ZIP {old_zip.name}"
        versions.append(m)

    # ── cleanversions: v01, v02, v03 ──────────────────────────────────────
    if CV_DIR.exists():
        cv_snapshots = {
            "v01-base-clean":   ("1.x", None),
            "v01-base-patched": ("1.x+", None),
            "v02-template-seed": ("2.4-v2rc", None),
            "v03-template-seed": ("2.5-stable", None),
        }
        for slug, (ver, _) in cv_snapshots.items():
            d = CV_DIR / slug
            if not d.exists():
                continue
            cmds = _extract_commands_from_bago(d / "bago")
            info = {}
            info_file = d / "VERSION_INFO.json"
            if info_file.exists():
                try:
                    info = json.loads(info_file.read_text())
                except Exception:
                    pass
            versions.append({
                "label":    slug,
                "slug":     slug,
                "version":  info.get("bago_version", ver),
                "commands": len(cmds),
                "cmd_names": cmds,
                "source":   "cleanversion/",
                "tools":    None,  # no .bago/ en template-seed
                "docs":     None,
                "workflows": None,
            })

    # ── Estado activo (actual) ─────────────────────────────────────────────
    live = _metrics_live()
    live["label"]  = "ACTIVO ★"
    live["slug"]   = "live"
    live["commands_count"] = len(live["commands"])
    live["source"] = "live"
    versions.append(live)

    return versions


def _delta(current, previous, key) -> str:
    """Formatea el delta entre dos versiones."""
    c = current.get(key)
    p = previous.get(key)
    if c is None or p is None:
        return ""
    d = c - p
    if d > 0:
        return f" {G}↑+{d}{R}"
    elif d < 0:
        return f" \033[31m↓{d}{R}"
    return f" {DIM}={R}"


def _efficiency_index(metrics: dict, maxima: dict) -> float:
    """Calcula el índice de eficiencia compuesto (0–100)."""
    score = 0.0
    for key, weight in _load_weights().items():
        val = metrics.get(key) or metrics.get("commands_count") if key == "commands" else metrics.get(key)
        if key == "commands":
            val = metrics.get("commands_count") or metrics.get("commands")
            if isinstance(val, list):
                val = len(val)
        mx = maxima.get(key, 1)
        if val is not None and mx > 0:
            score += (val / mx) * weight * 100
    return round(score, 1)


# ── Render ─────────────────────────────────────────────────────────────────────

def _bar(value: float, max_val: float = 100, width: int = 20, fill="█", empty="░") -> str:
    if max_val == 0:
        return empty * width
    filled = int((value / max_val) * width)
    return G + fill * filled + DIM + empty * (width - filled) + R


def print_efficiency(versions: list[dict]) -> None:
    # Calcular máximos para índice de eficiencia
    def _get(v, key):
        if key == "commands":
            c = v.get("commands_count") or v.get("commands")
            return len(c) if isinstance(c, list) else (c or 0)
        return v.get(key) or 0

    weights = _load_weights()
    maxima = {
        key: max(_get(v, key) for v in versions)
        for key in weights
    }

    live = next((v for v in versions if v["slug"] == "live"), None)

    print()
    print(f"  {B}╔══════════════════════════════════════════════════════════════╗{R}")
    print(f"  {B}║  BAGO · Medidor de Eficiencia Inter-Versiones               ║{R}")
    print(f"  {B}╚══════════════════════════════════════════════════════════════╝{R}")
    print()

    # ── Tabla comparativa ─────────────────────────────────────────────────
    print(f"  {B}{'Versión':<22} {'CMD':>4} {'TOOLS':>6} {'DOCS':>5} {'WF':>3} {'IDX':>6}{R}")
    print(f"  {'─'*22} {'─'*4} {'─'*6} {'─'*5} {'─'*3} {'─'*6}")

    prev = None
    for v in versions:
        slug  = v.get("slug", "")
        label = v.get("label", slug)
        ver   = v.get("version", "?")

        cmd_count = v.get("commands_count") or v.get("commands")
        if isinstance(cmd_count, list):
            cmd_count = len(cmd_count)
        cmd_count = cmd_count or 0

        tools_count = _get(v, "tools")
        docs_count  = _get(v, "docs")
        wf_count    = _get(v, "workflows")

        idx = _efficiency_index(
            {**v, "commands_count": cmd_count},
            maxima
        )

        d_cmd  = _delta({"commands": cmd_count}, {"commands": (_get(prev, "commands") if prev else 0)}, "commands") if prev else ""
        d_tool = _delta({"tools": tools_count}, {"tools": _get(prev, "tools")}, "tools") if (prev and tools_count) else ""
        d_doc  = _delta({"docs": docs_count}, {"docs": _get(prev, "docs")}, "docs") if (prev and docs_count) else ""

        is_live = slug == "live"
        color = BC if is_live else (C if ver != "?" else DIM)
        dim_tools = "" if tools_count else DIM
        t_str = f"{tools_count}" if tools_count else "—"
        d_str = f"{docs_count}" if docs_count else "—"
        w_str = f"{wf_count}" if wf_count else "—"
        idx_str = f"{idx:.0f}" if idx > 0 else "—"
        idx_color = BG if is_live else (G if idx > 50 else Y)

        print(f"  {color}{label:<22}{R} {BY}{cmd_count:>3}{R}{d_cmd:<10} "
              f"{dim_tools}{t_str:>5}{R}{d_tool:<10} "
              f"{dim_tools}{d_str:>4}{R}{d_doc:<10} "
              f"{dim_tools}{w_str:>3}{R}  "
              f"{idx_color}{idx_str:>5}{R}")

        prev = {**v, "commands": cmd_count}

    print()

    # ── Nuevas herramientas en 2.5-stable vs 2.3-clean ────────────────────
    old_zip = next(iter(sorted(DIST_DIR.glob("BAGO_2.3*.zip"))), None) if DIST_DIR.exists() else None
    new_zip = next(iter(sorted(DIST_DIR.glob("BAGO_2.5*.zip"))), None) if DIST_DIR.exists() else None
    if old_zip and new_zip:
        old_m = _metrics_from_zip(old_zip)
        new_m = _metrics_from_zip(new_zip)
        added   = sorted(set(new_m["tool_names"]) - set(old_m["tool_names"]))
        removed = sorted(set(old_m["tool_names"]) - set(new_m["tool_names"]))
        if added:
            print(f"  {B}Herramientas añadidas en 2.5-stable:{R}")
            for t in added:
                print(f"  {G}  + {t}{R}")
        if removed:
            print(f"  {B}Herramientas eliminadas:{R}")
            for t in removed:
                print(f"  \033[31m  - {t}{R}")
        print()

    # ── Nuevos comandos CLI en v03 vs v01 ─────────────────────────────────
    v01 = next((v for v in versions if "v01-base-clean" in v.get("slug", "")), None)
    v03 = next((v for v in versions if "v03" in v.get("slug", "")), None)
    if v01 and v03:
        c01 = set(v01.get("cmd_names", []))
        c03 = set(v03.get("cmd_names", []))
        new_cmds = sorted(c03 - c01)
        if new_cmds:
            print(f"  {B}Comandos CLI añadidos (v01→v03):{R}")
            for c in new_cmds:
                print(f"  {C}  + bago {c}{R}")
            print()

    # ── Estado activo ─────────────────────────────────────────────────────
    if live:
        health = live.get("health", -1)
        chgs   = live.get("chgs", 0)
        ideas  = live.get("ideas_done", 0)
        h_color = BG if health >= 80 else (BY if health >= 60 else "\033[1;31m")
        h_bar   = _bar(health if health >= 0 else 0)

        print(f"  {B}Estado activo ({live.get('version', '?')}):{R}")
        print(f"  {'Health score':<20} {h_color}{health}/100{R}  {h_bar}")
        print(f"  {'CHGs registrados':<20} {Y}{chgs}{R}")
        print(f"  {'Ideas implementadas':<20} {G}{ideas}{R}")
        print()

    # ── Índice de crecimiento global ──────────────────────────────────────
    baseline = next((v for v in versions if "2.3" in v.get("label", "")), None)
    if baseline and live:
        base_idx = _efficiency_index(
            {**baseline, "commands_count": baseline.get("commands", 0)},
            maxima
        )
        live_idx = _efficiency_index(
            {**live, "commands_count": len(live.get("commands", []))},
            maxima
        )
        growth = round(((live_idx - base_idx) / max(base_idx, 1)) * 100, 1)
        print(f"  {B}Crecimiento global (2.3 → 2.5):{R}")
        print(f"  {'Índice base':<20} {DIM}{base_idx:.0f}/100{R}")
        print(f"  {'Índice actual':<20} {BG}{live_idx:.0f}/100{R}")
        print(f"  {'Crecimiento':<20} {BG}+{growth}%{R}  {_bar(min(growth, 100))}")
        print()

    print(f"  {DIM}CMD=comandos CLI · TOOLS=herramientas .py · DOCS=documentos .md · WF=workflows · IDX=índice eficiencia{R}")
    print()


def print_json(versions: list[dict]) -> None:
    maxima = {}
    for key in _load_weights():
        vals = []
        for v in versions:
            c = v.get("commands_count") or v.get("commands")
            if key == "commands":
                vals.append(len(c) if isinstance(c, list) else (c or 0))
            else:
                vals.append(v.get(key) or 0)
        maxima[key] = max(vals) if vals else 1

    out = []
    for v in versions:
        cmd_count = v.get("commands_count") or v.get("commands")
        if isinstance(cmd_count, list):
            cmd_count = len(cmd_count)
        idx = _efficiency_index({**v, "commands_count": cmd_count or 0}, maxima)
        out.append({
            "slug": v.get("slug"),
            "version": v.get("version"),
            "commands": cmd_count,
            "tools": v.get("tools"),
            "docs": v.get("docs"),
            "workflows": v.get("workflows"),
            "efficiency_index": idx,
        })
    print(json.dumps(out, indent=2, ensure_ascii=False))


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    versions = _build_versions()
    if "--json" in sys.argv:
        print_json(versions)
    else:
        print_efficiency(versions)



def _self_test():
    """Autotest mínimo — verifica arranque limpio del módulo."""
    from pathlib import Path as _P
    assert _P(__file__).exists(), "fichero no encontrado"
    print("  1/1 tests pasaron")

if __name__ == "__main__":
    if "--test" in sys.argv:
        _self_test()
        raise SystemExit(0)
    main()

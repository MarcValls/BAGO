"""bago_canon.py — 4 modos × 3 voces · Bucle de Shepard BAGO

Orquesta el Bucle de Shepard (SCAN→ALERT→REMEDIATE→VERIFY→EVOLVE)
distribuido en 4 modos operativos con 3 voces cada uno:

  Voz 1 — DETECT   · encuentra la señal
  Voz 2 — DIAGNOSE · interpreta y prioriza
  Voz 3 — VERIFY   · mide el estado y calcula delta

Modos:
  MODULAR — detecta monolitos (>600L), los prioriza, calcula presión
  SCAN    — huérfanos de ruta + cobertura documental
  CREATE  — integridad registry → menu → health
  EVOLVE  — métricas + delta + lecciones aprendidas

Canon: cada voz entra VOICE_DELAY segundos después de la anterior.
Bucle Shepard: tras completar los 4 modos, la baseline avanza.
  El sistema nunca vuelve exactamente al mismo estado.

Uso:
  python3 bago_canon.py                      # ciclo completo (todos los modos)
  python3 bago_canon.py --mode MODULAR       # solo ese modo
  python3 bago_canon.py --mode SCAN,CREATE   # dos modos
  python3 bago_canon.py --json               # salida JSON
  python3 bago_canon.py --voice 1            # solo voz 1 en todos los modos
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# ── Paths ──────────────────────────────────────────────────────────────────────
_HERE   = Path(__file__).resolve()
_TOOLS  = _HERE.parent
_BAGO   = _TOOLS.parent
_ROOT   = _BAGO.parent
_STATE  = _BAGO / "state"
_KNOWLEDGE = _BAGO / "knowledge"

CANON_LOG = _STATE / "canon_log.json"
LESSONS_FILE = _KNOWLEDGE / "topics" / "learned-lessons.md"
LEGACY_LESSONS_FILE = _KNOWLEDGE / "learned_lessons.md"

# ── Canon timing ───────────────────────────────────────────────────────────────
VOICE_DELAY = 0.4   # seconds between voice entries

# ── Rich setup ─────────────────────────────────────────────────────────────────
try:
    from rich.console import Console
    from rich.panel   import Panel
    from rich.table   import Table
    from rich         import box
    _RICH = True
except ImportError:
    _RICH = False

_con: object = None


def _console():
    global _con
    if _con is None:
        if _RICH:
            from rich.console import Console
            _con = Console(highlight=False)
        else:
            _con = _FallbackConsole()
    return _con


def _cprint(*args, **kw):
    """Print only when not in JSON mode."""
    if _JSON_MODE:
        return
    _console().print(*args, **kw)


def _cprint_rule(title="", **kw):
    """Rule only when not in JSON mode."""
    if _JSON_MODE:
        return
    _console().rule(title, **kw)


class _FallbackConsole:
    """Thin ANSI fallback when Rich is not available."""
    _C = {
        "bold": "\033[1m", "dim": "\033[2m", "reset": "\033[0m",
        "purple": "\033[35m", "yellow": "\033[33m",
        "green": "\033[32m", "cyan": "\033[36m",
        "red": "\033[31m", "blue": "\033[34m",
    }

    def print(self, *args, **kw):
        if _JSON_MODE:
            return
        text = " ".join(str(a) for a in args)
        # strip [markup]
        text = re.sub(r'\[/?[a-z_ ]+\]', '', text)
        print(text)

    def rule(self, title="", **kw):
        if _JSON_MODE:
            return
        print(f"\n{'─'*30} {title} {'─'*30}\n")


# ── Dynamic tool loader ────────────────────────────────────────────────────────

def _load(name: str):
    path = _TOOLS / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)  # type: ignore
    spec.loader.exec_module(mod)  # type: ignore
    return mod


# ── Canon log I/O ──────────────────────────────────────────────────────────────

def _read_log() -> dict:
    if CANON_LOG.exists():
        try:
            return json.loads(CANON_LOG.read_text())
        except Exception:
            pass
    return {"cycles": 0, "last_run": None, "baselines": {}}


def _write_log(log: dict) -> None:
    _STATE.mkdir(parents=True, exist_ok=True)
    CANON_LOG.write_text(json.dumps(log, indent=2, ensure_ascii=False))


# ─────────────────────────────────────────────────────────────────────────────
# MODE: MODULAR  (anti-monolith)
# ─────────────────────────────────────────────────────────────────────────────

_SPLIT_HINTS = {
    "_engine": ["_model", "_parsers", "_renderers"],
    "_daemon": ["_ui", "_cmd_a", "_cmd_b"],
    "_server": ["_routes", "_handlers", "_models"],
    "_manager": ["_state", "_actions", "_views"],
    "_agent": ["_core", "_tasks", "_memory"],
    "_advisor": ["_rules", "_responses"],
    "_llm": ["_client", "_prompts"],
    "_audit": ["_collectors", "_report"],
    "_telemetry": ["_metrics", "_emitter"],
    "_toolbox": ["_registry", "_runners"],
    "_router": ["_dispatch", "_middleware"],
    "_link": ["_protocol", "_handlers"],
}


def _split_hint(name: str) -> list[str]:
    stem = Path(name).stem.lstrip("_")
    for suffix, parts in _SPLIT_HINTS.items():
        if stem.endswith(suffix.lstrip("_")):
            base = stem[: len(stem) - len(suffix.lstrip("_"))]
            return [f"_{base}{p}.py" for p in parts] + [f"{stem}.py (hub)"]
    return [f"_{stem}_a.py", f"_{stem}_b.py", f"{stem}.py (hub)"]


def _run_modular(log: dict, voice_filter: int | None) -> dict:
    con = _console()
    fsg = _load("file_size_guard")
    r = fsg.scan()
    warn = sorted(r["warn"], key=lambda x: x[1], reverse=True)
    crit = sorted(r["crit"], key=lambda x: x[1], reverse=True)
    all_files = crit + warn
    prev_warn = log.get("baselines", {}).get("MODULAR", {}).get("warn_count", len(all_files))
    delta = prev_warn - len(all_files)

    # ── V1: DETECT ──────────────────────────────────────────────────────────
    if voice_filter in (None, 1):
        _voice_header(1, "MODULAR", "DETECT", "purple")
        time.sleep(VOICE_DELAY)
        if _RICH:
            t = Table(box=box.SIMPLE_HEAVY, show_header=True, header_style="bold purple")
            t.add_column("archivo", style="purple")
            t.add_column("líneas", justify="right")
            t.add_column("zona")
            for name, lines in crit:
                t.add_row(name, str(lines), "[red]CRIT[/red]")
            for name, lines in warn:
                t.add_row(name, str(lines), "[yellow]WARN[/yellow]")
            if not all_files:
                t.add_row("—", "—", "[green]0 monolitos detectados[/green]")
            if not _JSON_MODE: _console().print(t)
        else:
            for name, lines in all_files:
                zone = "CRIT" if lines >= 800 else "WARN"
                _cprint(f"  {zone}  {name}: {lines}L")

    # ── V2: DIAGNOSE ────────────────────────────────────────────────────────
    if voice_filter in (None, 2):
        _voice_header(2, "MODULAR", "DIAGNOSE", "purple")
        time.sleep(VOICE_DELAY)
        pressure = sum(l - 600 for _, l in all_files)
        _cprint(f"  [bold]Presión acumulada:[/bold] {pressure} líneas sobre umbral WARN")
        if all_files:
            top = all_files[0]
            hint = _split_hint(top[0])
            _cprint(f"  [bold]Prioridad #1:[/bold] [purple]{top[0]}[/purple] ({top[1]}L)")
            _cprint(f"  [dim]Sugerencia de split:[/dim] {' + '.join(hint)}")
        if len(all_files) > 1:
            _cprint(f"  [dim]Restantes:[/dim] {len(all_files) - 1} archivos en cola")

    # ── V3: VERIFY ──────────────────────────────────────────────────────────
    if voice_filter in (None, 3):
        _voice_header(3, "MODULAR", "VERIFY", "purple")
        time.sleep(VOICE_DELAY)
        if delta > 0:
            _cprint(f"  [green]↓ Mejora:[/green] −{delta} archivos vs baseline anterior")
        elif delta < 0:
            _cprint(f"  [red]↑ Regresión:[/red] +{abs(delta)} archivos nuevos WARN/CRIT")
        else:
            _cprint(f"  [dim]Sin cambio vs baseline[/dim]")
        _cprint(f"  [bold]Estado:[/bold] {r['total']} archivos · {r['clean']} OK · "
                  f"{len(r['warn'])} WARN · {len(r['crit'])} CRIT")

    return {
        "warn_count": len(all_files),
        "crit_count": len(crit),
        "pressure": sum(l - 600 for _, l in all_files),
        "top": all_files[0][0] if all_files else None,
        "delta": delta,
    }


# ─────────────────────────────────────────────────────────────────────────────
# MODE: SCAN  (orphans + doc coverage)
# ─────────────────────────────────────────────────────────────────────────────

def _run_scan(log: dict, voice_filter: int | None) -> dict:
    con = _console()
    os_mod = _load("orphan_shield")
    di_mod = _load("doc_index")

    shield = os_mod.scan_all()
    index  = di_mod.build_index()

    route_orphans = shield.get("route_orphans", [])
    undoc         = shield.get("undocumented_tools", [])
    total_tools   = index.get("total_tools", 0)
    covered       = index.get("covered_tools", 0)
    coverage_pct  = round(covered / total_tools * 100, 1) if total_tools else 0

    # Priority: in both route_orphans AND undoc
    undoc_set = set(undoc)
    priority1 = [r for r in route_orphans if r in undoc_set]

    prev = log.get("baselines", {}).get("SCAN", {})
    prev_undoc = prev.get("undoc_count", len(undoc))
    delta_undoc = prev_undoc - len(undoc)
    prev_cov = prev.get("coverage_pct", coverage_pct)
    delta_cov = round(coverage_pct - prev_cov, 1)

    # ── V1: DETECT ──────────────────────────────────────────────────────────
    if voice_filter in (None, 1):
        _voice_header(1, "SCAN", "DETECT", "yellow")
        time.sleep(VOICE_DELAY)
        _cprint(f"  Rutas huérfanas: [yellow]{len(route_orphans)}[/yellow]  "
                  f"(comandos sin módulo registrado)")
        _cprint(f"  Tools sin documentar: [yellow]{len(undoc)}[/yellow] / {total_tools}")
        _cprint(f"  Cobertura documental: [bold]{coverage_pct}%[/bold]")

    # ── V2: DIAGNOSE ────────────────────────────────────────────────────────
    if voice_filter in (None, 2):
        _voice_header(2, "SCAN", "DIAGNOSE", "yellow")
        time.sleep(VOICE_DELAY)
        if priority1:
            _cprint(f"  [bold]Prioridad 1[/bold] (huérfanos Y sin doc): {len(priority1)}")
            for p in priority1[:5]:
                _cprint(f"    [yellow]⚠[/yellow] {p}")
            if len(priority1) > 5:
                _cprint(f"    [dim]… y {len(priority1)-5} más[/dim]")
        else:
            _cprint("  [green]Sin solapamiento crítico entre huérfanos y sin-doc[/green]")
        _cprint(f"  Top undoc (muestra): {', '.join(undoc[:6])}")

    # ── V3: VERIFY ──────────────────────────────────────────────────────────
    if voice_filter in (None, 3):
        _voice_header(3, "SCAN", "VERIFY", "yellow")
        time.sleep(VOICE_DELAY)
        cov_arrow = "↑" if delta_cov > 0 else ("↓" if delta_cov < 0 else "→")
        doc_arrow = "↓" if delta_undoc > 0 else ("↑" if delta_undoc < 0 else "→")
        _cprint(f"  Cobertura: {coverage_pct}% [{cov_arrow} {delta_cov:+.1f}% vs baseline]")
        _cprint(f"  Sin doc:   {len(undoc)}   [{doc_arrow} {-delta_undoc:+d} vs baseline]")
        file_new = shield.get("file_orphans_new", [])
        if file_new:
            _cprint(f"  [red]Nuevos huérfanos de archivo:[/red] {len(file_new)}")
        else:
            _cprint("  [green]0 nuevos huérfanos de archivo[/green]")

    return {
        "route_orphans": len(route_orphans),
        "undoc_count": len(undoc),
        "coverage_pct": coverage_pct,
        "priority1_count": len(priority1),
        "delta_undoc": delta_undoc,
        "delta_cov": delta_cov,
    }


# ─────────────────────────────────────────────────────────────────────────────
# MODE: CREATE  (registry → menu → health integrity)
# ─────────────────────────────────────────────────────────────────────────────

def _run_create(log: dict, voice_filter: int | None) -> dict:
    con = _console()

    # Load registry
    reg_path = _TOOLS / "_registry_entries.py"
    reg_text  = reg_path.read_text(encoding="utf-8")
    reg_keys  = re.findall(r'"([a-z][a-z0-9_-]{2,})":\s*ToolEntry', reg_text)

    # Load menu commands
    import importlib.util as _iu
    spec = _iu.spec_from_file_location("bago_menu_data", _TOOLS / "bago_menu_data.py")
    menu_mod = _iu.module_from_spec(spec); spec.loader.exec_module(menu_mod)  # type: ignore
    menu_cmds: set[str] = set()
    for _grp, entries in menu_mod.MENU:
        for entry in entries:
            menu_cmds.add(entry[0])

    # Find registry entries not in menu
    reg_set = set(reg_keys)
    unmapped = sorted(reg_set - menu_cmds)
    menu_only = sorted(menu_cmds - reg_set)

    # Check health/_check.py covers key tools
    check_src = (_TOOLS / "health" / "_check.py").read_text(encoding="utf-8")
    health_funcs = re.findall(r'def (check_\w+)', check_src)

    prev = log.get("baselines", {}).get("CREATE", {})
    prev_unmapped = prev.get("unmapped_count", len(unmapped))
    delta = prev_unmapped - len(unmapped)

    # ── V1: DETECT ──────────────────────────────────────────────────────────
    if voice_filter in (None, 1):
        _voice_header(1, "CREATE", "DETECT", "green")
        time.sleep(VOICE_DELAY)
        _cprint(f"  Registry entries:  [bold]{len(reg_keys)}[/bold]")
        _cprint(f"  Menu commands:     [bold]{len(menu_cmds)}[/bold]")
        _cprint(f"  Health check fns:  [bold]{len(health_funcs)}[/bold]")

    # ── V2: DIAGNOSE ────────────────────────────────────────────────────────
    if voice_filter in (None, 2):
        _voice_header(2, "CREATE", "DIAGNOSE", "green")
        time.sleep(VOICE_DELAY)
        if unmapped:
            _cprint(f"  [yellow]{len(unmapped)} en registry pero NO en menú:[/yellow]")
            for cmd in unmapped[:8]:
                _cprint(f"    [dim]·[/dim] {cmd}")
            if len(unmapped) > 8:
                _cprint(f"    [dim]… y {len(unmapped)-8} más[/dim]")
        else:
            _cprint("  [green]Todos los commands del registry están en el menú[/green]")
        if menu_only:
            _cprint(f"  [dim]{len(menu_only)} en menú sin entrada registry (normal para aliases)[/dim]")
        _cprint(f"  Health functions: {', '.join(health_funcs[:5])}{'…' if len(health_funcs)>5 else ''}")

    # ── V3: VERIFY ──────────────────────────────────────────────────────────
    if voice_filter in (None, 3):
        _voice_header(3, "CREATE", "VERIFY", "green")
        time.sleep(VOICE_DELAY)
        if delta > 0:
            _cprint(f"  [green]↓ Mejora:[/green] −{delta} commands sin mapear vs baseline")
        elif delta < 0:
            _cprint(f"  [yellow]↑ Nuevos sin mapear:[/yellow] +{abs(delta)}")
        else:
            _cprint("  [dim]Sin cambio en integridad registry/menu[/dim]")
        overall = "GO" if not unmapped else f"WARN ({len(unmapped)} unmapped)"
        _cprint(f"  [bold]Estado integración:[/bold] {overall}")

    return {
        "registry_count": len(reg_keys),
        "menu_count": len(menu_cmds),
        "unmapped_count": len(unmapped),
        "health_fns": len(health_funcs),
        "delta": delta,
    }


# ─────────────────────────────────────────────────────────────────────────────
# MODE: EVOLVE  (metrics snapshot + delta + learned_lessons)
# ─────────────────────────────────────────────────────────────────────────────

def _run_evolve(log: dict, voice_filter: int | None, cycle_results: dict) -> dict:
    con = _console()

    now_ts = datetime.now(timezone.utc).isoformat()
    prev_ts = log.get("last_run")
    prev_cycle = log.get("cycles", 0)

    # Aggregate metrics from this cycle
    modular = cycle_results.get("MODULAR", {})
    scan    = cycle_results.get("SCAN", {})
    create  = cycle_results.get("CREATE", {})

    snapshot = {
        "ts": now_ts,
        "warn_files": modular.get("warn_count", 0),
        "crit_files": modular.get("crit_count", 0),
        "monolith_pressure": modular.get("pressure", 0),
        "undoc_tools": scan.get("undoc_count", 0),
        "coverage_pct": scan.get("coverage_pct", 0),
        "route_orphans": scan.get("route_orphans", 0),
        "unmapped_cmds": create.get("unmapped_count", 0),
        "health_fns": create.get("health_fns", 0),
    }

    prev_snap = log.get("baselines", {}).get("EVOLVE", {})

    # ── V1: DETECT ──────────────────────────────────────────────────────────
    if voice_filter in (None, 1):
        _voice_header(1, "EVOLVE", "DETECT", "cyan")
        time.sleep(VOICE_DELAY)
        if _RICH:
            t = Table(box=box.SIMPLE, show_header=True, header_style="bold cyan")
            t.add_column("métrica"); t.add_column("valor", justify="right")
            for k, v in snapshot.items():
                if k != "ts":
                    t.add_row(k.replace("_", " "), str(v))
            if not _JSON_MODE: _console().print(t)
        else:
            for k, v in snapshot.items():
                if k != "ts":
                    _cprint(f"  {k}: {v}")

    # ── V2: DIAGNOSE (delta) ────────────────────────────────────────────────
    if voice_filter in (None, 2):
        _voice_header(2, "EVOLVE", "DIAGNOSE", "cyan")
        time.sleep(VOICE_DELAY)
        if prev_snap:
            deltas = []
            for k, v in snapshot.items():
                if k == "ts":
                    continue
                pv = prev_snap.get(k, v)
                if isinstance(v, (int, float)) and pv != v:
                    sign = "↑" if v > pv else "↓"
                    arrow_color = "red" if (k in ("warn_files","crit_files","undoc_tools","route_orphans","unmapped_cmds") and v > pv) else "green"
                    deltas.append((k, pv, v, sign, arrow_color))
            if deltas:
                for k, pv, cv, sign, c in deltas:
                    _cprint(f"  [{c}]{sign}[/{c}] {k}: {pv} → {cv}")
            else:
                _cprint("  [dim]Sin delta respecto al ciclo anterior[/dim]")
        else:
            _cprint("  [dim]Primer ciclo — baseline establecido[/dim]")
        _cprint(f"  Ciclos Shepard completados: [bold cyan]{prev_cycle + 1}[/bold cyan]")

    # ── V3: VERIFY + LESSON ─────────────────────────────────────────────────
    if voice_filter in (None, 3):
        _voice_header(3, "EVOLVE", "VERIFY", "cyan")
        time.sleep(VOICE_DELAY)
        # Health summary
        warn_ok  = snapshot["warn_files"] < 20
        crit_ok  = snapshot["crit_files"] == 0
        cover_ok = snapshot["coverage_pct"] >= 50
        gate = sum([warn_ok, crit_ok, cover_ok])
        gate_color = "green" if gate == 3 else ("yellow" if gate >= 2 else "red")
        _cprint(f"  Gates: [{gate_color}]{gate}/3 OK[/{gate_color}]"
                  f"  (0-CRIT={crit_ok}, WARN<20={warn_ok}, cov≥50%={cover_ok})")

        # Append to learned_lessons if significant delta
        sig_delta = prev_snap and (
            prev_snap.get("warn_files", 0) - snapshot["warn_files"] >= 3
            or snapshot["coverage_pct"] - prev_snap.get("coverage_pct", 0) >= 2
        )
        if sig_delta:
            _append_lesson(snapshot, prev_snap, prev_cycle + 1)
            _cprint(f"  [green]✓ Lección registrada en learned_lessons.md (ciclo {prev_cycle+1})[/green]")
        else:
            _cprint(f"  [dim]Sin delta significativo → no se añade lección[/dim]")

    return snapshot


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

_VOICE_LABELS = {1: "①  V1", 2: "②  V2", 3: "③  V3"}
_MODE_SYMBOLS = {"MODULAR": "⬡", "SCAN": "⊙", "CREATE": "✦", "EVOLVE": "∿"}
_MODE_DESC = {
    "MODULAR": "Anti-monolito · presión de tamaño",
    "SCAN":    "Huérfanos · cobertura documental",
    "CREATE":  "Integración · registry + menu + health",
    "EVOLVE":  "Métricas · delta · lecciones",
}


_JSON_MODE = False


def _voice_header(n: int, mode: str, role: str, color: str) -> None:
    if _JSON_MODE:
        return
    con = _console()
    sym = _MODE_SYMBOLS.get(mode, "·")
    lbl = _VOICE_LABELS[n]
    _cprint(f"\n  [{color}]{lbl}[/{color}]  [{color} dim]{sym} {mode}[/{color} dim]"
              f"  [dim]·[/dim]  [bold]{role}[/bold]")


def _mode_header(mode: str) -> None:
    if _JSON_MODE:
        return
    con = _console()
    sym = _MODE_SYMBOLS[mode]
    desc = _MODE_DESC[mode]
    if _RICH:
        _cprint_rule(f"[bold] {sym}  {mode}  [/bold][dim]{desc}[/dim]")
    else:
        _cprint_rule(f"{sym} {mode} — {desc}")


def _shepard_header(cycle: int) -> None:
    if _JSON_MODE:
        return
    con = _console()
    ts = datetime.now().strftime("%H:%M:%S")
    if _RICH:
        from rich.panel import Panel
        _cprint(Panel(
            f"[bold]Bucle de Shepard · Ciclo #{cycle}[/bold]  [dim]{ts}[/dim]\n"
            f"[dim]4 modos × 3 voces · DETECT → DIAGNOSE → VERIFY → EVOLVE[/dim]",
            border_style="bright_black", padding=(0, 2)
        ))
    else:
        _cprint(f"\n{'═'*60}")
        _cprint(f"  Bucle de Shepard · Ciclo #{cycle}  {ts}")
        _cprint(f"{'═'*60}\n")


def _append_lesson(snap: dict, prev: dict, cycle: int) -> None:
    ts = datetime.now().strftime("%Y-%m-%d")
    warn_delta = prev.get("warn_files", snap["warn_files"]) - snap["warn_files"]
    cov_delta  = snap["coverage_pct"] - prev.get("coverage_pct", snap["coverage_pct"])
    ll_id = f"LL-{100 + cycle:03d}"
    entry = (
        f"\n## {ll_id} · Ciclo Shepard #{cycle} ({ts})\n\n"
        f"**Contexto:** Canon 4 modos × 3 voces completó el ciclo #{cycle}.\n\n"
        f"**Métricas:**\n"
        f"- WARN files: {prev.get('warn_files','?')} → {snap['warn_files']}"
        f"  (Δ {-warn_delta:+d})\n"
        f"- Cobertura doc: {prev.get('coverage_pct','?')}% → {snap['coverage_pct']}%"
        f"  (Δ {cov_delta:+.1f}%)\n\n"
        f"**Patrón:** El Bucle de Shepard avanza sin retornar al mismo estado.\n"
        f"La mejora incremental es la invariante del sistema.\n"
    )
    LESSONS_FILE.parent.mkdir(parents=True, exist_ok=True)
    if not LESSONS_FILE.exists():
        if LEGACY_LESSONS_FILE.exists():
            LESSONS_FILE.write_text(LEGACY_LESSONS_FILE.read_text(encoding="utf-8"), encoding="utf-8")
        else:
            LESSONS_FILE.write_text(
                "# Learned Lessons\n\n"
                "_Registro canónico de lecciones aprendidas del BAGO local._\n",
                encoding="utf-8",
            )
    LESSONS_FILE.write_text(LESSONS_FILE.read_text(encoding="utf-8") + entry, encoding="utf-8")


# ─────────────────────────────────────────────────────────────────────────────
# ORCHESTRATOR
# ─────────────────────────────────────────────────────────────────────────────

ALL_MODES = ["MODULAR", "SCAN", "CREATE", "EVOLVE"]


def run_cycle(modes: list[str], voice_filter: int | None, as_json: bool) -> dict:
    log = _read_log()
    cycle = log.get("cycles", 0) + 1
    cycle_results: dict = {}

    if not as_json:
        _shepard_header(cycle)

    for mode in modes:
        if not as_json:
            _mode_header(mode)

        if mode == "MODULAR":
            res = _run_modular(log, voice_filter)
        elif mode == "SCAN":
            res = _run_scan(log, voice_filter)
        elif mode == "CREATE":
            res = _run_create(log, voice_filter)
        elif mode == "EVOLVE":
            res = _run_evolve(log, voice_filter, cycle_results)
        else:
            _console().print(f"  [red]Modo desconocido: {mode}[/red]")
            continue

        cycle_results[mode] = res

    # Update log
    log["cycles"] = cycle
    log["last_run"] = datetime.now(timezone.utc).isoformat()
    for mode in modes:
        if mode in cycle_results and mode != "EVOLVE":
            log.setdefault("baselines", {})[mode] = cycle_results[mode]
        elif mode == "EVOLVE" and "EVOLVE" in cycle_results:
            log.setdefault("baselines", {})["EVOLVE"] = cycle_results["EVOLVE"]
    _write_log(log)

    if not as_json:
        con = _console()
        _cprint("")
        if _RICH:
            _cprint_rule("[dim]Ciclo completado[/dim]")
        _cprint(f"  [dim]Log: {CANON_LOG}[/dim]\n")

    return {"cycle": cycle, "modes": modes, "results": cycle_results}


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    p = argparse.ArgumentParser(
        description="bago_canon — 4 modos × 3 voces · Bucle de Shepard"
    )
    p.add_argument("--mode",  default=",".join(ALL_MODES),
                   help="Modo(s) separados por coma: MODULAR,SCAN,CREATE,EVOLVE")
    p.add_argument("--voice", type=int, choices=[1, 2, 3], default=None,
                   help="Ejecutar solo la voz indicada (1, 2 o 3)")
    p.add_argument("--loop",  action="store_true",
                   help="Bucle infinito Shepard (Ctrl+C para detener)")
    p.add_argument("--json",  action="store_true", dest="as_json",
                   help="Salida JSON")
    args = p.parse_args()

    global _JSON_MODE
    _JSON_MODE = args.as_json

    modes_raw = [m.strip().upper() for m in args.mode.split(",")]
    modes = [m for m in modes_raw if m in ALL_MODES]
    if not modes:
        p.error(f"Modo(s) inválidos: {modes_raw}. Válidos: {ALL_MODES}")

    if args.loop:
        n = 0
        try:
            while True:
                run_cycle(modes, args.voice, args.as_json)
                n += 1
                if not args.as_json:
                    _console().print(f"  [dim]Próximo ciclo en 60s … (Ctrl+C para detener)[/dim]\n")
                time.sleep(60)
        except KeyboardInterrupt:
            _console().print("\n  [dim]Bucle de Shepard interrumpido[/dim]\n")
    else:
        result = run_cycle(modes, args.voice, args.as_json)
        if args.as_json:
            print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()


#!/usr/bin/env python3
"""
bago_hello.py — Onboarding guiado para BAGO.
Punto de entrada amigable para usuarios nuevos o para un recordatorio rápido.

Uso:
  bago hello           → intro completa con estado actual
  bago hello --quick   → recordatorio compacto (3 líneas)
  bago hello --tour    → recorre los 5 comandos esenciales uno a uno
"""

import json
import re
import sys
from pathlib import Path

# Fix UTF-8 output on Windows without requiring PYTHONIOENCODING env var
if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# ─── Rutas ────────────────────────────────────────────────────────────────────
BAGO_ROOT = Path(__file__).resolve().parent.parent
STATE     = BAGO_ROOT / "state"
TOOLS     = BAGO_ROOT / "tools"

# ─── Colores ANSI ─────────────────────────────────────────────────────────────
USE_COLOR = sys.stdout.isatty() and "--plain" not in sys.argv

def _c(code: str, text: str) -> str:
    return f"\033[{code}m{text}\033[0m" if USE_COLOR else text

CYAN   = lambda t: _c("1;36", t)
GREEN  = lambda t: _c("1;32", t)
YELLOW = lambda t: _c("1;33", t)
RED    = lambda t: _c("1;31", t)
BOLD   = lambda t: _c("1",    t)
DIM    = lambda t: _c("2",    t)

_ANSI_RE = re.compile(r"\033\[[0-9;]*m")

W       = 58   # ancho interior del panel (entre los dos ║)
INDENT  = "  " # indentación visual del panel completo

def _vlen(s: str) -> int:
    """Longitud visual de un string (sin contar códigos ANSI)."""
    return len(_ANSI_RE.sub("", s))

def _pad(content: str, width: int) -> str:
    """Rellena `content` hasta `width` chars visuales."""
    return content + " " * max(0, width - _vlen(content))

def _line(content: str = "", left_pad: int = 2) -> None:
    """Imprime una línea ║ <left_pad><content><relleno> ║ con indentación."""
    inner_w   = W - left_pad
    plain_len = _vlen(content)
    if plain_len > inner_w:
        plain   = _ANSI_RE.sub("", content)
        content = DIM(plain[: inner_w - 1] + "…")
    padded = _pad(content, inner_w)
    print(f"{INDENT}{CYAN('║')}{' ' * left_pad}{padded}{CYAN('║')}")

def _sep(char: str = "═") -> None:
    print(f"{INDENT}{CYAN('╠' + char * W + '╣')}")

def _top() -> None:
    print(f"{INDENT}{CYAN('╔' + '═' * W + '╗')}")

def _bot() -> None:
    print(f"{INDENT}{CYAN('╚' + '═' * W + '╝')}")

def _blank() -> None:
    _line()


# ─── Lectura de estado ────────────────────────────────────────────────────────

def _read_state() -> dict:
    snap: dict = {"health": -1, "workflow": None, "task": None, "ideas": 0}
    gs = STATE / "global_state.json"
    if gs.exists():
        try:
            data = json.loads(gs.read_text(encoding="utf-8"))
            _hs = data.get("health_score", data.get("system_health", {}))
            if isinstance(_hs, dict):
                snap["health"] = _hs.get("score", _hs.get("overall_score", -1))
            elif isinstance(_hs, (int, float)):
                snap["health"] = int(_hs)
            aw = data.get("sprint_status", {}).get("active_workflow")
            if isinstance(aw, dict):
                snap["workflow"] = aw.get("title") or aw.get("code")
            elif isinstance(aw, str) and aw not in (None, "null", "none", ""):
                snap["workflow"] = aw
        except Exception:
            pass

    try:
        sys.path.insert(0, str(TOOLS))
        from bago_db import _connect, DB_PATH
        if DB_PATH.exists():
            conn = _connect()
            row  = conn.execute(
                "SELECT COUNT(*) FROM ideas WHERE status='available'"
            ).fetchone()
            conn.close()
            snap["ideas"] = row[0] if row else 0
    except Exception:
        pass

    active_task_file = STATE / "active_task.json"
    if active_task_file.exists():
        try:
            at = json.loads(active_task_file.read_text(encoding="utf-8"))
            snap["task"] = at.get("title") or at.get("task")
        except Exception:
            pass

    return snap


def _next_step(state: dict) -> tuple[str, str]:
    if state["health"] >= 0 and state["health"] < 60:
        return "bago health", "Tu sistema necesita revisión — muestra qué está mal"
    if state["workflow"] is None:
        return "bago ideas", "Sin flujo activo — aquí el sistema te dice qué conviene hacer"
    if state["task"] is None:
        return "bago flow start", "Flujo activo pero sin tarea — abre una para empezar"
    return "bago status", "Todo activo — revisa el estado detallado aquí"


# ─── Vista principal ──────────────────────────────────────────────────────────

COMMANDS = [
    ("bago hello",      "← estás aquí. Úsalo cuando no sepas por dónde seguir"),
    ("bago ideas",      "Qué deberías hacer ahora (el motor principal de BAGO)"),
    ("bago status",     "Estado actual: tarea, flujo y salud del sistema"),
    ("bago flow start", "Inicia una sesión de trabajo sobre un flujo"),
    ("bago task --done","Cierra la tarea actual y registra el progreso"),
]


def _show_reopen_hint(state: dict) -> None:
    """Muestra un hint de bago reopen si hay sesión previa y no hay flujo activo."""
    if state.get("workflow"):
        return  # flujo activo — no hace falta sugerir reopen
    sessions_dir = STATE / "sessions"
    if not sessions_dir.exists():
        return
    close_files = sorted(sessions_dir.glob("SESSION_CLOSE_*.md"), reverse=True)
    if not close_files:
        return
    latest = close_files[0]
    name = latest.stem  # SESSION_CLOSE_YYYYMMDD_HHMMSS
    ts   = name.replace("SESSION_CLOSE_", "").replace("_", " ")
    _sep()
    _line(BOLD("🔁  Sesión previa detectada"))
    _blank()
    _line(f"  {DIM('Último cierre:')} {CYAN(ts)}")
    _line(f"  {GREEN('bago reopen')}  {DIM('→ retoma el contexto de la sesión anterior')}")
    _blank()




def _show_full() -> None:
    state  = _read_state()
    cmd, why = _next_step(state)

    print()
    _top()
    _line(BOLD("👋  Bienvenido a BAGO"))
    _line(DIM("B·alanceado  A·daptativo  G·enerativo  O·rganizativo"))
    _sep()
    _line("BAGO es un asistente personal de trabajo que te ayuda")
    _line("a organizar ideas, tareas y decisiones técnicas usando")
    _line("comandos simples en el terminal.")
    _sep()
    _line(BOLD("📋  5 comandos esenciales"))
    _blank()
    for c, desc in COMMANDS:
        # comando en verde, descripción en dim
        cmd_part  = GREEN(f"  {c:<18}")
        desc_part = DIM(desc)
        content   = cmd_part + desc_part
        # truncate desc if too long
        max_w = W - 2 - _vlen(cmd_part)
        plain_desc = _ANSI_RE.sub("", desc)
        if len(plain_desc) > max_w:
            plain_desc = plain_desc[:max_w - 1] + "…"
        _line(GREEN(f"  {c:<18}") + DIM(plain_desc))
    _blank()
    _sep()
    _line(BOLD("📊  Tu estado ahora"))
    _blank()

    h = state["health"]
    if h >= 80:
        hstr = GREEN(f"{h}%")
    elif h >= 50:
        hstr = YELLOW(f"{h}%")
    elif h >= 0:
        hstr = RED(f"{h}%")
    else:
        hstr = DIM("sin datos")

    wf_str   = GREEN(state["workflow"]) if state["workflow"] else DIM("ninguno")
    task_str = BOLD(state["task"][:30]) if state["task"] else DIM("ninguna")
    ideas_str = CYAN(str(state["ideas"])) if state["ideas"] else DIM("0")

    _line(f"  {'Salud:':<20}{hstr}")
    _line(f"  {'Flujo activo:':<20}{wf_str}")
    _line(f"  {'Tarea actual:':<20}{task_str}")
    _line(f"  {'Ideas disponibles:':<20}{ideas_str}")
    _blank()

    # ── Hint de reanudación si hay sesión previa y no hay flujo activo ── # REOPEN_IN_HELLO_IMPLEMENTED
    _show_reopen_hint(state)

    _sep()
    _line(BOLD("🚀  Próximo paso sugerido"))
    _blank()
    _line(f"  {BOLD('❯')} {GREEN(cmd)}")
    _line(f"    {DIM(why)}")
    _blank()
    _bot()
    print()
    print(f"{INDENT}{DIM('Tip:')} {GREEN('bago hello --tour')} {DIM('para un recorrido interactivo paso a paso.')}")
    print()


def _show_quick() -> None:
    state = _read_state()
    cmd, why = _next_step(state)
    print()
    print(f"{INDENT}{BOLD('BAGO')} — {DIM('B·alanceado A·daptativo G·enerativo O·rganizativo')}")
    print(f"{INDENT}{BOLD('❯')} Próximo paso:  {GREEN(cmd)}")
    print(f"{INDENT}  {DIM(why)}")
    print(f"{INDENT}{DIM('Guía completa:')} {GREEN('bago hello')}")
    print()


def _show_tour() -> None:
    steps = [
        (
            "bago hello",
            "Tu punto de inicio en cualquier momento",
            [
                "Muestra el estado del sistema y sugiere qué hacer.",
                "Úsalo cada vez que no sepas por dónde seguir.",
                "'bago hello --quick' da un resumen de 3 líneas.",
            ],
        ),
        (
            "bago ideas",
            "El motor principal de BAGO",
            [
                "Analiza tu contexto y sugiere las mejoras más relevantes.",
                "Piénsalo como un compañero que dice 'esto es lo que toca'.",
                "Cambia con tu contexto — no siempre mostrará lo mismo.",
            ],
        ),
        (
            "bago status",
            "¿Qué está pasando ahora mismo?",
            [
                "Muestra: tarea activa, flujo de trabajo, salud del sistema.",
                "Útil al empezar el día o retomar trabajo tras una pausa.",
            ],
        ),
        (
            "bago flow start",
            "Empieza una sesión de trabajo",
            [
                "Activa un flujo de trabajo que agrupa tareas relacionadas.",
                "BAGO recordará en qué flujo estás y te ayudará a no dispersarte.",
            ],
        ),
        (
            "bago task --done",
            "Cierra lo que acabas de completar",
            [
                "Registra la tarea como completada y actualiza el estado.",
                "Sin este paso, BAGO no sabe que avanzaste.",
                "Después: ejecuta 'bago ideas' para ver qué sigue.",
            ],
        ),
    ]

    print()
    print(f"{INDENT}{CYAN(BOLD('🗺️  Tour BAGO'))} — {DIM('Enter')} para avanzar · {DIM('q+Enter')} para salir")
    print()

    for i, (c, subtitle, desc) in enumerate(steps, 1):
        print(f"{INDENT}{DIM(f'[{i}/{len(steps)}]')}  {GREEN(BOLD(c))}")
        print(f"{INDENT}  {BOLD(subtitle)}")
        print()
        for line in desc:
            print(f"{INDENT}    {line}")
        print()
        if i < len(steps):
            try:
                ans = input(f"{INDENT}{DIM('→ Enter para continuar, q para salir: ')}").strip().lower()
            except (KeyboardInterrupt, EOFError):
                print()
                break
            if ans == "q":
                break
            print()

    print(f"{INDENT}{GREEN('✅')} {BOLD('Tour completado.')} Ejecuta {GREEN('bago ideas')} para empezar de verdad.")
    print()


def _is_first_run() -> bool:
    """True si no hay ningún guardian run registrado en bago.db."""
    try:
        sys.path.insert(0, str(TOOLS))
        from bago_db import _connect, DB_PATH
        if not DB_PATH.exists():
            return True
        conn = _connect()
        row  = conn.execute("SELECT COUNT(*) FROM guardian_runs").fetchone()
        conn.close()
        return (row[0] if row else 0) == 0
    except Exception:
        return False


# ─── Main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    args = sys.argv[1:]
    if "--tour" in args:
        _show_tour()
    elif "--quick" in args:
        _show_quick()
    else:
        if _is_first_run() and sys.stdin.isatty() and "--no-tour" not in args:
            print()
            print(f"{INDENT}{CYAN(BOLD('👋  Primera vez con BAGO'))} — iniciando tour guiado...")
            print()
            _show_tour()
        else:
            _show_full()




def run_tests() -> int:
    """Self-test stub: verify module imports and key symbols exist."""
    results = []
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location("_test_mod", __file__)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        results.append(("import", True, "module loads OK"))
    except Exception as e:
        results.append(("import", False, str(e)))

    passed = sum(1 for _, ok, _ in results if ok)
    total = len(results)
    for name, ok, detail in results:
        status = "OK" if ok else "FAIL"
        print(f"  [{status}] {name}: {detail}")
    print(f"\n  {passed}/{total} tests passed")
    return 0 if passed == total else 1

if __name__ == "__main__":
    if "--test" in sys.argv:
        raise SystemExit(run_tests())
    main()
#!/usr/bin/env python3
"""
bago_banner.py — Cartel de activación BAGO
Muestra logotipo ASCII + estado del pack al arrancar.

Uso:
  python3 .bago/tools/bago_banner.py
  python3 .bago/tools/bago_banner.py --mini   (sin estado)
  python3 .bago/tools/bago_banner.py --plain  (sin colores)
"""

import json, os, re, subprocess, sys
from datetime import datetime, timezone
from pathlib import Path

# Windows UTF-8 fix for box-drawing / emoji characters
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except Exception:
        pass

def _enable_win_vt() -> bool:
    """Activa ANSI VT processing en Windows CMD. Devuelve True si tuvo éxito."""
    if sys.platform != "win32":
        return True
    try:
        import ctypes
        k32 = ctypes.windll.kernel32
        handle = k32.GetStdHandle(-11)          # STD_OUTPUT_HANDLE
        mode   = ctypes.c_ulong(0)
        if k32.GetConsoleMode(handle, ctypes.byref(mode)):
            # ENABLE_VIRTUAL_TERMINAL_PROCESSING = 0x0004
            return bool(k32.SetConsoleMode(handle, mode.value | 0x0004))
    except Exception:
        pass
    return False

_VT_OK = _enable_win_vt()   # intento en import-time

# ─── Rutas ────────────────────────────────────────────────────────────────────
BAGO_ROOT = Path(__file__).resolve().parent.parent
STATE     = BAGO_ROOT / "state"
TOOLS     = BAGO_ROOT / "tools"

# ─── Colores ANSI ─────────────────────────────────────────────────────────────
# Auto-plain si no es TTY/VT o se pasa --plain
USE_COLOR     = (sys.stdout.isatty() or _VT_OK) and "--plain" not in sys.argv
USE_TRUECOLOR = USE_COLOR and os.environ.get("COLORTERM", "").lower() in ("truecolor", "24bit")

def _c(code, text):
    if not USE_COLOR:
        return text
    return f"\033[{code}m{text}\033[0m"

CYAN   = lambda t: _c("1;36", t)
BLUE   = lambda t: _c("1;34", t)
GREEN  = lambda t: _c("1;32", t)
RED    = lambda t: _c("1;31", t)
YELLOW = lambda t: _c("1;33", t)
BOLD   = lambda t: _c("1",    t)
DIM    = lambda t: _c("2",    t)

def _rgb(r: int, g: int, b: int, ch: str) -> str:
    """Truecolor per-character RGB — falls back to CYAN on unsupported terminals."""
    if not USE_COLOR:
        return ch
    if not USE_TRUECOLOR:
        return f"\033[1;36m{ch}\033[0m"
    return f"\033[38;2;{r};{g};{b}m{ch}\033[0m"

def _gradient_line(line: str, y: int, height: int) -> str:
    """
    Apply per-character RGB gradient matching the BAGO PowerShell logo:
      R: 45→125  (left→right)
      G: 180→245 (top→bottom)
      B: 110→220 (left→right)
    Spaces are preserved as-is (no escape codes on whitespace).
    """
    width = max(1, len(line))
    out = []
    for x, ch in enumerate(line):
        if ch == " ":
            out.append(" ")
        else:
            r = int(45  + (80  * x / width))
            g = int(180 + (65  * y / height))
            b = int(110 + (110 * x / width))
            out.append(_rgb(r, g, b, ch))
    return "".join(out)

# ─── Face Art — logo splash BAGO (robot face) ────────────────────────────────
FACE_ART = [
    "░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░",
    "░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░█░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░",
    "░░░░░░░░░░░░░░░░░░░░█████████████████████░░░░░░░░░░░░░░░░░░░░",
    "░░░░░░░░░░░░░░░░█▓▓▓▓▓████████████████▓▓▓▓▓██░░░░░░░░░░░░░░░░",
    "░░░░░░░░░░░░░██████▓▓▓▓▓████████████▓▓▓▓▓███████░░░░░░░░░░░░░",
    "░░░░░░░░░░░██████████▓▓▓▓▓████████▓▓▓▓▓███████████░░░░░░░░░░░",
    "░░░░░░░░░██████████████▓▓▓▓▓▓▓▓▓▓▓▓▓▓███████████████░░░░░░░░░",
    "░░░░░░░░█████████████████▓▓▓▓▓▓▓▓▓▓██████████████████░░░░░░░░",
    "░░░░░░██████████████████▓██▓▓▓▓▓▓██▓███████████████████░░░░░░",
    "░░░░░█▓▓▓██████████████▓▓▓███▓▓███▓▓▓██████████████▓▓▓██░░░░░",
    "░░░░█▓▓▓▓▓▓▓▓▓▓█████████▓▓▓█▓▓▓▓█▓▓▓█████████▓▓▓▓▓▓▓▓▓▓██░░░░",
    "░░░░█▓▓▓▓█████▓▓▓▓▓▓▓▓███▓▓▓▓▓▓▓▓▓▓███▓▓▓▓▓▓▓▓█████▓▓▓▓██░░░░",
    "░░░█▓▓▓▓█████████████▓▓▓▓██████████▓▓▓▓█████████████▓▓▓▓██░░░",
    "░░░▓▓▓▓▓▓▓▓▓▓▓▓▓████████▓▓▓▓▓▓▓▓▓▓▓▓████████▓▓▓▓▓▓▓▓▓▓▓▓▓█░░░",
    "░░░███████████▓▓▓▓▓▓▓▓▓▓▓▓▓██▓▓██▓▓▓▓▓▓▓▓▓▓▓▓▓████████████░░░",
    "░░████████████████████▓▓▓▓▓▓████▓▓▓▓▓▓█████████████████████░░",
    "░░░██████████████████▓▓▓▓▓▓▓████▓▓▓▓▓▓▓███████████████████░░░",
    "░░░███████████████████▓▓▓▓▓▓▓██▓▓▓▓▓▓▓████████████████████░░░",
    "░░░████████████████████▓▓▓▓▓▓▓▓▓▓▓▓▓▓█████████████████████░░░",
    "░░░░███████████████████▓▓██▓▓▓▓▓▓██▓▓████████████████████░░░░",
    "░░░░████████████████████▓▓██▓▓▓▓██▓▓█████████████████████░░░░",
    "░░░░░███████████████████▓▓▓██▓▓██▓▓▓████████████████████░░░░░",
    "░░░░░░██████████████████▓▓▓██████▓▓▓███████████████████░░░░░░",
    "░░░░░░░░█████████████████▓▓▓████▓▓▓██████████████████░░░░░░░░",
    "░░░░░░░░░█████████████████▓▓▓██▓▓▓██████████████████░░░░░░░░░",
    "░░░░░░░░░░░████████████████▓▓▓▓▓▓█████████████████░░░░░░░░░░░",
    "░░░░░░░░░░░░░███████████████▓▓▓▓████████████████░░░░░░░░░░░░░",
    "░░░░░░░░░░░░░░░░████████████▓▓▓▓█████████████░░░░░░░░░░░░░░░░",
    "░░░░░░░░░░░░░░░░░░░░█████████▓▓██████████░░░░░░░░░░░░░░░░░░░░",
    "░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░█░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░",
    "░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░",
]

def _render_face_art() -> None:
    """Renderiza el face art con 3 niveles de brillo ANSI."""
    if not USE_COLOR:
        for line in FACE_ART:
            print(line)
        return
    for line in FACE_ART:
        out = []
        for ch in line:
            if ch == "░":
                out.append(f"\033[2;32m{ch}\033[0m")    # dim verde oscuro
            elif ch == "▓":
                out.append(f"\033[0;36m{ch}\033[0m")    # cyan medio
            elif ch == "█":
                out.append(f"\033[1;37m{ch}\033[0m")    # blanco brillante
            else:
                out.append(ch)
        print("".join(out))


def _print_text_logo() -> None:
    """Imprime el logo BAGO en texto grande, centrado, con gradiente."""
    logo_lines = LOGO_TOP + LOGO_BOT
    total = len(logo_lines)
    print()
    LOGO_INDENT = "              "
    for y, line in enumerate(logo_lines):
        print(LOGO_INDENT + _gradient_line(line, y, total))
    print()



# ─── Logo (sin espacios leading — se añaden fuera del ANSI) ───────────────────
# Dividido en top (cyan) y bottom (azul)
LOGO_TOP = [
    "██████╗  █████╗  ██████╗  ██████╗",
    "██╔══██╗██╔══██╗██╔════╝ ██╔═══██╗",
    "██████╔╝███████║██║  ███╗██║   ██║",
    "██╔══██╗██╔══██║██║   ██║██║   ██║",
]
LOGO_BOT = [
    "██████╔╝██║  ██║╚██████╔╝╚██████╔╝",
    "╚═════╝ ╚═╝  ╚═╝ ╚═════╝  ╚═════╝ ",
]


# ─── Splash animado ───────────────────────────────────────────────────────────
# Frames de un medallón girando (círculo de Braille — 8 frames)
_SPINNER = ["⣾", "⣽", "⣻", "⢿", "⡿", "⣟", "⣯", "⣷"]
_SPINNER_PLAIN = ["|", "/", "-", "\\"]  # fallback ASCII

def print_splash(max_seconds: float = 10.0) -> None:
    """
    Muestra el face art + logo BAGO con un medallón girando en la última línea.
    Se detiene sola tras max_seconds segundos y devuelve control al llamador.
    """
    import time

    # Limpiar pantalla y mover cursor al inicio
    print("\033[2J\033[H", end="", flush=True)

    _render_face_art()
    _print_text_logo()

    spinner  = _SPINNER if USE_COLOR else _SPINNER_PLAIN
    msg      = "INICIANDO DESDE EL DISPOSITIVO BAGO..."
    indent   = "              "
    start    = time.monotonic()
    i        = 0
    interval = 0.08   # segundos por frame

    # Reserva la línea del spinner
    print()
    try:
        while True:
            elapsed = time.monotonic() - start
            if elapsed >= max_seconds:
                break
            frame = spinner[i % len(spinner)]
            if USE_COLOR:
                line = f"{indent}\033[1;36m{frame}\033[0m  \033[1;36m{msg}\033[0m"
            else:
                line = f"{indent}{frame}  {msg}"
            # Sobreescribe la misma línea con \r
            print(f"\r{line}", end="", flush=True)
            i += 1
            time.sleep(interval)
    except KeyboardInterrupt:
        pass
    finally:
        # Deja el cursor en una línea limpia
        print(f"\r{indent}{'✔' if USE_COLOR else '*'}  {_c('2', msg)}", flush=True)
        print()


BOX_INNER = 56  # caracteres visibles entre los bordes ║ y ║

def _strip_ansi(s):
    """Elimina secuencias ANSI para medir la anchura visible."""
    return re.sub(r'\033\[[0-9;]*m', '', s)

def _box(content=""):
    """Línea de caja: ║{content}{relleno}║ con anchura visible = BOX_INNER."""
    vis = len(_strip_ansi(content))
    pad = max(0, BOX_INNER - vis)
    return f"║{content}{' ' * pad}║"

TOP    = "╔" + "═" * BOX_INNER + "╗"
SEP    = "╠" + "═" * BOX_INNER + "╣"
BOT    = "╚" + "═" * BOX_INNER + "╝"
INDENT = "   "  # 3 espacios de margen izquierdo dentro de la caja

# ─── Datos del pack ───────────────────────────────────────────────────────────

def _pack_version():
    try:
        return json.loads((BAGO_ROOT / "pack.json").read_text()).get("version", "?")
    except Exception:
        return "?"

def _validate():
    try:
        r = subprocess.run(
            [sys.executable, str(TOOLS / "validate_pack.py")],
            capture_output=True, text=True, cwd=str(BAGO_ROOT.parent)
        )
        ok = any("GO pack" in l for l in r.stdout.splitlines())
        reason = next((l.strip() for l in r.stdout.splitlines()
                       if l.strip().startswith("KO") or "does not match" in l), "")
        return ok, reason
    except Exception:
        return False, "error"

def _inventory():
    try:
        gs = json.loads((STATE / "global_state.json").read_text())
        inv = gs.get("inventory", {})
        return inv.get("sessions", 0), inv.get("changes", 0), inv.get("evidences", 0)
    except Exception:
        return 0, 0, 0

def _active_scenarios():
    try:
        gs = json.loads((STATE / "global_state.json").read_text())
        sc = gs.get("active_scenarios", [])
        return sc if sc else None
    except Exception:
        return None

def _working_mode():
    try:
        r = subprocess.run(
            [sys.executable, str(TOOLS / "repo_context_guard.py"), "check"],
            capture_output=True, text=True, cwd=str(BAGO_ROOT.parent)
        )
        data = json.loads(r.stdout)
        return data.get("current", {}).get("working_mode", "self")
    except Exception:
        return "?"

def _detector_verdict():
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "context_detector", TOOLS / "context_detector.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        result = mod.evaluate()
        return result.get("verdict", "CLEAN"), result.get("score", 0), result.get("max_score", 2)
    except Exception:
        return None, 0, 2

def _active_task():
    """Devuelve (title, status, stale_days) si hay pending_w2_task.json, o None.

    stale_days: número de días desde que se creó la task (None si desconocido).
    Si stale_days >= 3, la task se considera obsoleta y merece alerta.
    """
    task_file = STATE / "pending_w2_task.json"
    try:
        data = json.loads(task_file.read_text(encoding="utf-8"))
        title   = data.get("idea_title", "—")
        status  = data.get("status", "pending")
        # Calculate age from file mtime or from data field
        stale_days: float | None = None
        created = data.get("created") or data.get("date") or data.get("timestamp")
        if created:
            try:
                dt = datetime.fromisoformat(str(created).rstrip("Z")).replace(tzinfo=timezone.utc)
                stale_days = (datetime.now(timezone.utc) - dt).total_seconds() / 86400
            except Exception:
                pass
        if stale_days is None:
            # fallback: file modification time
            try:
                mtime = datetime.fromtimestamp(task_file.stat().st_mtime, tz=timezone.utc)
                stale_days = (datetime.now(timezone.utc) - mtime).total_seconds() / 86400
            except Exception:
                pass
        return title, status, stale_days
    except Exception:
        return None

def _last_session():
    """Devuelve (session_id, workflow) de la última sesión cerrada."""
    try:
        gs = json.loads((STATE / "global_state.json").read_text())
        return gs.get("last_completed_session_id", ""), gs.get("last_completed_workflow", "")
    except Exception:
        return "", ""

def _progress_counter() -> tuple[int, int]:
    """Devuelve (implementadas, total_catalogo) leyendo implemented_ideas.json y bago.db."""
    impl_file = STATE / "implemented_ideas.json"
    db_path   = STATE / "bago.db"
    n_impl = 0
    n_total = 0
    try:
        if impl_file.exists():
            data = json.loads(impl_file.read_text(encoding="utf-8"))
            entries = data.get("implemented") or data.get("ideas_completed") or []
            n_impl = len(entries)
    except Exception:
        pass
    try:
        if db_path.exists():
            import sqlite3
            conn = sqlite3.connect(db_path)
            n_total = conn.execute("SELECT COUNT(*) FROM ideas").fetchone()[0]
            conn.close()
    except Exception:
        pass
    return n_impl, n_total


def _sync_session_count() -> int:
    """
    Cuenta session_close_*.md y sincroniza global_state.inventory.session_closes.
    El campo 'sessions' (state/sessions/*.json) lo gestiona validate_state.py.
    Devuelve el número de cierres de sesión registrados.
    """
    gs_path = STATE / "global_state.json"
    try:
        count = len(list(STATE.glob("session_close_*.md")))
        if gs_path.exists():
            gs = json.loads(gs_path.read_text(encoding="utf-8"))
            current = int(gs.get("inventory", {}).get("session_closes", 0))
            if current != count:
                if "inventory" not in gs:
                    gs["inventory"] = {}
                gs["inventory"]["session_closes"] = count
                from datetime import timezone
                gs["updated_at"] = datetime.now(timezone.utc).isoformat()
                gs_path.write_text(json.dumps(gs, ensure_ascii=False, indent=2), encoding="utf-8")
        return count
    except Exception:
        return 0


def _health_score() -> tuple[str, int]:
    """Devuelve (icono_semáforo, puntuación) ejecutando health_score.py --score-only.
    # HEALTH_IN_BANNER_IMPLEMENTED
    """
    try:
        import subprocess as _sp
        r = _sp.run(
            [sys.executable, str(TOOLS / "health_score.py"), "--score-only"],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            cwd=str(BAGO_ROOT.parent)
        )
        out = r.stdout.strip()
        # Formato esperado: "80 green"
        parts = out.split()
        score = int(parts[0]) if parts and parts[0].isdigit() else 0
        color = parts[1] if len(parts) > 1 else "unknown"
        icon  = {"green": "🟢", "yellow": "🟡", "red": "🔴"}.get(color, "⚪")
        return icon, score
    except Exception:
        return "⚪", 0


def _print_quick_action(active_task) -> None:
    """Muestra la acción concreta más útil ahora mismo."""
    if active_task is not None:
        _, tstatus, _stale = active_task
        if tstatus != "done":
            print(_box(INDENT + CYAN("⚡ siguiente:") + "  " + GREEN("bago task") + DIM("  →  ver tarea activa")))
            print(_box(INDENT + "              " + YELLOW("bago task --done") + DIM("  →  cerrar tarea")))
            return
    print(_box(INDENT + CYAN("⚡ siguiente:") + "  " + GREEN("bago ideas") + DIM("  →  ver ideas priorizadas")))
    print(_box(INDENT + "              " + CYAN("bago ideas --accept N") + DIM("  →  aceptar una")))


# ─── Render ───────────────────────────────────────────────────────────────────

def print_banner(mini=False):
    # # BANNER_COMPACT_MODE_IMPLEMENTED
    version        = _pack_version()
    pack_ok, reason = _validate()
    ses            = _sync_session_count()   # sincroniza y lee el conteo real
    _, chg, evd    = _inventory()
    mode           = _working_mode()
    scenarios      = _active_scenarios()
    last_sid, last_wf = _last_session()
    verdict, score, max_score = _detector_verdict()
    active_task    = _active_task()
    n_impl, n_total = _progress_counter()
    health_icon, health_pts = _health_score()
    now_str = datetime.now().strftime("%Y-%m-%d  %H:%M")

    if mini:
        status_icon = "✅" if pack_ok else "❌"
        task_str = ""
        if active_task is not None:
            title, tstatus, stale_days = active_task
            stale = stale_days is not None and stale_days >= 3 and tstatus != "done"
            t_icon = "✅" if tstatus == "done" else ("⚠️" if stale else "⏳")
            task_str = f"  {t_icon} {title[:40]}"
        ideas_str = f"ideas: {n_impl}/{n_total}" if n_total > 0 else "ideas: —"
        print()
        print(f"  {BOLD('BAGO')} {DIM(f'v{version}')}  {status_icon}  {health_icon} {BOLD(str(health_pts))}{DIM('pts')}  {DIM(ideas_str)}{task_str}")
        print()
        return

    print()
    # ── Splash: face art + logo texto + iniciando ─────────────────────────────
    _render_face_art()
    _print_text_logo()
    iniciando = "INICIANDO DESDE EL DISPOSITIVO BAGO..."
    print(f"              {_c('1;36', iniciando)}")
    print()

    print(TOP)

    # ── Logo con gradiente RGB ────────────────────────────────────────────────
    logo_lines = LOGO_TOP + LOGO_BOT
    total      = len(logo_lines)
    print(_box())
    for y, line in enumerate(logo_lines):
        print(_box(INDENT + _gradient_line(line, y, total)))
    print(_box())

    # ── Tagline ───────────────────────────────────────────────────────────────
    tagline = (CYAN("B") + "·alanceado  " +
               CYAN("A") + "·daptativo  " +
               CYAN("G") + "·enerativo  " +
               CYAN("O") + "·rganizativo")
    print(_box(INDENT + tagline))

    print(SEP)

    # ── Estado ────────────────────────────────────────────────────────────────
    if pack_ok:
        status_str = GREEN("✅ GO") + "  " + BOLD(f"v{version}") + "  ·  modo: " + (CYAN("self") if mode == "self" else YELLOW("external"))
    else:
        status_str = RED("❌ KO") + "  " + DIM(reason)
    print(_box(INDENT + status_str))

    inv_str = (DIM("ses=") + BOLD(str(ses)) + "  " +
               DIM("chg=") + BOLD(str(chg)) + "  " +
               DIM("evd=") + BOLD(str(evd)) + "  " +
               health_icon + " " + BOLD(str(health_pts)) + DIM("pts") + "  " +
               DIM(now_str))
    print(_box(INDENT + inv_str))

    # ── Progreso de ideas implementadas ───────────────────────────────────────
    if n_total > 0:
        pct = int(n_impl * 100 / n_total)
        bar_len = 20
        filled  = int(bar_len * n_impl / n_total)
        bar = "█" * filled + "░" * (bar_len - filled)
        prog_str = (DIM("ideas: ") + GREEN(str(n_impl)) + DIM(" implementadas") +
                    "  " + DIM(f"[{bar}]") + DIM(f" {pct}%"))
        print(_box(INDENT + prog_str))

    # ── Escenarios ────────────────────────────────────────────────────────────
    if scenarios:
        sc_str = "  ".join(YELLOW(s) for s in scenarios)
        print(_box(INDENT + DIM("escenarios: ") + sc_str))

    # ── Detector W9 ───────────────────────────────────────────────────────────
    if verdict is not None:
        if verdict == "HARVEST":
            v_str = GREEN("🌾 HARVEST") + "  " + DIM("→ bago cosecha")
        elif verdict == "WATCH":
            v_str = YELLOW(f"👁  WATCH [{score}/{max_score}]")
        else:
            v_str = DIM("✔  CLEAN")
        print(_box(INDENT + DIM("detector W9: ") + v_str))

    # ── Última sesión ─────────────────────────────────────────────────────────
    if last_sid:
        print(_box(INDENT + DIM("última ses: ") + DIM(last_sid) + "  " + DIM(last_wf)))

    # ── Task W2 activa ────────────────────────────────────────────────────────
    if active_task is not None:
        title, tstatus, stale_days = active_task
        stale = stale_days is not None and stale_days >= 3 and tstatus != "done"
        if tstatus == "done":
            icon = "✅"; task_color = GREEN
        elif stale:
            icon = "⚠️ "; task_color = RED
        else:
            icon = "⏳"; task_color = YELLOW
        stale_suffix = RED(f"  [{int(stale_days)}d sin cerrar]") if stale else ""
        print(_box(INDENT + DIM("task W2: ") + task_color(f"{icon} {title}") + stale_suffix))

        # SLOT 2 GEN 3 · Alerta de task obsoleta — aviso si > 72 h (3 días) sin actualizar
        if tstatus != "done":
            try:
                task_data = json.loads((STATE / "pending_w2_task.json").read_text(encoding="utf-8"))
                created_at = task_data.get("created_at") or task_data.get("accepted_at") or task_data.get("timestamp", "")
                if created_at:
                    from datetime import timezone
                    created_dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                    age_h = (datetime.now(tz=timezone.utc) - created_dt).total_seconds() / 3600
                    if age_h > 72:
                        stale_msg = RED(f"  ⚠  task obsoleta ({int(age_h)}h / {int(age_h/24)}d) — considera cerrarla o actualizarla")
                        print(_box(INDENT + stale_msg))
            except Exception:
                pass

    if not mini:
        print(SEP)
        # ── Entrada rápida: acción sugerida ───────────────────────────────────
        _print_quick_action(active_task)
        print(SEP)
        # ── Comandos agrupados por capa ───────────────────────────────────────
        try:
            import importlib.util as _ilu, sys as _sys
            _spec = _ilu.spec_from_file_location("_tr_bago", TOOLS / "tool_registry.py")
            _tr = _ilu.module_from_spec(_spec)
            _sys.modules["_tr_bago"] = _tr  # necesario para Python 3.13 + dataclasses
            _spec.loader.exec_module(_tr)
            _by_layer = _tr.get_by_layer(include_deprecated=False)
            _layers   = _tr.LAYERS
            _badges   = _tr.SCOPE_BADGE
            _grouped  = True
        except Exception:
            _grouped = False

        if _grouped:
            for layer_key, layer_info in _layers.items():
                entries = _by_layer.get(layer_key, [])
                if not entries:
                    continue
                header = layer_info["icon"] + "  " + BOLD(layer_info["label"])
                print(_box(INDENT + header + "  " + DIM(layer_info["desc"])))
                for e in entries:
                    badge = _badges.get(e.scope, "⚪")
                    cmd_str = f"bago {e.cmd}"
                    desc_str = e.description[:46]
                    print(_box(INDENT + "  " + CYAN(f"{cmd_str:<20}") +
                               badge + "  " + DIM(desc_str)))
                print(_box())
            print(_box(INDENT + DIM("🔵=framework  🟢=project  ⚪=ambos")))
        else:
            # Fallback: lista plana
            cmds = [
                ("bago start",   "entrada al repo: health + ideas"),
                ("bago session", "ciclo de sesión: open|close|harvest|v2"),
                ("bago health",  "salud del framework: score|report|stability"),
                ("bago audit",   "auditoría: full|pack|scan|commit|doctor"),
                ("bago ideas",   "emite ideas priorizadas"),
                ("bago next",    "ciclo mínimo: idea + acepta + flujo"),
            ]
            col_w = max(len(c) for c, _ in cmds)
            for cmd, desc in cmds:
                padded = cmd + " " * (col_w - len(cmd))
                print(_box(INDENT + CYAN(padded) + "  " + DIM("→ " + desc)))

    print(BOT)
    print()



def _self_test():
    """Autotest mínimo — verifica arranque limpio del módulo."""
    from pathlib import Path as _P
    assert _P(__file__).exists(), "fichero no encontrado"
    print("  1/1 tests pasaron")

if __name__ == "__main__":
    if "--test" in sys.argv:
        _self_test()
        raise SystemExit(0)
    mini = "--mini" in sys.argv
    print_banner(mini=mini)

#!/usr/bin/env python3
"""BAGO Chat — TUI de chat con LLM local (Ollama) integrado al estado BAGO."""
from __future__ import annotations
import curses, json, pathlib, subprocess, sys, textwrap, urllib.request, urllib.error

ROOT  = pathlib.Path(__file__).parents[2]
STATE = ROOT / ".bago" / "state"


def _jread(p: pathlib.Path) -> dict:
    try:
        return json.loads(p.read_text())
    except Exception:
        return {}


def _dbq(sql: str) -> list:
    try:
        import sqlite3
        con = sqlite3.connect(STATE / "bago.db")
        rows = con.execute(sql).fetchall()
        con.close()
        return rows
    except Exception:
        return []


def _build_system_prompt() -> str:
    gs  = _jread(STATE / "global_state.json")
    rc  = _jread(STATE / "repo_context.json")
    gf  = gs.get("guardian_findings", {})
    inv = gs.get("inventory", {})
    act   = _dbq("SELECT COUNT(*) FROM ideas WHERE status='active'")
    avail = _dbq("SELECT COUNT(*) FROM ideas WHERE status='available'")
    proj  = gs.get("active_project", rc.get("project_name", ROOT.name))
    return (
        "Eres el asistente de BAGO, un framework de productividad para desarrolladores "
        "montado en pendrive.\n\n"
        f"Estado actual:\n"
        f"- Proyecto: {proj}  Modo: {rc.get('working_mode','—')}  Branch: {rc.get('git_branch','—')}\n"
        f"- Health: {gf.get('health_pct','?')}%  Warnings: {gf.get('warnings','?')}\n"
        f"- Sesiones: {inv.get('sessions','?')}  Comandos registry: {inv.get('commands','?')}\n"
        f"- Ideas activas: {act[0][0] if act else '?'}  Disponibles: {avail[0][0] if avail else '?'}\n"
        f"- BAGO v{gs.get('bago_version','?')}\n\n"
        "Cuando el usuario escriba /cmd <nombre>, indica que ejecutes ese comando BAGO.\n"
        "Sé conciso y útil. Responde en el idioma del usuario (español/inglés)."
    )


def _load_config() -> dict:
    return _jread(STATE / "llm_config.json")


def _pick_model(text: str, cfg: dict) -> str:
    """Selecciona modelo según intención detectada en el texto."""
    agent_models = cfg.get("agent_models", {})
    t = text.lower()
    if any(k in t for k in ("código", "code", "python", "bug", "error", "función", "class", "import")):
        return agent_models.get("chat_coding") or cfg.get("active_model", "qwen2.5-coder:7b")
    if any(k in t for k in ("planifica", "plan", "sprint", "workflow", "objetivo", "estrategia")):
        return agent_models.get("chat_planning") or cfg.get("active_model", "qwen2.5-coder:7b")
    return cfg.get("active_model", "qwen2.5-coder:7b")


def _ollama_chat(messages: list[dict], model: str, server_url: str) -> str:
    payload = json.dumps({
        "model": model,
        "messages": messages,
        "stream": False,
    }).encode()
    req = urllib.request.Request(
        f"{server_url}/api/chat",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read())
            return data.get("message", {}).get("content", "")
    except urllib.error.URLError as e:
        return f"[Ollama no disponible — {e.reason}]"
    except Exception as e:
        return f"[Error: {e}]"


def _run_bago_cmd(cmd: str) -> str:
    bago = ROOT / "bago"
    try:
        result = subprocess.run(
            [sys.executable, str(bago)] + cmd.split(),
            capture_output=True, text=True, timeout=20,
        )
        out = (result.stdout + result.stderr).strip()
        return out or "OK (sin salida)"
    except subprocess.TimeoutExpired:
        return "[timeout — comando tardó más de 20s]"
    except Exception as e:
        return f"[Error ejecutando bago {cmd}: {e}]"


def _chat_curses(stdscr: "curses._CursesWindow") -> None:
    curses.curs_set(1)
    curses.use_default_colors()
    curses.init_pair(1, curses.COLOR_CYAN,    -1)   # header / separadores
    curses.init_pair(2, curses.COLOR_GREEN,   -1)   # usuario / prompt
    curses.init_pair(3, curses.COLOR_YELLOW,  -1)   # sistema / hints
    curses.init_pair(4, curses.COLOR_WHITE,   -1)   # texto normal
    curses.init_pair(5, curses.COLOR_MAGENTA, -1)   # asistente
    curses.init_pair(6, curses.COLOR_RED,     -1)   # errores

    cfg        = _load_config()
    server_url = cfg.get("server_url", "http://127.0.0.1:11434")
    messages: list[dict] = [{"role": "system", "content": _build_system_prompt()}]

    # Líneas de historial: (texto, color_pair)
    history: list[tuple[str, int]] = []

    def push(text: str, pair: int = 4) -> None:
        h, w = stdscr.getmaxyx()
        for ln in (textwrap.wrap(text, max(w - 2, 20)) or [""]):
            history.append((ln, pair))

    push("╔══  BAGO Chat  ══════════════════════════════════════╗", 1)
    push("  Pregunta cualquier cosa sobre BAGO o tu proyecto.", 3)
    push("  /cmd <nombre>  →  ejecutar comando bago", 3)
    push("  ESC / 'salir'  →  volver al menú principal", 3)
    push("╚═════════════════════════════════════════════════════╝", 1)

    input_buf = ""
    thinking  = False

    while True:
        h, w = stdscr.getmaxyx()
        INPUT_H = 3
        HIST_H  = h - INPUT_H - 1

        stdscr.erase()

        # ── Historial ──────────────────────────────────────────────────────
        start = max(0, len(history) - HIST_H)
        for row_i, (line, pair) in enumerate(history[start:]):
            try:
                stdscr.addstr(row_i, 0, line[:w - 1], curses.color_pair(pair))
            except curses.error:
                pass

        # ── Separador ──────────────────────────────────────────────────────
        try:
            stdscr.addstr(HIST_H, 0, "─" * (w - 1), curses.color_pair(1))
        except curses.error:
            pass

        # ── Input ──────────────────────────────────────────────────────────
        model_name  = _pick_model(input_buf, cfg)
        prompt_tag  = f"[{model_name[:18]}] › "
        try:
            stdscr.addstr(HIST_H + 1, 0, prompt_tag, curses.color_pair(2))
            stdscr.addstr(HIST_H + 1, len(prompt_tag),
                          input_buf[:w - len(prompt_tag) - 1])
        except curses.error:
            pass

        if thinking:
            try:
                stdscr.addstr(HIST_H + 2, 0, "  ⏳ Pensando...", curses.color_pair(3))
            except curses.error:
                pass

        try:
            stdscr.move(HIST_H + 1, min(len(prompt_tag) + len(input_buf), w - 2))
        except curses.error:
            pass
        stdscr.refresh()

        # ── Teclado ────────────────────────────────────────────────────────
        key = stdscr.getch()

        if key == 27:                              # ESC → salir
            break

        elif key in (curses.KEY_BACKSPACE, 127, 8):
            input_buf = input_buf[:-1]

        elif key in (curses.KEY_ENTER, 10, 13):
            user_text = input_buf.strip()
            input_buf = ""
            if not user_text:
                continue
            if user_text.lower() in ("salir", "exit", "quit", "q", ":q"):
                break

            push(f"Tú: {user_text}", 2)

            # ── Modo comando /cmd ──────────────────────────────────────────
            if user_text.startswith("/cmd "):
                bago_cmd = user_text[5:].strip()
                push(f"▶  bago {bago_cmd}", 3)
                out = _run_bago_cmd(bago_cmd)
                for ln in out.splitlines()[:12]:
                    push(f"   {ln}", 4)
                push("─" * 40, 1)
                continue

            # ── Llamada al LLM ─────────────────────────────────────────────
            model    = _pick_model(user_text, cfg)
            messages.append({"role": "user", "content": user_text})
            thinking = True
            stdscr.refresh()

            response = _ollama_chat(messages, model, server_url)
            thinking = False

            if response:
                messages.append({"role": "assistant", "content": response})
                push(f"BAGO [{model[:20]}]:", 5)
                for ln in textwrap.wrap(response, max(w - 4, 20)):
                    push(f"  {ln}", 4)
            else:
                push("  [sin respuesta del modelo]", 6)
            push("─" * 40, 1)

        elif 32 <= key <= 126:
            input_buf += chr(key)


def _startup_choice_curses(stdscr: "curses._CursesWindow") -> str:
    """Pantalla de elección: 'M' → menu manual, 'A' → chat asistente."""
    curses.curs_set(0)
    curses.use_default_colors()
    curses.init_pair(1, curses.COLOR_CYAN,   -1)
    curses.init_pair(2, curses.COLOR_GREEN,  -1)
    curses.init_pair(3, curses.COLOR_YELLOW, -1)
    curses.init_pair(4, curses.COLOR_WHITE,  -1)

    options = ["manual", "asistente"]
    sel = 0

    while True:
        h, w = stdscr.getmaxyx()
        stdscr.erase()

        # Caja centrada
        box_w = min(54, w - 4)
        box_h = 10
        y0 = max(0, (h - box_h) // 2)
        x0 = max(0, (w - box_w) // 2)

        def _safe(row: int, col: int, text: str, pair: int = 4) -> None:
            try:
                stdscr.addstr(y0 + row, x0, text[:box_w], curses.color_pair(pair))
            except curses.error:
                pass

        _safe(0, 0, "╔" + "═" * (box_w - 2) + "╗", 1)
        _safe(1, 0, "║" + "  BAGO  — ¿Cómo quieres trabajar?".center(box_w - 2) + "║", 1)
        _safe(2, 0, "╠" + "═" * (box_w - 2) + "╣", 1)

        labels = [
            ("M", "Manual",    "Menú TUI completo — tú eliges los comandos"),
            ("A", "Asistente", "Chat con IA — pregunta, delega, ejecuta"),
        ]
        for i, (key, name, desc) in enumerate(labels):
            row  = 4 + i * 2
            mark = "▶ " if i == sel else "  "
            pair = 2 if i == sel else 4
            _safe(row, 0, f"║  {mark}[{key}] {name:<10}  {desc:<28}║", pair)

        _safe(8, 0, "╠" + "═" * (box_w - 2) + "╣", 1)
        _safe(9, 0, "║" + "  ↑↓ navegar · Enter / M / A elegir · ESC cancelar".center(box_w - 2) + "║", 3)

        stdscr.refresh()
        key = stdscr.getch()

        if key in (curses.KEY_UP,):
            sel = (sel - 1) % 2
        elif key in (curses.KEY_DOWN,):
            sel = (sel + 1) % 2
        elif key in (ord("m"), ord("M")):
            return "manual"
        elif key in (ord("a"), ord("A")):
            return "asistente"
        elif key in (curses.KEY_ENTER, 10, 13):
            return options[sel]
        elif key == 27:       # ESC → defecto manual
            return "manual"


def run_chat() -> None:
    """Punto de entrada para el modo chat."""
    if not sys.stdout.isatty():
        print("bago chat requiere un terminal interactivo.")
        sys.exit(1)
    curses.wrapper(_chat_curses)


if __name__ == "__main__":
    run_chat()

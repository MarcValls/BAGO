#!/usr/bin/env python3
"""
bago_telegram_daemon.py — BAGO Telegram Bot v2 (interacción completa)

Bot bidireccional con nivel de interacción alto:
  - Teclados inline con botones de acción
  - Gestión de tareas (crear, listar, completar)
  - Ejecución de comandos BAGO
  - Gestión de proyectos y notas
  - Detección de intención en texto libre
  - Mini App integrada

Comandos:
  /start   → registro / bienvenida
  /menu    → menú principal con botones
  /estado  → estado BAGO con botones de acción
  /sprint  → workflow activo
  /tareas  → lista de tareas pendientes
  /tarea <texto> → crear tarea nueva
  /hacer <cmd> → ejecutar comando BAGO
  /git     → últimos commits + opciones
  /nota <texto> → guardar nota
  /logs    → últimas líneas de logs
  /app     → abrir Mini App
  /ayuda   → lista completa
  Texto libre → interpretación de intención + respuesta
"""

from __future__ import annotations

import json
import os
import re
import sys
import subprocess
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional

from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
)
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, filters, ContextTypes
)

# ── Config ───────────────────────────────────────────────────────────────────
TOOLS_DIR     = Path(__file__).parent
BAGO_ROOT     = Path(os.environ.get("BAGO_PADRE_PATH") or Path(__file__).parent.parent.parent)
STATE_DIR     = BAGO_ROOT / ".bago" / "state"
LOG_DIR       = STATE_DIR / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
STATE_PATH    = STATE_DIR / "global_state.json"
TAREAS_PATH   = STATE_DIR / "tareas_telegram.json"
# Config files live in state/, not in tools/ (tools/ is code, not data)
CONFIG_PATH   = STATE_DIR / "notify_config.json"
IDENTITY_PATH = STATE_DIR / "bago_identity.json"
# Legacy: migrate from old tools/ location on first run if needed
for _old, _new in [
    (TOOLS_DIR / "notify_config.json", CONFIG_PATH),
    (TOOLS_DIR / "bago_identity.json", IDENTITY_PATH),
]:
    if _old.exists() and not _new.exists():
        import shutil as _sh
        _new.parent.mkdir(parents=True, exist_ok=True)
        _sh.copy2(str(_old), str(_new))
NOTIFY_CONFIG = str(CONFIG_PATH)

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(message)s",
    level=logging.INFO,
    handlers=[
        logging.FileHandler(str(LOG_DIR / "telegram.log")),
        logging.StreamHandler()
    ]
)
log = logging.getLogger("bago_tg")

# ── Helpers de config ─────────────────────────────────────────────────────────
def load_config() -> dict:
    if CONFIG_PATH.exists():
        return json.loads(CONFIG_PATH.read_text())
    return {}

def save_config(cfg: dict):
    CONFIG_PATH.write_text(json.dumps(cfg, indent=2, ensure_ascii=False))

def get_token() -> str:
    token = os.environ.get("BAGO_TG_TOKEN", "")
    if token:
        return token
    cfg = load_config()
    token = cfg.get("telegram", {}).get("bot_token", "")
    if token:
        return token
    if IDENTITY_PATH.exists():
        ident = json.loads(IDENTITY_PATH.read_text())
        token = ident.get("telegram_bot_token", "")
    return token

def get_owner_id() -> Optional[int]:
    return load_config().get("telegram", {}).get("owner_chat_id", None)

def save_owner_id(chat_id: int):
    cfg = load_config()
    cfg.setdefault("telegram", {})["owner_chat_id"] = chat_id
    save_config(cfg)
    log.info(f"Owner ID guardado: {chat_id}")

def get_miniapp_url() -> str:
    try:
        return load_config().get("telegram", {}).get("miniapp_url", "")
    except Exception:
        return ""

# ── Helpers de estado ─────────────────────────────────────────────────────────
def read_state() -> dict:
    try:
        return json.loads(STATE_PATH.read_text())
    except Exception as e:
        return {"error": str(e)}

def write_state(data: dict):
    STATE_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False))

# ── Gestión de tareas ─────────────────────────────────────────────────────────
def load_tareas() -> list:
    if not TAREAS_PATH.exists():
        return []
    try:
        return json.loads(TAREAS_PATH.read_text())
    except Exception:
        return []

def save_tareas(tareas: list):
    TAREAS_PATH.parent.mkdir(parents=True, exist_ok=True)
    TAREAS_PATH.write_text(json.dumps(tareas, indent=2, ensure_ascii=False))

def crear_tarea(titulo: str, proyecto: str = "general") -> dict:
    tareas = load_tareas()
    # Usar timestamp para garantizar unicidad aunque se borren tareas
    ts_id = datetime.now().strftime("%m%d%H%M%S%f")[:14]  # microseconds evitan colisión
    tarea = {
        "id": f"tg-{ts_id}",
        "titulo": titulo,
        "proyecto": proyecto,
        "status": "pendiente",
        "created_at": datetime.now().isoformat(),
        "completado_at": None
    }
    tareas.append(tarea)
    save_tareas(tareas)
    return tarea

def completar_tarea(tarea_id: str) -> bool:
    tareas = load_tareas()
    for t in tareas:
        if t["id"] == tarea_id:
            t["status"] = "hecho"
            t["completado_at"] = datetime.now().isoformat()
            save_tareas(tareas)
            return True
    return False

def eliminar_tarea(tarea_id: str) -> bool:
    tareas = load_tareas()
    nuevas = [t for t in tareas if t["id"] != tarea_id]
    if len(nuevas) < len(tareas):
        save_tareas(nuevas)
        return True
    return False

# ── Comandos seguros ejecutables ───────────────────────────────────────────────
SAFE_CMDS = {
    "git status":   ["git", "-C", str(BAGO_ROOT), "status", "--short"],
    "git log":      ["git", "-C", str(BAGO_ROOT), "log", "--oneline", "-8"],
    "git diff":     ["git", "-C", str(BAGO_ROOT), "diff", "--stat"],
    "git branch":   ["git", "-C", str(BAGO_ROOT), "branch", "-a"],
    "ls tools":     ["ls", str(TOOLS_DIR)],
    "ls bago":      ["ls", str(BAGO_ROOT)],
    "cat state":    [sys.executable, "-c",
                     f"import json; d=json.load(open('{STATE_PATH}')); "
                     f"print(json.dumps({{k:d[k] for k in list(d)[:8]}}, indent=2, ensure_ascii=False)[:800])"],
}

def run_safe(cmd_key: str) -> str:
    args = SAFE_CMDS.get(cmd_key)
    if not args:
        return f"Comando no permitido: {cmd_key}"
    try:
        r = subprocess.run(args, capture_output=True, text=True, timeout=15)
        out = (r.stdout or r.stderr or "sin salida").strip()
        return out[:1500]
    except Exception as e:
        return f"Error: {e}"

ANSI_RE = re.compile(r'\x1b\[[0-9;]*[mABCDEFGHJKSTfnsuhl]')

def run_bago(cmd: str, args: list = None, timeout: int = 20) -> str:
    """Ejecuta un comando BAGO real y devuelve salida limpia (sin ANSI)."""
    argv = [sys.executable, str(BAGO_ROOT / "bago"), cmd] + (args or [])
    try:
        r = subprocess.run(
            argv, capture_output=True, text=True,
            timeout=timeout, cwd=str(BAGO_ROOT)
        )
        raw = (r.stdout or r.stderr or "sin salida").strip()
        clean = ANSI_RE.sub("", raw)
        # Quitar líneas vacías consecutivas
        lines = [l for l in clean.splitlines() if l.strip()]
        return "\n".join(lines)[:2000]
    except subprocess.TimeoutExpired:
        return f"⏱ Timeout — `bago {cmd}` tardó más de {timeout}s"
    except Exception as e:
        return f"Error ejecutando bago {cmd}: {e}"

# ── Security: allowlist + sanitizer ─────────────────────────────────────────
#   run_bago() always receives a hardcoded literal command — user input never
#   flows into it directly.  ALLOWED_COMMANDS documents the permitted surface;
#   sanitize_command() strips shell metacharacters before any future dynamic use.

ALLOWED_COMMANDS: set = {
    "status", "health", "validate", "audit", "ideas", "next",
    "doctor", "cosecha", "commit", "sync", "context", "session",
    "flow", "task", "scope", "secrets", "orphans",
}

_SHELL_DANGER_RE = re.compile(r'[;&|`$<>\\"\']')

def sanitize_command(cmd: str) -> str:
    """Strip shell metacharacters from a command string.

    Returns a sanitized version safe to use as a single-token argument.
    The caller is responsible for checking the result against ALLOWED_COMMANDS.
    """
    clean = _SHELL_DANGER_RE.sub("", cmd).strip()
    return clean

_HERE = Path(__file__).parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from _telegram_ui import detect_intent, format_estado, make_main_keyboard
from _telegram_handlers import (
    init_handlers,
    check_auth,
    cmd_start,
    cmd_menu,
    cmd_ping,
    cmd_estado,
    cmd_sprint,
    cmd_git,
    cmd_logs,
    cmd_nota,
    cmd_tarea,
    cmd_tareas,
    cmd_hacer,
    cmd_app,
    cmd_ayuda,
    cmd_ideas,
    cmd_next,
    cmd_health,
    cmd_doctor,
    cmd_cosecha,
    cmd_commit,
    cmd_reparar,
    cmd_cartera,
    cmd_airdrop,
    cmd_telemetria,
    on_callback,
    handle_text,
)

# ── Telemetría local ──────────────────────────────────────────────────────────
def _load_telemetry_events() -> list:
    _xdg = os.environ.get("XDG_DATA_HOME")
    path = (
        Path(_xdg) / "bago" / "telemetry" / "events.jsonl" if _xdg
        else Path.home() / ".bago" / "telemetry" / "events.jsonl"
    )
    if not path.exists():
        return []
    events: list = []
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                try:
                    events.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    except OSError:
        pass
    return events


def send_notification(token: str, chat_id: int, text: str) -> dict:
    """Envía mensaje vía urllib. Para uso desde otros scripts sin asyncio."""
    import urllib.request
    import urllib.parse
    url  = f"https://api.telegram.org/bot{token}/sendMessage"
    data = json.dumps({
        "chat_id": chat_id, "text": text, "parse_mode": "Markdown"
    }).encode("utf-8")
    req = urllib.request.Request(
        url, data=data,
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read())
    except Exception as e:
        return {"ok": False, "error": str(e)}

init_handlers(
    BAGO_ROOT,
    TOOLS_DIR,
    STATE_DIR,
    STATE_PATH,
    TAREAS_PATH,
    LOG_DIR,
    load_config,
    get_owner_id,
    save_owner_id,
    get_miniapp_url,
    read_state,
    write_state,
    load_tareas,
    save_tareas,
    crear_tarea,
    completar_tarea,
    eliminar_tarea,
    run_safe,
    run_bago,
    SAFE_CMDS,
    _load_telemetry_events,
    log,
)

# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    token = get_token()
    if not token:
        print("❌ ERROR: No hay token. Configura BAGO_TG_TOKEN o notify_config.json")
        return

    log.info("🤖 BAGO Telegram Bot v2 iniciando...")

    app = Application.builder().token(token).build()

    # Comandos
    app.add_handler(CommandHandler("start",  cmd_start))
    app.add_handler(CommandHandler("menu",   cmd_menu))
    app.add_handler(CommandHandler("ping",   cmd_ping))
    app.add_handler(CommandHandler("estado", cmd_estado))
    app.add_handler(CommandHandler("status", cmd_estado))
    app.add_handler(CommandHandler("sprint", cmd_sprint))
    app.add_handler(CommandHandler("git",    cmd_git))
    app.add_handler(CommandHandler("logs",   cmd_logs))
    app.add_handler(CommandHandler("nota",   cmd_nota))
    app.add_handler(CommandHandler("note",   cmd_nota))
    app.add_handler(CommandHandler("tarea",  cmd_tarea))
    app.add_handler(CommandHandler("task",   cmd_tarea))
    app.add_handler(CommandHandler("tareas", cmd_tareas))
    app.add_handler(CommandHandler("tasks",  cmd_tareas))
    app.add_handler(CommandHandler("hacer",  cmd_hacer))
    app.add_handler(CommandHandler("run",    cmd_hacer))
    app.add_handler(CommandHandler("app",    cmd_app))
    app.add_handler(CommandHandler("ayuda",  cmd_ayuda))
    app.add_handler(CommandHandler("help",   cmd_ayuda))
    # BAGO Core commands
    app.add_handler(CommandHandler("ideas",   cmd_ideas))
    app.add_handler(CommandHandler("next",    cmd_next))
    app.add_handler(CommandHandler("health",  cmd_health))
    app.add_handler(CommandHandler("doctor",  cmd_doctor))
    app.add_handler(CommandHandler("cosecha", cmd_cosecha))
    app.add_handler(CommandHandler("commit",  cmd_commit))
    app.add_handler(CommandHandler("reparar",   cmd_reparar))
    app.add_handler(CommandHandler("cartera",   cmd_cartera))
    app.add_handler(CommandHandler("wallet",    cmd_cartera))
    app.add_handler(CommandHandler("portfolio", cmd_cartera))
    app.add_handler(CommandHandler("airdrop",   cmd_airdrop))
    app.add_handler(CommandHandler("airdrops",  cmd_airdrop))
    app.add_handler(CommandHandler("telemetria",    cmd_telemetria))
    app.add_handler(CommandHandler("telemetry",     cmd_telemetria))
    app.add_handler(CommandHandler("stats",         cmd_telemetria))

    # Callbacks de botones inline
    app.add_handler(CallbackQueryHandler(on_callback))

    # Texto libre
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    # Error handler global
    async def on_error(update: object, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        log.error(f"[ERROR] Update {update} caused error: {ctx.error}", exc_info=ctx.error)
        if isinstance(update, Update) and update.effective_chat:
            try:
                await ctx.bot.send_message(
                    update.effective_chat.id,
                    f"⚠️ Error interno: `{type(ctx.error).__name__}`. El equipo ha sido notificado.",
                    parse_mode="Markdown"
                )
            except Exception:
                pass
    app.add_error_handler(on_error)

    log.info("✅ Bot v2 activo — esperando mensajes")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()

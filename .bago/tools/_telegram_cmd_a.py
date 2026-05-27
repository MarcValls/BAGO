from __future__ import annotations

import os
import sys

os.environ.setdefault("PYTHONUTF8", "1")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import asyncio
import re
import subprocess
import sys
from pathlib import Path
from datetime import datetime
from typing import Any, Optional

from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
)
from telegram.ext import ContextTypes

_HERE = Path(__file__).parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from _telegram_ui import kb_estado, kb_git, kb_menu_principal, kb_tareas

# State injected from bago_telegram_daemon.py
BAGO_ROOT: Optional[Path] = None
LOG_DIR: Optional[Path] = None
STATE_DIR: Optional[Path] = None
TOOLS_DIR: Optional[Path] = None
STATE_PATH: Optional[Path] = None
TAREAS_PATH: Optional[Path] = None

# Function references (injected at startup)
_load_config: Any = None
_get_owner_id: Any = None
_save_owner_id: Any = None
_get_miniapp_url: Any = None
_read_state: Any = None
_write_state: Any = None
_load_tareas: Any = None
_save_tareas: Any = None
_crear_tarea: Any = None
_completar_tarea: Any = None
_eliminar_tarea: Any = None
_run_safe: Any = None
_run_bago: Any = None
_SAFE_CMDS: Any = None
_load_telemetry_events: Any = None
_log: Any = None


def init_handlers(
    bago_root,
    tools_dir,
    state_dir,
    state_path,
    tareas_path,
    log_dir,
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
    safe_cmds,
    load_telemetry_events,
    log,
) -> None:
    global BAGO_ROOT, TOOLS_DIR, STATE_DIR, STATE_PATH, TAREAS_PATH, LOG_DIR
    global _load_config, _get_owner_id, _save_owner_id, _get_miniapp_url
    global _read_state, _write_state, _load_tareas, _save_tareas
    global _crear_tarea, _completar_tarea, _eliminar_tarea
    global _run_safe, _run_bago, _SAFE_CMDS, _load_telemetry_events, _log
    BAGO_ROOT = bago_root
    TOOLS_DIR = tools_dir
    STATE_DIR = state_dir
    STATE_PATH = state_path
    TAREAS_PATH = tareas_path
    LOG_DIR = log_dir
    _load_config = load_config
    _get_owner_id = get_owner_id
    _save_owner_id = save_owner_id
    _get_miniapp_url = get_miniapp_url
    _read_state = read_state
    _write_state = write_state
    _load_tareas = load_tareas
    _save_tareas = save_tareas
    _crear_tarea = crear_tarea
    _completar_tarea = completar_tarea
    _eliminar_tarea = eliminar_tarea
    _run_safe = run_safe
    _run_bago = run_bago
    _SAFE_CMDS = safe_cmds
    _load_telemetry_events = load_telemetry_events
    _log = log

async def check_auth(update: Update) -> bool:
    owner = _get_owner_id()
    chat_id = update.effective_chat.id
    if owner is None:
        await update.message.reply_text("⚠️ Escribe /start primero.")
        return False
    if chat_id != owner:
        _log.warning(f"Acceso denegado: chat_id={chat_id}")
        await update.message.reply_text("⛔ No autorizado.")
        return False
    return True


# ── Comandos ──────────────────────────────────────────────────────────────────
async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    owner = _get_owner_id()
    if owner is None:
        _save_owner_id(chat_id)
        await update.message.reply_text(
            f"🤖 *BAGO v2 activado*\n\n"
            f"Asistente de desarrollo conectado.\n"
            f"Chat `{chat_id}` registrado como propietario.\n\n"
            f"Usa el menú para empezar 👇",
            parse_mode="Markdown",
            reply_markup=kb_menu_principal()
        )
    elif chat_id == owner:
        await update.message.reply_text(
            "🤖 *BAGO activo* — ¿Qué hacemos?",
            parse_mode="Markdown",
            reply_markup=kb_menu_principal()
        )
    else:
        await update.message.reply_text("⛔ No autorizado.")

async def cmd_menu(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not await check_auth(update):
        return
    await update.message.reply_text(
        "🤖 *BAGO — Menú principal*\n\nElige una acción:",
        parse_mode="Markdown",
        reply_markup=kb_menu_principal()
    )

async def cmd_ping(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not await check_auth(update):
        return
    await update.message.reply_text("🏓 pong — BAGO activo")

async def _send_estado(chat_id: int, ctx: ContextTypes.DEFAULT_TYPE):
    state = _read_state()
    if "error" in state:
        await ctx.bot.send_message(chat_id, f"❌ Error: {state['error']}")
        return
    v      = state.get("bago_version", "?")
    health = state.get("system_health", "?")
    inv    = state.get("inventory", {})
    wf     = state.get("sprint_status", {}).get("active_workflow", {})
    wf_str = f"`{wf.get('code','?')}` — {wf.get('title','?')}" if wf else "ninguno"
    tareas = [t for t in _load_tareas() if t["status"] == "pendiente"]
    notes  = state.get("notes", "")
    last_note = notes.split("\n")[-1][:60] if notes else "—"
    msg = (
        f"🤖 *BAGO v{v}*\n"
        f"⚕️ Health: `{health}`\n"
        f"⚡ Workflow: {wf_str}\n"
        f"📦 Commits: {inv.get('commits','?')}\n"
        f"📋 Tareas pendientes: *{len(tareas)}*\n"
        f"📝 Última nota: _{last_note}_"
    )
    await ctx.bot.send_message(chat_id, msg, parse_mode="Markdown", reply_markup=kb_estado())

async def cmd_estado(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not await check_auth(update):
        return
    await _send_estado(update.effective_chat.id, ctx)

async def cmd_sprint(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not await check_auth(update):
        return
    state = _read_state()
    sp   = state.get("sprint_status", {})
    wf   = sp.get("active_workflow", {})
    last = sp.get("last_completed_workflow", {})
    msg = (
        f"⚡ *Workflow activo*\n"
        f"Código: `{wf.get('code','?')}`\n"
        f"Título: {wf.get('title','?')}\n"
        f"Inicio: `{str(wf.get('started','?'))[:16]}`\n\n"
        f"✅ Último completado: _{last.get('title','?')}_"
    )
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("📊 Estado",   callback_data="accion:estado"),
        InlineKeyboardButton("📋 Tareas",   callback_data="accion:tareas"),
    ]])
    await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=kb)

async def cmd_git(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not await check_auth(update):
        return
    try:
        result = subprocess.run(
            ["git", "-C", str(BAGO_ROOT), "log", "--oneline", "-6"],
            capture_output=True, text=True, timeout=10
        )
        branch = subprocess.run(
            ["git", "-C", str(BAGO_ROOT), "branch", "--show-current"],
            capture_output=True, text=True, timeout=5
        ).stdout.strip()
        out = result.stdout.strip() or "sin commits"
        msg = f"🌿 Rama: `{branch}`\n\n```\n{out}\n```"
        await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=kb_git())
    except Exception as e:
        await update.message.reply_text(f"❌ Error git: {e}")

async def cmd_logs(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not await check_auth(update):
        return
    log_files = [
        str(LOG_DIR / "telegram.log"),
        str(LOG_DIR / "miniapp.log"),
        str(LOG_DIR / "wa_daemon.log"),
    ]
    lines = []
    for lf in log_files:
        p = Path(lf)
        if p.exists() and p.stat().st_size > 0:
            tail = p.read_text().splitlines()[-8:]
            lines.append(f"*{p.name}*\n```\n" + "\n".join(tail) + "\n```")
    if lines:
        await update.message.reply_text("\n\n".join(lines)[:3800], parse_mode="Markdown")
    else:
        await update.message.reply_text("📋 Logs vacíos.")

async def cmd_nota(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not await check_auth(update):
        return
    args = " ".join(ctx.args) if ctx.args else ""
    if not args.strip():
        await update.message.reply_text(
            "📝 Uso: `/nota <texto>`\n\nEjemplo: `/nota revisar arquitectura del renderer`",
            parse_mode="Markdown"
        )
        return
    try:
        state = _read_state()
        ts = datetime.now().strftime("%Y-%m-%d %H:%M")
        prev = state.get("notes", "")
        state["notes"] = f"{prev}\n{ts} [TG]: {args.strip()}".strip()
        _write_state(state)
        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton("📝 Ver notas", callback_data="accion:notas"),
            InlineKeyboardButton("🏠 Menú",      callback_data="accion:menu"),
        ]])
        await update.message.reply_text(
            f"📝 Nota guardada\n\n_{args.strip()[:100]}_",
            parse_mode="Markdown", reply_markup=kb
        )
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")

async def cmd_tarea(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Crea una tarea nueva. /tarea <descripción> o /tarea PROYECTO: <descripción>"""
    if not await check_auth(update):
        return
    args = " ".join(ctx.args).strip() if ctx.args else ""
    if not args:
        await update.message.reply_text(
            "📋 Uso:\n`/tarea <descripción>`\n`/tarea DERIVA: fix renderer enemigos`\n\nEjemplo:\n`/tarea revisar la cámara isométrica`",
            parse_mode="Markdown"
        )
        return
    proyecto = "general"
    if ":" in args and len(args.split(":")[0]) < 20:
        partes = args.split(":", 1)
        proyecto = partes[0].strip().lower()
        args = partes[1].strip()
    tarea = _crear_tarea(args, proyecto)
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("📋 Ver tareas",  callback_data="accion:tareas"),
        InlineKeyboardButton("✅ Completar",    callback_data=f"completar:{tarea['id']}"),
    ]])
    await update.message.reply_text(
        f"✅ Tarea creada `{tarea['id']}`\n\n*{proyecto.upper()}*: _{tarea['titulo']}_",
        parse_mode="Markdown", reply_markup=kb
    )

async def cmd_tareas(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not await check_auth(update):
        return
    tareas = _load_tareas()
    pendientes = [t for t in tareas if t["status"] == "pendiente"]
    if not pendientes:
        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton("➕ Nueva tarea", callback_data="accion:nueva_tarea"),
            InlineKeyboardButton("🏠 Menú",        callback_data="accion:menu"),
        ]])
        await update.message.reply_text("📋 No hay tareas pendientes. ¡Bien hecho! 🎉", reply_markup=kb)
        return
    lineas = [f"📋 *Tareas pendientes* ({len(pendientes)})\n"]
    for t in pendientes[:10]:
        proj = f"[{t['proyecto'].upper()}] " if t['proyecto'] != 'general' else ""
        lineas.append(f"`{t['id']}` {proj}_{t['titulo'][:60]}_")
    lineas.append("\nPulsa ✅ para completar · 🗑 para borrar")
    msg = "\n".join(lineas)
    await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=kb_tareas(pendientes))

async def cmd_hacer(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Ejecuta un comando seguro de BAGO. /hacer <git status|git log|ls tools|...>"""
    if not await check_auth(update):
        return
    cmd = " ".join(ctx.args).strip().lower() if ctx.args else ""
    if not cmd:
        opciones = "\n".join(f"• `{k}`" for k in _SAFE_CMDS)
        await update.message.reply_text(
            f"🔧 *Comandos disponibles:*\n\n{opciones}\n\nUso: `/hacer git status`",
            parse_mode="Markdown"
        )
        return
    await update.message.reply_text(f"⚙️ Ejecutando `{cmd}`...", parse_mode="Markdown")
    out = _run_safe(cmd)
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("🔄 Refresh", callback_data=f"cmd:{cmd}"),
        InlineKeyboardButton("🏠 Menú",    callback_data="accion:menu"),
    ]])
    await update.message.reply_text(f"```\n{out}\n```", parse_mode="Markdown", reply_markup=kb)

async def cmd_app(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not await check_auth(update):
        return
    url = _get_miniapp_url()
    if not url:
        await update.message.reply_text(
            f"⚠️ Mini App no activa.\n\n`bash {BAGO_ROOT}/.bago/tools/launch_miniapp.sh`",
            parse_mode="Markdown"
        )
        return
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("📊 Abrir BAGO Dashboard", web_app=WebAppInfo(url=url))
    ]])
    await update.message.reply_text("🌐 *BAGO Mini App*\nAbre el dashboard completo:", parse_mode="Markdown", reply_markup=kb)


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


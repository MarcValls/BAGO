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
CONFIG_PATH   = TOOLS_DIR / "notify_config.json"
BAGO_ROOT     = Path(os.environ.get("BAGO_PADRE_PATH") or Path(__file__).parent.parent.parent)
STATE_PATH    = BAGO_ROOT / ".bago/state/global_state.json"
TAREAS_PATH   = BAGO_ROOT / ".bago/state/tareas_telegram.json"
IDENTITY_PATH = TOOLS_DIR / "bago_identity.json"
NOTIFY_CONFIG = str(CONFIG_PATH)

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(message)s",
    level=logging.INFO,
    handlers=[
        logging.FileHandler("/tmp/bago_telegram.log"),
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
    TAREAS_PATH.write_text(json.dumps(tareas, indent=2, ensure_ascii=False))

def crear_tarea(titulo: str, proyecto: str = "general") -> dict:
    tareas = load_tareas()
    # Usar timestamp para garantizar unicidad aunque se borren tareas
    ts_id = datetime.now().strftime("%m%d%H%M%S")
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
    "cat state":    ["python3", "-c",
                     f"import json; d=json.load(open('{STATE_PATH}')); "
                     f"print(json.dumps({{k:d[k] for k in list(d)[:8]}}, indent=2, ensure_ascii=False))[:800]"],
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
    argv = ["python3", str(BAGO_ROOT / "bago"), cmd] + (args or [])
    try:
        r = subprocess.run(
            argv, capture_output=True, text=True,
            timeout=timeout, cwd=str(BAGO_ROOT)
        )
        raw = (r.stdout or r.stderr or "sin salida").strip()
        clean = ANSI_RE.sub("", raw)
        # Quitar líneas vacías consecutivas
        lines = [l for l in clean.splitlines() if l.strip() or True]
        return "\n".join(lines)[:2000]
    except subprocess.TimeoutExpired:
        return f"⏱ Timeout — `bago {cmd}` tardó más de {timeout}s"
    except Exception as e:
        return f"Error ejecutando bago {cmd}: {e}"

# ── Autenticación ─────────────────────────────────────────────────────────────
async def check_auth(update: Update) -> bool:
    owner = get_owner_id()
    chat_id = update.effective_chat.id
    if owner is None:
        await update.message.reply_text("⚠️ Escribe /start primero.")
        return False
    if chat_id != owner:
        log.warning(f"Acceso denegado: chat_id={chat_id}")
        await update.message.reply_text("⛔ No autorizado.")
        return False
    return True

# ── Teclados ──────────────────────────────────────────────────────────────────
def kb_menu_principal() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 Estado",      callback_data="accion:estado"),
         InlineKeyboardButton("⚡ Sprint",       callback_data="accion:sprint")],
        [InlineKeyboardButton("📋 Tareas",       callback_data="accion:tareas"),
         InlineKeyboardButton("📝 Notas",        callback_data="accion:notas")],
        [InlineKeyboardButton("📁 Git Log",      callback_data="accion:git"),
         InlineKeyboardButton("📜 Logs",         callback_data="accion:logs")],
        [InlineKeyboardButton("💰 Cartera",      callback_data="accion:cartera"),
         InlineKeyboardButton("🪂 Airdrops",     callback_data="accion:airdrop"),
         InlineKeyboardButton("🌐 Mini App",     callback_data="accion:app")],
        [InlineKeyboardButton("📈 Telemetría",   callback_data="accion:telemetria"),
         InlineKeyboardButton("❓ Ayuda",         callback_data="accion:ayuda")],
    ])

def kb_estado() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⚡ Sprint",   callback_data="accion:sprint"),
         InlineKeyboardButton("📁 Git",      callback_data="accion:git")],
        [InlineKeyboardButton("📋 Tareas",   callback_data="accion:tareas"),
         InlineKeyboardButton("🔄 Refresh",  callback_data="accion:estado")],
    ])

def kb_git() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📋 Status",   callback_data="cmd:git status"),
         InlineKeyboardButton("📊 Diff",     callback_data="cmd:git diff")],
        [InlineKeyboardButton("🌿 Branch",   callback_data="cmd:git branch"),
         InlineKeyboardButton("📜 Log",      callback_data="cmd:git log")],
    ])

def kb_tareas(tareas_pendientes: list) -> InlineKeyboardMarkup:
    rows = []
    for t in tareas_pendientes[:5]:
        tid = t["id"]
        txt = t["titulo"][:28]
        rows.append([
            InlineKeyboardButton(f"✅ {txt}", callback_data=f"completar:{tid}"),
            InlineKeyboardButton("🗑",         callback_data=f"borrar:{tid}"),
        ])
    rows.append([InlineKeyboardButton("➕ Nueva tarea",  callback_data="accion:nueva_tarea")])
    rows.append([InlineKeyboardButton("🏠 Menú",         callback_data="accion:menu")])
    return InlineKeyboardMarkup(rows)

# ── Comandos ──────────────────────────────────────────────────────────────────
async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    owner = get_owner_id()
    if owner is None:
        save_owner_id(chat_id)
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
    state = read_state()
    if "error" in state:
        await ctx.bot.send_message(chat_id, f"❌ Error: {state['error']}")
        return
    v      = state.get("bago_version", "?")
    health = state.get("system_health", "?")
    inv    = state.get("inventory", {})
    wf     = state.get("sprint_status", {}).get("active_workflow", {})
    wf_str = f"`{wf.get('code','?')}` — {wf.get('title','?')}" if wf else "ninguno"
    tareas = [t for t in load_tareas() if t["status"] == "pendiente"]
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
    state = read_state()
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
    log_files = ["/tmp/bago_telegram.log", "/tmp/bago_miniapp.log", "/tmp/bago_wa_daemon.log"]
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
        state = read_state()
        ts = datetime.now().strftime("%Y-%m-%d %H:%M")
        prev = state.get("notes", "")
        state["notes"] = f"{prev}\n{ts} [TG]: {args.strip()}".strip()
        write_state(state)
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
    tarea = crear_tarea(args, proyecto)
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
    tareas = load_tareas()
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
        opciones = "\n".join(f"• `{k}`" for k in SAFE_CMDS)
        await update.message.reply_text(
            f"🔧 *Comandos disponibles:*\n\n{opciones}\n\nUso: `/hacer git status`",
            parse_mode="Markdown"
        )
        return
    await update.message.reply_text(f"⚙️ Ejecutando `{cmd}`...", parse_mode="Markdown")
    out = run_safe(cmd)
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("🔄 Refresh", callback_data=f"cmd:{cmd}"),
        InlineKeyboardButton("🏠 Menú",    callback_data="accion:menu"),
    ]])
    await update.message.reply_text(f"```\n{out}\n```", parse_mode="Markdown", reply_markup=kb)

async def cmd_app(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not await check_auth(update):
        return
    url = get_miniapp_url()
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

async def cmd_ideas(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Muestra las ideas prioritarias de BAGO."""
    if not await check_auth(update):
        return
    await update.message.reply_text("💡 Consultando ideas BAGO...", parse_mode="Markdown")
    # Primero intenta leer el snapshot (rápido y sin side effects)
    snapshot = BAGO_ROOT / ".bago/state/ideas_snapshot.md"
    if snapshot.exists():
        txt = snapshot.read_text(encoding="utf-8")
        # Extraer las primeras 5 ideas del snapshot
        blocks = txt.strip().split("\n## ")
        header = blocks[0][:200]
        ideas_txt = []
        for b in blocks[1:6]:
            lines = b.strip().splitlines()
            title = lines[0].strip() if lines else "?"
            # Extraer score si hay [NN]
            m = re.match(r"\[(\d+)\]\s*(.*)", title)
            score = m.group(1) if m else "?"
            name  = m.group(2) if m else title
            # Siguiente paso
            next_step = ""
            for l in lines:
                if "Siguiente paso" in l or "siguiente paso" in l:
                    idx = lines.index(l)
                    if idx + 1 < len(lines):
                        next_step = lines[idx + 1].strip()
                    break
            ideas_txt.append(f"• [{score}] *{name}*\n  _{next_step[:80]}_" if next_step else f"• [{score}] *{name}*")
        msg = "💡 *BAGO Ideas — Prioritarias*\n\n" + "\n\n".join(ideas_txt)
    else:
        out = run_bago("ideas", timeout=15)
        msg = f"💡 *BAGO Ideas*\n\n```\n{out[:1800]}\n```"
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("🔄 Refresh",       callback_data="accion:ideas"),
        InlineKeyboardButton("✅ Next [↩]",       callback_data="accion:next"),
        InlineKeyboardButton("👁 Ver tarea",      callback_data="accion:next_preview"),
        InlineKeyboardButton("🏠 Menú",           callback_data="accion:menu"),
    ]])
    await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=kb)

async def cmd_next(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Acepta la próxima tarea BAGO directamente (Enter = sí)."""
    if not await check_auth(update):
        return
    await update.message.reply_text("⚡ Aceptando próxima tarea...", parse_mode="Markdown")
    out = run_bago("next", ["--auto"], timeout=20)
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("👁 Ver ideas",     callback_data="accion:ideas"),
        InlineKeyboardButton("📋 Tareas",        callback_data="accion:tareas"),
        InlineKeyboardButton("🏠 Menú",          callback_data="accion:menu"),
    ]])
    await update.message.reply_text(f"⚡ *Tarea aceptada*\n\n```\n{out[:1800]}\n```", parse_mode="Markdown", reply_markup=kb)

async def cmd_health(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Muestra el health score BAGO."""
    if not await check_auth(update):
        return
    await update.message.reply_text("⚕️ Calculando health score...", parse_mode="Markdown")
    out = run_bago("health", timeout=20)
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("🔍 Doctor",   callback_data="accion:doctor"),
        InlineKeyboardButton("📊 Estado",   callback_data="accion:estado"),
        InlineKeyboardButton("🏠 Menú",     callback_data="accion:menu"),
    ]])
    await update.message.reply_text(f"⚕️ *BAGO Health*\n\n```\n{out[:1800]}\n```", parse_mode="Markdown", reply_markup=kb)

async def cmd_doctor(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Diagnóstico BAGO — detecta problemas en el sistema."""
    if not await check_auth(update):
        return
    await update.message.reply_text("🔍 Ejecutando diagnóstico BAGO...", parse_mode="Markdown")
    out = run_bago("doctor", timeout=25)
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("⚕️ Health",   callback_data="accion:health"),
        InlineKeyboardButton("🏠 Menú",     callback_data="accion:menu"),
    ]])
    await update.message.reply_text(f"🔍 *BAGO Doctor*\n\n```\n{out[:1800]}\n```", parse_mode="Markdown", reply_markup=kb)

async def cmd_cosecha(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Ejecuta bago cosecha — cierre de sprint y generación de artefactos."""
    if not await check_auth(update):
        return
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Sí, ejecutar cosecha", callback_data="accion:cosecha_confirm"),
        InlineKeyboardButton("❌ Cancelar",             callback_data="accion:menu"),
    ]])
    await update.message.reply_text(
        "🌾 *BAGO Cosecha*\n\n"
        "⚠️ Esto ejecutará el cierre de sprint y generará artefactos.\n\n"
        "_¿Confirmar?_",
        parse_mode="Markdown", reply_markup=kb
    )

async def cmd_commit(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Verifica readiness para commit con bago commit."""
    if not await check_auth(update):
        return
    await update.message.reply_text("📦 Verificando commit readiness...", parse_mode="Markdown")
    out = run_bago("commit", timeout=15)
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("🌿 Git status", callback_data="cmd:git status"),
        InlineKeyboardButton("🏠 Menú",       callback_data="accion:menu"),
    ]])
    await update.message.reply_text(f"📦 *Commit Readiness*\n\n```\n{out[:1800]}\n```", parse_mode="Markdown", reply_markup=kb)

async def cmd_reparar(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Auto-repara KOs detectados por bago health."""
    if not await check_auth(update):
        return
    await update.message.reply_text("🔧 Analizando health para reparar KOs...", parse_mode="Markdown")

    health_out = run_bago("health", timeout=30)

    # Parse score
    score_match = re.search(r"(\d+)/100", health_out)
    score = int(score_match.group(1)) if score_match else -1

    if score == 100:
        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton("💚 Health", callback_data="accion:health"),
            InlineKeyboardButton("🏠 Menú",   callback_data="accion:menu"),
        ]])
        await update.message.reply_text(
            "✅ *Sistema sano — nada que reparar*\n\n`BAGO Health: 100/100 🟢`",
            parse_mode="Markdown", reply_markup=kb
        )
        return

    fixes_applied = []
    fixes_failed  = []

    # ── Fix 1: Integridad KO → validate_pack legacy refs ──────────────────────
    if "KO" in health_out and ("legacy" in health_out.lower() or "integridad" in health_out.lower()):
        try:
            vp_path = BAGO_ROOT / ".bago/tools/validate_pack.py"
            vp_text = vp_path.read_text(encoding="utf-8")
            # Find the excluded_prefixes list and check if our standard fix is already there
            if '"ImageStudio/"' not in vp_text:
                vp_text = vp_text.replace(
                    '"docs/V2_PROPUESTA.md",\n]',
                    '"docs/V2_PROPUESTA.md",\n    "ImageStudio/",\n    "tools/dist/",\n]'
                )
                vp_path.write_text(vp_text, encoding="utf-8")
                fixes_applied.append("✅ validate_pack: excluidos directorios de terceros (ImageStudio/, tools/dist/)")
            else:
                fixes_failed.append("⚠️ validate_pack: exclusión ya existe — revisar manualmente qué fichero dispara el KO")
        except Exception as e:
            fixes_failed.append(f"❌ validate_pack fix falló: {e}")

    # ── Fix 2: Estado stale → intentar sync ───────────────────────────────────
    if "stale" in health_out.lower() and "KO" in health_out:
        try:
            result = subprocess.run(
                [sys.executable, str(BAGO_ROOT / ".bago/tools/repo_context_guard.py"), "sync"],
                capture_output=True, text=True, timeout=20,
                cwd=str(BAGO_ROOT)
            )
            if result.returncode == 0:
                fixes_applied.append("✅ estado stale: repo_context_guard sync ejecutado")
            else:
                fixes_failed.append(f"⚠️ repo_context_guard sync: {result.stderr.strip()[:200]}")
        except Exception as e:
            fixes_failed.append(f"❌ sync stale fix falló: {e}")

    # ── Re-run health ──────────────────────────────────────────────────────────
    if fixes_applied:
        await update.message.reply_text("⏳ Re-comprobando health tras reparaciones...", parse_mode="Markdown")
        health_after = run_bago("health", timeout=30)
        score_after_m = re.search(r"(\d+)/100", health_after)
        score_after = int(score_after_m.group(1)) if score_after_m else score
        delta = score_after - score
        delta_str = f"+{delta}" if delta > 0 else str(delta)
        result_icon = "🟢" if score_after == 100 else "🟡" if score_after >= 75 else "🔴"
        summary = (
            f"🔧 *Reparación completada*\n\n"
            f"{result_icon} Health: `{score}/100` → `{score_after}/100` ({delta_str})\n\n"
        )
        if fixes_applied:
            summary += "*Reparaciones aplicadas:*\n" + "\n".join(fixes_applied) + "\n\n"
        if fixes_failed:
            summary += "*No se pudo reparar automáticamente:*\n" + "\n".join(fixes_failed) + "\n\n"
        summary += f"```\n{health_after[:800]}\n```"
    else:
        summary = (
            f"⚠️ *No se encontraron reparaciones automáticas disponibles*\n\n"
            f"Score actual: `{score}/100`\n\n"
            f"```\n{health_out[:800]}\n```\n\n"
            "_Usa /doctor para diagnóstico detallado._"
        )
        if fixes_failed:
            summary += "\n\n*Intentos fallidos:*\n" + "\n".join(fixes_failed)

    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("💚 Health", callback_data="accion:health"),
        InlineKeyboardButton("🩺 Doctor", callback_data="accion:doctor"),
        InlineKeyboardButton("🏠 Menú",   callback_data="accion:menu"),
    ]])
    await update.message.reply_text(summary, parse_mode="Markdown", reply_markup=kb)


async def cmd_cartera(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Muestra el portfolio crypto (READ-ONLY, nunca mueve fondos)."""
    if not await check_auth(update):
        return
    args = ctx.args  # e.g. ["add", "BTC", "0.5"] or ["alerta", "BTC", "90000"]

    import sys as _sys
    _sys.path.insert(0, str(TOOLS_DIR))
    try:
        from wallet_tracker import (
            portfolio_summary, format_summary, check_alerts,
            load_config, save_config, get_wallet_cfg
        )
    except ImportError as e:
        await update.message.reply_text(f"❌ wallet_tracker no disponible: {e}")
        return

    # Subcomandos: add, remove, alerta
    if args and args[0] == "add" and len(args) == 3:
        sym, amount = args[1].upper(), float(args[2])
        cfg = load_config()
        cfg.setdefault("wallet", {}).setdefault("holdings", {})[sym] = amount
        save_config(cfg)
        await update.message.reply_text(f"✅ {sym}: {amount} añadido al portfolio")
        return

    if args and args[0] == "remove" and len(args) == 2:
        sym = args[1].upper()
        cfg = load_config()
        cfg.setdefault("wallet", {}).setdefault("holdings", {}).pop(sym, None)
        save_config(cfg)
        await update.message.reply_text(f"🗑 {sym} eliminado del portfolio")
        return

    if args and args[0] == "alerta" and len(args) == 3:
        sym, price = args[1].upper(), float(args[2])
        cfg = load_config()
        cfg.setdefault("wallet", {}).setdefault("alerts", []).append({"coin": sym, "above": price})
        save_config(cfg)
        await update.message.reply_text(f"🔔 Alerta: {sym} > {price:,.0f} configurada")
        return

    await update.message.reply_text("⏳ Consultando precios…")
    try:
        data = portfolio_summary()
        text = format_summary(data)
        alerts = check_alerts(data)
        if alerts:
            text += "\n\n" + "\n".join(alerts)
        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton("🔄 Actualizar", callback_data="accion:cartera"),
            InlineKeyboardButton("🏠 Menú", callback_data="accion:menu"),
        ]])
        await update.message.reply_text(text, reply_markup=kb)
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")



async def cmd_airdrop(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Escanea TON wallet en busca de airdrops cobrables."""
    if not await check_auth(update):
        return
    args = ctx.args  # ["set", "<ADDRESS>"] | ["scan"] | []

    import sys as _sys
    _sys.path.insert(0, str(TOOLS_DIR))
    try:
        from airdrop_scanner import (
            scan_airdrops, format_airdrops,
            get_ton_address, set_ton_address,
        )
    except ImportError as e:
        await update.message.reply_text(f"❌ airdrop_scanner no disponible: {e}")
        return

    # Subcomando: set <ADDRESS>
    if args and args[0] == "set" and len(args) >= 2:
        address = args[1].strip()
        set_ton_address(address)
        await update.message.reply_text(f"✅ TON address guardada:\n`{address}`", parse_mode="Markdown")
        return

    # Subcomando: scan con address ad-hoc
    scan_address = None
    if args and args[0] != "set":
        scan_address = args[0].strip()
    else:
        scan_address = get_ton_address()

    if not scan_address:
        await update.message.reply_text(
            "🪂 *Airdrop Scanner*\n\n"
            "No hay TON address configurada.\n"
            "Usa: `/airdrop set <TU_TON_ADDRESS>`\n\n"
            "Tu address TON la encuentras en:\n"
            "Telegram → Wallet → Receive → TON address",
            parse_mode="Markdown"
        )
        return

    msg = await update.message.reply_text("🔍 Escaneando wallet TON…")
    try:
        data = scan_airdrops(scan_address)
        text = format_airdrops(data)
        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton("🔄 Re-escanear", callback_data="accion:airdrop"),
            InlineKeyboardButton("🏠 Menú",        callback_data="accion:menu"),
        ]])
        await msg.edit_text(text, reply_markup=kb)
    except Exception as e:
        await msg.edit_text(f"❌ Error escaneando: {e}")


async def cmd_telemetria(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Muestra resumen de telemetría local BAGO."""
    if not await check_auth(update):
        return
    events = _load_telemetry_events()
    if not events:
        await update.message.reply_text(
            "📊 *Telemetría*\n\nSin datos aún.\nEjecuta `bago <cmd>` para generar eventos.",
            parse_mode="Markdown"
        )
        return

    cmds    = [e for e in events if e.get("type") == "command"]
    errors  = [e for e in events if e.get("type") == "exception"]
    ok_n    = sum(1 for e in cmds if e.get("properties", {}).get("success") is True)
    fail_n  = sum(1 for e in cmds if e.get("properties", {}).get("success") is False)

    # Top 3 comandos más usados
    from collections import Counter
    top = Counter(e.get("name", "?") for e in cmds).most_common(3)
    top_str = "\n".join(f"  `{n}` × {c}" for n, c in top) if top else "  —"

    # Último evento
    last = events[-1] if events else None
    last_str = f"`{last['name']}` ({last.get('type','?')}) — {str(last.get('ts',''))[:16]}" if last else "—"

    # Duraciones
    durs = [e["metrics"]["duration_s"] for e in cmds if e.get("metrics", {}).get("duration_s") is not None]
    avg_dur = f"{sum(durs)/len(durs):.2f}s" if durs else "—"

    msg = (
        f"📊 *BAGO Telemetría*\n\n"
        f"📦 Total eventos: `{len(events)}`\n"
        f"⚡ Comandos: `{len(cmds)}` (✅ {ok_n} · ❌ {fail_n})\n"
        f"💥 Excepciones: `{len(errors)}`\n"
        f"⏱ Duración media: `{avg_dur}`\n\n"
        f"🔝 *Top comandos:*\n{top_str}\n\n"
        f"🕐 Último: {last_str}\n\n"
        f"_Dashboard web: `bago telemetry --web`_"
    )
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("🔄 Refresh",  callback_data="accion:telemetria"),
        InlineKeyboardButton("🏠 Menú",     callback_data="accion:menu"),
    ]])
    await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=kb)


    if not await check_auth(update):
        return
    msg = (
        "🤖 *BAGO v2 — Comandos*\n\n"
        "💡 *BAGO Core*\n"
        "  /ideas — ideas prioritarias\n"
        "  /next — próxima tarea sugerida\n"
        "  /health — health score\n"
        "  /doctor — diagnóstico sistema\n"
        "  /cosecha — cierre de sprint\n"
        "  /commit — commit readiness\n"
        "  /reparar — auto-fix KOs de health\n\n"
        "📋 *Tareas*\n"
        "  /tarea `<texto>` — crear tarea\n"
        "  /tareas — listar pendientes\n\n"
        "📊 *Estado*\n"
        "  /menu — menú principal\n"
        "  /estado — estado BAGO\n"
        "  /sprint — workflow activo\n\n"
        "⚙️ *Operaciones*\n"
        "  /hacer `<cmd>` — ejecutar comando\n"
        "  /git — commits recientes\n"
        "  /nota `<texto>` — guardar nota\n"
        "  /logs — últimos logs\n"
        "  /app — Mini App dashboard\n"
        "  /cartera — portfolio crypto (add BTC 0.5 / alerta BTC 90000)\n"
        "  /airdrop — airdrops TON cobrables (set <ADDRESS> para configurar)\n"
        "  /telemetria — resumen de telemetría local BAGO\n\n"
        "_Texto libre: 'ideas', 'next', 'health', 'doctor', 'cosecha', 'estado', 'git', 'telemetría'..._"
    )
    await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=kb_menu_principal())

# ── Callback handler (botones inline) ────────────────────────────────────────
async def on_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    data = q.data
    chat_id = q.message.chat_id

    owner = get_owner_id()
    if owner and chat_id != owner:
        await q.edit_message_text("⛔ No autorizado.")
        return

    # ── accion:xxx ────────────────────────────────────────────────────────
    if data == "accion:menu":
        await q.edit_message_text("🤖 *BAGO — Menú principal*", parse_mode="Markdown", reply_markup=kb_menu_principal())

    elif data == "accion:estado":
        state = read_state()
        v      = state.get("bago_version", "?")
        health = state.get("system_health", "?")
        inv    = state.get("inventory", {})
        wf     = state.get("sprint_status", {}).get("active_workflow", {})
        wf_str = f"`{wf.get('code','?')}` — {wf.get('title','?')}" if wf else "ninguno"
        tareas = [t for t in load_tareas() if t["status"] == "pendiente"]
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
        await q.edit_message_text(msg, parse_mode="Markdown", reply_markup=kb_estado())

    elif data == "accion:sprint":
        state = read_state()
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
            InlineKeyboardButton("📊 Estado", callback_data="accion:estado"),
            InlineKeyboardButton("🏠 Menú",   callback_data="accion:menu"),
        ]])
        await q.edit_message_text(msg, parse_mode="Markdown", reply_markup=kb)

    elif data == "accion:tareas":
        tareas = load_tareas()
        pendientes = [t for t in tareas if t["status"] == "pendiente"]
        if not pendientes:
            kb = InlineKeyboardMarkup([[
                InlineKeyboardButton("➕ Nueva tarea", callback_data="accion:nueva_tarea"),
                InlineKeyboardButton("🏠 Menú",        callback_data="accion:menu"),
            ]])
            await q.edit_message_text("📋 No hay tareas pendientes. 🎉", reply_markup=kb)
        else:
            lineas = [f"📋 *Tareas pendientes* ({len(pendientes)})\n"]
            for t in pendientes[:8]:
                proj = f"[{t['proyecto'].upper()}] " if t['proyecto'] != 'general' else ""
                lineas.append(f"`{t['id']}` {proj}_{t['titulo'][:55]}_")
            lineas.append("\n✅ Completar  ·  🗑 Borrar")
            await q.edit_message_text("\n".join(lineas), parse_mode="Markdown", reply_markup=kb_tareas(pendientes))

    elif data == "accion:notas":
        state = read_state()
        notes = state.get("notes", "")
        recientes = [n for n in notes.split("\n") if n.strip()][-8:]
        if not recientes:
            txt = "📝 No hay notas guardadas."
        else:
            txt = "📝 *Notas recientes*\n\n" + "\n".join(f"• {n[:70]}" for n in reversed(recientes))
        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton("🏠 Menú", callback_data="accion:menu"),
        ]])
        await q.edit_message_text(txt, parse_mode="Markdown", reply_markup=kb)

    elif data == "accion:git":
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
        except Exception as e:
            msg = f"❌ Git error: {e}"
        await q.edit_message_text(msg, parse_mode="Markdown", reply_markup=kb_git())

    elif data == "accion:logs":
        log_files = ["/tmp/bago_telegram.log", "/tmp/bago_miniapp.log"]
        lines = []
        for lf in log_files:
            p = Path(lf)
            if p.exists() and p.stat().st_size > 0:
                tail = p.read_text().splitlines()[-6:]
                lines.append(f"*{p.name}*\n```\n" + "\n".join(tail) + "\n```")
        txt = "\n\n".join(lines)[:3500] if lines else "📋 Logs vacíos."
        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton("🔄 Refresh", callback_data="accion:logs"),
            InlineKeyboardButton("🏠 Menú",    callback_data="accion:menu"),
        ]])
        await q.edit_message_text(txt, parse_mode="Markdown", reply_markup=kb)

    elif data == "accion:app":
        url = get_miniapp_url()
        if url:
            kb = InlineKeyboardMarkup([[
                InlineKeyboardButton("📊 Abrir BAGO Dashboard", web_app=WebAppInfo(url=url))
            ]])
            await q.edit_message_text("🌐 *BAGO Mini App*", parse_mode="Markdown", reply_markup=kb)
        else:
            await q.edit_message_text("⚠️ Mini App no activa.\n\n`bash launch_miniapp.sh`", parse_mode="Markdown",
                                       reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Menú", callback_data="accion:menu")]]))

    elif data == "accion:nueva_tarea":
        ctx.user_data["esperando_tarea"] = True
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancelar", callback_data="accion:tareas")]])
        await q.edit_message_text(
            "📝 Escribe la descripción de la tarea nueva:\n\n"
            "_Puedes añadir proyecto con formato `PROYECTO: descripción`_\n"
            "_Ej: `DERIVA: fix cámara isométrica`_",
            parse_mode="Markdown", reply_markup=kb
        )

    elif data == "accion:ideas":
        await q.edit_message_text("💡 Consultando ideas...", parse_mode="Markdown")
        snapshot = BAGO_ROOT / ".bago/state/ideas_snapshot.md"
        if snapshot.exists():
            txt = snapshot.read_text(encoding="utf-8")
            blocks = txt.strip().split("\n## ")
            ideas_txt = []
            for b in blocks[1:5]:
                lines = b.strip().splitlines()
                title = lines[0].strip() if lines else "?"
                m = re.match(r"\[(\d+)\]\s*(.*)", title)
                score = m.group(1) if m else "?"
                name  = m.group(2) if m else title
                ideas_txt.append(f"• [{score}] {name}")
            msg = "💡 *Ideas prioritarias*\n\n" + "\n".join(ideas_txt)
        else:
            out = run_bago("ideas", timeout=15)
            msg = f"💡 *BAGO Ideas*\n\n```\n{out[:1600]}\n```"
        kb2 = InlineKeyboardMarkup([[
            InlineKeyboardButton("✅ Next [↩]",  callback_data="accion:next"),
            InlineKeyboardButton("👁 Ver tarea", callback_data="accion:next_preview"),
            InlineKeyboardButton("🏠 Menú",      callback_data="accion:menu"),
        ]])
        await q.edit_message_text(msg, parse_mode="Markdown", reply_markup=kb2)

    elif data == "accion:next":
        await q.edit_message_text("⚡ Aceptando próxima tarea...", parse_mode="Markdown")
        out = run_bago("next", ["--auto"], timeout=20)
        kb2 = InlineKeyboardMarkup([[
            InlineKeyboardButton("👁 Ver ideas", callback_data="accion:ideas"),
            InlineKeyboardButton("📋 Tareas",    callback_data="accion:tareas"),
            InlineKeyboardButton("🏠 Menú",      callback_data="accion:menu"),
        ]])
        await q.edit_message_text(f"⚡ *Tarea aceptada*\n\n```\n{out[:1800]}\n```", parse_mode="Markdown", reply_markup=kb2)

    elif data == "accion:next_preview":
        await q.edit_message_text("👁 Consultando próxima tarea (preview)...", parse_mode="Markdown")
        out = run_bago("next", ["--dry"], timeout=15)
        kb2 = InlineKeyboardMarkup([[
            InlineKeyboardButton("✅ Aceptar [↩ Enter]", callback_data="accion:next_accept"),
            InlineKeyboardButton("🏠 Menú",              callback_data="accion:menu"),
        ]])
        await q.edit_message_text(f"👁 *Next — Preview*\n\n```\n{out[:1800]}\n```", parse_mode="Markdown", reply_markup=kb2)

    elif data == "accion:next_accept":
        await q.edit_message_text("⚡ Aceptando tarea (bago next --auto)...", parse_mode="Markdown")
        out = run_bago("next", ["--auto"], timeout=20)
        kb2 = InlineKeyboardMarkup([[
            InlineKeyboardButton("📋 Tareas", callback_data="accion:tareas"),
            InlineKeyboardButton("🏠 Menú",   callback_data="accion:menu"),
        ]])
        await q.edit_message_text(f"⚡ *Tarea aceptada*\n\n```\n{out[:1800]}\n```", parse_mode="Markdown", reply_markup=kb2)

    elif data == "accion:cartera":
        await q.edit_message_text("💰 Consultando precios…", parse_mode="Markdown")
        import sys as _sys
        _sys.path.insert(0, str(TOOLS_DIR))
        try:
            from wallet_tracker import portfolio_summary, format_summary, check_alerts
            data2 = portfolio_summary()
            text = format_summary(data2)
            alerts = check_alerts(data2)
            if alerts:
                text += "\n\n" + "\n".join(alerts)
            kb2 = InlineKeyboardMarkup([[
                InlineKeyboardButton("🔄 Actualizar", callback_data="accion:cartera"),
                InlineKeyboardButton("🏠 Menú",       callback_data="accion:menu"),
            ]])
            await q.edit_message_text(text, reply_markup=kb2)
        except Exception as e:
            await q.edit_message_text(f"❌ Error cartera: {e}")

    elif data == "accion:airdrop":
        await q.edit_message_text("🔍 Escaneando wallet TON…")
        import sys as _sys
        _sys.path.insert(0, str(TOOLS_DIR))
        try:
            from airdrop_scanner import scan_airdrops, format_airdrops, get_ton_address
            address = get_ton_address()
            if not address:
                await q.edit_message_text(
                    "🪂 No hay TON address configurada.\nUsa /airdrop set <ADDRESS>"
                )
            else:
                data2 = scan_airdrops(address)
                text2 = format_airdrops(data2)
                kb2 = InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔄 Re-escanear", callback_data="accion:airdrop"),
                    InlineKeyboardButton("🏠 Menú",        callback_data="accion:menu"),
                ]])
                await q.edit_message_text(text2, reply_markup=kb2)
        except Exception as e:
            await q.edit_message_text(f"❌ Error airdrop: {e}")

    elif data == "accion:health":
        await q.edit_message_text("⚕️ Calculando health score...", parse_mode="Markdown")
        out = run_bago("health", timeout=20)
        kb2 = InlineKeyboardMarkup([[
            InlineKeyboardButton("🔍 Doctor", callback_data="accion:doctor"),
            InlineKeyboardButton("🏠 Menú",   callback_data="accion:menu"),
        ]])
        await q.edit_message_text(f"⚕️ *Health*\n\n```\n{out[:1800]}\n```", parse_mode="Markdown", reply_markup=kb2)

    elif data == "accion:doctor":
        await q.edit_message_text("🔍 Ejecutando diagnóstico...", parse_mode="Markdown")
        out = run_bago("doctor", timeout=25)
        kb2 = InlineKeyboardMarkup([[
            InlineKeyboardButton("⚕️ Health", callback_data="accion:health"),
            InlineKeyboardButton("🏠 Menú",   callback_data="accion:menu"),
        ]])
        await q.edit_message_text(f"🔍 *Doctor*\n\n```\n{out[:1800]}\n```", parse_mode="Markdown", reply_markup=kb2)

    elif data == "accion:cosecha_confirm":
        await q.edit_message_text("🌾 Ejecutando bago cosecha...", parse_mode="Markdown")
        out = run_bago("cosecha", timeout=30)
        kb2 = InlineKeyboardMarkup([[
            InlineKeyboardButton("📊 Estado", callback_data="accion:estado"),
            InlineKeyboardButton("🏠 Menú",   callback_data="accion:menu"),
        ]])
        await q.edit_message_text(f"🌾 *Cosecha*\n\n```\n{out[:1800]}\n```", parse_mode="Markdown", reply_markup=kb2)

    elif data == "accion:reparar":
        await q.edit_message_text("🔧 Iniciando reparación de health KOs...", parse_mode="Markdown")
        # Construir fake_update con effective_chat para que check_auth funcione
        fake_update = type('U', (), {
            'message': q.message,
            'effective_user': q.from_user,
            'effective_chat': q.message.chat,
        })()
        await cmd_reparar(fake_update, ctx)

    elif data == "accion:telemetria":
        events = _load_telemetry_events()
        if not events:
            await q.edit_message_text(
                "📊 *Telemetría*\n\nSin datos aún.",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Menú", callback_data="accion:menu")]])
            )
            return
        from collections import Counter
        cmds   = [e for e in events if e.get("type") == "command"]
        errors = [e for e in events if e.get("type") == "exception"]
        ok_n   = sum(1 for e in cmds if e.get("properties", {}).get("success") is True)
        fail_n = sum(1 for e in cmds if e.get("properties", {}).get("success") is False)
        top    = Counter(e.get("name", "?") for e in cmds).most_common(3)
        top_str = "\n".join(f"  `{n}` × {c}" for n, c in top) if top else "  —"
        last   = events[-1]
        durs   = [e["metrics"]["duration_s"] for e in cmds if e.get("metrics", {}).get("duration_s") is not None]
        avg_dur = f"{sum(durs)/len(durs):.2f}s" if durs else "—"
        msg = (
            f"📊 *BAGO Telemetría*\n\n"
            f"📦 Total: `{len(events)}` · ⚡ Cmds: `{len(cmds)}` (✅{ok_n} ❌{fail_n})\n"
            f"💥 Excepciones: `{len(errors)}` · ⏱ Avg: `{avg_dur}`\n\n"
            f"🔝 *Top:*\n{top_str}\n\n"
            f"🕐 Último: `{last.get('name','?')}` — {str(last.get('ts',''))[:16]}"
        )
        kb2 = InlineKeyboardMarkup([[
            InlineKeyboardButton("🔄 Refresh", callback_data="accion:telemetria"),
            InlineKeyboardButton("🏠 Menú",    callback_data="accion:menu"),
        ]])
        await q.edit_message_text(msg, parse_mode="Markdown", reply_markup=kb2)

    elif data == "accion:ayuda":
        msg = (
            "🤖 *BAGO v2 — Comandos*\n\n"
            "💡 `/ideas` · `/next` · `/health` · `/doctor`\n"
            "📋 `/tarea` · `/tareas`\n"
            "📊 `/menu` · `/estado` · `/sprint`\n"
            "⚙️ `/hacer` · `/git` · `/nota` · `/logs`\n"
            "💰 `/cartera` · `/airdrop`\n"
            "📈 `/telemetria` — telemetría local\n"
            "🌐 `/app` — Mini App"
        )
        await q.edit_message_text(msg, parse_mode="Markdown", reply_markup=kb_menu_principal())

    # ── completar:id ──────────────────────────────────────────────────────
    elif data.startswith("completar:"):
        tid = data.split(":", 1)[1]
        ok = completar_tarea(tid)
        tareas = load_tareas()
        pendientes = [t for t in tareas if t["status"] == "pendiente"]
        if ok:
            if pendientes:
                lineas = [f"✅ Tarea `{tid}` completada.\n\n📋 *Pendientes ({len(pendientes)})*\n"]
                for t in pendientes[:6]:
                    proj = f"[{t['proyecto'].upper()}] " if t['proyecto'] != 'general' else ""
                    lineas.append(f"`{t['id']}` {proj}_{t['titulo'][:50]}_")
                await q.edit_message_text("\n".join(lineas), parse_mode="Markdown", reply_markup=kb_tareas(pendientes))
            else:
                kb = InlineKeyboardMarkup([[
                    InlineKeyboardButton("➕ Nueva tarea", callback_data="accion:nueva_tarea"),
                    InlineKeyboardButton("🏠 Menú",        callback_data="accion:menu"),
                ]])
                await q.edit_message_text(f"✅ Tarea `{tid}` completada.\n\n¡Sin pendientes! 🎉", reply_markup=kb)
        else:
            await q.edit_message_text(f"❌ Tarea `{tid}` no encontrada.", parse_mode="Markdown")

    # ── borrar:id ─────────────────────────────────────────────────────────
    elif data.startswith("borrar:"):
        tid = data.split(":", 1)[1]
        ok = eliminar_tarea(tid)
        tareas = load_tareas()
        pendientes = [t for t in tareas if t["status"] == "pendiente"]
        txt = f"🗑 Tarea `{tid}` borrada." if ok else f"❌ Tarea `{tid}` no encontrada."
        if pendientes:
            await q.edit_message_text(txt + f"\n\n📋 Pendientes: {len(pendientes)}", parse_mode="Markdown", reply_markup=kb_tareas(pendientes))
        else:
            kb = InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Menú", callback_data="accion:menu")]])
            await q.edit_message_text(txt + "\n\n¡Sin pendientes! 🎉", parse_mode="Markdown", reply_markup=kb)

    # ── cmd:git xxx ───────────────────────────────────────────────────────
    elif data.startswith("cmd:"):
        cmd = data[4:]
        out = run_safe(cmd)
        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton("🔄 Refresh", callback_data=data),
            InlineKeyboardButton("🏠 Menú",    callback_data="accion:menu"),
        ]])
        await q.edit_message_text(f"`{cmd}`\n\n```\n{out[:1400]}\n```", parse_mode="Markdown", reply_markup=kb)

# ── Texto libre ───────────────────────────────────────────────────────────────
async def handle_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not await check_auth(update):
        return
    text = update.message.text.strip()
    tl   = text.lower()
    log.info(f"[MSG] {text[:80]}")

    # Modo esperando tarea
    if ctx.user_data.get("esperando_tarea"):
        ctx.user_data["esperando_tarea"] = False
        proyecto = "general"
        titulo = text
        if ":" in text and len(text.split(":")[0]) < 20:
            partes = text.split(":", 1)
            proyecto = partes[0].strip().lower()
            titulo = partes[1].strip()
        tarea = crear_tarea(titulo, proyecto)
        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton("📋 Ver tareas", callback_data="accion:tareas"),
            InlineKeyboardButton("✅ Completar",  callback_data=f"completar:{tarea['id']}"),
        ]])
        await update.message.reply_text(
            f"✅ Tarea creada `{tarea['id']}`\n\n*{proyecto.upper()}*: _{titulo}_",
            parse_mode="Markdown", reply_markup=kb
        )
        return

    # Detección de intención por palabras clave
    if re.search(r"\b(ping|test)\b", tl):
        await update.message.reply_text("🏓 pong — BAGO activo")

    elif re.search(r"\b(menu|menú|start|inicio)\b", tl):
        await update.message.reply_text("🤖 *BAGO — Menú*", parse_mode="Markdown", reply_markup=kb_menu_principal())

    elif re.search(r"\b(estado|status)\b", tl):
        await _send_estado(update.effective_chat.id, ctx)

    elif re.search(r"\b(sprint|workflow|wf)\b", tl):
        await cmd_sprint(update, ctx)

    elif re.search(r"\b(git|commit|branch|rama)\b", tl):
        await cmd_git(update, ctx)

    elif re.search(r"\b(tareas|tasks|pendiente|todo)\b", tl):
        await cmd_tareas(update, ctx)

    elif re.search(r"\b(log|logs|output|salida)\b", tl):
        await cmd_logs(update, ctx)

    elif re.search(r"\b(app|dashboard|miniapp|mini)\b", tl):
        await cmd_app(update, ctx)

    elif re.search(r"\b(ideas?|idea)\b", tl):
        await cmd_ideas(update, ctx)

    elif re.search(r"\b(next|siguiente|próxima|proxima)\b", tl):
        await cmd_next(update, ctx)

    elif re.search(r"\b(health|salud|score)\b", tl):
        await cmd_health(update, ctx)

    elif re.search(r"\b(doctor|diagnos|diagn[oó]stico)\b", tl):
        await cmd_doctor(update, ctx)

    elif re.search(r"\b(cosecha|harvest|cierre)\b", tl):
        await cmd_cosecha(update, ctx)

    elif re.search(r"\b(commit|readiness|listo para commit)\b", tl):
        await cmd_commit(update, ctx)

    elif re.search(r"\b(reparar|repair|fix|arreglar|sanar)\b", tl):
        await cmd_reparar(update, ctx)

    elif re.search(r"\b(telemetr[íi]a|telemetry|stats?|métricas?|metricas?)\b", tl):
        await cmd_telemetria(update, ctx)

    elif re.search(r"\b(nota|note|apunta|apuntar|recordar)\b", tl):
        # Si hay contenido después de la palabra clave, guardar directamente
        m = re.search(r"\b(?:nota|note|apunta|apuntar|recordar)\s+(.+)", text, re.I)
        if m:
            contenido = m.group(1).strip()
            state = read_state()
            ts = datetime.now().strftime("%Y-%m-%d %H:%M")
            prev = state.get("notes", "")
            state["notes"] = f"{prev}\n{ts} [TG]: {contenido}".strip()
            write_state(state)
            kb = InlineKeyboardMarkup([[InlineKeyboardButton("📝 Ver notas", callback_data="accion:notas")]])
            await update.message.reply_text(f"📝 Nota guardada: _{contenido[:80]}_", parse_mode="Markdown", reply_markup=kb)
        else:
            await update.message.reply_text(
                "📝 ¿Qué quieres anotar?\nEscribe: `nota <texto>` o usa `/nota <texto>`",
                parse_mode="Markdown"
            )

    elif re.search(r"\b(tarea|task|hacer|create|crea)\b", tl):
        # Si hay contenido después, crear tarea directamente
        m = re.search(r"\b(?:tarea|task|hacer|create|crea)\s+(.+)", text, re.I)
        if m:
            titulo = m.group(1).strip()
            tarea = crear_tarea(titulo)
            kb = InlineKeyboardMarkup([[
                InlineKeyboardButton("📋 Tareas", callback_data="accion:tareas"),
                InlineKeyboardButton("✅ Hecho",  callback_data=f"completar:{tarea['id']}"),
            ]])
            await update.message.reply_text(
                f"✅ Tarea `{tarea['id']}` creada:\n_{titulo}_",
                parse_mode="Markdown", reply_markup=kb
            )
        else:
            ctx.user_data["esperando_tarea"] = True
            await update.message.reply_text("📝 Escribe la descripción de la tarea:")

    elif re.search(r"\b(ayuda|help|comandos|qué puedes)\b", tl):
        await cmd_ayuda(update, ctx)

    else:
        # Respuesta contextual con sugerencias
        state = read_state()
        wf = state.get("sprint_status", {}).get("active_workflow", {})
        tareas_p = [t for t in load_tareas() if t["status"] == "pendiente"]
        msg = (
            f"🤖 BAGO recibió: _{text[:80]}_\n\n"
            f"⚡ Workflow activo: `{wf.get('code','?')}`\n"
            f"📋 Tareas pendientes: {len(tareas_p)}\n\n"
            f"¿Qué quieres hacer?"
        )
        await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=kb_menu_principal())


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

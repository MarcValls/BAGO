from __future__ import annotations

from bago_utils import load_json, save_json, timestamp_iso

import re
from datetime import datetime
from pathlib import Path

from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
)
from telegram.ext import ContextTypes

# Sub-modules with the actual command handlers
import _telegram_cmd_a as _a
import _telegram_cmd_b as _b

from _telegram_ui import kb_estado, kb_git, kb_menu_principal, kb_tareas

# ── Re-exports so bago_telegram_daemon.py imports unchanged ──────────────────
from _telegram_cmd_a import (
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
)
from _telegram_cmd_b import (
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
    cmd_ayuda,
)


# ── Callback query handler ────────────────────────────────────────────────────
async def on_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    data = q.data
    chat_id = q.message.chat_id

    owner = _a._get_owner_id()
    if owner and chat_id != owner:
        await q.edit_message_text("⛔ No autorizado.")
        return

    # ── accion:xxx ────────────────────────────────────────────────────────
    if data == "accion:menu":
        await q.edit_message_text("🤖 *BAGO — Menú principal*", parse_mode="Markdown", reply_markup=kb_menu_principal())

    elif data == "accion:estado":
        state = _a._read_state()
        v      = state.get("bago_version", "?")
        health = state.get("system_health", "?")
        inv    = state.get("inventory", {})
        wf     = state.get("sprint_status", {}).get("active_workflow", {})
        wf_str = f"`{wf.get('code','?')}` — {wf.get('title','?')}" if wf else "ninguno"
        tareas = [t for t in _a._load_tareas() if t["status"] == "pendiente"]
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
        state = _a._read_state()
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
        tareas = _a._load_tareas()
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
        state = _a._read_state()
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
                ["git", "-C", str(_a.BAGO_ROOT), "log", "--oneline", "-6"],
                capture_output=True, text=True, timeout=10
            )
            branch = subprocess.run(
                ["git", "-C", str(_a.BAGO_ROOT), "branch", "--show-current"],
                capture_output=True, text=True, timeout=5
            ).stdout.strip()
            out = result.stdout.strip() or "sin commits"
            msg = f"🌿 Rama: `{branch}`\n\n```\n{out}\n```"
        except Exception as e:
            msg = f"❌ Git error: {e}"
        await q.edit_message_text(msg, parse_mode="Markdown", reply_markup=kb_git())

    elif data == "accion:logs":
        log_files = [str(_a.LOG_DIR / "telegram.log"), str(_a.LOG_DIR / "miniapp.log")]
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
        url = _a._get_miniapp_url()
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
        snapshot = _a.BAGO_ROOT / ".bago/state/ideas_snapshot.md"
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
            out = _a._run_bago("ideas", timeout=15)
            msg = f"💡 *BAGO Ideas*\n\n```\n{out[:1600]}\n```"
        kb2 = InlineKeyboardMarkup([[
            InlineKeyboardButton("✅ Next [↩]",  callback_data="accion:next"),
            InlineKeyboardButton("👁 Ver tarea", callback_data="accion:next_preview"),
            InlineKeyboardButton("🏠 Menú",      callback_data="accion:menu"),
        ]])
        await q.edit_message_text(msg, parse_mode="Markdown", reply_markup=kb2)

    elif data == "accion:next":
        await q.edit_message_text("⚡ Aceptando próxima tarea...", parse_mode="Markdown")
        out = _a._run_bago("next", ["--auto"], timeout=20)
        kb2 = InlineKeyboardMarkup([[
            InlineKeyboardButton("👁 Ver ideas", callback_data="accion:ideas"),
            InlineKeyboardButton("📋 Tareas",    callback_data="accion:tareas"),
            InlineKeyboardButton("🏠 Menú",      callback_data="accion:menu"),
        ]])
        await q.edit_message_text(f"⚡ *Tarea aceptada*\n\n```\n{out[:1800]}\n```", parse_mode="Markdown", reply_markup=kb2)

    elif data == "accion:next_preview":
        await q.edit_message_text("👁 Consultando próxima tarea (preview)...", parse_mode="Markdown")
        out = _a._run_bago("next", ["--dry"], timeout=15)
        kb2 = InlineKeyboardMarkup([[
            InlineKeyboardButton("✅ Aceptar [↩ Enter]", callback_data="accion:next_accept"),
            InlineKeyboardButton("🏠 Menú",              callback_data="accion:menu"),
        ]])
        await q.edit_message_text(f"👁 *Next — Preview*\n\n```\n{out[:1800]}\n```", parse_mode="Markdown", reply_markup=kb2)

    elif data == "accion:next_accept":
        await q.edit_message_text("⚡ Aceptando tarea (bago next --auto)...", parse_mode="Markdown")
        out = _a._run_bago("next", ["--auto"], timeout=20)
        kb2 = InlineKeyboardMarkup([[
            InlineKeyboardButton("📋 Tareas", callback_data="accion:tareas"),
            InlineKeyboardButton("🏠 Menú",   callback_data="accion:menu"),
        ]])
        await q.edit_message_text(f"⚡ *Tarea aceptada*\n\n```\n{out[:1800]}\n```", parse_mode="Markdown", reply_markup=kb2)

    elif data == "accion:cartera":
        await q.edit_message_text("💰 Consultando precios…", parse_mode="Markdown")
        import sys as _sys
        _sys.path.insert(0, str(_a.TOOLS_DIR))
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
        _sys.path.insert(0, str(_a.TOOLS_DIR))
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
        out = _a._run_bago("health", timeout=20)
        kb2 = InlineKeyboardMarkup([[
            InlineKeyboardButton("🔍 Doctor", callback_data="accion:doctor"),
            InlineKeyboardButton("🏠 Menú",   callback_data="accion:menu"),
        ]])
        await q.edit_message_text(f"⚕️ *Health*\n\n```\n{out[:1800]}\n```", parse_mode="Markdown", reply_markup=kb2)

    elif data == "accion:doctor":
        await q.edit_message_text("🔍 Ejecutando diagnóstico...", parse_mode="Markdown")
        out = _a._run_bago("doctor", timeout=25)
        kb2 = InlineKeyboardMarkup([[
            InlineKeyboardButton("⚕️ Health", callback_data="accion:health"),
            InlineKeyboardButton("🏠 Menú",   callback_data="accion:menu"),
        ]])
        await q.edit_message_text(f"🔍 *Doctor*\n\n```\n{out[:1800]}\n```", parse_mode="Markdown", reply_markup=kb2)

    elif data == "accion:cosecha_confirm":
        await q.edit_message_text("🌾 Ejecutando bago cosecha...", parse_mode="Markdown")
        out = _a._run_bago("cosecha", timeout=30)
        kb2 = InlineKeyboardMarkup([[
            InlineKeyboardButton("📊 Estado", callback_data="accion:estado"),
            InlineKeyboardButton("🏠 Menú",   callback_data="accion:menu"),
        ]])
        await q.edit_message_text(f"🌾 *Cosecha*\n\n```\n{out[:1800]}\n```", parse_mode="Markdown", reply_markup=kb2)

    elif data == "accion:reparar":
        # _b.cmd_reparar envía sus propios mensajes de progreso vía reply_text;
        # no editamos aquí para evitar doble mensaje
        fake_update = type('U', (), {
            'message': q.message,
            'effective_user': q.from_user,
            'effective_chat': q.message.chat,
        })()
        await _b.cmd_reparar(fake_update, ctx)

    elif data == "accion:telemetria":
        events = _a._load_telemetry_events()
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
        ok = _a._completar_tarea(tid)
        tareas = _a._load_tareas()
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
        ok = _a._eliminar_tarea(tid)
        tareas = _a._load_tareas()
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
        out = _a._run_safe(cmd)
        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton("🔄 Refresh", callback_data=data),
            InlineKeyboardButton("🏠 Menú",    callback_data="accion:menu"),
        ]])
        await q.edit_message_text(f"`{cmd}`\n\n```\n{out[:1400]}\n```", parse_mode="Markdown", reply_markup=kb)

    else:
        _a._log.warning(f"[CALLBACK] Sin handler para: {data!r}")
        await q.answer("⚠️ Acción no reconocida", show_alert=False)



# ── Texto libre ───────────────────────────────────────────────────────────────
async def handle_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not await check_auth(update):
        return
    text = update.message.text.strip()
    tl   = text.lower()
    _a._log.info(f"[MSG] {text[:80]}")

    # Modo esperando tarea
    if ctx.user_data.get("esperando_tarea"):
        ctx.user_data["esperando_tarea"] = False
        proyecto = "general"
        titulo = text
        if ":" in text and len(text.split(":")[0]) < 20:
            partes = text.split(":", 1)
            proyecto = partes[0].strip().lower()
            titulo = partes[1].strip()
        tarea = _a._crear_tarea(titulo, proyecto)
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
        await _a._send_estado(update.effective_chat.id, ctx)

    elif re.search(r"\b(sprint|workflow|wf)\b", tl):
        await _a.cmd_sprint(update, ctx)

    elif re.search(r"\b(git|commit|branch|rama)\b", tl):
        await _a.cmd_git(update, ctx)

    elif re.search(r"\b(tareas|tasks|pendiente|todo)\b", tl):
        await _a.cmd_tareas(update, ctx)

    elif re.search(r"\b(log|logs|output|salida)\b", tl):
        await _a.cmd_logs(update, ctx)

    elif re.search(r"\b(app|dashboard|miniapp|mini)\b", tl):
        await _a.cmd_app(update, ctx)

    elif re.search(r"\b(ideas?|idea)\b", tl):
        await _b.cmd_ideas(update, ctx)

    elif re.search(r"\b(next|siguiente|próxima|proxima)\b", tl):
        await _b.cmd_next(update, ctx)

    elif re.search(r"\b(health|salud|score)\b", tl):
        await _b.cmd_health(update, ctx)

    elif re.search(r"\b(doctor|diagnos|diagn[oó]stico)\b", tl):
        await _b.cmd_doctor(update, ctx)

    elif re.search(r"\b(cosecha|harvest|cierre)\b", tl):
        await _b.cmd_cosecha(update, ctx)

    elif re.search(r"\b(commit|readiness|listo para commit)\b", tl):
        await _b.cmd_commit(update, ctx)

    elif re.search(r"\b(reparar|repair|fix|arreglar|sanar)\b", tl):
        await _b.cmd_reparar(update, ctx)

    elif re.search(r"\b(telemetr[íi]a|telemetry|stats?|métricas?|metricas?)\b", tl):
        await _b.cmd_telemetria(update, ctx)

    elif re.search(r"\b(nota|note|apunta|apuntar|recordar)\b", tl):
        # Si hay contenido después de la palabra clave, guardar directamente
        m = re.search(r"\b(?:nota|note|apunta|apuntar|recordar)\s+(.+)", text, re.I)
        if m:
            contenido = m.group(1).strip()
            state = _a._read_state()
            ts = datetime.now().strftime("%Y-%m-%d %H:%M")
            prev = state.get("notes", "")
            state["notes"] = f"{prev}\n{ts} [TG]: {contenido}".strip()
            _a._write_state(state)
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
            tarea = _a._crear_tarea(titulo)
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
        await _b.cmd_ayuda(update, ctx)

    else:
        # Respuesta contextual con sugerencias
        state = _a._read_state()
        wf = state.get("sprint_status", {}).get("active_workflow", {})
        tareas_p = [t for t in _a._load_tareas() if t["status"] == "pendiente"]
        msg = (
            f"🤖 BAGO recibió: _{text[:80]}_\n\n"
            f"⚡ Workflow activo: `{wf.get('code','?')}`\n"
            f"📋 Tareas pendientes: {len(tareas_p)}\n\n"
            f"¿Qué quieres hacer?"
        )
        await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=kb_menu_principal())



from __future__ import annotations

from bago_utils import load_json, save_json, timestamp_iso

import asyncio
import re
import subprocess
import sys
from pathlib import Path

from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
)
from telegram.ext import ContextTypes

# State and helpers are in _telegram_cmd_a (the shared root module)
import _telegram_cmd_a as _a
from _telegram_ui import kb_menu_principal

async def cmd_ideas(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Muestra las ideas prioritarias de BAGO."""
    if not await _a.check_auth(update):
        return
    await update.message.reply_text("💡 Consultando ideas BAGO...", parse_mode="Markdown")
    # Primero intenta leer el snapshot (rápido y sin side effects)
    snapshot = _a.BAGO_ROOT / ".bago/state/ideas_snapshot.md"
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
        out = _a._run_bago("ideas", timeout=15)
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
    if not await _a.check_auth(update):
        return
    await update.message.reply_text("⚡ Aceptando próxima tarea...", parse_mode="Markdown")
    out = _a._run_bago("next", ["--auto"], timeout=20)
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("👁 Ver ideas",     callback_data="accion:ideas"),
        InlineKeyboardButton("📋 Tareas",        callback_data="accion:tareas"),
        InlineKeyboardButton("🏠 Menú",          callback_data="accion:menu"),
    ]])
    await update.message.reply_text(f"⚡ *Tarea aceptada*\n\n```\n{out[:1800]}\n```", parse_mode="Markdown", reply_markup=kb)

async def cmd_health(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Muestra el health score BAGO."""
    if not await _a.check_auth(update):
        return
    await update.message.reply_text("⚕️ Calculando health score...", parse_mode="Markdown")
    out = _a._run_bago("health", timeout=20)
    # SAC: si score bajo, sugerir audit full (Pit of Success R-PROD-06)
    import re as _re
    _m = _re.search(r"(\d+)/100", out)
    sac_hint = "\n\n💡 *SAC* — Score bajo\\. Ejecuta: `bago audit full` para diagnosticar\\." if (_m and int(_m.group(1)) < 60) else ""
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("🔍 Doctor",   callback_data="accion:doctor"),
        InlineKeyboardButton("📊 Estado",   callback_data="accion:estado"),
        InlineKeyboardButton("🏠 Menú",     callback_data="accion:menu"),
    ]])
    await update.message.reply_text(f"⚕️ *BAGO Health*\n\n```\n{out[:1800]}\n```{sac_hint}", parse_mode="Markdown", reply_markup=kb)

async def cmd_doctor(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Diagnóstico BAGO — detecta problemas en el sistema."""
    if not await _a.check_auth(update):
        return
    await update.message.reply_text("🔍 Ejecutando diagnóstico BAGO...", parse_mode="Markdown")
    out = _a._run_bago("doctor", timeout=25)
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("⚕️ Health",   callback_data="accion:health"),
        InlineKeyboardButton("🏠 Menú",     callback_data="accion:menu"),
    ]])
    await update.message.reply_text(f"🔍 *BAGO Doctor*\n\n```\n{out[:1800]}\n```", parse_mode="Markdown", reply_markup=kb)

async def cmd_cosecha(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Ejecuta bago cosecha — cierre de sprint y generación de artefactos."""
    if not await _a.check_auth(update):
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
    if not await _a.check_auth(update):
        return
    await update.message.reply_text("📦 Verificando commit readiness...", parse_mode="Markdown")
    out = _a._run_bago("commit", timeout=15)
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("🌿 Git status", callback_data="cmd:git status"),
        InlineKeyboardButton("🏠 Menú",       callback_data="accion:menu"),
    ]])
    await update.message.reply_text(f"📦 *Commit Readiness*\n\n```\n{out[:1800]}\n```", parse_mode="Markdown", reply_markup=kb)

async def cmd_reparar(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Auto-repara KOs detectados por bago health."""
    if not await _a.check_auth(update):
        return
    await update.message.reply_text("🔧 Analizando health para reparar KOs...", parse_mode="Markdown")

    health_out = _a._run_bago("health", timeout=30)

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
            vp_path = _a.BAGO_ROOT / ".bago/tools/validate_pack.py"
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
                [sys.executable, str(_a.BAGO_ROOT / ".bago/tools/repo_context_guard.py"), "sync"],
                capture_output=True, text=True, timeout=20,
                cwd=str(_a.BAGO_ROOT)
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
        health_after = _a._run_bago("health", timeout=30)
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
    if not await _a.check_auth(update):
        return
    args = ctx.args  # e.g. ["add", "BTC", "0.5"] or ["alerta", "BTC", "90000"]

    import sys as _sys
    _sys.path.insert(0, str(_a.TOOLS_DIR))
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
    if not await _a.check_auth(update):
        return
    args = ctx.args  # ["set", "<ADDRESS>"] | ["scan"] | []

    import sys as _sys
    _sys.path.insert(0, str(_a.TOOLS_DIR))
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
    if not await _a.check_auth(update):
        return
    events = _a._load_telemetry_events()
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



async def cmd_ayuda(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not await _a.check_auth(update):
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

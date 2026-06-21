"""
Bot de Telegram — Tragaperras 🎰

Comandos:
  /start       → Bienvenida + 500 fichas gratis (saldo persistente en SQLite)
  /girar       → Girar los rodillos
  /saldo       → Ver saldo y estadísticas
  /apostar <N> → Cambiar la apuesta
  /diario      → Reclamar giros gratis diarios (50 fichas cada 24h)
  /milink      → Obtener link de referido (gana 50 fichas por amigo)
  /ranking     → Ver top 10 jugadores
  /casino      → Abrir interfaz gráfica (Mini App)
  /tabla       → Tabla de pagos
  /ayuda       → Esta ayuda
"""

import os
import logging
from dotenv import load_dotenv

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)
from telegram.constants import ParseMode

import db
from slot_engine import paytable

load_dotenv()

WEBAPP_URL = os.getenv("WEBAPP_URL", "")
BOT_USERNAME = os.getenv("BOT_USERNAME", "N_jubot")

_MIN_BET = 5
_MAX_BET = 500

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ─── Teclado inline ───────────────────────────────────────────────────────────

def _main_keyboard(p: dict) -> InlineKeyboardMarkup:
    vip = "👑 " if p.get("vip_tier", 0) > 0 else ""
    rows = [
        [InlineKeyboardButton(f"{vip}🎰 GIRAR  (apuesta: {p['bet']}🪙)", callback_data="girar")],
        [
            InlineKeyboardButton("➖ Bajar apuesta", callback_data="bet_down"),
            InlineKeyboardButton("➕ Subir apuesta", callback_data="bet_up"),
        ],
        [
            InlineKeyboardButton("💰 Saldo", callback_data="saldo"),
            InlineKeyboardButton("🎁 Diario", callback_data="diario"),
        ],
        [
            InlineKeyboardButton("📋 Tabla pagos", callback_data="tabla"),
            InlineKeyboardButton("🏆 Ranking", callback_data="ranking"),
        ],
        [
            InlineKeyboardButton("💎 Comprar fichas", callback_data="pkg_standard"),
        ],
    ]
    if WEBAPP_URL:
        rows.append([
            InlineKeyboardButton(
                "🖥️ Casino gráfico",
                web_app=WebAppInfo(url=WEBAPP_URL),
            )
        ])
    return InlineKeyboardMarkup(rows)


# ─── Handlers ─────────────────────────────────────────────────────────────────

async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    uid = user.id
    name = user.first_name
    username = user.username or name

    # Detectar referido en args: /start ref_12345
    referred_by = None
    if ctx.args:
        arg = ctx.args[0]
        if arg.startswith("ref_"):
            try:
                referred_by = int(arg[4:])
            except ValueError:
                pass

    p = db.ensure_player(uid, username=username, referred_by=referred_by)
    jackpot = db.get_jackpot()

    welcome = "🔄 ¡Bienvenido de vuelta" if p["total_spins"] > 0 else "🎰 ¡Bienvenido"
    ref_note = ""
    if referred_by and p["total_spins"] == 0:
        ref_note = f"\n🎁 *Registrado por un amigo* — te han regalado fichas extra.\n"

    text = (
        f"{welcome}, *{name}*!\n"
        f"{ref_note}\n"
        f"💰 Saldo: *{p['balance']}🪙*\n"
        f"🎯 Jackpot progresivo: *{jackpot}🪙*\n\n"
        "━━━━━━━━━━━━━━━━━\n"
        "🍒🍒🍒 Cerezas  ×8\n"
        "🍋🍋🍋 Limones  ×8\n"
        "🍊🍊🍊 Naranjas ×15\n"
        "🍇🍇🍇 Uvas     ×25\n"
        "⭐⭐⭐ Estrellas ×60\n"
        "💎💎💎 Diamantes ×150\n"
        "7️⃣7️⃣7️⃣  JACKPOT  ×500 + pozo 🎉\n"
        "━━━━━━━━━━━━━━━━━\n\n"
        "Pulsa *GIRAR* para empezar. ¡Buena suerte! 🤞"
    )
    await update.message.reply_text(
        text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=_main_keyboard(p),
    )


async def cmd_girar(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    p = db.get_player(uid)
    if p is None:
        p = db.ensure_player(uid, username=update.effective_user.username or "")

    if p["balance"] < p["bet"]:
        await update.message.reply_text(
            "💸 ¡Sin fichas! Usa /diario para fichas gratis o /start.",
            reply_markup=_main_keyboard(p),
        )
        return
    await _do_spin(update, uid, via_message=True)


async def cmd_saldo(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    p = db.get_player(uid)
    if p is None:
        p = db.ensure_player(uid, username=update.effective_user.username or "")
    await update.message.reply_text(
        _saldo_text(p),
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=_main_keyboard(p),
    )


async def cmd_apostar(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    p = db.get_player(uid)
    if p is None:
        p = db.ensure_player(uid, username=update.effective_user.username or "")
    try:
        amount = int(ctx.args[0])
        if not (_MIN_BET <= amount <= _MAX_BET):
            raise ValueError
        db.update_player(uid, bet=amount)
        p["bet"] = amount
        await update.message.reply_text(
            f"✅ Apuesta fijada en *{amount}🪙* por giro.",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=_main_keyboard(p),
        )
    except (IndexError, ValueError):
        await update.message.reply_text(
            f"⚠️ Uso: `/apostar <cantidad>`  (entre {_MIN_BET} y {_MAX_BET})",
            parse_mode=ParseMode.MARKDOWN,
        )


async def cmd_diario(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    p = db.get_player(uid)
    if p is None:
        p = db.ensure_player(uid, username=update.effective_user.username or "")

    result = db.claim_daily(uid)
    if result.get("granted"):
        p["balance"] = result["balance"]
        text = (
            f"🎁 *¡Bonus diario reclamado!*\n\n"
            f"Has recibido *+{result['bonus']}🪙* de regalo.\n"
            f"💰 Saldo actual: *{result['balance']}🪙*\n\n"
            "_Vuelve mañana para más fichas gratis._"
        )
    else:
        text = (
            f"⏳ *Ya reclamaste el bonus hoy*\n\n"
            f"Vuelve en *{result.get('hours_left', 24):.1f}h*.\n"
            f"💰 Saldo: *{result['balance']}🪙*"
        )
    await update.message.reply_text(
        text, parse_mode=ParseMode.MARKDOWN, reply_markup=_main_keyboard(p)
    )


async def cmd_milink(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    p = db.get_player(uid)
    if p is None:
        p = db.ensure_player(uid, username=update.effective_user.username or "")

    link = f"https://t.me/{BOT_USERNAME}?start=ref_{uid}"
    text = (
        f"🔗 *Tu link de referido*\n\n"
        f"`{link}`\n\n"
        f"Por cada amigo que se registre con tu link:\n"
        f"• Tú recibes *+50🪙*\n"
        f"• Ellos empiezan con fichas de bienvenida\n\n"
        f"👥 Referidos hasta ahora: *{p.get('referral_count', 0)}*\n"
        f"💰 Fichas ganadas por referidos: *{p.get('referral_count', 0) * 50}🪙*"
    )
    await update.message.reply_text(
        text, parse_mode=ParseMode.MARKDOWN, reply_markup=_main_keyboard(p)
    )


async def cmd_ranking(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    board = db.get_leaderboard(10)
    lines = ["🏆 *Top 10 — Casino BAGO*\n"]
    medals = ["🥇", "🥈", "🥉"] + ["4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
    for i, entry in enumerate(board):
        vip = "👑" if entry.get("vip_tier", 0) > 0 else ""
        marker = " ◀ tú" if entry["uid"] == uid else ""
        lines.append(
            f"{medals[i]} {vip}*{entry['username']}*  —  {entry['balance']}🪙{marker}"
        )
    await update.message.reply_text(
        "\n".join(lines),
        parse_mode=ParseMode.MARKDOWN,
    )


async def cmd_tabla(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    p = db.get_player(uid) or db.ensure_player(uid)
    await update.message.reply_text(
        paytable(), parse_mode=ParseMode.MARKDOWN, reply_markup=_main_keyboard(p)
    )


async def cmd_casino(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    p = db.get_player(uid) or db.ensure_player(uid)
    if not WEBAPP_URL:
        await update.message.reply_text(
            "⚠️ La interfaz gráfica no está disponible.",
            parse_mode=ParseMode.MARKDOWN,
        )
        return
    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("🎰 Abrir Casino gráfico", web_app=WebAppInfo(url=WEBAPP_URL))
    ]])
    await update.message.reply_text(
        "🖥️ *¡Casino BAGO — Edición Visual!*\n\n"
        "Carretes animados, jackpot progresivo, efectos neon y sonido.\n"
        "Tu saldo se sincroniza automáticamente 🔄",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=keyboard,
    )


async def cmd_ayuda(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text = (
        "🎰 *Tragaperras Casino BAGO — Ayuda*\n\n"
        "/start — Bienvenida y saldo\n"
        "/girar — Girar los rodillos\n"
        "/casino — Abrir interfaz gráfica 🖥️\n"
        "/apostar <N> — Cambiar la apuesta\n"
        "/saldo — Ver tu saldo y estadísticas\n"
        "/diario — 50 fichas gratis cada 24h 🎁\n"
        "/milink — Tu link de referido 🔗\n"
        "/ranking — Top 10 jugadores 🏆\n"
        "/tabla — Tabla de pagos\n"
        "/ayuda — Esta ayuda\n\n"
        "_Juega con responsabilidad. Solo entretenimiento._"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)


# ─── Callback inline ──────────────────────────────────────────────────────────

async def on_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = query.from_user.id
    await query.answer()

    p = db.get_player(uid)
    if p is None:
        p = db.ensure_player(uid, username=query.from_user.username or "")

    action = query.data

    if action == "girar":
        if p["balance"] < p["bet"]:
            await query.edit_message_text(
                "💸 Sin fichas. Usa /diario o /start."
            )
            return
        await _do_spin(update, uid, via_message=False)

    elif action == "bet_down":
        new_bet = max(_MIN_BET, p["bet"] - 5)
        db.update_player(uid, bet=new_bet)
        p["bet"] = new_bet
        await query.edit_message_reply_markup(_main_keyboard(p))

    elif action == "bet_up":
        new_bet = min(_MAX_BET, p["bet"] + 5)
        db.update_player(uid, bet=new_bet)
        p["bet"] = new_bet
        await query.edit_message_reply_markup(_main_keyboard(p))

    elif action == "saldo":
        p = db.get_player(uid)
        await query.edit_message_text(
            _saldo_text(p), parse_mode=ParseMode.MARKDOWN, reply_markup=_main_keyboard(p)
        )

    elif action == "diario":
        result = db.claim_daily(uid)
        p = db.get_player(uid)
        if result.get("granted"):
            msg = f"🎁 *+{result['bonus']}🪙 bonus diario!*\n💰 Saldo: *{result['balance']}🪙*"
        else:
            msg = f"⏳ Vuelve en *{result.get('hours_left', 24):.1f}h*\n💰 Saldo: *{p['balance']}🪙*"
        await query.edit_message_text(
            msg, parse_mode=ParseMode.MARKDOWN, reply_markup=_main_keyboard(p)
        )

    elif action == "tabla":
        p = db.get_player(uid)
        await query.edit_message_text(
            paytable(), parse_mode=ParseMode.MARKDOWN, reply_markup=_main_keyboard(p)
        )

    elif action == "ranking":
        board = db.get_leaderboard(5)
        lines = ["🏆 *Top 5*\n"]
        medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"]
        for i, entry in enumerate(board):
            marker = " ◀" if entry["uid"] == uid else ""
            lines.append(f"{medals[i]} *{entry['username']}*  {entry['balance']}🪙{marker}")
        p = db.get_player(uid)
        await query.edit_message_text(
            "\n".join(lines), parse_mode=ParseMode.MARKDOWN, reply_markup=_main_keyboard(p)
        )

    elif action.startswith("pkg_"):
        pkg_id = action[4:]
        packages = db.TON_PACKAGES
        if pkg_id not in packages:
            await query.answer("❌ Paquete no encontrado", show_alert=True)
            return
        pkg = packages[pkg_id]
        ton = pkg["nanoton"] / 1_000_000_000
        bonus_str = f" (+{pkg['bonus_pct']}% extra)" if pkg.get("bonus_pct", 0) > 0 else ""
        text = (
            f"💎 *{pkg['label']}*\n\n"
            f"Recibirás: *{pkg['fichas']}🪙*{bonus_str}\n"
            f"Precio: *{ton:.1f} TON*\n\n"
            "_Abre el casino gráfico para completar el pago con tu wallet TON._"
        )
        kb = []
        if WEBAPP_URL:
            kb.append([InlineKeyboardButton("🖥️ Pagar en casino", web_app=WebAppInfo(url=WEBAPP_URL))])
        kb.append([InlineKeyboardButton("« Volver", callback_data="pkg_back")])
        await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=InlineKeyboardMarkup(kb))

    elif action == "pkg_back":
        p = db.get_player(uid)
        await query.edit_message_text(_saldo_text(p), parse_mode=ParseMode.MARKDOWN, reply_markup=_main_keyboard(p))


# ─── Lógica del giro ──────────────────────────────────────────────────────────

async def _do_spin(update: Update, uid: int, via_message: bool):
    p = db.get_player(uid)
    result = db.do_spin(uid, p["bet"])

    if "error" in result:
        msg = "💸 Sin fichas. Usa /diario o /start."
        if via_message:
            await update.message.reply_text(msg)
        else:
            await update.callback_query.edit_message_text(msg)
        return

    r1, r2, r3 = result["reels"]
    reel_line = f"┃ {r1}  {r2}  {r3} ┃"
    p_fresh = db.get_player(uid)

    if result["win"] > 0:
        if result["is_jackpot"] and result.get("progressive_jackpot", 0) > 0:
            win_line = (
                f"🎉 *JACKPOT PROGRESIVO!*\n"
                f"*+{result['base_win']}🪙* base *+{result['progressive_jackpot']}🪙* pozo\n"
                f"*= {result['win']}🪙 TOTAL!*"
            )
        elif result["is_jackpot"]:
            win_line = f"🎉 *JACKPOT! +{result['win']}🪙*  ({result['message']})"
        else:
            win_line = f"✅ *+{result['win']}🪙*  ({result['message']})"
    else:
        icon = "🔥" if result["is_near_miss"] else "❌"
        win_line = f"{icon} *+0🪙*  {result['message']}"

    vip_badge = " 👑 VIP" if result.get("vip_tier", 0) > 0 else ""
    text = (
        f"🎰 *Tragaperras Casino BAGO*{vip_badge}\n"
        "┌─────────────┐\n"
        f"{reel_line}\n"
        "└─────────────┘\n\n"
        f"{win_line}\n\n"
        f"💰 Saldo: *{result['balance']}🪙*  │  Apuesta: *{p['bet']}🪙*\n"
        f"🎯 Jackpot pool: *{result['jackpot_pool']}🪙*"
    )

    if via_message:
        await update.message.reply_text(
            text, parse_mode=ParseMode.MARKDOWN, reply_markup=_main_keyboard(p_fresh)
        )
    else:
        await update.callback_query.edit_message_text(
            text, parse_mode=ParseMode.MARKDOWN, reply_markup=_main_keyboard(p_fresh)
        )


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _saldo_text(p: dict) -> str:
    spent = p.get("total_spent", 0)
    won = p.get("total_won", 0)
    rtp = (won / spent * 100) if spent > 0 else 0
    net = won - spent
    net_str = f"+{net}" if net >= 0 else str(net)
    vip_labels = {0: "Normal", 1: "VIP ⭐", 2: "VIP 👑"}
    vip = vip_labels.get(p.get("vip_tier", 0), "Normal")
    return (
        "💰 *Tu estado en Casino BAGO*\n\n"
        f"Saldo actual: *{p['balance']}🪙*\n"
        f"Apuesta por giro: *{p['bet']}🪙*\n"
        f"Rango: *{vip}*\n"
        f"Giros totales: *{p.get('total_spins', 0)}*\n"
        f"Total apostado: *{spent}🪙*\n"
        f"Total ganado: *{won}🪙*\n"
        f"Balance neto: *{net_str}🪙*\n"
        f"Tu RTP personal: *{rtp:.1f}%*\n"
        f"👥 Referidos: *{p.get('referral_count', 0)}*\n\n"
        "_Recuerda: el juego es solo entretenimiento._"
    )


# ─── /comprar — Comprar fichas con TON ──────────────────────────────────────

async def cmd_comprar(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    db.ensure_player(uid)
    packages = db.TON_PACKAGES
    lines = [
        "💎 *Compra fichas con TON Coin*\n",
        "Selecciona un paquete:",
    ]
    rows = []
    for pkg_id, pkg in packages.items():
        ton = pkg["nanoton"] / 1_000_000_000
        bonus_str = f" (+{pkg['bonus_pct']}% bonus)" if pkg.get("bonus_pct", 0) > 0 else ""
        lines.append(f"• {pkg['label']} — {pkg['fichas']}🪙 por {ton:.1f} TON{bonus_str}")
        rows.append([
            InlineKeyboardButton(
                f"{pkg['label']} {ton:.1f}TON→{pkg['fichas']}🪙",
                callback_data=f"pkg_{pkg_id}",
            )
        ])

    if WEBAPP_URL:
        rows.append([
            InlineKeyboardButton("🖥️ Abrir casino y pagar", web_app=WebAppInfo(url=WEBAPP_URL))
        ])

    text = "\n".join(lines) + "\n\n_Pago seguro vía TonConnect desde la billetera._"
    await update.message.reply_text(
        text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup(rows),
    )



def main():
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError("Falta TELEGRAM_BOT_TOKEN en .env")

    app = Application.builder().token(token).build()

    app.add_handler(CommandHandler("start",    cmd_start))
    app.add_handler(CommandHandler("girar",    cmd_girar))
    app.add_handler(CommandHandler("casino",   cmd_casino))
    app.add_handler(CommandHandler("saldo",    cmd_saldo))
    app.add_handler(CommandHandler("apostar",  cmd_apostar))
    app.add_handler(CommandHandler("diario",   cmd_diario))
    app.add_handler(CommandHandler("milink",   cmd_milink))
    app.add_handler(CommandHandler("ranking",  cmd_ranking))
    app.add_handler(CommandHandler("tabla",    cmd_tabla))
    app.add_handler(CommandHandler("comprar",  cmd_comprar))
    app.add_handler(CommandHandler("ayuda",    cmd_ayuda))
    app.add_handler(CallbackQueryHandler(on_callback))

    logger.info("🎰 Bot arrancado. Esperando mensajes...")
    app.run_polling(
        allowed_updates=Update.ALL_TYPES,
        drop_pending_updates=True,
    )


if __name__ == "__main__":
    main()

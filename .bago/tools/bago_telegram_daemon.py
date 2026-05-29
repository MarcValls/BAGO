#!/usr/bin/env python3
"""BAGO Telegram Daemon — polling real de mensajes + ejecución de comandos"""

from bago_utils import load_json, save_json, timestamp_iso
import html, json, os, sys, subprocess, time, threading, re
from pathlib import Path
from datetime import datetime

import requests

TOKEN = os.environ.get("BAGO_TELEGRAM_TOKEN", "").strip()
API_URL = f"https://api.telegram.org/bot{TOKEN}" if TOKEN else ""
BAGO_DIR = Path.home() / "BAGO"
LOG_FILE = Path.home() / ".bago" / "state" / "logs" / "telegram_daemon.log"
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)


def _parse_allowed_chat_ids() -> set:
    """Parse BAGO_TELEGRAM_ALLOWED_CHAT_IDS env var → set of int chat_ids.

    Formato: '123,456,-100789' (separados por coma). Vacío = lista vacía (rechaza todo).
    """
    raw = os.environ.get("BAGO_TELEGRAM_ALLOWED_CHAT_IDS", "").strip()
    if not raw:
        return set()
    result = set()
    for tok in raw.split(","):
        tok = tok.strip()
        if not tok:
            continue
        try:
            result.add(int(tok))
        except ValueError:
            pass
    return result


ALLOWED_CHAT_IDS = _parse_allowed_chat_ids()

OFFSET = 0
RUNNING = True

# ── Security: allowlist + sanitizer ──────────────────────────────────────────

ALLOWED_COMMANDS = {
    "status", "health", "ideas", "launch", "apk",
    "validate", "scan", "sync", "version", "help",
    "neural", "agents", "log", "reset", "build",
}

_SHELL_METACHARACTERS = re.compile(r'[;&|$`\\\n\r<>]|&&|\|\|')


def sanitize_command(cmd: str) -> str:
    """Strip shell injection metacharacters. Returns safe string."""
    return _SHELL_METACHARACTERS.sub("", cmd).strip()


# ── Intent detection ──────────────────────────────────────────────────────────

_INTENT_PATTERNS = [
    ("tarea",  re.compile(r'\b(tarea|task|pendiente|recordar|a[ñn]adir|crear|agregar)\b', re.I)),
    ("estado", re.compile(r'\b(estado|status|health|salud|c[oó]mo\s+est[aá])\b', re.I)),
    ("ayuda",  re.compile(r'\b(ayuda|help|comandos|qu[eé]\s+puedes)\b', re.I)),
    ("ideas",  re.compile(r'\b(ideas?|cat[aá]logo|inspiraci[oó]n)\b', re.I)),
    ("sync",   re.compile(r'\b(sync|sincronizar|subir|push|guardar)\b', re.I)),
]


def detect_intent(text: str) -> str:
    """Classify free-text into an intent label. Returns a string."""
    for label, pattern in _INTENT_PATTERNS:
        if pattern.search(text):
            return label
    return "generico"


# ── Keyboard builder ──────────────────────────────────────────────────────────

def make_main_keyboard():
    """Build the main inline keyboard for Telegram."""
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    rows = [
        [
            InlineKeyboardButton("📊 Estado",  callback_data="status"),
            InlineKeyboardButton("💡 Ideas",   callback_data="ideas"),
        ],
        [
            InlineKeyboardButton("🔄 Sync",    callback_data="sync"),
            InlineKeyboardButton("❓ Ayuda",   callback_data="help"),
        ],
    ]
    return InlineKeyboardMarkup(rows)

_LOG_SAFE = re.compile(r'[\x00-\x1f\x7f]')


def _safe_log(s: str, limit: int = 200) -> str:
    """Strip control chars + truncate. Prevents log injection / line splitting."""
    if not isinstance(s, str):
        s = str(s)
    return _LOG_SAFE.sub("?", s)[:limit]


def log(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except:
        pass

def send_message(text, chat_id):
    try:
        r = requests.post(f"{API_URL}/sendMessage", json={
            "chat_id": chat_id, "text": text, "parse_mode": "HTML"
        }, timeout=30)
        return r.json().get("ok", False)
    except Exception as e:
        log(f"[ERR send] {e}")
        return False

def execute_bago(cmd):
    cmd = sanitize_command(cmd)
    if not cmd:
        return "❌ Comando vacío."
    first_word = cmd.split()[0].lower()
    if first_word not in ALLOWED_COMMANDS:
        return f"❌ Comando '{first_word}' no permitido. Usa /help para ver los disponibles."
    ps1 = BAGO_DIR / "bago.ps1"
    if not ps1.exists():
        return f"❌ BAGO no encontrado en {BAGO_DIR}"
    try:
        result = subprocess.run(
            ["powershell", "-ExecutionPolicy", "Bypass", "-File", str(ps1), *cmd.split()],
            capture_output=True, text=True, timeout=60, cwd=str(BAGO_DIR)
        )
        out = result.stdout.strip() or result.stderr.strip() or "(sin salida)"
        return out[:3800]
    except subprocess.TimeoutExpired:
        return "⏱️ Timeout (60s)"
    except Exception as e:
        return f"❌ Error: {e}"

def process_message(msg):
    global OFFSET
    text = msg.get("text", "").strip()
    chat = msg.get("chat") or {}
    chat_id = chat.get("id")
    if chat_id is None:
        log("[SEC] mensaje sin chat.id — ignorado")
        return

    # ── Security: allowlist de chat_id ──────────────────────────────────────
    if not ALLOWED_CHAT_IDS:
        log(f"[SEC] BAGO_TELEGRAM_ALLOWED_CHAT_IDS vacío — rechazando chat_id={chat_id}")
        return
    if chat_id not in ALLOWED_CHAT_IDS:
        log(f"[SEC] chat_id={chat_id} no autorizado — ignorado")
        return

    user = (msg.get("from") or {}).get("first_name", "Usuario")

    log(f"MSG de {_safe_log(user, 40)} ({chat_id}): {_safe_log(text)}")
    
    if text.startswith("/start"):
        send_message(
            "🎵 <b>BAGO Music</b> activo\n\n"
            "Escribe cualquier comando BAGO (sin 'BAGO '):\n"
            "<code>status</code>, <code>ideas</code>, <code>launch</code>, etc.\n\n"
            "O escribe libremente una tarea.",
            chat_id
        )
        return
    
    if text.startswith("/help"):
        send_message(
            "Comandos:\n"
            "• <code>status</code> — estado BAGO\n"
            "• <code>ideas</code> — ideas del catálogo\n"
            "• <code>apk</code> — monitorizar build APK\n"
            "• <code>launch</code> — orquestador\n"
            "• Cualquier texto → BAGO lo interpretará",
            chat_id
        )
        return
    
    # Ejecutar comando BAGO
    safe_text = html.escape(text)
    send_message(f"⚡ Ejecutando: <code>BAGO {safe_text}</code>...", chat_id)
    result = execute_bago(text)
    send_message(f"<pre>{html.escape(result)}</pre>", chat_id)

def poll_loop():
    global OFFSET, RUNNING
    log("[DAEMON] Iniciando polling...")
    while RUNNING:
        try:
            r = requests.get(
                f"{API_URL}/getUpdates",
                params={"offset": OFFSET, "limit": 10},
                timeout=30
            )
            data = r.json()
            if not data.get("ok"):
                time.sleep(2)
                continue
            
            for update in data.get("result", []):
                OFFSET = max(OFFSET, update["update_id"] + 1)
                if "message" in update:
                    threading.Thread(
                        target=process_message,
                        args=(update["message"],),
                        daemon=True
                    ).start()
            
            time.sleep(1.5)
        except KeyboardInterrupt:
            log("[DAEMON] Cerrando por SIGINT...")
            break
        except Exception as e:
            log(f"[ERR poll] {e}")
            time.sleep(5)
    log("[DAEMON] Detenido")

if __name__ == "__main__":
    if not TOKEN:
        sys.stderr.write(
            "[FATAL] BAGO_TELEGRAM_TOKEN no definido. "
            "Exporta el token antes de lanzar el daemon.\n"
        )
        sys.exit(1)
    if not ALLOWED_CHAT_IDS:
        sys.stderr.write(
            "[FATAL] BAGO_TELEGRAM_ALLOWED_CHAT_IDS vacío o no definido. "
            "Por seguridad el daemon se niega a arrancar sin allowlist.\n"
        )
        sys.exit(1)
    poll_loop()

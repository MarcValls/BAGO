#!/usr/bin/env python3
"""
bago_wa_daemon.py — BAGO WhatsApp command listener

Polling daemon que recibe mensajes de WhatsApp y ejecuta comandos BAGO.
Solo acepta mensajes del número autorizado en notify_config.json.

Uso:
  python3 bago_wa_daemon.py          # arranca el daemon (Ctrl+C para parar)
  python3 bago_wa_daemon.py --once   # procesa mensajes pendientes y sale

Comandos disponibles desde WhatsApp:
  estado / status    → estado global de BAGO
  sprint             → sprint y workflow activo
  ping               → pong (test de conexión)
  ayuda / help       → lista de comandos
  nota <texto>       → añade nota al global_state
  notify <mensaje>   → reenvía el mensaje como notificación BAGO
"""

import os
import sys

os.environ.setdefault("PYTHONUTF8", "1")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import json
import sys
import time
import subprocess
import os
import requests
from pathlib import Path
from datetime import datetime

# ── Config ──────────────────────────────────────────────────────────────────
TOOLS_DIR   = Path(__file__).parent
_BAGO_ROOT  = Path(os.environ.get("BAGO_PADRE_PATH") or Path(__file__).parent.parent.parent)
_STATE_DIR  = _BAGO_ROOT / ".bago" / "state"
STATE_PATH  = _STATE_DIR / "global_state.json"
# Config lives in state/, not tools/ (tools/ is code, not data)
CONFIG_PATH = _STATE_DIR / "notify_config.json"
# Migrate from legacy tools/ location on first run
_old_cfg = TOOLS_DIR / "notify_config.json"
if _old_cfg.exists() and not CONFIG_PATH.exists():
    import shutil as _sh
    _STATE_DIR.mkdir(parents=True, exist_ok=True)
    _sh.copy2(str(_old_cfg), str(CONFIG_PATH))
POLL_INTERVAL = 5   # segundos entre polls
MAX_MSG_AGE   = 60  # ignorar mensajes más viejos que X segundos

config = json.loads(CONFIG_PATH.read_text())
wa = config.get("whatsapp", config)   # soporta config plana o anidada
INSTANCE_ID  = str(wa.get("instance_id", ""))
API_TOKEN    = wa.get("api_token", "")
API_URL      = wa.get("api_url", "").rstrip("/")
OWNER_PHONE  = wa.get("to_phone", config.get("phone", "")).lstrip("+").replace(" ", "")
OWNER_CHAT   = f"{OWNER_PHONE}@c.us"


# ── API helpers ──────────────────────────────────────────────────────────────
def wa_get(path: str, timeout: int = 10):
    url = f"{API_URL}/waInstance{INSTANCE_ID}/{path}/{API_TOKEN}"
    r = requests.get(url, timeout=timeout)
    r.raise_for_status()
    return r.json()

def wa_receive():
    """Long-polling: espera hasta 25s por un mensaje. Devuelve None si no hay nada."""
    url = f"{API_URL}/waInstance{INSTANCE_ID}/receiveNotification/{API_TOKEN}"
    try:
        r = requests.get(url, timeout=30)   # servidor retiene ~20s si no hay msgs
        r.raise_for_status()
        data = r.json()
        return data if data and data.get("body") else None
    except requests.exceptions.ReadTimeout:
        return None   # sin mensajes — normal en long-polling

def wa_delete(receipt_id: int):
    url = f"{API_URL}/waInstance{INSTANCE_ID}/deleteNotification/{API_TOKEN}/{receipt_id}"
    requests.delete(url, timeout=10)

def wa_send(text: str):
    url = f"{API_URL}/waInstance{INSTANCE_ID}/sendMessage/{API_TOKEN}"
    requests.post(url, json={"chatId": OWNER_CHAT, "message": text}, timeout=15)


# ── Comandos ─────────────────────────────────────────────────────────────────
def cmd_ping(_args: str) -> str:
    return "🏓 pong — BAGO activo"

def cmd_estado(_args: str) -> str:
    try:
        state = json.loads(STATE_PATH.read_text())
        v       = state.get("bago_version", "?")
        health  = state.get("system_health", "?")
        commits = state.get("inventory", {}).get("commits", "?")
        last_c  = state.get("inventory", {}).get("last_commit_msg", "?")
        wf      = state.get("sprint_status", {}).get("active_workflow", {})
        wf_str  = f"{wf.get('code','?')} — {wf.get('title','?')}" if wf else "ninguno"
        lines = [
            f"🤖 *BAGO v{v}* | health: {health}",
            f"📦 Commits: {commits}",
            f"🔧 Último commit: {last_c[:60]}",
            f"⚡ Workflow: {wf_str}",
        ]
        return "\n".join(lines)
    except Exception as e:
        return f"❌ Error leyendo estado: {e}"

def cmd_sprint(_args: str) -> str:
    try:
        state = json.loads(STATE_PATH.read_text())
        sp = state.get("sprint_status", {})
        wf = sp.get("active_workflow", {})
        last = sp.get("last_completed_workflow", {})
        lines = [
            f"⚡ *Workflow activo*: {wf.get('code','?')} — {wf.get('title','?')}",
            f"   Iniciado: {wf.get('started','?')[:16]}",
            f"✅ Último completado: {last.get('title','?')}",
        ]
        return "\n".join(lines)
    except Exception as e:
        return f"❌ Error: {e}"

def cmd_nota(args: str) -> str:
    if not args.strip():
        return "❌ Uso: nota <texto>"
    try:
        state = json.loads(STATE_PATH.read_text())
        ts = datetime.now().strftime("%Y-%m-%d %H:%M")
        prev = state.get("notes", "")
        state["notes"] = f"{prev}\n{ts} [WA]: {args.strip()}"
        STATE_PATH.write_text(json.dumps(state, indent=2, ensure_ascii=False))
        return f"📝 Nota guardada: {args.strip()[:80]}"
    except Exception as e:
        return f"❌ Error guardando nota: {e}"

def cmd_notify(args: str) -> str:
    if not args.strip():
        return "❌ Uso: notify <mensaje>"
    result = subprocess.run(
        [sys.executable, str(TOOLS_DIR / "notify_bago.py"), args.strip()],
        capture_output=True, text=True
    )
    return f"📢 Notificación enviada: {args.strip()[:60]}" if result.returncode == 0 else f"❌ Error: {result.stderr[:100]}"

def cmd_ayuda(_args: str) -> str:
    return (
        "🤖 *BAGO — Comandos WhatsApp*\n\n"
        "• `ping` — test conexión\n"
        "• `estado` — estado global BAGO\n"
        "• `sprint` — workflow activo\n"
        "• `nota <texto>` — añadir nota\n"
        "• `notify <msg>` — enviar notificación\n"
        "• `ayuda` — esta lista"
    )

COMMANDS = {
    "ping":    cmd_ping,
    "estado":  cmd_estado,
    "status":  cmd_estado,
    "sprint":  cmd_sprint,
    "nota":    cmd_nota,
    "note":    cmd_nota,
    "notify":  cmd_notify,
    "ayuda":   cmd_ayuda,
    "help":    cmd_ayuda,
}


# ── Dispatch ──────────────────────────────────────────────────────────────────
def dispatch(text: str) -> str | None:
    text = text.strip()
    if not text:
        return None
    parts = text.split(" ", 1)
    cmd   = parts[0].lower()
    args  = parts[1] if len(parts) > 1 else ""
    handler = COMMANDS.get(cmd)
    if handler:
        return handler(args)
    return None


# ── Main loop ─────────────────────────────────────────────────────────────────
def process_once():
    """Procesa todos los mensajes pendientes en la cola y sale."""
    processed = 0
    while True:
        data = wa_receive()
        if not data:
            break
        receipt_id = data.get("receiptId")
        body       = data.get("body", {})
        wa_delete(receipt_id)

        type_webhook = body.get("typeWebhook", "")
        # Aceptar mensajes entrantes Y salientes (el usuario se escribe a sí mismo)
        if type_webhook not in ("incomingMessageReceived", "outgoingMessageReceived"):
            continue

        msg_data   = body.get("messageData", {})
        msg_type   = msg_data.get("typeMessage", "")
        timestamp  = body.get("timestamp", 0)

        # Para outgoing y incoming: verificar que es el chat del owner
        sender = body.get("senderData", {}).get("chatId", "")
        if sender != OWNER_CHAT:
            continue
        # Extraer texto según tipo de mensaje
        if msg_type == "textMessage":
            text = msg_data.get("textMessageData", {}).get("textMessage", "")
        elif msg_type == "extendedTextMessage":
            text = msg_data.get("extendedTextMessageData", {}).get("text", "")
        else:
            continue  # audio, imagen, etc — ignorar

        age = time.time() - timestamp
        if age > MAX_MSG_AGE:
            continue
        print(f"[MSG] {sender}: {text!r}", flush=True)

        reply = dispatch(text)
        if reply:
            wa_send(reply)
            print(f"[SENT] {reply[:80]}", flush=True)
            processed += 1

    return processed

def run_daemon():
    print(f"🤖 BAGO WA Daemon iniciado — escuchando {OWNER_CHAT}", flush=True)
    print(f"   Poll interval: {POLL_INTERVAL}s | Ctrl+C para parar", flush=True)
    wa_send("🤖 *BAGO Daemon activo* — ya puedes enviar comandos\n\nEscribe `ayuda` para ver los comandos disponibles.")
    while True:
        try:
            process_once()
        except KeyboardInterrupt:
            print("\n[STOP] Daemon detenido", flush=True)
            wa_send("🛑 BAGO Daemon detenido.")
            break
        except Exception as e:
            print(f"[ERR] {e}", flush=True)
        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    if "--once" in sys.argv:
        n = process_once()
        print(f"[DONE] {n} mensajes procesados", flush=True)
    else:
        run_daemon()

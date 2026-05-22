#!/usr/bin/env python3
"""
notify_bago.py — BAGO universal notification tool

Providers soportados:
  - whatsapp  (Green API — QR scan, gratuito 3 chats, RECOMENDADO)
  - ntfy      (push notification sin WhatsApp, gratuito)
  - telegram  (bot oficial)

Uso:
  python3 notify_bago.py "Mensaje"
  python3 notify_bago.py --title "Sprites listos" "char_bianca_walk_6x8.png ✅"
  python3 notify_bago.py --priority high "ERROR en build"
  python3 notify_bago.py --setup          # instrucciones paso a paso
  python3 notify_bago.py --test           # enviar mensaje de prueba

SETUP WhatsApp — Green API (recomendado):
  1. Ve a https://console.green-api.com y regístrate gratis
  2. Crea una instancia Developer (gratuita)
  3. Escanea el QR con WhatsApp → Menu → Dispositivos vinculados
  4. Copia ID_INSTANCE y API_TOKEN_INSTANCE del dashboard
  5. python3 notify_bago.py --set-wa-instance ID_INSTANCE API_TOKEN
"""

import sys
import json
import urllib.request
import urllib.parse
from pathlib import Path

CONFIG_PATH = Path(__file__).parent / "notify_config.json"

DEFAULT_CONFIG = {
    "provider": "ntfy",
    "phone": "+34684798513",
    "whatsapp": {
        "provider": "green-api",
        "instance_id": "",
        "api_token": "",
        "to_phone": "34684798513"
    },
    "ntfy": {
        "topic": "bago-684798513",
        "server": "https://ntfy.sh"
    },
    "telegram": {
        "token": "",
        "chat_id": ""
    }
}


def load_config() -> dict:
    if not CONFIG_PATH.exists():
        save_config(DEFAULT_CONFIG)
    with open(CONFIG_PATH) as f:
        return json.load(f)


def save_config(cfg: dict):
    with open(CONFIG_PATH, "w") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)


# ── WHATSAPP vía Green API ─────────────────────────────────────────────────────

def send_whatsapp(message: str, title: str = "") -> bool:
    cfg         = load_config()
    wa          = cfg.get("whatsapp", {})
    instance_id = wa.get("instance_id", "")
    api_token   = wa.get("api_token", "")
    to_phone    = wa.get("to_phone", "")

    if not instance_id or not api_token:
        print("❌ Green API no configurado. Ejecuta: python3 notify_bago.py --setup")
        return False

    full_msg = f"*{title}*\n{message}" if title else message
    # Usar apiUrl de la instancia si está disponible, fallback a api.green-api.com
    api_base = wa.get("api_url", "https://api.green-api.com")
    url = f"{api_base.rstrip('/')}/waInstance{instance_id}/sendMessage/{api_token}"
    payload = {
        "chatId": f"{to_phone}@c.us",
        "message": full_msg
    }

    try:
        import requests as _req
        resp = _req.post(url, json=payload, timeout=15)
        data = resp.json()
        if data.get("idMessage"):
            print(f"✅ WhatsApp enviado → +{to_phone}")
            return True
        else:
            print(f"⚠️ Green API respuesta: {data}")
            return False
    except Exception as e:
        print(f"❌ WhatsApp error: {e}")
        return False


# ── NTFY ──────────────────────────────────────────────────────────────────────

def send_ntfy(message: str, title: str = "BAGO", priority: str = "default") -> bool:
    cfg = load_config()
    topic  = cfg["ntfy"]["topic"]
    server = cfg["ntfy"]["server"]
    url    = f"{server}/{topic}"

    prio_map = {"low": "2", "default": "3", "high": "4", "urgent": "5"}
    prio_val = prio_map.get(priority, "3")

    try:
        data = message.encode("utf-8")
        req  = urllib.request.Request(url, data=data, headers={
            "Title":    title.encode(),
            "Priority": prio_val.encode(),
            "Tags":     b"bago"
        }, method="POST")
        with urllib.request.urlopen(req, timeout=10) as resp:
            ok = resp.status == 200
            if ok:
                print(f"✅ ntfy → {topic}")
            return ok
    except Exception as e:
        print(f"❌ ntfy error: {e}")
        return False


# ── TELEGRAM ──────────────────────────────────────────────────────────────────

def send_telegram(message: str, title: str = "") -> bool:
    cfg     = load_config()
    token   = cfg["telegram"].get("token", "")
    chat_id = cfg["telegram"].get("chat_id", "")

    if not token or not chat_id:
        print("❌ Telegram no configurado.")
        return False

    full_msg = f"*{title}*\n{message}" if title else message
    url  = f"https://api.telegram.org/bot{token}/sendMessage"
    data = urllib.parse.urlencode({
        "chat_id": chat_id, "text": full_msg, "parse_mode": "Markdown"
    }).encode()

    try:
        with urllib.request.urlopen(
            urllib.request.Request(url, data=data), timeout=10
        ) as resp:
            ok = resp.status == 200
            if ok:
                print(f"✅ Telegram → {chat_id}")
            return ok
    except Exception as e:
        print(f"❌ Telegram error: {e}")
        return False


# ── DISPATCH ──────────────────────────────────────────────────────────────────

def notify(message: str, title: str = "BAGO", priority: str = "default") -> bool:
    cfg      = load_config()
    provider = cfg.get("provider", "ntfy")

    if provider == "whatsapp":
        return send_whatsapp(message, title)
    elif provider == "ntfy":
        return send_ntfy(message, title, priority)
    elif provider == "telegram":
        return send_telegram(message, title)
    else:
        print(f"❌ Provider desconocido: {provider}")
        return False


# ── CLI ───────────────────────────────────────────────────────────────────────

def setup_instructions():
    cfg = load_config()
    print(f"""
╔══════════════════════════════════════════════════════════╗
║         BAGO · WhatsApp Setup — Green API                ║
╠══════════════════════════════════════════════════════════╣
║                                                          ║
║  1. Ve a → https://console.green-api.com                 ║
║     Regístrate gratis (email)                            ║
║                                                          ║
║  2. Crea una instancia "Developer" (gratuita)            ║
║                                                          ║
║  3. En WhatsApp → Menú → Dispositivos vinculados         ║
║     Escanea el QR del dashboard de Green API             ║
║                                                          ║
║  4. Copia el ID_INSTANCE y API_TOKEN del dashboard       ║
║                                                          ║
║  5. Ejecuta:                                             ║
║     python3 notify_bago.py --set-wa-instance ID TOKEN    ║
║                                                          ║
╠══════════════════════════════════════════════════════════╣
║  Provider activo : {cfg.get('provider', 'ntfy'):<38}║
║  WhatsApp instancia: {cfg['whatsapp'].get('instance_id') or 'no configurada':<36}║
╚══════════════════════════════════════════════════════════╝
""")


if __name__ == "__main__":
    args = sys.argv[1:]

    if not args or args[0] == "--help":
        print(__doc__)
        sys.exit(0)

    if args[0] == "--setup":
        setup_instructions()
        sys.exit(0)

    if args[0] == "--test":
        ok = notify("✅ BAGO conectado. Notificaciones WhatsApp activas 🎮", title="BAGO")
        sys.exit(0 if ok else 1)

    if args[0] == "--set-wa-instance" and len(args) > 2:
        cfg = load_config()
        cfg["whatsapp"]["instance_id"] = args[1].strip()
        cfg["whatsapp"]["api_token"]   = args[2].strip()
        cfg["provider"] = "whatsapp"
        save_config(cfg)
        print("✅ Green API configurado. Provider → whatsapp")
        print("   Probando conexión...")
        send_whatsapp("✅ BAGO conectado vía WhatsApp (Green API) 🎮", "BAGO")
        sys.exit(0)

    if args[0] == "--set-telegram-token" and len(args) > 1:
        cfg = load_config()
        cfg["telegram"]["token"] = args[1].strip()
        cfg["provider"] = "telegram"
        save_config(cfg)
        print("✅ Telegram token guardado")
        sys.exit(0)

    if args[0] == "--set-telegram-chatid" and len(args) > 1:
        cfg = load_config()
        cfg["telegram"]["chat_id"] = args[1].strip()
        save_config(cfg)
        print(f"✅ Telegram chat_id: {args[1]}")
        sys.exit(0)

    # Envío normal
    title = "BAGO"
    priority = "default"
    msg_parts = []
    i = 0
    while i < len(args):
        if args[i] == "--title" and i+1 < len(args):
            title = args[i+1]; i += 2
        elif args[i] == "--priority" and i+1 < len(args):
            priority = args[i+1]; i += 2
        else:
            msg_parts.append(args[i]); i += 1

    message = " ".join(msg_parts)
    if not message:
        print("❌ Falta el mensaje"); sys.exit(1)

    ok = notify(message, title=title, priority=priority)
    sys.exit(0 if ok else 1)

#!/usr/bin/env python3
"""
notify_whatsapp.py — BAGO WhatsApp notification tool (CallMeBot)

Uso:
  python3 notify_whatsapp.py "Mensaje aquí"
  python3 notify_whatsapp.py --setup          # instrucciones de registro
  python3 notify_whatsapp.py --set-key XXXX   # guardar apikey tras registro

SETUP (una sola vez):
  1. Añade +34 644 22 03 20 a contactos como "CallMeBot"
  2. Envía por WhatsApp: "I allow callmebot to send me messages"
  3. Recibes un API key por WhatsApp
  4. Ejecuta: python3 notify_whatsapp.py --set-key TU_APIKEY
"""

import sys
import json
import urllib.request
import urllib.parse
from pathlib import Path

CONFIG_PATH = Path(__file__).parent / "whatsapp_config.json"


def load_config() -> dict:
    if not CONFIG_PATH.exists():
        print("❌ whatsapp_config.json no encontrado")
        sys.exit(1)
    with open(CONFIG_PATH) as f:
        return json.load(f)


def save_config(cfg: dict):
    with open(CONFIG_PATH, "w") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)


def send_whatsapp(message: str) -> bool:
    cfg = load_config()
    phone   = cfg.get("phone", "")
    apikey  = cfg.get("apikey", "")

    if not apikey:
        print("❌ API key vacía. Ejecuta: python3 notify_whatsapp.py --setup")
        return False

    encoded = urllib.parse.quote(message)
    url = f"https://api.callmebot.com/whatsapp.php?phone={phone}&text={encoded}&apikey={apikey}"

    try:
        with urllib.request.urlopen(url, timeout=15) as resp:
            body = resp.read().decode()
            if "Message queued" in body or resp.status == 200:
                print(f"✅ WhatsApp enviado → {phone}")
                return True
            else:
                print(f"⚠️ Respuesta inesperada: {body[:200]}")
                return False
    except Exception as e:
        print(f"❌ Error al enviar: {e}")
        return False


def setup_instructions():
    cfg = load_config()
    print("""
╔══════════════════════════════════════════════════════╗
║         BAGO · WhatsApp Setup (CallMeBot)            ║
╠══════════════════════════════════════════════════════╣
║                                                      ║
║  1. Añade este número a contactos de WhatsApp:       ║
║     +34 644 22 03 20  (CallMeBot)                    ║
║                                                      ║
║  2. Envía este mensaje exacto por WhatsApp:          ║
║     I allow callmebot to send me messages            ║
║                                                      ║
║  3. Recibirás un API key en WhatsApp (~1 min)        ║
║                                                      ║
║  4. Guarda el key con:                               ║
║     python3 notify_whatsapp.py --set-key TU_KEY      ║
║                                                      ║
╠══════════════════════════════════════════════════════╣
""")
    print(f"  Tu número configurado: {cfg.get('phone')}")
    print(f"  API key actual: {'✅ configurada' if cfg.get('apikey') else '❌ vacía'}")
    print("╚══════════════════════════════════════════════════════╝")


def set_key(apikey: str):
    cfg = load_config()
    cfg["apikey"] = apikey.strip()
    cfg["registered"] = True
    save_config(cfg)
    print(f"✅ API key guardada en {CONFIG_PATH}")
    print("   Probando conexión...")
    send_whatsapp("✅ BAGO conectado. WhatsApp notifications activadas 🎮")


if __name__ == "__main__":
    args = sys.argv[1:]

    if not args or args[0] == "--help":
        print(__doc__)
        sys.exit(0)

    if args[0] == "--setup":
        setup_instructions()
    elif args[0] == "--set-key" and len(args) > 1:
        set_key(args[1])
    else:
        message = " ".join(args)
        ok = send_whatsapp(message)
        sys.exit(0 if ok else 1)

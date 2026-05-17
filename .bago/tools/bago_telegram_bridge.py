#!/usr/bin/env python3
"""BAGO Telegram Bridge — recibe mensajes de Telegram y ejecuta comandos BAGO"""
import json, os, sys, subprocess, time, threading, re
from pathlib import Path
from datetime import datetime

import requests

TOKEN = os.environ.get("BAGO_TELEGRAM_TOKEN", "8519892399:AAHTKzfu_VyLUSpJ-iNjmSn9RcgFOsddeKA")
CHAT_ID = os.environ.get("BAGO_TELEGRAM_CHAT", "7752787448")
API_URL = f"https://api.telegram.org/bot{TOKEN}"
OFFSET = 0

def send_message(text, chat_id=None):
    cid = chat_id or CHAT_ID
    try:
        requests.post(f"{API_URL}/sendMessage", json={
            "chat_id": cid, "text": text, "parse_mode": "HTML"
        }, timeout=30)
    except Exception as e:
        print(f"[ERR send] {e}")

def execute_bago(cmd):
    """Ejecuta un comando BAGO y devuelve la salida"""
    bago_dir = Path.home() / "BAGO"
    ps1 = bago_dir / "bago.ps1"
    if not ps1.exists():
        return f"❌ BAGO no encontrado en {bago_dir}"
    try:
        result = subprocess.run(
            ["powershell", "-ExecutionPolicy", "Bypass", "-File", str(ps1), *cmd.split()],
            capture_output=True, text=True, timeout=60, cwd=str(bago_dir)
        )
        out = result.stdout.strip() or result.stderr.strip() or "(sin salida)"
        return out[:4000]  # Telegram limit
    except subprocess.TimeoutExpired:
        return "⏱️ Timeout (60s)"
    except Exception as e:
        return f"❌ Error: {e}"

def process_message(msg):
    text = msg.get("text", "").strip()
    chat_id = msg["chat"]["id"]
    user = msg["from"].get("first_name", "Usuario")
    
    print(f"[{datetime.now()}] {user}: {text}")
    
    # Comandos directos
    if text.startswith("/start"):
        send_message("🎵 <b>BAGO Music</b>\n\nEscribe cualquier comando BAGO o pregunta.\n\nEjemplos:\n<code>BAGO status</code>\n<code>BAGO ideas</code>\n<code>BAGO launch</code>", chat_id)
        return
    
    if text.startswith("/help"):
        send_message("Comandos disponibles:\n\n• Escribe <code>BAGO <comando></code>\n• Escribe ideas libres\n• /start para reiniciar", chat_id)
        return
    
    # Detectar comandos BAGO
    if text.upper().startswith("BAGO "):
        cmd = text[5:].strip()
        send_message(f"⚡ Ejecutando: <code>BAGO {cmd}</code>...", chat_id)
        result = execute_bago(cmd)
        send_message(f"<pre>{result}</pre>", chat_id)
        return
    
    # Mensaje libre — interpretar como tarea/pregunta
    send_message(f"📝 Recibido: <i>{text}</i>\n\nPuedes ejecutar:\n<code>BAGO launch {text}</code>", chat_id)

def poll_loop():
    global OFFSET
    print("[BAGO Telegram Bridge] Iniciando polling...")
    while True:
        try:
            r = requests.get(f"{API_URL}/getUpdates", params={"offset": OFFSET, "limit": 10}, timeout=30)
            data = r.json()
            if not data.get("ok"):
                time.sleep(5)
                continue
            for update in data.get("result", []):
                OFFSET = max(OFFSET, update["update_id"] + 1)
                if "message" in update:
                    threading.Thread(target=process_message, args=(update["message"],), daemon=True).start()
            time.sleep(1)
        except KeyboardInterrupt:
            print("\n[SIGINT] Cerrando...")
            break
        except Exception as e:
            print(f"[ERR poll] {e}")
            time.sleep(5)

if __name__ == "__main__":
    poll_loop()

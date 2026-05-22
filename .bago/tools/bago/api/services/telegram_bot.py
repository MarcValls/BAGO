"""bago.api.services.telegram_bot — Bot de Telegram para BAGO.

Recibe mensajes de Telegram, los envia a la API BAGO (puerto 11435),
y devuelve la respuesta. Permite enviar ordenes y recibir informes
desde el movil.

Configuracion:
    configurar TELEGRAM_BOT_TOKEN en el entorno
    python -m bago.api.services.telegram_bot

Puerto: 11439 (webhook opcional) / polling por defecto
Comandos del bot:
    /start — Presentacion
    /status — Estado de providers
    /model <nombre> — Cambiar modelo
    /help — Ayuda
    (cualquier texto) — Chat con BAGO
"""

from __future__ import annotations

import json
import os
import sys
import time
import threading
import urllib.request
import urllib.error
from pathlib import Path

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
BAGO_API_URL = os.environ.get("BAGO_API_URL", "http://127.0.0.1:11435")
TELEGRAM_API_URL = "https://api.telegram.org/bot{token}"
TELEGRAM_WEBHOOK_PORT = 11439


def _tg(method: str, payload: dict | None = None) -> dict:
    """Llama a la API de Telegram."""
    if not TELEGRAM_BOT_TOKEN:
        return {"ok": False, "error": "TELEGRAM_BOT_TOKEN no configurado"}
    url = f"{TELEGRAM_API_URL.format(token=TELEGRAM_BOT_TOKEN)}/{method}"
    data = json.dumps(payload).encode() if payload else None
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"} if data else {}, method="POST" if data else "GET")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return {"ok": False, "error": f"HTTP {e.code}"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def _bago_chat(messages: list[dict], model: str = "", system: str = "") -> str:
    """Envia mensaje a BAGO API y devuelve texto de respuesta."""
    payload = {
        "model": model,
        "messages": messages,
        "system": system,
        "stream": False,
    }
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        f"{BAGO_API_URL}/api/chat",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            result = json.loads(resp.read())
            msg = result.get("message", {})
            return msg.get("content", "(sin respuesta)")
    except Exception as e:
        return f"Error BAGO API: {e}"


def _bago_health() -> dict:
    """Health check de BAGO API."""
    try:
        req = urllib.request.Request(f"{BAGO_API_URL}/api/health", method="POST")
        with urllib.request.urlopen(req, timeout=5) as resp:
            return json.loads(resp.read())
    except Exception:
        return {"score": 0}


def _bago_tags() -> dict:
    """Lista modelos de BAGO API."""
    try:
        req = urllib.request.Request(f"{BAGO_API_URL}/api/tags", method="GET")
        with urllib.request.urlopen(req, timeout=5) as resp:
            return json.loads(resp.read())
    except Exception:
        return {"models": []}


class TelegramBot:
    """Bot de Telegram con polling para BAGO."""

    def __init__(self, token: str | None = None):
        global TELEGRAM_BOT_TOKEN
        if token:
            TELEGRAM_BOT_TOKEN = token
        self.offset = 0
        self.sessions: dict[int, list[dict]] = {}  # chat_id -> messages
        self.default_model = "llama3.2:3b"
        self.chat_models: dict[int, str] = {}  # chat_id -> model override

    def _send(self, chat_id: int, text: str, parse_mode: str = "") -> None:
        if len(text) > 4096:
            text = text[:4090] + "..."
        payload = {"chat_id": chat_id, "text": text}
        if parse_mode:
            payload["parse_mode"] = parse_mode
        _tg("sendMessage", payload)

    def _handle_command(self, chat_id: int, text: str) -> bool:
        parts = text.split(None, 1)
        cmd = parts[0].lower()
        arg = parts[1].strip() if len(parts) > 1 else ""

        if cmd == "/start":
            self._send(chat_id,
                "BAGO Bot activado.\n\n"
                "Envia cualquier mensaje para chatear con el orquestador.\n"
                "Comandos:\n"
                "  /status — Estado de providers\n"
                "  /model \u003cnombre\u003e — Cambiar modelo\n"
                "  /models — Listar modelos\n"
                "  /clear — Limpiar historial\n"
                "  /help — Esta ayuda"
            )
            return True

        if cmd == "/status":
            h = _bago_health()
            score = h.get("score", 0)
            status = "ONLINE" if score > 0 else "OFFLINE"
            self._send(chat_id, f"BAGO API: {status} (score: {score})")
            return True

        if cmd == "/model":
            if arg:
                self.chat_models[chat_id] = arg
                self._send(chat_id, f"Modelo cambiado a: {arg}")
            else:
                current = self.chat_models.get(chat_id, self.default_model)
                self._send(chat_id, f"Modelo actual: {current}\nUso: /model \u003cnombre\u003e")
            return True

        if cmd == "/models":
            t = _bago_tags()
            models = t.get("models", [])
            if not models:
                self._send(chat_id, "No hay modelos disponibles. Verifica que BAGO API este corriendo.")
            else:
                lines = ["Modelos disponibles:"]
                for m in models[:20]:
                    name = m.get("name", "?")
                    lines.append(f"  • {name}")
                self._send(chat_id, "\n".join(lines))
            return True

        if cmd == "/clear":
            self.sessions[chat_id] = []
            self._send(chat_id, "Historial limpiado.")
            return True

        if cmd == "/help":
            self._send(chat_id,
                "BAGO Bot — Comandos:\n\n"
                "/start — Presentacion\n"
                "/status — Estado de BAGO API\n"
                "/model \u003cnombre\u003e — Cambiar modelo\n"
                "/models — Listar modelos disponibles\n"
                "/clear — Limpiar historial de chat\n"
                "/help — Esta ayuda\n\n"
                "Cualquier otro texto se envia al orquestador BAGO."
            )
            return True

        return False

    def _process_message(self, chat_id: int, text: str) -> None:
        if self._handle_command(chat_id, text):
            return

        # Chat normal via BAGO API
        messages = self.sessions.get(chat_id, [])
        messages.append({"role": "user", "content": text})

        model = self.chat_models.get(chat_id, self.default_model)
        response = _bago_chat(messages, model=model)

        messages.append({"role": "assistant", "content": response})
        self.sessions[chat_id] = messages

        self._send(chat_id, response)

    def poll_once(self) -> None:
        result = _tg("getUpdates", {"offset": self.offset, "limit": 10})
        if not result.get("ok"):
            return
        for update in result.get("result", []):
            self.offset = update["update_id"] + 1
            msg = update.get("message") or update.get("edited_message")
            if not msg:
                continue
            chat_id = msg["chat"]["id"]
            text = msg.get("text", "")
            if text:
                try:
                    self._process_message(chat_id, text)
                except Exception as e:
                    self._send(chat_id, f"Error procesando mensaje: {e}")

    def run(self) -> None:
        if not TELEGRAM_BOT_TOKEN:
            print("[telegram_bot] ERROR: TELEGRAM_BOT_TOKEN no configurado.")
            print("[telegram_bot] Crea un bot con @BotFather y ejecuta:")
            print("[telegram_bot]   export TELEGRAM_BOT_TOKEN='tu_token'")
            return

        me = _tg("getMe")
        if me.get("ok"):
            bot_name = me["result"].get("username", "BAGO Bot")
            print(f"[telegram_bot] @{bot_name} conectado.")
            print(f"[telegram_bot] BAGO API: {BAGO_API_URL}")
            print(f"[telegram_bot] Polling activo. Ctrl+C para detener.")
        else:
            print(f"[telegram_bot] Error conectando a Telegram: {me}")
            return

        try:
            while True:
                self.poll_once()
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n[telegram_bot] Detenido.")


def main() -> None:
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if len(sys.argv) > 1:
        token = sys.argv[1]
    bot = TelegramBot(token=token)
    bot.run()


if __name__ == "__main__":
    main()

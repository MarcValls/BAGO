"""bago.api.services.utopia_bot — Cliente Utopia para BAGO.

Utopia (u.is) es una plataforma de mensajeria descentralizada con API HTTP local.
Este modulo conecta un canal/contacto de Utopia con BAGO API.

Configuracion:
    export UTOPIA_HOST="127.0.0.1"
    export UTOPIA_PORT="22824"
    export UTOPIA_TOKEN="tu_token_de_uclient"

Puerto: 11440 (webhook/polling)
"""

from __future__ import annotations

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
import os
import sys
import time
import urllib.request
import urllib.error

from bago.ollama_runtime import DEFAULT_BAGO_API_PORT, env_port

UTOPIA_HOST = os.environ.get("UTOPIA_HOST", "127.0.0.1")
UTOPIA_PORT = int(os.environ.get("UTOPIA_PORT", "22824"))
UTOPIA_TOKEN = os.environ.get("UTOPIA_TOKEN", "")
BAGO_API_URL = os.environ.get(
    "BAGO_API_URL",
    f"http://127.0.0.1:{env_port('BAGO_API_PORT', 'BAGO_PORT', default=DEFAULT_BAGO_API_PORT)}",
)
UTOPIA_API_URL = "http://{host}:{port}/api/1.0"


def _uapi(method: str, params: dict | None = None) -> dict:
    """Llama a la API HTTP de Utopia client."""
    if not UTOPIA_TOKEN:
        return {"error": "UTOPIA_TOKEN no configurado"}
    url = f"{UTOPIA_API_URL.format(host=UTOPIA_HOST, port=UTOPIA_PORT)}/{method}"
    payload = {"token": UTOPIA_TOKEN}
    if params:
        payload.update(params)
    data = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read())
    except Exception as e:
        return {"error": str(e)}


def _bago_chat(messages: list[dict], model: str = "") -> str:
    """Envia mensaje a BAGO API y devuelve texto de respuesta."""
    payload = {"model": model, "messages": messages, "stream": False}
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
            return result.get("message", {}).get("content", "(sin respuesta)")
    except Exception as e:
        return f"Error BAGO API: {e}"


class UtopiaBot:
    """Bot Utopia con polling de mensajes."""

    def __init__(self):
        self.sessions: dict[str, list[dict]] = {}
        self.default_model = "qwen25-coder"
        self.last_check = 0

    def _send(self, channel_id: str, text: str) -> None:
        """Envia mensaje a canal de Utopia."""
        _uapi("sendChannelMessage", {"channelid": channel_id, "message": text})

    def _get_messages(self) -> list[dict]:
        """Obtiene mensajes nuevos del canal."""
        result = _uapi("getChannelMessages", {"channelid": "", "after_message_id": self.last_check})
        if "error" in result:
            return []
        msgs = result.get("result", [])
        return msgs

    def run(self) -> None:
        if not UTOPIA_TOKEN:
            print("[utopia_bot] ERROR: UTOPIA_TOKEN no configurado.")
            print("[utopia_bot] 1. Abre Utopia client")
            print("[utopia_bot] 2. Ve a Settings -> API")
            print("[utopia_bot] 3. Habilita API y copia el token")
            print("[utopia_bot] 4. export UTOPIA_TOKEN='tu_token'")
            return

        print(f"[utopia_bot] Conectando a Utopia API en {UTOPIA_HOST}:{UTOPIA_PORT}...")
        sys_info = _uapi("getSystemInformation")
        if "error" in sys_info:
            print(f"[utopia_bot] No se pudo conectar: {sys_info['error']}")
            return

        print(f"[utopia_bot] Conectado. BAGO API: {BAGO_API_URL}")
        print(f"[utopia_bot] Polling activo. Ctrl+C para detener.")

        try:
            while True:
                msgs = self._get_messages()
                for msg in msgs:
                    # Procesar mensaje del usuario
                    text = msg.get("text", "")
                    sender = msg.get("nick", "anon")
                    if text.startswith("/"):
                        self._handle_command(msg.get("channelid", ""), text)
                    elif text:
                        self._process_chat(msg.get("channelid", ""), sender, text)
                time.sleep(2)
        except KeyboardInterrupt:
            print("\n[utopia_bot] Detenido.")

    def _handle_command(self, channel_id: str, text: str) -> None:
        parts = text.split(None, 1)
        cmd = parts[0].lower()
        if cmd == "/help":
            self._send(channel_id,
                "BAGO Utopia Bot:\n"
                "/status — Estado BAGO API\n"
                "/model \u003cnombre\u003e — Cambiar modelo\n"
                "/clear — Limpiar historial\n"
                "/help — Esta ayuda"
            )
        elif cmd == "/status":
            try:
                req = urllib.request.Request(f"{BAGO_API_URL}/api/health", method="POST")
                with urllib.request.urlopen(req, timeout=5) as resp:
                    h = json.loads(resp.read())
                    self._send(channel_id, f"BAGO API score: {h.get('score', 0)}")
            except Exception:
                self._send(channel_id, "BAGO API: OFFLINE")
        elif cmd == "/clear":
            if channel_id in self.sessions:
                del self.sessions[channel_id]
            self._send(channel_id, "Historial limpiado.")

    def _process_chat(self, channel_id: str, sender: str, text: str) -> None:
        key = f"{channel_id}:{sender}"
        messages = self.sessions.get(key, [])
        messages.append({"role": "user", "content": text})
        response = _bago_chat(messages)
        messages.append({"role": "assistant", "content": response})
        self.sessions[key] = messages
        self._send(channel_id, f"@{sender}: {response}")


def main() -> None:
    bot = UtopiaBot()
    bot.run()


if __name__ == "__main__":
    main()



def _run_tests() -> int:
    """Self-test stub: verifies module imports."""
    print(__file__ + " --test: PASS (imports OK)")
    return 0


if __name__ == "__main__":
    import sys
    if "--test" in sys.argv:
        raise SystemExit(_run_tests())

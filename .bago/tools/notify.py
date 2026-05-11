#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
notify.py — BAGO notification hub: desktop (Windows toast), push (ntfy/Telegram/WhatsApp).

Subcomandos:
    desktop   Notificación de escritorio Windows (BurntToast / WSH)
    push      Notificación remota: ntfy / Telegram / WhatsApp (Green API)
    whatsapp  WhatsApp directo vía CallMeBot (configuración propia)

Uso:
    python3 .bago/tools/notify.py "Mensaje"             → push (provider configurado)
    python3 .bago/tools/notify.py "Título" "Mensaje"    → desktop Windows
    python3 .bago/tools/notify.py desktop "Mensaje"
    python3 .bago/tools/notify.py push "Mensaje" [--title T] [--priority high]
    python3 .bago/tools/notify.py whatsapp "Mensaje"
    python3 .bago/tools/notify.py --test                → probar todos los backends
    python3 .bago/tools/notify.py --task-done           → notificación de tarea completada
    python3 .bago/tools/notify.py --build-ok APP        → notificación de build OK
    python3 .bago/tools/notify.py --setup               → instrucciones de configuración

Códigos de salida: 0 = OK, 1 = error (no es fatal)
"""
from __future__ import annotations

import json
import subprocess
import sys
import urllib.parse
import urllib.request
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except Exception:
        pass

ROOT    = Path(__file__).resolve().parents[2]
STATE   = ROOT / ".bago" / "state"
TOOLS   = Path(__file__).parent
IS_WIN  = sys.platform == "win32"

PUSH_CONFIG_PATH      = TOOLS / "notify_config.json"
WHATSAPP_CONFIG_PATH  = TOOLS / "whatsapp_config.json"

PUSH_DEFAULT_CONFIG = {
    "provider": "ntfy",
    "phone": "+34684798513",
    "whatsapp": {
        "provider": "green-api",
        "instance_id": "",
        "api_token": "",
        "to_phone": "34684798513",
    },
    "ntfy": {
        "topic": "bago-684798513",
        "server": "https://ntfy.sh",
    },
    "telegram": {
        "token": "",
        "chat_id": "",
    },
}


def BOLD(s: str)   -> str: return f"\033[1m{s}\033[0m"
def DIM(s: str)    -> str: return f"\033[2m{s}\033[0m"
def GREEN(s: str)  -> str: return f"\033[32m{s}\033[0m"
def YELLOW(s: str) -> str: return f"\033[33m{s}\033[0m"
def RED(s: str)    -> str: return f"\033[31m{s}\033[0m"
def CYAN(s: str)   -> str: return f"\033[36m{s}\033[0m"


# ── Shared helpers ─────────────────────────────────────────────────────────────

def _load_active_task() -> dict:
    task_file = STATE / "pending_w2_task.json"
    if task_file.exists():
        try:
            return json.loads(task_file.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _print_notification(title: str, message: str, icon: str = "🔔") -> None:
    print()
    print(f"  ┌{'─' * 61}┐")
    print(f"  │  {icon}  BAGO Notificación{' ' * (58 - len(icon))}│")
    print(f"  ├{'─' * 61}┤")
    print(f"  │  {BOLD(title):<59}  │")
    print(f"  │  {DIM(message):<59}  │")
    print(f"  └{'─' * 61}┘")
    print()


# ── DESKTOP backend (Windows BurntToast / WSH / MSG) ─────────────────────────

def _desktop_burnttoast(title: str, message: str) -> bool:
    if not IS_WIN:
        return False
    ps = f"""
$ErrorActionPreference = 'Stop'
try {{
    Import-Module BurntToast -ErrorAction Stop
    New-BurntToastNotification -Text '{title}', '{message}'
    exit 0
}} catch {{
    exit 1
}}
"""
    try:
        r = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps],
            capture_output=True, timeout=10,
        )
        return r.returncode == 0
    except Exception:
        return False


def _desktop_wsh(title: str, message: str) -> bool:
    if not IS_WIN:
        return False
    ps = f"""
Add-Type -AssemblyName System.Windows.Forms
$n = New-Object System.Windows.Forms.NotifyIcon
$n.Icon = [System.Drawing.SystemIcons]::Information
$n.Visible = $true
$n.ShowBalloonTip(5000, '{title}', '{message}', [System.Windows.Forms.ToolTipIcon]::Info)
Start-Sleep -Seconds 5
$n.Dispose()
"""
    try:
        r = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps],
            capture_output=True, timeout=15,
        )
        return r.returncode == 0
    except Exception:
        return False


def notify_desktop(title: str, message: str, icon: str = "🔔") -> bool:
    """Send a Windows desktop toast notification. Returns True if sent."""
    if _desktop_burnttoast(title, message):
        return True
    if _desktop_wsh(title, message):
        return True
    try:
        subprocess.run(["msg", "*", f"{title}: {message}"[:100]], capture_output=True, timeout=5)
        return True
    except Exception:
        return False


def cmd_desktop(args: list[str]) -> int:
    if "--task-done" in args:
        task    = _load_active_task()
        title   = "BAGO · Tarea completada"
        message = f"✓ {task.get('idea_title', task.get('title', 'Tarea'))}"
        sent    = notify_desktop(title, message, "✅")
        _print_notification(title, message, "✅")
        return 0 if sent else 1

    if "--build-ok" in args:
        idx     = args.index("--build-ok")
        app     = args[idx + 1] if idx + 1 < len(args) else "app"
        title   = "BAGO · Build completado"
        message = f"✓ {app} compilado correctamente"
        sent    = notify_desktop(title, message, "🏗")
        _print_notification(title, message, "🏗")
        return 0 if sent else 1

    if "--alert" in args:
        idx     = args.index("--alert")
        msg     = args[idx + 1] if idx + 1 < len(args) else "Alerta BAGO"
        sent    = notify_desktop("BAGO · Alerta", msg, "⚠")
        _print_notification("BAGO · Alerta", msg, "⚠")
        return 0 if sent else 1

    if not args or "--test" in args:
        title   = "BAGO · Test de notificación"
        message = "Las notificaciones de escritorio funcionan correctamente."
        print(f"\n  Sistema: {'Windows' if IS_WIN else sys.platform}")
        sent = notify_desktop(title, message, "✅")
        _print_notification(title, message, "✅")
        if sent:
            print(f"  {GREEN('✅')} Notificación enviada correctamente\n")
        else:
            print(f"  {YELLOW('⚠')} Solo terminal (instala BurntToast para toasts)\n")
        return 0

    pos = [a for a in args if not a.startswith("-")]
    if len(pos) >= 2:
        sent = notify_desktop(pos[0], pos[1])
        _print_notification(pos[0], pos[1])
        return 0 if sent else 1
    if len(pos) == 1:
        sent = notify_desktop("BAGO", pos[0])
        _print_notification("BAGO", pos[0])
        return 0 if sent else 1

    print(f"  Uso: notify desktop \"Título\" \"Mensaje\"")
    return 0


# ── PUSH backend (ntfy / Telegram / WhatsApp Green API) ──────────────────────

def _push_load_config() -> dict:
    if not PUSH_CONFIG_PATH.exists():
        _push_save_config(PUSH_DEFAULT_CONFIG)
    with open(PUSH_CONFIG_PATH) as f:
        return json.load(f)


def _push_save_config(cfg: dict) -> None:
    with open(PUSH_CONFIG_PATH, "w") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)


def _push_ntfy(message: str, title: str, priority: str) -> bool:
    cfg    = _push_load_config()
    topic  = cfg["ntfy"]["topic"]
    server = cfg["ntfy"]["server"]
    url    = f"{server}/{topic}"
    prio_map = {"low": "2", "default": "3", "high": "4", "urgent": "5"}
    prio_val = prio_map.get(priority, "3")
    try:
        req = urllib.request.Request(
            url, data=message.encode("utf-8"),
            headers={
                "Title": title.encode(),
                "Priority": prio_val.encode(),
                "Tags": b"bago",
            }, method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            ok = resp.status == 200
            if ok:
                print(f"✅ ntfy → {topic}")
            return ok
    except Exception as e:
        print(f"❌ ntfy error: {e}")
        return False


def _push_whatsapp_green(message: str, title: str) -> bool:
    cfg         = _push_load_config()
    wa          = cfg.get("whatsapp", {})
    instance_id = wa.get("instance_id", "")
    api_token   = wa.get("api_token", "")
    to_phone    = wa.get("to_phone", "")
    if not instance_id or not api_token:
        print("❌ Green API no configurado. Ejecuta: notify push --setup")
        return False
    full_msg = f"*{title}*\n{message}" if title else message
    api_base = wa.get("api_url", "https://api.green-api.com")
    url = f"{api_base.rstrip('/')}/waInstance{instance_id}/sendMessage/{api_token}"
    try:
        import requests as _req
        resp = _req.post(url, json={"chatId": f"{to_phone}@c.us", "message": full_msg}, timeout=15)
        data = resp.json()
        if data.get("idMessage"):
            print(f"✅ WhatsApp (Green API) → +{to_phone}")
            return True
        print(f"⚠️ Green API: {data}")
        return False
    except Exception as e:
        print(f"❌ WhatsApp Green API error: {e}")
        return False


def _push_telegram(message: str, title: str) -> bool:
    cfg     = _push_load_config()
    token   = cfg["telegram"].get("token", "")
    chat_id = cfg["telegram"].get("chat_id", "")
    if not token or not chat_id:
        print("❌ Telegram no configurado.")
        return False
    full_msg = f"*{title}*\n{message}" if title else message
    url  = f"https://api.telegram.org/bot{token}/sendMessage"
    data = urllib.parse.urlencode(
        {"chat_id": chat_id, "text": full_msg, "parse_mode": "Markdown"}
    ).encode()
    try:
        with urllib.request.urlopen(urllib.request.Request(url, data=data), timeout=10) as resp:
            ok = resp.status == 200
            if ok:
                print(f"✅ Telegram → {chat_id}")
            return ok
    except Exception as e:
        print(f"❌ Telegram error: {e}")
        return False


def notify_push(message: str, title: str = "BAGO", priority: str = "default") -> bool:
    cfg      = _push_load_config()
    provider = cfg.get("provider", "ntfy")
    if provider == "whatsapp":
        return _push_whatsapp_green(message, title)
    elif provider == "ntfy":
        return _push_ntfy(message, title, priority)
    elif provider == "telegram":
        return _push_telegram(message, title)
    else:
        print(f"❌ Provider desconocido: {provider}")
        return False


def _push_setup_instructions() -> None:
    cfg = _push_load_config()
    print(f"""
╔══════════════════════════════════════════════════════════╗
║         BAGO · Push Notifications Setup                  ║
╠══════════════════════════════════════════════════════════╣
║  Provider activo: {cfg.get('provider', 'ntfy'):<39}║
║                                                          ║
║  WhatsApp (Green API — recomendado):                     ║
║    1. https://console.green-api.com  (gratis)            ║
║    2. Crea instancia Developer                           ║
║    3. Escanea QR con WhatsApp                            ║
║    4. Copia ID_INSTANCE y API_TOKEN                      ║
║    5. notify push --set-wa-instance ID TOKEN             ║
║                                                          ║
║  ntfy (sin cuenta):                                      ║
║    Ya configurado — topic: {cfg['ntfy']['topic']:<31}║
║                                                          ║
╚══════════════════════════════════════════════════════════╝
""")


def cmd_push(args: list[str]) -> int:
    if not args or args[0] in ("--help", "-h"):
        _push_setup_instructions()
        return 0

    if args[0] == "--setup":
        _push_setup_instructions()
        return 0

    if args[0] == "--test":
        ok = notify_push("✅ BAGO conectado. Notificaciones activas 🎮", "BAGO")
        return 0 if ok else 1

    if "--set-wa-instance" in args and len(args) > 2:
        idx = args.index("--set-wa-instance")
        cfg = _push_load_config()
        cfg["whatsapp"]["instance_id"] = args[idx + 1].strip()
        cfg["whatsapp"]["api_token"]   = args[idx + 2].strip()
        cfg["provider"] = "whatsapp"
        _push_save_config(cfg)
        print("✅ Green API configurado. Provider → whatsapp")
        _push_whatsapp_green("✅ BAGO conectado vía WhatsApp (Green API) 🎮", "BAGO")
        return 0

    if "--set-telegram-token" in args:
        idx = args.index("--set-telegram-token")
        if idx + 1 < len(args):
            cfg = _push_load_config()
            cfg["telegram"]["token"] = args[idx + 1].strip()
            cfg["provider"] = "telegram"
            _push_save_config(cfg)
            print("✅ Telegram token guardado")
        return 0

    if "--set-telegram-chatid" in args:
        idx = args.index("--set-telegram-chatid")
        if idx + 1 < len(args):
            cfg = _push_load_config()
            cfg["telegram"]["chat_id"] = args[idx + 1].strip()
            _push_save_config(cfg)
            print(f"✅ Telegram chat_id: {args[idx + 1]}")
        return 0

    title    = "BAGO"
    priority = "default"
    msg_parts: list[str] = []
    i = 0
    while i < len(args):
        if args[i] == "--title" and i + 1 < len(args):
            title = args[i + 1]; i += 2
        elif args[i] == "--priority" and i + 1 < len(args):
            priority = args[i + 1]; i += 2
        else:
            msg_parts.append(args[i]); i += 1

    message = " ".join(msg_parts)
    if not message:
        print("❌ Falta el mensaje")
        return 1

    ok = notify_push(message, title=title, priority=priority)
    return 0 if ok else 1


# ── WHATSAPP backend (CallMeBot) ──────────────────────────────────────────────

def _wa_load_config() -> dict:
    if not WHATSAPP_CONFIG_PATH.exists():
        print("❌ whatsapp_config.json no encontrado")
        sys.exit(1)
    with open(WHATSAPP_CONFIG_PATH) as f:
        return json.load(f)


def _wa_save_config(cfg: dict) -> None:
    with open(WHATSAPP_CONFIG_PATH, "w") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)


def notify_whatsapp_callmebot(message: str) -> bool:
    cfg    = _wa_load_config()
    phone  = cfg.get("phone", "")
    apikey = cfg.get("apikey", "")
    if not apikey:
        print("❌ API key vacía. Ejecuta: notify whatsapp --setup")
        return False
    encoded = urllib.parse.quote(message)
    url = f"https://api.callmebot.com/whatsapp.php?phone={phone}&text={encoded}&apikey={apikey}"
    try:
        with urllib.request.urlopen(url, timeout=15) as resp:
            body = resp.read().decode()
            if "Message queued" in body or resp.status == 200:
                print(f"✅ WhatsApp (CallMeBot) → {phone}")
                return True
            print(f"⚠️ Respuesta inesperada: {body[:200]}")
            return False
    except Exception as e:
        print(f"❌ Error al enviar: {e}")
        return False


def cmd_whatsapp(args: list[str]) -> int:
    if not args or args[0] in ("--help", "-h"):
        print("""
  BAGO · WhatsApp (CallMeBot)

  Setup (una sola vez):
    1. Añade +34 644 22 03 20 a contactos como "CallMeBot"
    2. Envía: "I allow callmebot to send me messages"
    3. Recibes un API key por WhatsApp
    4. Ejecuta: notify whatsapp --set-key TU_APIKEY

  Uso: notify whatsapp "Mensaje"
""")
        return 0

    if args[0] == "--setup":
        cfg = _wa_load_config()
        print(f"""
╔══════════════════════════════════════════════╗
║    BAGO · WhatsApp Setup (CallMeBot)         ║
╠══════════════════════════════════════════════╣
║  1. Añade +34 644 22 03 20 a contactos       ║
║  2. Envía: I allow callmebot to send...      ║
║  3. Recibes un API key                       ║
║  4. notify whatsapp --set-key TU_KEY         ║
╠══════════════════════════════════════════════╣
║  Número: {cfg.get('phone', ''):<38}║
║  Key:    {'✅' if cfg.get('apikey') else '❌ vacía':<38}║
╚══════════════════════════════════════════════╝""")
        return 0

    if args[0] == "--set-key" and len(args) > 1:
        cfg = _wa_load_config()
        cfg["apikey"] = args[1].strip()
        cfg["registered"] = True
        _wa_save_config(cfg)
        print(f"✅ API key guardada")
        notify_whatsapp_callmebot("✅ BAGO conectado. WhatsApp (CallMeBot) activo 🎮")
        return 0

    message = " ".join(args)
    ok = notify_whatsapp_callmebot(message)
    return 0 if ok else 1


# ── DISPATCH ──────────────────────────────────────────────────────────────────

_HELP = """
  BAGO · Notify — Hub de notificaciones

  Subcomandos:
    desktop   Notificación de escritorio Windows (toast)
    push      Notificación remota (ntfy / Telegram / WhatsApp Green API)
    whatsapp  WhatsApp directo vía CallMeBot

  Atajos:
    --task-done        Notificar tarea completada (desktop)
    --build-ok APP     Notificar build OK (desktop)
    --alert "msg"      Alerta urgente (desktop)
    --test             Probar todos los backends
    --setup            Ver instrucciones de configuración

  Ejemplos:
    notify "Mensaje"                   → push con provider configurado
    notify "Título" "Mensaje"          → desktop Windows
    notify push "Hola" --title BAGO
    notify desktop --test
    notify whatsapp --setup
"""


def main() -> int:
    args = sys.argv[1:]

    if not args or args[0] in ("-h", "--help"):
        print(_HELP)
        return 0

    sub = args[0]
    rest = args[1:]

    if sub == "desktop":
        return cmd_desktop(rest)
    elif sub == "push":
        return cmd_push(rest)
    elif sub == "whatsapp":
        return cmd_whatsapp(rest)
    elif sub == "--task-done":
        return cmd_desktop(args)
    elif sub == "--build-ok":
        return cmd_desktop(args)
    elif sub == "--alert":
        return cmd_desktop(args)
    elif sub == "--test":
        print("  BAGO · Test de notificaciones\n")
        ok_d = cmd_desktop(["--test"])
        ok_p = cmd_push(["--test"])
        return 0 if (ok_d == 0 or ok_p == 0) else 1
    elif sub == "--setup":
        cmd_push(["--setup"])
        cmd_whatsapp(["--setup"])
        return 0
    else:
        # Passthrough: single message → push
        return cmd_push(args)


if __name__ == "__main__":
    raise SystemExit(main())

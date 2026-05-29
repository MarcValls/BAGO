#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
notifier.py — Envía notificaciones de escritorio (Windows toast).

Usa PowerShell BurntToast o New-BurntToast si está instalado.
Fallback: mensaje en terminal con sonido de alerta.

Uso:
    python3 .bago/tools/notifier.py "Título" "Mensaje"    # notificación directa
    python3 .bago/tools/notifier.py --task-done           # notificación de tarea completada
    python3 .bago/tools/notifier.py --build-ok APP        # notificación de build OK
    python3 .bago/tools/notifier.py --alert "Texto"       # alerta urgente
    python3 .bago/tools/notifier.py --test                # prueba de notificación

También se puede importar:
    from notifier import notify
    notify("Título", "Mensaje")

Códigos de salida: 0 = OK, 1 = notificación fallida (pero no es error fatal)
"""
from __future__ import annotations

from bago_utils import load_json, save_json, timestamp_iso

import json
import subprocess
import sys
from pathlib import Path


ROOT  = Path(__file__).resolve().parents[2]
STATE = ROOT / ".bago" / "state"
IS_WIN = sys.platform == "win32"


def BOLD(s: str)   -> str: return f"\033[1m{s}\033[0m"
def DIM(s: str)    -> str: return f"\033[2m{s}\033[0m"
def GREEN(s: str)  -> str: return f"\033[32m{s}\033[0m"
def YELLOW(s: str) -> str: return f"\033[33m{s}\033[0m"
def RED(s: str)    -> str: return f"\033[31m{s}\033[0m"
def CYAN(s: str)   -> str: return f"\033[36m{s}\033[0m"


def _load_active_task() -> dict:
    task_file = STATE / "pending_w2_task.json"
    if task_file.exists():
        try:
            return json.loads(task_file.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def notify_windows_powershell(title: str, message: str, icon: str = "ℹ") -> bool:
    """Try Windows PowerShell toast notification via BurntToast or MSG."""
    if not IS_WIN:
        return False

    # Method 1: BurntToast module (if installed)
    ps_burnttoast = f"""
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
        result = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_burnttoast],
            capture_output=True, timeout=10,
        )
        if result.returncode == 0:
            return True
    except Exception:
        pass

    # Method 2: Windows Script Host (works on all Windows, shows balloon-style)
    ps_wsh = f"""
Add-Type -AssemblyName System.Windows.Forms
$notify = New-Object System.Windows.Forms.NotifyIcon
$notify.Icon = [System.Drawing.SystemIcons]::Information
$notify.Visible = $true
$notify.ShowBalloonTip(5000, '{title}', '{message}', [System.Windows.Forms.ToolTipIcon]::Info)
Start-Sleep -Seconds 5
$notify.Dispose()
"""
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_wsh],
            capture_output=True, timeout=15,
        )
        if result.returncode == 0:
            return True
    except Exception:
        pass

    # Method 3: MSG command (works on Windows Pro/Enterprise)
    try:
        msg = f"{title}: {message}"[:100]
        subprocess.run(
            ["msg", "*", msg],
            capture_output=True, timeout=5,
        )
        return True
    except Exception:
        pass

    return False


def notify(title: str, message: str, icon: str = "🔔") -> bool:
    """Send a notification. Returns True if notification was sent."""
    sent = notify_windows_powershell(title, message, icon)
    return sent


def _print_notification(title: str, message: str, icon: str = "🔔") -> None:
    """Always print to terminal regardless of OS notification success."""
    print()
    print(f"  ┌{'─' * 61}┐")
    print(f"  │  {icon}  BAGO Notificación{' ' * (58 - len(icon))}│")
    print(f"  ├{'─' * 61}┤")
    print(f"  │  {BOLD(title):<59}  │")
    print(f"  │  {DIM(message):<59}  │")
    print(f"  └{'─' * 61}┘")
    print()


def main() -> int:
    args = sys.argv[1:]

    if not args or "--test" in args:
        title   = "BAGO · Test de notificación"
        message = "Las notificaciones de escritorio funcionan correctamente."
        icon    = "✅"

        print()
        print("  ┌─────────────────────────────────────────────────────────────┐")
        print("  │  BAGO · Notificaciones de escritorio                        │")
        print("  └─────────────────────────────────────────────────────────────┘")
        print(f"  Sistema: {'Windows' if IS_WIN else sys.platform}")
        print(f"  Enviando notificación de prueba...")
        print()

        sent = notify(title, message, icon)
        _print_notification(title, message, icon)

        if sent:
            print(f"  {GREEN('✅')} Notificación enviada correctamente\n")
        else:
            print(f"  {YELLOW('⚠')} Notificación en terminal (no se pudo enviar toast de escritorio)")
            if IS_WIN:
                print(f"  {DIM('Para habilitar toasts: Install-Module BurntToast -Scope CurrentUser')}")
            print()
        return 0

    if "--task-done" in args:
        task = _load_active_task()
        title   = "BAGO · Tarea completada"
        task_name = task.get("idea_title", task.get("title", "Tarea"))
        message = f"✓ {task_name}"
        sent = notify(title, message, "✅")
        _print_notification(title, message, "✅")
        return 0 if sent else 1

    if "--build-ok" in args:
        idx = args.index("--build-ok")
        app = args[idx + 1] if idx + 1 < len(args) else "app"
        title   = "BAGO · Build completado"
        message = f"✓ {app} compilado correctamente"
        sent = notify(title, message, "🏗")
        _print_notification(title, message, "🏗")
        return 0 if sent else 1

    if "--alert" in args:
        idx = args.index("--alert")
        msg = args[idx + 1] if idx + 1 < len(args) else "Alerta BAGO"
        sent = notify("BAGO · Alerta", msg, "⚠")
        _print_notification("BAGO · Alerta", msg, "⚠")
        return 0 if sent else 1

    # Direct: bago notify "Title" "Message"
    pos = [a for a in args if not a.startswith("-")]
    if len(pos) >= 2:
        title, message = pos[0], pos[1]
        icon = "🔔"
        sent = notify(title, message, icon)
        _print_notification(title, message, icon)
        return 0 if sent else 1

    if len(pos) == 1:
        sent = notify("BAGO", pos[0], "🔔")
        _print_notification("BAGO", pos[0], "🔔")
        return 0 if sent else 1

    print(f"\n  Uso: bago notify \"Título\" \"Mensaje\"\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

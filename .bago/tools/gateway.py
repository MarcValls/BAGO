#!/usr/bin/env python3
"""
gateway.py — BAGO Messaging Gateway

Configura, arranca y monitoriza canales de mensajería como puerta de entrada
a BAGO desde Telegram, WhatsApp, Discord, Slack, Signal, Email, SMS y más.

Subcomandos:
    install     TUI selector de plataformas → wizard de configuración
    status      Estado de todos los canales configurados
    start       Arranca los daemons activos
    stop        Para los daemons activos
    test        Envía mensaje de prueba por cada canal configurado

Uso:
    python3 gateway.py              → muestra status + menú
    python3 gateway.py install      → selector de plataformas
    python3 gateway.py status       → tabla de estado
    python3 gateway.py start        → arranca daemons
    python3 gateway.py test         → test de conexión
    python3 gateway.py --once       → modo no-interactivo (CI)
"""
from __future__ import annotations

import json
import os
import signal
import sys
import subprocess
import termios
import tty
import urllib.request
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.layout import Layout
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich import box

# ── Paths ────────────────────────────────────────────────────────────────────
ROOT    = Path(__file__).resolve().parents[2]
STATE   = ROOT / ".bago" / "state"
TOOLS   = Path(__file__).parent
CONFIG  = STATE / "gateway_config.json"

console = Console()

# ── Platform catalog ─────────────────────────────────────────────────────────
PLATFORMS: list[dict[str, Any]] = [
    {"id": "telegram",   "icon": "📱", "name": "Telegram",              "fields": [("token", "Bot Token (@BotFather)", True), ("chat_id", "Chat ID", False)]},
    {"id": "whatsapp",   "icon": "📲", "name": "WhatsApp",              "fields": [("instance_id", "Green API Instance ID", False), ("api_token", "API Token", True), ("phone", "Tu número (+34…)", False)]},
    {"id": "discord",    "icon": "🎮", "name": "Discord",               "fields": [("webhook_url", "Webhook URL", True)]},
    {"id": "slack",      "icon": "💼", "name": "Slack",                 "fields": [("webhook_url", "Webhook URL", True)]},
    {"id": "signal",     "icon": "📡", "name": "Signal",                "fields": [("phone", "Número registrado", False), ("signal_cli", "Ruta signal-cli", False)]},
    {"id": "email",      "icon": "📧", "name": "Email",                 "fields": [("smtp_host", "SMTP Host", False), ("smtp_port", "Puerto", False), ("user", "Usuario", False), ("password", "Contraseña", True), ("to", "Destinatario", False)]},
    {"id": "sms",        "icon": "📱", "name": "SMS (Twilio)",          "fields": [("account_sid", "Account SID", False), ("auth_token", "Auth Token", True), ("from_number", "Número Twilio", False), ("to_number", "Destinatario", False)]},
    {"id": "matrix",     "icon": "🔐", "name": "Matrix",                "fields": [("homeserver", "Homeserver URL", False), ("token", "Access Token", True), ("room_id", "Room ID", False)]},
    {"id": "mattermost", "icon": "💬", "name": "Mattermost",            "fields": [("webhook_url", "Incoming Webhook URL", True)]},
    {"id": "ntfy",       "icon": "🔔", "name": "ntfy (push)",           "fields": [("server", "Servidor (https://ntfy.sh)", False), ("topic", "Topic", False)]},
    {"id": "teams",      "icon": "💼", "name": "Microsoft Teams",       "fields": [("webhook_url", "Webhook URL", True)]},
    {"id": "gchat",      "icon": "💬", "name": "Google Chat",           "fields": [("webhook_url", "Webhook URL", True)]},
    {"id": "line",       "icon": "💚", "name": "LINE",                  "fields": [("token", "Channel Access Token", True)]},
    {"id": "irc",        "icon": "💬", "name": "IRC",                   "fields": [("server", "Servidor IRC", False), ("port", "Puerto", False), ("nick", "Nick", False), ("channel", "Canal (#bago)", False)]},
    {"id": "simplex",    "icon": "🔒", "name": "SimpleX Chat",          "fields": [("server_url", "SimpleX server URL", False)]},
]

_PLATFORM_BY_ID = {p["id"]: p for p in PLATFORMS}

# ── Config I/O ───────────────────────────────────────────────────────────────

def _load_config() -> dict:
    if CONFIG.exists():
        try:
            return json.loads(CONFIG.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _save_config(cfg: dict) -> None:
    STATE.mkdir(parents=True, exist_ok=True)
    CONFIG.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")


def _is_configured(cfg: dict, pid: str) -> bool:
    return bool(cfg.get(pid))


# ── Keyboard (raw tty) ────────────────────────────────────────────────────────

def _getch() -> str:
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        ch = sys.stdin.read(1)
        if ch == "\x1b":
            ch2 = sys.stdin.read(1)
            ch3 = sys.stdin.read(1)
            return ch + ch2 + ch3
        return ch
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)


# ── Status table ─────────────────────────────────────────────────────────────

def _status_table(cfg: dict) -> Table:
    t = Table(box=box.SIMPLE_HEAD, padding=(0, 1), show_header=True, header_style="bold white on grey23")
    t.add_column("Canal", min_width=20)
    t.add_column("Estado", min_width=12)
    t.add_column("Campos", min_width=10)
    t.add_column("Daemon", min_width=14)

    for p in PLATFORMS:
        pid = p["id"]
        pdata = cfg.get(pid, {})
        if pdata:
            filled = sum(1 for f, _, _ in p["fields"] if pdata.get(f))
            total  = len(p["fields"])
            status = Text("✅ configurado", style="green") if filled == total else Text(f"⚠ incompleto ({filled}/{total})", style="yellow")
            daemon = _daemon_status(pid)
        else:
            status = Text("○ no configurado", style="dim")
            filled, total = 0, len(p["fields"])
            daemon = Text("—", style="dim")

        t.add_row(
            f"{p['icon']} {p['name']}",
            status,
            f"{filled}/{total}" if pdata else "—",
            daemon,
        )
    return t


def _daemon_status(pid: str) -> Text:
    """Check if a daemon process is running for this platform."""
    try:
        out = subprocess.check_output(["pgrep", "-f", f"bago.*{pid}.*daemon"], text=True).strip()
        if out:
            return Text(f"▶ activo ({out.split()[0]})", style="green")
    except Exception:
        pass
    return Text("◼ parado", style="dim")


# ── Install TUI ───────────────────────────────────────────────────────────────

def _install_tui(cfg: dict) -> dict:
    """Interactive platform selector → per-platform wizard."""
    sel = 0
    while True:
        console.clear()
        console.print(Panel(
            Text("BAGO Messaging Gateway — Selecciona una plataforma", style="bold cyan"),
            subtitle="↑↓ navegar  ENTER configurar  q salir",
            border_style="blue",
        ))

        for i, p in enumerate(PLATFORMS):
            pid = p["id"]
            configured = _is_configured(cfg, pid)
            marker = "✅" if configured else "○"
            badge  = " (configurado)" if configured else " (no configurado)"
            style  = "bold cyan on grey23" if i == sel else ("green" if configured else "dim")
            prefix = "❯ " if i == sel else "  "
            console.print(f"  {prefix}{marker} {p['icon']} {p['name']:<28}", badge, style=style)

        key = _getch()
        if key in ("\x1b[A", "k") and sel > 0:
            sel -= 1
        elif key in ("\x1b[B", "j") and sel < len(PLATFORMS) - 1:
            sel += 1
        elif key in ("\r", "\n"):
            cfg = _configure_platform(cfg, PLATFORMS[sel])
        elif key in ("q", "\x03", "\x1b"):
            break

    return cfg


def _configure_platform(cfg: dict, platform: dict) -> dict:
    """Wizard for a single platform."""
    pid = platform["id"]
    existing = cfg.get(pid, {})

    console.clear()
    console.print(Panel(
        Text(f"Configurar {platform['icon']} {platform['name']}", style="bold cyan"),
        subtitle="Deja vacío para mantener el valor actual • Ctrl+C para cancelar",
        border_style="cyan",
    ))

    new_vals: dict[str, str] = {}
    try:
        for field, label, is_secret in platform["fields"]:
            current = existing.get(field, "")
            hint = " [dim](oculto)[/]" if is_secret and current else (f" [dim][{current}][/]" if current else "")
            console.print(f"\n  [bold]{label}[/]{hint}")
            raw = input("  → ").strip()
            new_vals[field] = raw if raw else current
    except KeyboardInterrupt:
        console.print("\n  [yellow]Cancelado[/]")
        return cfg

    # Merge and save
    merged = {**existing, **{k: v for k, v in new_vals.items() if v}}
    cfg[pid] = merged
    _save_config(cfg)

    # Verify connectivity
    ok = _verify_platform(pid, merged)
    if ok is True:
        console.print(f"\n  [green]✅ {platform['name']} verificado correctamente[/]")
    elif ok is False:
        console.print(f"\n  [yellow]⚠  Configuración guardada pero la verificación falló.[/]")
        console.print("  Revisa los valores e inténtalo de nuevo con 'bago gateway install'")
    else:
        console.print(f"\n  [dim]Configuración guardada. Verificación no disponible para {platform['name']}.[/]")

    input("\n  Pulsa ENTER para continuar...")
    return cfg


def _verify_platform(pid: str, data: dict) -> bool | None:
    """Try a connectivity check. Returns True/False/None (not verifiable)."""
    try:
        if pid == "telegram":
            token = data.get("token", "")
            if not token:
                return False
            url = f"https://api.telegram.org/bot{token}/getMe"
            with urllib.request.urlopen(url, timeout=8) as r:
                body = json.loads(r.read())
                return body.get("ok", False)

        elif pid == "ntfy":
            server = data.get("server", "https://ntfy.sh").rstrip("/")
            topic  = data.get("topic", "bago-test")
            req = urllib.request.Request(
                f"{server}/{topic}",
                data=b"BAGO gateway test",
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=8):
                return True

        elif pid in ("discord", "slack", "mattermost", "teams", "gchat"):
            url = data.get("webhook_url", "")
            if not url:
                return False
            payload = json.dumps({"text": "🤖 BAGO gateway test"}).encode()
            req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=8) as r:
                return r.status < 400

    except Exception:
        return False

    return None  # no verifier for this platform


# ── Send via configured channels ──────────────────────────────────────────────

def _send_all(message: str, cfg: dict) -> None:
    """Send message through all configured channels."""
    for p in PLATFORMS:
        pid = p["id"]
        data = cfg.get(pid)
        if not data:
            continue
        ok = _send_one(pid, data, message)
        icon = "✅" if ok else "❌"
        console.print(f"  {icon} {p['icon']} {p['name']}")


def _send_one(pid: str, data: dict, message: str) -> bool:
    try:
        if pid == "telegram":
            token   = data.get("token", "")
            chat_id = data.get("chat_id", "")
            if not token or not chat_id:
                return False
            payload = json.dumps({"chat_id": chat_id, "text": message}).encode()
            req = urllib.request.Request(
                f"https://api.telegram.org/bot{token}/sendMessage",
                data=payload,
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=8) as r:
                return r.status == 200

        elif pid in ("discord", "slack", "mattermost", "teams", "gchat"):
            url = data.get("webhook_url", "")
            if not url:
                return False
            payload = json.dumps({"text": message, "content": message}).encode()
            req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=8) as r:
                return r.status < 400

        elif pid == "ntfy":
            server = data.get("server", "https://ntfy.sh").rstrip("/")
            topic  = data.get("topic", "bago")
            req = urllib.request.Request(
                f"{server}/{topic}",
                data=message.encode(),
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=8):
                return True

    except Exception:
        pass
    return False


# ── Start/Stop daemons ───────────────────────────────────────────────────────

_DAEMON_MAP = {
    "telegram": TOOLS / "bago_telegram_daemon.py",
    "whatsapp": TOOLS / "bago_wa_daemon.py",
}


def _start_daemons(cfg: dict) -> None:
    for pid, script in _DAEMON_MAP.items():
        if not cfg.get(pid):
            continue
        if not script.exists():
            console.print(f"  [yellow]⚠  daemon para {pid} no encontrado[/]")
            continue
        proc = subprocess.Popen(
            [sys.executable, str(script)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        console.print(f"  [green]▶ {pid} daemon iniciado (pid {proc.pid})[/]")


def _stop_daemons(_cfg: dict) -> None:
    for pid in _DAEMON_MAP:
        try:
            pids = subprocess.check_output(["pgrep", "-f", f"bago.*{pid}.*daemon"], text=True).strip().split()
            for p in pids:
                os.kill(int(p), signal.SIGTERM)
                console.print(f"  [dim]◼ {pid} daemon parado (pid {p})[/]")
        except Exception:
            pass


# ── Main status screen (default) ─────────────────────────────────────────────

def _show_status(cfg: dict) -> None:
    configured = sum(1 for p in PLATFORMS if cfg.get(p["id"]))

    layout = Layout()
    layout.split_column(
        Layout(name="header", size=3),
        Layout(name="body"),
        Layout(name="footer", size=3),
    )

    header_text = Text()
    header_text.append("⊞ BAGO Gateway", style="bold cyan")
    header_text.append(f"  —  {configured}/{len(PLATFORMS)} canales configurados", style="dim")
    layout["header"].update(Panel(header_text, border_style="blue"))

    layout["body"].update(Panel(_status_table(cfg), border_style="grey42", title="Canales"))

    footer = Text()
    footer.append("install", style="bold cyan")
    footer.append(" configurar  │  ", style="dim")
    footer.append("start", style="bold green")
    footer.append(" arrancar  │  ", style="dim")
    footer.append("stop", style="bold red")
    footer.append(" parar  │  ", style="dim")
    footer.append("test", style="bold yellow")
    footer.append(" prueba", style="dim")
    layout["footer"].update(Panel(footer, border_style="grey42"))

    console.print(layout, height=30)


# ── Entry point ───────────────────────────────────────────────────────────────

def main(argv: list[str] | None = None) -> None:
    args = argv if argv is not None else sys.argv[1:]
    subcmd = args[0] if args else "status"
    once   = "--once" in args

    cfg = _load_config()

    if subcmd == "install":
        cfg = _install_tui(cfg)
        console.clear()
        _show_status(cfg)

    elif subcmd == "status":
        _show_status(cfg)
        if not once:
            try:
                input("\n  [q] salir  [i] instalar  → ")
            except (KeyboardInterrupt, EOFError):
                pass

    elif subcmd == "start":
        console.print(Panel("▶ Arrancando daemons...", border_style="green"))
        _start_daemons(cfg)

    elif subcmd == "stop":
        console.print(Panel("◼ Parando daemons...", border_style="red"))
        _stop_daemons(cfg)

    elif subcmd == "test":
        console.print(Panel("🧪 Enviando mensaje de prueba a todos los canales configurados...", border_style="yellow"))
        _send_all("🤖 BAGO gateway test — " + __import__("datetime").datetime.now().strftime("%H:%M:%S"), cfg)

    else:
        console.print(f"[red]Subcomando desconocido: {subcmd}[/]")
        console.print("Uso: bago gateway [install|status|start|stop|test]")
        sys.exit(1)


if __name__ == "__main__":
    main()

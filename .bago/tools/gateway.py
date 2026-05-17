#!/usr/bin/env python3
"""
gateway.py — BAGO Messaging Gateway

Plataformas soportadas (España-first + Utopia P2P):
  WhatsApp   Green API REST              [#1 España, 80%]
  Telegram   Bot API oficial             [#2 España, 19%]
  Signal     signal-cli local            [privacidad E2E]
  Email      SMTP estándar               [universal]
  ntfy       push HTTP auto-hospedable   [dev-friendly]
  Utopia P2P API local 1984 Group LP     [cifrado P2P descentralizado]

Subcomandos:
    install   TUI selector → wizard de configuración por plataforma
    status    Estado de todos los canales configurados
    start     Arranca los daemons activos (Telegram, WhatsApp)
    stop      Para los daemons activos
    test      Envía mensaje de prueba por cada canal configurado

Uso:
    python3 gateway.py              → status
    python3 gateway.py install      → selector TUI
    python3 gateway.py status       → tabla de estado
    python3 gateway.py start        → arranca daemons
    python3 gateway.py test         → test de conexión
    python3 gateway.py --once       → modo no-interactivo (CI)
"""
from __future__ import annotations

import json
import os
import signal
import smtplib
import sys
import subprocess
import termios
import tty
import urllib.request
from email.mime.text import MIMEText
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

# ── Platform catalog — España-first + Utopia P2P ─────────────────────────────
PLATFORMS: list[dict[str, Any]] = [
    {
        "id": "whatsapp",
        "icon": "📲",
        "name": "WhatsApp",
        "badge": "#1 España · 80%",
        "help": "Requiere cuenta Green API (green-api.com) — plan gratuito disponible.",
        "fields": [
            ("instance_id", "Instance ID (ej. 1101XXXXXXXX)", False),
            ("api_token",   "API Token",                      True),
            ("phone",       "Número destino (+34XXXXXXXXX)",  False),
        ],
    },
    {
        "id": "telegram",
        "icon": "✈️ ",
        "name": "Telegram",
        "badge": "#2 España · 19%",
        "help": "Crea un bot en @BotFather. Obtén tu chat_id con @userinfobot.",
        "fields": [
            ("token",   "Bot Token (ej. 7123456789:AAF…)", True),
            ("chat_id", "Chat ID (ej. -100XXXXXXXXXX)",    False),
        ],
    },
    {
        "id": "signal",
        "icon": "📡",
        "name": "Signal",
        "badge": "Privacidad · E2E",
        "help": "Requiere signal-cli instalado. https://github.com/AsamK/signal-cli",
        "fields": [
            ("phone",      "Número registrado (+34…)",           False),
            ("signal_cli", "Ruta signal-cli (o 'signal-cli')",   False),
            ("recipient",  "Número destinatario (+34…)",         False),
        ],
    },
    {
        "id": "email",
        "icon": "📧",
        "name": "Email",
        "badge": "Universal",
        "help": "Funciona con Gmail (App Password), Outlook, cualquier SMTP.",
        "fields": [
            ("smtp_host", "SMTP Host (ej. smtp.gmail.com)",    False),
            ("smtp_port", "Puerto (587=TLS / 465=SSL)",        False),
            ("user",      "Usuario (tu email)",                False),
            ("password",  "Contraseña / App Password",         True),
            ("to",        "Destinatario",                      False),
        ],
    },
    {
        "id": "ntfy",
        "icon": "🔔",
        "name": "ntfy",
        "badge": "Push · self-host",
        "help": "ntfy.sh es gratuito y open source. Instala la app en móvil.",
        "fields": [
            ("server", "Servidor (ej. https://ntfy.sh)",    False),
            ("topic",  "Topic secreto (ej. bago-mi-clave)", False),
        ],
    },
    {
        "id": "utopia",
        "icon": "🔐",
        "name": "Utopia P2P",
        "badge": "1984 Group LP · Cifrado P2P",
        "help": (
            "Requiere el cliente Utopia corriendo localmente (https://u.is).\n"
            "  1. Instala Utopia desde https://u.is\n"
            "  2. Activa la API: Ajustes → API (puerto 22091 por defecto)\n"
            "  3. Copia el Token que genera el cliente\n"
            "  4. Obtén la Public Key del destinatario desde su perfil"
        ),
        "fields": [
            ("host",      "Host API (ej. localhost)",           False),
            ("port",      "Puerto API (ej. 22091)",             False),
            ("token",     "API Token (desde cliente Utopia)",   True),
            ("recipient", "Public Key del destinatario",        False),
        ],
    },
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
            badge  = p.get("badge", "")
            state  = "configurado" if configured else "no configurado"
            style  = "bold cyan on grey23" if i == sel else ("green" if configured else "dim")
            prefix = "❯ " if i == sel else "  "
            console.print(
                f"  {prefix}{marker} {p['icon']} {p['name']:<22} [dim]{badge}[/]  [{'green' if configured else 'dim'}]({state})[/]",
                style=style,
            )

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
    badge = platform.get("badge", "")
    help_text = platform.get("help", "")
    console.print(Panel(
        Text(f"{platform['icon']} {platform['name']}  [{badge}]", style="bold cyan"),
        subtitle="Deja vacío para mantener el valor actual  •  Ctrl+C para cancelar",
        border_style="cyan",
    ))
    if help_text:
        for line in help_text.splitlines():
            console.print(f"  [dim]{line}[/]")
        console.print()

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

        elif pid == "whatsapp":
            # Green API: verificar que la instancia está activa
            iid   = data.get("instance_id", "")
            token = data.get("api_token", "")
            if not iid or not token:
                return False
            url = f"https://api.green-api.com/waInstance{iid}/getStateInstance/{token}"
            with urllib.request.urlopen(url, timeout=8) as r:
                body = json.loads(r.read())
                return body.get("stateInstance") == "authorized"

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

        elif pid == "utopia":
            # Utopia P2P: llama a getSystemInfo para verificar API activa
            host  = data.get("host", "localhost")
            port  = data.get("port", "22091")
            token = data.get("token", "")
            if not token:
                return False
            url = f"http://{host}:{port}/api/v1/getSystemInfo"
            req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
            with urllib.request.urlopen(req, timeout=5) as r:
                body = json.loads(r.read())
                return body.get("result") is not None

        elif pid == "email":
            host = data.get("smtp_host", "")
            port = int(data.get("smtp_port", "587") or "587")
            user = data.get("user", "")
            pwd  = data.get("password", "")
            if not all([host, user, pwd]):
                return False
            with smtplib.SMTP(host, port, timeout=8) as s:
                s.starttls()
                s.login(user, pwd)
            return True

    except Exception:
        return False

    return None  # no verifier disponible para esta plataforma


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

        elif pid == "whatsapp":
            # Green API send message
            iid   = data.get("instance_id", "")
            token = data.get("api_token", "")
            phone = data.get("phone", "").lstrip("+")
            if not all([iid, token, phone]):
                return False
            url = f"https://api.green-api.com/waInstance{iid}/sendMessage/{token}"
            payload = json.dumps({
                "chatId": f"{phone}@c.us",
                "message": message,
            }).encode()
            req = urllib.request.Request(
                url, data=payload,
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=10) as r:
                body = json.loads(r.read())
                return "idMessage" in body

        elif pid == "signal":
            cli       = data.get("signal_cli", "signal-cli")
            phone     = data.get("phone", "")
            recipient = data.get("recipient", "")
            if not all([phone, recipient]):
                return False
            result = subprocess.run(
                [cli, "-u", phone, "send", "-m", message, recipient],
                capture_output=True, timeout=15,
            )
            return result.returncode == 0

        elif pid == "email":
            host = data.get("smtp_host", "")
            port = int(data.get("smtp_port", "587") or "587")
            user = data.get("user", "")
            pwd  = data.get("password", "")
            to   = data.get("to", "")
            if not all([host, user, pwd, to]):
                return False
            msg = MIMEText(message, "plain", "utf-8")
            msg["Subject"] = "🤖 BAGO"
            msg["From"]    = user
            msg["To"]      = to
            with smtplib.SMTP(host, port, timeout=10) as s:
                s.starttls()
                s.login(user, pwd)
                s.sendmail(user, [to], msg.as_string())
            return True

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

        elif pid == "utopia":
            # Utopia P2P — REST API local (1984 Group LP)
            host      = data.get("host", "localhost")
            port      = data.get("port", "22091")
            token     = data.get("token", "")
            recipient = data.get("recipient", "")
            if not token or not recipient:
                return False
            payload = json.dumps({
                "to":      recipient,
                "message": message,
                "isText":  True,
            }).encode()
            req = urllib.request.Request(
                f"http://{host}:{port}/api/v1/sendInstantMessage",
                data=payload,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {token}",
                },
            )
            with urllib.request.urlopen(req, timeout=8) as r:
                body = json.loads(r.read())
                return body.get("result") is not None

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

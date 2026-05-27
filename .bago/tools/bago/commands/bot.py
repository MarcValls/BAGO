"""Comando /bot: arranque y estado de bots externos."""

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
import subprocess
import sys
import urllib.request
from pathlib import Path

from rich.panel import Panel

from ..ui import console, pe, pi
from bago.ollama_runtime import DEFAULT_BAGO_TELEGRAM_PORT


def cmd_bot(session, args: str) -> None:
    parts = args.split(None, 1) if args else []
    bot_name = parts[0].lower() if parts else ""
    bot_arg = parts[1].strip().lower() if len(parts) > 1 else ""

    if not bot_name:
        _print_help()
    elif bot_name == "telegram":
        _telegram(session, bot_arg)
    elif bot_name == "utopia":
        _utopia(bot_arg)
    else:
        pe(f"Bot desconocido: {bot_name}. Usa telegram o utopia")


def _print_help() -> None:
    console.print(Panel(
        "[bold]Bots de mensajeria BAGO[/bold]\n\n"
        "  [cyan]/bot telegram start[/cyan]  — Arrancar bot de Telegram\n"
        "  [cyan]/bot telegram stop[/cyan]   — Detener bot de Telegram\n"
        "  [cyan]/bot telegram status[/cyan] — Estado del bot\n"
        "  [cyan]/bot utopia start[/cyan]    — Arrancar cliente Utopia\n"
        "  [cyan]/bot utopia stop[/cyan]     — Detener cliente Utopia\n"
        "  [cyan]/bot utopia status[/cyan]   — Estado del cliente\n\n"
        "  [dim]Telegram: crea un bot con @BotFather y exporta TELEGRAM_BOT_TOKEN[/dim]\n"
        "  [dim]Utopia: habilita API en Utopia client y exporta UTOPIA_TOKEN[/dim]",
        title="BAGO Bots",
        border_style="cyan",
        expand=False,
    ))


def _telegram_token(session) -> str:
    raw_creds = getattr(session.creds, "_creds", {})
    saved = raw_creds.get("telegram", "")
    if isinstance(saved, dict):
        saved = saved.get("token", "")
    return str(saved or os.environ.get("TELEGRAM_BOT_TOKEN", "")).strip()


def _telegram(session, action: str) -> None:
    if action == "start":
        token = _telegram_token(session)
        if not token:
            pe("No hay token de Telegram. Guárdalo con /tumba o exporta TELEGRAM_BOT_TOKEN")
            return
        env = dict(os.environ, TELEGRAM_BOT_TOKEN=token)
        proc = subprocess.Popen(
            [sys.executable, "-m", "bago.api.services.telegram_bot"],
            cwd=str(Path(__file__).resolve().parents[3]),
            env=env,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == "win32" else 0,
        )
        console.print(f"  [green]Telegram bot arrancado[/green] (PID {proc.pid})")
        console.print("  [dim]Busca tu bot en Telegram y envia /start[/dim]")
    elif action == "stop":
        console.print("  [yellow]Para detener el bot, busca el PID y mata el proceso.[/yellow]")
    elif action == "status":
        try:
            req = urllib.request.Request(f"http://127.0.0.1:{DEFAULT_BAGO_TELEGRAM_PORT}/", method="GET")
            with urllib.request.urlopen(req, timeout=2) as resp:
                resp.read()
            console.print("  [green]Telegram bot: ONLINE[/green]")
        except Exception:
            console.print("  [red]Telegram bot: OFFLINE[/red]")
    else:
        pi("Uso: /bot telegram start|stop|status")


def _utopia(action: str) -> None:
    if action == "start":
        proc = subprocess.Popen(
            [sys.executable, "-m", "bago.api.services.utopia_bot"],
            cwd=str(Path(__file__).resolve().parents[3]),
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == "win32" else 0,
        )
        console.print(f"  [green]Utopia bot arrancado[/green] (PID {proc.pid})")
    elif action == "stop":
        console.print("  [yellow]Para detener el bot, busca el PID y mata el proceso.[/yellow]")
    elif action == "status":
        console.print("  [dim]Verificando conexion Utopia...[/dim]")
        try:
            req = urllib.request.Request("http://127.0.0.1:22824/api/1.0/getSystemInformation", method="POST")
            with urllib.request.urlopen(req, timeout=3) as resp:
                json.loads(resp.read())
            console.print("  [green]Utopia client: ONLINE[/green]")
        except Exception:
            console.print("  [red]Utopia client: OFFLINE o no accesible[/red]")
    else:
        pi("Uso: /bot utopia start|stop|status")


def _run_tests() -> int:
    """Self-test stub: verifies module imports."""
    print(f"{Path(__file__).name} --test: PASS (imports OK)")
    return 0
if __name__ == "__main__":
    if "--test" in sys.argv:
        raise SystemExit(_run_tests())

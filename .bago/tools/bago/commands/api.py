"""Comandos /serve y /api del chat BAGO."""

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

import subprocess
import sys
from pathlib import Path

from rich.panel import Panel

from ..ui import console, pe, pi
from bago.ollama_runtime import DEFAULT_BAGO_API_PORT


def cmd_serve(args: str) -> None:
    port = args.strip() if args.strip() else str(DEFAULT_BAGO_API_PORT)
    try:
        port_int = int(port)
    except ValueError:
        pe(f"Puerto invalido: {port}")
        return

    pi(f"[cyan]Arrancando BAGO API en puerto {port_int}...[/cyan]")
    try:
        proc = subprocess.Popen(
            [sys.executable, "-m", "bago.api.server", "--port", str(port_int)],
            cwd=str(Path(__file__).resolve().parents[3]),
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == "win32" else 0,
        )
        console.print(f"  [green]BAGO API arrancado[/green] (PID {proc.pid}, puerto {port_int})")
        console.print(f"  [dim]Endpoints: http://127.0.0.1:{port_int}/docs[/dim]")
        console.print("  [dim]Usa /api on para enrutar chat via API[/dim]")
    except Exception as exc:
        pe(f"Error arrancando API: {exc}")


def cmd_api(args: str) -> None:
    from ..api.bridge import api_health, get_mode, set_mode

    sub = args.strip().lower()
    if not sub:
        mode = get_mode()
        health = api_health()
        score = health.get("score", 0)
        status = "[green]online[/green]" if score > 0 else "[red]offline[/red]"
        console.print(Panel(
            "[bold]Modo API BAGO[/bold]\n\n"
            f"  Modo actual: [cyan]{mode}[/cyan]\n"
            f"  Servidor: {status} (score: {score})\n\n"
            "  [dim]Usa /api on|off|hybrid|status para cambiar[/dim]",
            title="BAGO API",
            border_style="cyan",
            expand=False,
        ))
    elif sub == "on":
        set_mode("api")
        pi("Modo API: [green]ACTIVADO[/green] — chat via HTTP API")
    elif sub == "off":
        set_mode("direct")
        pi("Modo API: [yellow]DESACTIVADO[/yellow] — chat directo")
    elif sub == "hybrid":
        set_mode("hybrid")
        pi("Modo API: [cyan]HIBRIDO[/cyan] — intenta API primero, cae a directo")
    elif sub == "status":
        _api_status()
    else:
        pi(f"Opcion desconocida: {sub}. Usa on|off|hybrid|status")


def _api_status() -> None:
    from ..api.bridge import api_health, api_services, api_tags

    health = api_health()
    tags = api_tags()
    services = api_services()
    providers_list = ""
    for service, info in services.items():
        available = "[green]OK[/green]" if info.get("available") else "[red]DOWN[/red]"
        providers_list += f"\n    {service}: {available} (:{info.get('port', '?')})"
    console.print(Panel(
        "[bold]Estado API BAGO[/bold]\n\n"
        f"  Health score: {health.get('score', 0)}\n"
        f"  Modelos disponibles: {len(tags.get('models', []))}\n"
        f"  Servicios:{providers_list or ' (sin datos)'}",
        title="BAGO API Status",
        border_style="cyan",
        expand=False,
    ))

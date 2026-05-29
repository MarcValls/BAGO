"""Comando /status del chat BAGO."""

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

import datetime

from rich import box
from rich.panel import Panel

from ..hw_probe import hw_summary_lines
from ..providers import scan_provider_health
from ..ui import console


def cmd_status(session) -> None:
    console.print("[dim]  Escaneando providers...[/dim]")
    health = scan_provider_health(session.creds, session.providers, timeout=3)
    session._last_health = health

    elapsed = str(datetime.datetime.now() - session.started_at).split(".")[0]
    route = session.last_route or {}
    temp_tag = " [yellow][TEMP][/yellow]" if session.temp_mode else ""
    auto_tag = f" [green]AUTONOMO[/green] ({session.auto_confirm})" if session.autonomous else ""
    plan_tag = " [magenta]PLAN[/magenta]" if session.plan_mode else ""
    brain_tag = " [green]BRAINSTORM[/green]" if session.brainstorm else ""
    tumba_tag = " [red]TUMBA[/red]" if session.tumba_mode else ""

    prov_lines = []
    for pname, h in health.items():
        if h.get("ok"):
            col = "yellow" if (pname == "ollama-local" and not h.get("models")) else "green"
            dot = f"[{col}]●[/{col}]"
            detail = h.get("detail", "OK")
            if pname == "ollama-local" and h.get("models"):
                detail += f" | modelos: {', '.join(h['models'][:3])}"
                if len(h.get("models", [])) > 3:
                    detail += f" +{len(h['models']) - 3} más"
        else:
            dot = "[red]●[/red]"
            detail = h.get("detail", "no disponible")
        prov_lines.append(f"  {dot} [bold]{pname:<14}[/bold]  [dim]{detail}[/dim]")
        auth_detail = h.get("auth_detail")
        quota_detail = h.get("quota_detail")
        if auth_detail or quota_detail:
            prov_lines.append(
                f"      [dim]auth: {auth_detail or 'no comprobado'}"
                f"  |  cuota/gasto: {quota_detail or 'no comprobada'}[/dim]"
            )

    prov_panel = "\n".join(prov_lines) if prov_lines else "  (sin datos)"
    skip = ", ".join(session.skip_providers) if session.skip_providers else "ninguno"
    degraded_section = f"\n[bold]Providers degradados en runtime:[/bold]\n{session.degraded_summary()}"
    tokens_section = f"\n[bold]Tokens esta sesión:[/bold]\n{session.tokens_summary()}"

    hw_section = ""
    if session.hw:
        hw_section = "\n[bold]Hardware:[/bold]\n" + "\n".join(hw_summary_lines(session.hw))

    console.print(Panel(
        f"Modelo:      {session.model_name} ({session.provider}){auto_tag}\n"
        f"Wire:        {session.wire_name}\n"
        f"Servicio:    {session.model_origin.get('service', '') or session.model_origin.get('route', '')}\n"
        f"Modo:        {session.orch_mode}{temp_tag}{plan_tag}{brain_tag}{tumba_tag}\n"
        f"Routing:     {route.get('mode', 'manual').upper()} → {route.get('model', session.model_name)} ({route.get('provider', session.provider)})"
        f"{' / ' + route.get('service') if route.get('service') else ''}\n"
        f"Motivo:      {route.get('reason', '—')}\n"
        f"Historial:   {len(session.history) - 1} mensajes\n"
        f"Switches:    {session.switches}\n"
        f"Tiempo:      {elapsed}\n"
        f"Auto-route:  {'ON' if session.autoroute else 'OFF'}  |  Single: {'ON' if session.single_model else 'OFF'}  |  Skip: {skip}\n"
        f"\n[bold]Providers — estado en vivo:[/bold]\n{prov_panel}"
        f"{degraded_section}"
        f"{tokens_section}"
        f"{hw_section}",
        title="[bold]Estado BAGO[/bold]", box=box.ROUNDED,
    ))

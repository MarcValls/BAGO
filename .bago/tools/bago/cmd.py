
import datetime

from rich import box
from rich.panel import Panel

from .constants import BAGO_SYSTEM, HELP
from .llm import run_chain, run_ensemble
from .menus import (
    _cmd_agents,
    _cmd_auth,
    _cmd_auto,
    _cmd_config,
    _cmd_framework,
    _cmd_login,
    _cmd_main_menu,
    _cmd_memory,
    _cmd_mode,
    _cmd_projects,
    _cmd_roles,
    _cmd_routing,
    _cmd_session,
    _cmd_skills,
    _cmd_sync,
    _cmd_wizard,
    _cmd_workspaces,
)
from .ui import console, pe, pi

def cmd(line, session):
    parts = line.strip().split(None, 1)
    v = parts[0].lower(); a = parts[1].strip() if len(parts) > 1 else ""

    if v == "/exit":
        console.print("[dim]BAGO Chat terminado.[/dim]"); return False

    # ── Menú principal navegable ──────────────────────────────────────────────
    elif v == "/":
        selected = _cmd_main_menu(session)
        if selected:
            return cmd(selected, session)   # ejecuta el comando elegido
    elif v == "/help":
        console.print(HELP)
    elif v == "/login":
        if not a:
            _cmd_login(session)          # picker navegable con flechas
        else:
            result = session.creds.do_login(a)
            console.print(f"  {result}")
    elif v == "/switch":
        if not a: pe("Uso: /switch <modelo|provider>")
        else:
            msg = session.switch_model(a)
            pi(msg)
    elif v == "/chain":
        if ":" not in a:
            pe("Uso: /chain modelo1->modelo2: prompt")
        else:
            chain_part, prompt_part = a.split(":", 1)
            models = [m.strip() for m in chain_part.split("->") if m.strip()]
            if len(models) < 2 or not prompt_part.strip():
                pe("Necesitas al menos 2 modelos y un prompt.")
            else:
                run_chain(session, models, prompt_part.strip())
    elif v == "/ensemble":
        if ":" not in a:
            pe("Uso: /ensemble modelo1 modelo2: prompt")
        else:
            mp, pp = a.split(":", 1)
            models = [m.strip() for m in mp.split() if m.strip()]
            if len(models) < 2 or not pp.strip():
                pe("Necesitas al menos 2 modelos y un prompt.")
            else:
                run_ensemble(session, models, pp.strip())
    elif v == "/autoroute":
        session.autoroute = a.lower() != "off"
        state = "ACTIVADO (auto single/chain/ensemble)" if session.autoroute else "DESACTIVADO"
        pi(f"Auto-routing: {state}")
    elif v == "/models":
        console.print(Panel(session.models_table(), title="[bold]Registry BAGO[/bold]", box=box.SIMPLE))
    elif v == "/status":
        elapsed = str(datetime.datetime.now()-session.started_at).split(".")[0]
        active = ", ".join(session.creds.active_bago_providers()) or "ninguno"
        temp_tag  = " [yellow][TEMP][/yellow]" if session.temp_mode else ""
        auto_tag  = f" [green]AUTONOMO[/green] ({session.auto_confirm})" if session.autonomous else ""
        plan_tag  = " [magenta]PLAN[/magenta]" if session.plan_mode else ""
        brain_tag = " [green]BRAINSTORM[/green]" if session.brainstorm else ""
        route = session.last_route or {}
        console.print(Panel(
            f"Modelo:      {session.model_name} ({session.provider}){auto_tag}\n"
            f"Wire:        {session.wire_name}\n"
            f"Modo:        {session.orch_mode}{temp_tag}{plan_tag}{brain_tag}\n"
            f"Routing:     {route.get('mode','manual').upper()} → {route.get('model', session.model_name)} ({route.get('provider', session.provider)})\n"
            f"Motivo:      {route.get('reason','—')}\n"
            f"Historial:   {len(session.history)-1} mensajes\n"
            f"Switches:    {session.switches}\n"
            f"Tiempo:      {elapsed}\n"
            f"Auto-route:  {'ON' if session.autoroute else 'OFF'}\n"
            f"Post-sync:   {session.sync_after}\n"
            f"Providers:   {active}",
            title="[bold]Estado BAGO[/bold]", box=box.ROUNDED))
    elif v == "/save":
        pi(f"Guardado: {session.save()}")
    elif v == "/clear":
        session.history = [{"role":"system","content":BAGO_SYSTEM}]
        pi("Historial limpiado.")

    # ── Agentes ────────────────────────────────────────────────────────────────
    elif v == "/agents":
        _cmd_agents(a)

    # ── Roles / modos del orquestador ─────────────────────────────────────────
    elif v == "/roles":
        _cmd_roles(a)

    # ── Skills ────────────────────────────────────────────────────────────────
    elif v == "/skills":
        _cmd_skills(a)

    # ── Matriz de routing ─────────────────────────────────────────────────────
    elif v == "/routing":
        _cmd_routing(a)

    # ── Fabrica / Wizard LM ───────────────────────────────────────────────────
    elif v in ("/new", "/fabrica", "/wizard"):
        _cmd_wizard(session)

    # ── Sesion ────────────────────────────────────────────────────────────────
    elif v == "/session":
        _cmd_session(session)

    # ── Auth (superset de /login) ─────────────────────────────────────────────
    elif v in ("/auth",):
        _cmd_auth(session)

    # ── Modo autonomo ─────────────────────────────────────────────────────────
    elif v == "/auto":
        _cmd_auto(session)

    # ── Modo del orquestador ──────────────────────────────────────────────────
    elif v == "/mode":
        _cmd_mode(session)

    # ── Modos conversacionales ────────────────────────────────────────────────
    elif v == "/plan":
        session.plan_mode = not session.plan_mode
        state = "[bold magenta]ACTIVADO[/bold magenta]" if session.plan_mode else "[dim]DESACTIVADO[/dim]"
        pi(f"Modo PLAN: {state}  — BAGO razonará y propondrá un plan antes de actuar.")
    elif v == "/brainstorm":
        session.brainstorm = not session.brainstorm
        state = "[bold green]ACTIVADO[/bold green]" if session.brainstorm else "[dim]DESACTIVADO[/dim]"
        pi(f"Modo BRAINSTORM: {state}  — BAGO expandirá ideas sin restricciones de acción.")

    # ── Sincronizacion + repliegue/letargo ────────────────────────────────────
    elif v == "/sync":
        _cmd_sync(session)

    # ── Memoria y conocimiento ────────────────────────────────────────────────
    elif v == "/memory":
        _cmd_memory(session)

    # ── Configuracion global ──────────────────────────────────────────────────
    elif v == "/config":
        _cmd_config(session)

    # ── Framework evolutivo ───────────────────────────────────────────────────
    elif v == "/framework":
        _cmd_framework(session)

    # ── Workspaces ────────────────────────────────────────────────────────────
    elif v == "/workspaces":
        _cmd_workspaces(session)

    # ── Proyectos ─────────────────────────────────────────────────────────────
    elif v == "/projects":
        _cmd_projects(session)

    else:
        pe(f"Desconocido: {v}  —  /help")
    return True

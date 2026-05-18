
import datetime
import json
from pathlib import Path

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
    _cmd_generative,
    _cmd_projects,
    _cmd_roles,
    _cmd_routing,
    _cmd_scan,
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
        if not a:
            # Interactive model picker
            from .ui import _menu_pick
            rows = []
            for pn, pd in session.providers.items():
                rows.append((None, f"── {pn} ──"))
                for mn in pd.get("models", {}):
                    rows.append((f"{pn}/{mn}", f"  {mn}  [{pn}]"))
            chosen = _menu_pick("/switch — Elegir modelo", "Selecciona un modelo:", rows)
            if chosen:
                msg = session.switch_model(chosen)
                pi(msg)
        else:
            msg = session.switch_model(a)
            pi(msg)
    elif v == "/chain":
        if ":" not in a:
            # Modo interactivo: pedir modelos y prompt
            from .ui import _menu_input, _menu_select
            pi("[dim]Ejemplo: qwen25-coder->gpt-4o[/dim]")
            modelos_str = _menu_input("/chain — modelos", "Modelos (m1->m2->...):", default="qwen25-coder->gpt-4o")
            if not modelos_str: pe("Cancelado."); return True
            prompt_txt = _menu_input("/chain — prompt", "Prompt a encadenar:")
            if not prompt_txt: pe("Cancelado."); return True
            a = f"{modelos_str}:{prompt_txt}"
        chain_part, prompt_part = a.split(":", 1)
        models = [m.strip() for m in chain_part.split("->") if m.strip()]
        if len(models) < 2 or not prompt_part.strip():
            pe("Necesitas al menos 2 modelos y un prompt.")
        else:
            run_chain(session, models, prompt_part.strip())
    elif v == "/ensemble":
        if ":" not in a:
            from .ui import _menu_input
            pi("[dim]Ejemplo: qwen25-coder gpt-4o[/dim]")
            modelos_str = _menu_input("/ensemble — modelos", "Modelos (m1 m2 ...):", default="qwen25-coder gpt-4o")
            if not modelos_str: pe("Cancelado."); return True
            prompt_txt = _menu_input("/ensemble — prompt", "Prompt para todos:")
            if not prompt_txt: pe("Cancelado."); return True
            a = f"{modelos_str}:{prompt_txt}"
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
        from .providers import scan_provider_health
        console.print("[dim]  Escaneando providers...[/dim]")
        health = scan_provider_health(session.creds, session.providers, timeout=3)
        session._last_health = health

        elapsed = str(datetime.datetime.now()-session.started_at).split(".")[0]
        route = session.last_route or {}
        temp_tag  = " [yellow][TEMP][/yellow]" if session.temp_mode else ""
        auto_tag  = f" [green]AUTONOMO[/green] ({session.auto_confirm})" if session.autonomous else ""
        plan_tag  = " [magenta]PLAN[/magenta]" if session.plan_mode else ""
        brain_tag = " [green]BRAINSTORM[/green]" if session.brainstorm else ""

        # ── Tabla de providers ────────────────────────────────────────────────
        prov_lines = []
        for pname, h in health.items():
            if h.get("ok"):
                col = "yellow" if (pname == "ollama-local" and not h.get("models")) else "green"
                dot = f"[{col}]●[/{col}]"
                detail = h.get("detail", "OK")
                if pname == "ollama-local" and h.get("models"):
                    detail += f" | modelos: {', '.join(h['models'][:3])}"
                    if len(h.get("models", [])) > 3:
                        detail += f" +{len(h['models'])-3} más"
            else:
                dot = "[red]●[/red]"
                detail = h.get("detail", "no disponible")
            prov_lines.append(f"  {dot} [bold]{pname:<14}[/bold]  [dim]{detail}[/dim]")

        prov_panel = "\n".join(prov_lines) if prov_lines else "  (sin datos)"
        skip = ", ".join(session.skip_providers) if session.skip_providers else "ninguno"

        # ── Tokens de la sesión ───────────────────────────────────────────────
        tokens_section = f"\n[bold]Tokens esta sesión:[/bold]\n{session.tokens_summary()}"

        console.print(Panel(
            f"Modelo:      {session.model_name} ({session.provider}){auto_tag}\n"
            f"Wire:        {session.wire_name}\n"
            f"Modo:        {session.orch_mode}{temp_tag}{plan_tag}{brain_tag}\n"
            f"Routing:     {route.get('mode','manual').upper()} → {route.get('model', session.model_name)} ({route.get('provider', session.provider)})\n"
            f"Motivo:      {route.get('reason','—')}\n"
            f"Historial:   {len(session.history)-1} mensajes\n"
            f"Switches:    {session.switches}\n"
            f"Tiempo:      {elapsed}\n"
            f"Auto-route:  {'ON' if session.autoroute else 'OFF'}  |  Skip: {skip}\n"
            f"\n[bold]Providers — estado en vivo:[/bold]\n{prov_panel}"
            f"{tokens_section}",
            title="[bold]Estado BAGO[/bold]", box=box.ROUNDED))

    # ── Scan completo de providers y modelos ──────────────────────────────────
    elif v == "/scan":
        _cmd_scan(session)

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

    # ── Modo generativo ───────────────────────────────────────────────────────
    elif v in ("/generative", "/gen"):
        _cmd_generative(session)

    # ── Modo del orquestador (alias legacy) ───────────────────────────────────
    elif v == "/mode":
        _cmd_generative(session)

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
        # ── Atajos de agente (/code /debug /arch /sprint /refactor /git …) ────
        _agents_file = Path(__file__).resolve().parents[3] / "state" / "agents_registry.json"
        try:
            _agents_data = json.loads(_agents_file.read_text(encoding="utf-8-sig"))
            _agent_by_shortcut = {}
            for _aname, _ag in _agents_data.items():
                if _aname.startswith("_"): continue
                for _s in _ag.get("shortcuts", []):
                    _agent_by_shortcut[_s.lower()] = (_aname, _ag)
        except Exception:
            _agent_by_shortcut = {}

        if v in _agent_by_shortcut:
            _aname, _ag = _agent_by_shortcut[v]
            _model    = _ag.get("model", session.model_name)
            _provider = _ag.get("provider", session.provider)
            _sysprompt = _ag.get("system_prompt", "")
            # Switch model/provider (provider/model format now supported by _find_model)
            try:
                msg = session.switch_model(f"{_provider}/{_model}")
            except Exception:
                msg = session.switch_model(_model)
            # Override system message in history
            if _sysprompt and session.history:
                session.history[0] = {"role": "system", "content": _sysprompt}
            pi(f"[bold cyan]Agente activado:[/bold cyan] {_aname}  |  {_model} ({_provider})")
            pi(f"Skills: {', '.join(_ag.get('skills', []))}")
            if a:
                # Inline prompt: send immediately to the LLM
                from .llm import chat as _chat
                result = _chat(session, a)
                if result:
                    from .ui import show_response as _show
                    _show(result, session.model_name, session.provider)
            return True
        else:
            pe(f"Desconocido: {v}  —  /help")
    return True

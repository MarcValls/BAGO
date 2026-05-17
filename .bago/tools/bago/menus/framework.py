
from pathlib import Path

from rich import box
from rich.panel import Panel

from ..constants import TOOLS_DIR
from ..llm import _llm_call
from ..storage import ORCH_FILE, _STATE_DIR, _load_json, _save_json
from ..ui import console, _menu_action, _menu_input, _menu_select, pe, pi

def _cmd_framework(session):
    """Vista evolutiva del framework BAGO: sprint, health, ideas, componentes, historia."""
    while True:
        choices = [
            ("sprint",      "Sprint activo  (workflow actual, tareas, historial)"),
            ("health",      "Health check  (estado del guardian y sistema)"),
            ("components",  "Mapa de componentes  (agentes, skills, tools, routing)"),
            ("ideas",       "Ideas de mejora  (anotar + asistido por LM)"),
            ("history",     "Historia de sprints  (sprint_summary_*.md)"),
            ("evolve",      "[bold cyan]Modo evolutivo[/bold cyan]  (disenyo iterativo asistido por LM)"),
        ]
        sel = _menu_select("BAGO / Framework", "Vista evolutiva del framework BAGO:", choices)
        if sel is None: break

        if sel == "sprint":
            _fw_sprint()
        elif sel == "health":
            _fw_health()
        elif sel == "components":
            _fw_components()
        elif sel == "ideas":
            _fw_ideas(session)
        elif sel == "history":
            _fw_history()
        elif sel == "evolve":
            _fw_evolve(session)

def _fw_sprint():
    sprint = _load_json(_STATE_DIR / "sprint.json")
    gs     = _load_json(_STATE_DIR / "global_state.json")
    active = gs.get("sprint_status", {}).get("active_workflow") or sprint.get("sprint_status", {}).get("active_workflow")
    last   = gs.get("sprint_status", {}).get("last_completed_workflow", {})
    inv    = gs.get("inventory", {})

    lines = []
    if active:
        lines.append(f"[bold green]WORKFLOW ACTIVO[/bold green]")
        lines.append(f"  Codigo:  {active.get('code','?')}")
        lines.append(f"  Titulo:  {active.get('title','?')}")
        lines.append(f"  Inicio:  {str(active.get('started','?'))[:16]}")
    else:
        lines.append("[dim]No hay workflow activo.[/dim]")

    if last:
        lines.append(f"\n[bold]Ultimo completado:[/bold]")
        lines.append(f"  {last.get('code','?')} — {last.get('title','?')}")
        lines.append(f"  Duracion: {last.get('duration','?')}")

    if inv:
        lines.append(f"\n[bold]Inventario:[/bold]")
        lines.append(f"  Sessions: {inv.get('sessions','?')} | Changes: {inv.get('changes','?')} | Commits: {inv.get('commits','?')}")
        lines.append(f"  Ultimo commit: {inv.get('last_commit_sha','?')} — {str(inv.get('last_commit_msg',''))[:60]}")

    _menu_action("Sprint / Workflow Activo", "\n".join(lines), [("Cerrar","ok")])

def _fw_health():
    h = _load_json(_STATE_DIR / "health.json")
    v = h.get("last_validation", {})
    g = h.get("guardian_findings", {})
    sys_ok = h.get("system_health", "unknown")

    health_color = "green" if sys_ok == "ok" else "red"
    pct = g.get("health_pct", "?")
    lines = [
        f"[bold {health_color}]Sistema: {sys_ok.upper()}[/bold {health_color}]",
        f"Guardian: {pct}% salud  |  Tools: {g.get('tools_total','?')}",
        f"",
        f"[bold]Ultima validacion:[/bold]  {str(v.get('date','?'))[:16]}",
        f"  manifest: {v.get('validate_manifest','?')}  |  state: {v.get('validate_state','?')}  |  pack: {v.get('validate_pack','?')}",
        f"  sincerity: {v.get('sincerity','?')}",
        f"  stability: {v.get('stability','?')}",
        f"",
        f"[bold]Errores/Advertencias guardian:[/bold]",
        f"  E001 (sin test):       {g.get('e001_no_test',0)}",
        f"  E002 (no registrado):  {g.get('e002_not_registered',0)}",
        f"  W001 (sin routing):    {g.get('w001_no_routing',0)}",
        f"  W002 (sin docstring):  {g.get('w002_no_docstring',0)}",
        f"  Prioridad fix:         {g.get('priority_fix','ninguna')}",
    ]
    if g.get("dead_ref"):
        lines.append(f"  [yellow]Dead ref:[/yellow] {g['dead_ref']}")
    _menu_action("Framework Health Check", "\n".join(lines), [("Cerrar","ok")])

def _fw_components():
    agents   = {k: v for k, v in _load_json(_STATE_DIR / "agents_registry.json").items() if k != "_meta"}
    skills   = _load_json(_STATE_DIR / "skill_registry.json")
    routing  = _load_json(_STATE_DIR / "model_routing.json")
    orch     = _load_json(ORCH_FILE)
    rules    = routing.get("rules", [])
    modes    = orch.get("modes", {})
    tasks    = orch.get("task_preference", {})

    # Contar tools
    tools_dir = TOOLS_DIR
    tool_count = len(list(tools_dir.glob("*.py")))

    lines = [
        f"[bold]Agentes:[/bold]      {len(agents)}  ({', '.join(list(agents.keys())[:5])})",
        f"[bold]Skills:[/bold]       {len(skills)}  ({', '.join(list(skills.keys())[:5])})",
        f"[bold]Reglas routing:[/bold] {len(rules)}",
        f"[bold]Modos orch:[/bold]   {len(modes)}  ({', '.join(modes.keys())})",
        f"[bold]Task prefs:[/bold]   {len(tasks)}",
        f"[bold]Tools Python:[/bold] {tool_count} archivos en tools/",
        f"",
        f"[bold]Routing fallback:[/bold] {routing.get('fallback',{}).get('provider','?')} / {routing.get('fallback',{}).get('model','?')}",
    ]
    _menu_action("Mapa de Componentes BAGO", "\n".join(lines), [("Cerrar","ok")])

def _fw_ideas(session):
    ideas_file = _STATE_DIR / "implemented_ideas.json"
    ideas_data = _load_json(ideas_file) or {}
    implemented = ideas_data.get("ideas", ideas_data) if isinstance(ideas_data, dict) else ideas_data

    while True:
        choices = [
            ("list",    f"Ver ideas implementadas  ({len(implemented) if isinstance(implemented, list) else len(implemented)} ideas)"),
            ("add_lm",  "Anadir idea asistida por LM  (describe el objetivo, el LM propone)"),
            ("add_raw", "Anadir idea manualmente"),
        ]
        sel = _menu_select("Framework / Ideas", "Gestion de ideas de mejora:", choices)
        if sel is None: break

        if sel == "list":
            if isinstance(implemented, list):
                entries = implemented[:20]
            else:
                entries = list(implemented.values())[:20]
            if not entries:
                pi("No hay ideas registradas."); continue
            ideas_choices = []
            for i, e in enumerate(entries):
                label = e.get("idea", e.get("title", str(e)[:60]))[:70] if isinstance(e, dict) else str(e)[:70]
                ideas_choices.append((str(i), label))
            sel2 = _menu_select("Ideas implementadas", f"{len(entries)} ideas:", ideas_choices)
            if sel2:
                e = entries[int(sel2)] if isinstance(implemented, list) else entries[int(sel2)]
                info = "\n".join(f"{k}: {v}" for k, v in e.items()) if isinstance(e, dict) else str(e)
                _menu_action("Idea", info[:500], [("Cerrar","ok")])

        elif sel == "add_lm":
            objetivo = _menu_input("Idea (LM asistido)", "Describe el objetivo o mejora que quieres para el framework:")
            if not objetivo: continue
            prompt_idea = (
                "Eres arquitecto del framework BAGO (orquestador multi-modelo). "
                "El usuario describe una mejora. Propone un plan de implementacion conciso:\n"
                "- Titulo\n- Descripcion\n- Componentes afectados\n- Pasos de implementacion (max 5)\n"
                f"Objetivo: {objetivo}"
            )
            pi("Consultando al LM para estructurar la idea...")
            try:
                lm, kw = session.litellm_info
                resp = _llm_call(lm, kw, [{"role":"user","content":prompt_idea}])
                _menu_action("Propuesta del LM", resp[:800], [("Cerrar","ok")])
            except Exception as e:
                pe(f"Error LM: {e}")

        elif sel == "add_raw":
            title = _menu_input("Titulo", "Titulo de la idea:")
            if not title: continue
            desc  = _menu_input("Descripcion", "Descripcion:")
            import datetime as _dt
            new_idea = {"idea": title, "description": desc or "", "date": _dt.date.today().isoformat(), "status": "proposed"}
            if isinstance(implemented, list):
                implemented.append(new_idea)
                ideas_data = implemented
            else:
                ideas_data.setdefault("ideas", []).append(new_idea)
            _save_json(ideas_file, ideas_data)
            pi(f"Idea '{title}' anadida.")

def _fw_history():
    state_dir = _STATE_DIR
    summaries = sorted(state_dir.glob("sprint_summary_*.md"), key=lambda f: f.name)
    if not summaries:
        pi("No hay summaries de sprint guardados."); return
    choices = [(str(f), f.name) for f in summaries]
    while True:
        sel = _menu_select("Historial de Sprints", f"{len(summaries)} sprint summaries:", choices)
        if sel is None: break
        try:
            content = Path(sel).read_text(encoding="utf-8-sig")
            preview = content[:800] + ("\n...(truncado)" if len(content) > 800 else "")
            _menu_action(Path(sel).name, preview, [("Cerrar","ok")])
        except Exception as e:
            pe(str(e))

def _fw_evolve(session):
    """Modo evolutivo: disenyo iterativo del framework asistido por LM."""
    # Contexto del framework para el LM
    agents   = {k: v for k, v in _load_json(_STATE_DIR / "agents_registry.json").items() if k != "_meta"}
    skills   = _load_json(_STATE_DIR / "skill_registry.json")
    routing  = _load_json(_STATE_DIR / "model_routing.json")
    gs       = _load_json(_STATE_DIR / "global_state.json")
    active_wf = gs.get("sprint_status", {}).get("active_workflow", {})

    context_lines = [
        f"Framework BAGO v{gs.get('bago_version','?')}",
        f"Workflow activo: {active_wf.get('code','ninguno')} — {active_wf.get('title','')}",
        f"Agentes: {list(agents.keys())}",
        f"Skills: {list(skills.keys())}",
        f"Reglas routing: {len(routing.get('rules',[]))}",
    ]
    fw_context = "\n".join(context_lines)

    evolve_system = (
        "Eres el arquitecto evolucionario del framework BAGO, un orquestador multi-modelo adaptativo. "
        "Tu rol es guiar el desarrollo iterativo del framework: proponer mejoras, detectar gaps, "
        "sugerir nuevas piezas (agentes/skills/routing/modos), y conectar las necesidades del usuario "
        "con la arquitectura existente. Siempre propones cambios concretos y accionables.\n\n"
        f"Estado actual del framework:\n{fw_context}"
    )

    console.print(Panel(
        f"[bold cyan]Modo Evolutivo BAGO[/bold cyan]\n"
        f"[dim]El LM conoce el estado del framework y te ayuda a evolucionar cada pieza.\n"
        f"Escribe tu objetivo, problema o mejora. /exit para salir.[/dim]",
        box=box.ROUNDED))

    evolve_history = [{"role": "system", "content": evolve_system}]

    while True:
        try:
            from prompt_toolkit import prompt as pt_prompt
            user_in = pt_prompt("[framework] > ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not user_in or user_in.lower() in ("/exit", "/salir", "exit", "salir"):
            break

        evolve_history.append({"role": "user", "content": user_in})
        lm, kw = session.litellm_info
        try:
            with console.status(f"[dim]{session.model_name} (modo evolutivo)...[/dim]", spinner="dots"):
                resp = _llm_call(lm, kw, evolve_history)
            evolve_history.append({"role": "assistant", "content": resp})
            console.print(Panel(resp, title=f"[dim]{session.model_name}[/dim]", box=box.SIMPLE))
        except Exception as e:
            pe(f"Error LM: {e}")

    pi("Saliendo del modo evolutivo.")

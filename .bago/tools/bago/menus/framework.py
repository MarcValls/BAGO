
from pathlib import Path

from rich import box
from rich.panel import Panel

from ..constants import TOOLS_DIR
from ..llm import _llm_call, OllamaNoModelAvailable
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
                resp = _llm_call(
                    lm, kw, [{"role":"user","content":prompt_idea}],
                    session=session,
                    _provider=session.provider,
                    _model=session.model_name,
                )
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
    import re

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

    # Dos system prompts: uno para planear, otro para implementar
    _PLAN_SYSTEM = (
        "Eres el arquitecto evolucionario del framework BAGO, un orquestador multi-modelo adaptativo. "
        "Tu rol es guiar el diseño iterativo: proponer mejoras, detectar gaps, sugerir nuevas piezas "
        "(agentes/skills/routing/modos) y conectar las necesidades del usuario con la arquitectura existente. "
        "Propón cambios concretos y accionables. Cuando el usuario esté satisfecho con el plan elegirá 'Implementar'.\n\n"
        f"Estado actual del framework:\n{fw_context}"
    )
    _IMPL_SYSTEM = (
        "Eres el implementador del framework BAGO. El usuario aprobó el plan: ahora IMPLEMENTA.\n"
        "REGLAS ESTRICTAS:\n"
        "1. Genera INMEDIATAMENTE el código completo listo para guardar. NO hagas resúmenes ni planes.\n"
        "2. Cada fichero va en un bloque de código con la ruta como comentario en la primera línea:\n"
        "   ```python\n   # ruta/al/fichero.py\n   <código completo>\n   ```\n"
        "3. Si solo hay que modificar parte de un fichero existente, usa `# EDIT: ruta/fichero.py` "
        "y muestra el fragmento con contexto suficiente para ubicarlo.\n"
        "4. Tras los bloques de código, escribe UNA línea de resumen de qué ficheros creaste/modificaste.\n"
        "5. CERO planes, CERO preguntas, CERO confirmaciones — solo código.\n\n"
        f"Estado actual del framework:\n{fw_context}"
    )

    console.print(Panel(
        f"[bold cyan]Modo Evolutivo BAGO[/bold cyan]\n"
        f"[dim]Diseña con el LM y cuando el plan te convenza elige [bold]Implementar[/bold].\n"
        f"El LM generara codigo completo que se puede escribir a disco directamente.\n"
        f"/exit para salir.[/dim]",
        box=box.ROUNDED))

    evolve_history = [{"role": "system", "content": _PLAN_SYSTEM}]
    mode = "plan"  # "plan" | "impl"

    while True:
        try:
            try:
                from prompt_toolkit import prompt as pt_prompt
            except ModuleNotFoundError:
                from ..ui import _stdin_prompt as pt_prompt
            prefix = "[framework|IMPL] > " if mode == "impl" else "[framework] > "
            user_in = pt_prompt(prefix).strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not user_in or user_in.lower() in ("/exit", "/salir", "exit", "salir"):
            break

        evolve_history.append({"role": "user", "content": user_in})
        lm, kw = session.litellm_info
        try:
            with console.status(f"[dim]{session.model_name} (modo evolutivo)...[/dim]", spinner="dots"):
                resp = _llm_call(
                    lm, kw, evolve_history,
                    session=session,
                    _provider=session.provider,
                    _model=session.model_name,
                )
            evolve_history.append({"role": "assistant", "content": resp})
            console.print(Panel(resp, title=f"[dim]{session.model_name}[/dim]", box=box.SIMPLE))

            # Detectar bloques de código con ruta en primera línea
            code_blocks = re.findall(
                r"```(?:python|js|json|yaml|toml|sh|bash|text|)\n(# (?:EDIT: )?(.+?)\n([\s\S]*?))```",
                resp
            )

            # Menú de acción tras cada respuesta
            action_choices = []
            if code_blocks:
                action_choices.append(("write",   f"Escribir {len(code_blocks)} fichero(s) a disco"))
                action_choices.append(("review",  "Revisar ficheros uno a uno antes de escribir"))
            if mode == "plan":
                action_choices.append(("impl",    "[bold green]Implementar[/bold green]  — pedir codigo completo al LM"))
            else:
                action_choices.append(("plan",    "Volver a modo planificacion"))
            action_choices.append(("continue", "Seguir adaptando el plan  (escribir al LM)"))

            sel_action = _menu_select("Modo Evolutivo", "¿Que hacemos ahora?", action_choices)

            if sel_action == "write" and code_blocks:
                _write_evolve_files(code_blocks)
            elif sel_action == "review" and code_blocks:
                _review_evolve_files(code_blocks)
            elif sel_action == "impl":
                # Cambia a modo implementación: inyecta nuevo system prompt y pide código
                mode = "impl"
                evolve_history[0] = {"role": "system", "content": _IMPL_SYSTEM}
                evolve_history.append({"role": "user", "content": "Implementa ahora el plan acordado. Genera el código completo."})
                with console.status(f"[dim]{session.model_name} (implementando)...[/dim]", spinner="dots"):
                    impl_resp = _llm_call(
                        lm, kw, evolve_history,
                        session=session,
                        _provider=session.provider,
                        _model=session.model_name,
                    )
                evolve_history.append({"role": "assistant", "content": impl_resp})
                console.print(Panel(impl_resp, title=f"[dim]{session.model_name} — IMPLEMENTACION[/dim]", box=box.SIMPLE))
                impl_blocks = re.findall(
                    r"```(?:python|js|json|yaml|toml|sh|bash|text|)\n(# (?:EDIT: )?(.+?)\n([\s\S]*?))```",
                    impl_resp
                )
                if impl_blocks:
                    sel2 = _menu_select(
                        "Escribir implementacion",
                        f"Se generaron {len(impl_blocks)} fichero(s). ¿Escribir a disco?",
                        [
                            ("write",  "Escribir todos a disco"),
                            ("review", "Revisar uno a uno"),
                            ("skip",   "No escribir"),
                        ]
                    )
                    if sel2 == "write":
                        _write_evolve_files(impl_blocks)
                    elif sel2 == "review":
                        _review_evolve_files(impl_blocks)
            elif sel_action == "plan":
                mode = "plan"
                evolve_history[0] = {"role": "system", "content": _PLAN_SYSTEM}
                pi("Volviendo a modo planificacion.")
            # sel_action == "continue" → loop continúa, el usuario escribe al LM

        except OllamaNoModelAvailable as e:
            console.print(Panel(
                f"[bold red]🚨 Sin modelo disponible[/bold red]\n\n"
                f"  Modelo [cyan]{e.missing}[/cyan] no instalado.\n"
                f"  [dim]Intentados: {', '.join(e.tried) or 'ninguno'}[/dim]\n\n"
                f"  [yellow]Opciones:[/yellow]\n"
                f"   • Instala un modelo: [cyan]ollama pull qwen2.5-coder:7b[/cyan]\n"
                f"   • Configura credenciales: [cyan]/login[/cyan]\n"
                f"   • Cambia de proveedor:   [cyan]/switch[/cyan]",
                title="Modo Evolutivo — Sin Modelo",
                border_style="red",
                expand=False,
            ))
            sel_recover = _menu_select(
                "Sin modelo",
                "¿Qué hacemos?",
                [
                    ("pull",  "Intentar instalar qwen2.5-coder:7b ahora"),
                    ("exit",  "Salir del modo evolutivo"),
                ],
            )
            if sel_recover == "pull":
                from ..providers import ollama_pull
                ollama_pull("qwen2.5-coder:7b")
                pi("Si la instalación tuvo éxito, vuelve a escribir tu mensaje.")
            else:
                break
        except Exception as e:
            pe(f"Error LM: {e}")

    pi("Saliendo del modo evolutivo.")


def _write_evolve_files(code_blocks):
    """Escribe los ficheros generados por el LM a disco."""
    import re
    written = []
    for _, raw_path, code_body in code_blocks:
        is_edit = raw_path.startswith("EDIT: ")
        clean_path = raw_path.replace("EDIT: ", "").strip()
        target = Path(clean_path) if Path(clean_path).is_absolute() else TOOLS_DIR / clean_path
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(code_body, encoding="utf-8")
            written.append(str(target))
            pi(f"  [green]OK[/green] {target}")
        except Exception as e:
            pe(f"  Error escribiendo {target}: {e}")
    if written:
        pi(f"[bold green]{len(written)} fichero(s) escritos.[/bold green]")


def _review_evolve_files(code_blocks):
    """Revisa y escribe ficheros uno a uno con confirmación."""
    for _, raw_path, code_body in code_blocks:
        is_edit = raw_path.startswith("EDIT: ")
        clean_path = raw_path.replace("EDIT: ", "").strip()
        target = Path(clean_path) if Path(clean_path).is_absolute() else TOOLS_DIR / clean_path
        preview = code_body[:600] + ("\n...(truncado)" if len(code_body) > 600 else "")
        action_label = "EDITAR" if is_edit else "CREAR"
        sel = _menu_select(
            f"{action_label}: {clean_path}",
            f"[dim]{preview}[/dim]",
            [("yes", "Escribir este fichero"), ("no", "Saltar")]
        )
        if sel == "yes":
            try:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(code_body, encoding="utf-8")
                pi(f"  [green]OK[/green] {target}")
            except Exception as e:
                pe(f"  Error: {e}")

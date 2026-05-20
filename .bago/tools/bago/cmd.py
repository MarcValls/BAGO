
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
    cmd_catalog,
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
            # Interactive model picker — incluye acceso al catálogo
            from .ui import _menu_pick
            rows = [
                ("__catalog__", "✨ Explorar catálogo de modelos (instalar / comparar)"),
                (None, "── Modelos activos ──"),
            ]
            for pn, pd in session.providers.items():
                rows.append((None, f"  [{pn}]"))
                for mn in pd.get("models", {}):
                    rows.append((f"{pn}/{mn}", f"    {mn}"))
            chosen = _menu_pick("/switch — Elegir modelo", "Selecciona un modelo:", rows)
            if chosen == "__catalog__":
                cmd_catalog(session)
            elif chosen:
                msg = session.switch_model(chosen)
                pi(msg)
        else:
            msg = session.switch_model(a)
            pi(msg)
    elif v == "/chain":
        if ":" not in a:
            # Modo interactivo: pedir modelos y prompt
            from .ui import _menu_input
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
    elif v == "/catalog":
        cmd_catalog(session)
    elif v == "/status":
        from .providers import scan_provider_health
        from .hw_probe import hw_summary_lines
        console.print("[dim]  Escaneando providers...[/dim]")
        health = scan_provider_health(session.creds, session.providers, timeout=3)
        session._last_health = health

        elapsed = str(datetime.datetime.now()-session.started_at).split(".")[0]
        route = session.last_route or {}
        temp_tag  = " [yellow][TEMP][/yellow]" if session.temp_mode else ""
        auto_tag  = f" [green]AUTONOMO[/green] ({session.auto_confirm})" if session.autonomous else ""
        plan_tag  = " [magenta]PLAN[/magenta]" if session.plan_mode else ""
        brain_tag = " [green]BRAINSTORM[/green]" if session.brainstorm else ""
        tumba_tag = " [red]🪦 TUMBA[/red]" if session.tumba_mode else ""

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

        # ── Tokens de la sesión ───────────────────────────────────────────────
        tokens_section = f"\n[bold]Tokens esta sesión:[/bold]\n{session.tokens_summary()}"

        # ── Hardware ──────────────────────────────────────────────────────────
        hw_section = ""
        if session.hw:
            hw_lines = hw_summary_lines(session.hw)
            hw_section = "\n[bold]Hardware:[/bold]\n" + "\n".join(hw_lines)

        console.print(Panel(
            f"Modelo:      {session.model_name} ({session.provider}){auto_tag}\n"
            f"Wire:        {session.wire_name}\n"
            f"Modo:        {session.orch_mode}{temp_tag}{plan_tag}{brain_tag}{tumba_tag}\n"
            f"Routing:     {route.get('mode','manual').upper()} → {route.get('model', session.model_name)} ({route.get('provider', session.provider)})\n"
            f"Motivo:      {route.get('reason','—')}\n"
            f"Historial:   {len(session.history)-1} mensajes\n"
            f"Switches:    {session.switches}\n"
            f"Tiempo:      {elapsed}\n"
            f"Auto-route:  {'ON' if session.autoroute else 'OFF'}  |  Skip: {skip}\n"
            f"\n[bold]Providers — estado en vivo:[/bold]\n{prov_panel}"
            f"{degraded_section}"
            f"{tokens_section}"
            f"{hw_section}",
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

    # ── Modo Tumba ────────────────────────────────────────────────────────────
    elif v == "/tumba":
        from .tumba import tumba_list, tumba_delete, tumba_clear, tumba_add
        from .tumba_schema import (
            get_slots, all_providers, missing_slots, all_by_group, provider_group,
        )

        sub_parts = a.split(None, 1)
        sub = sub_parts[0].lower() if sub_parts else ""
        sub_arg = sub_parts[1].strip() if len(sub_parts) > 1 else ""

        if sub in ("list", "ls", "listar"):
            keys = tumba_list()
            if not keys:
                pi("🪦 Tumba vacía.")
            else:
                pi("[bold]🪦 Claves en tumba:[/bold] (los valores nunca se muestran)")
                for i, k in enumerate(keys, 1):
                    console.print(f"  {i:>2}. [bold cyan]{k}[/bold cyan]  →  {{{{{k}}}}}")

        elif sub.startswith("del") or sub.startswith("rm"):
            name = sub_arg or (a.split(None, 1)[1].strip() if " " in a else "")
            if name:
                console.print(tumba_delete(name))
            else:
                pi("[red]Uso: /tumba del <nombre>[/red]")

        elif sub in ("clear", "limpiar", "vaciar"):
            n = tumba_clear()
            pi(f"🪦 Tumba vaciada — {n} entradas eliminadas.")

        elif sub == "schema":
            # /tumba schema [provider]  — muestra slots de un provider o todos los grupos
            if sub_arg:
                prov = sub_arg.lower()
                slots = get_slots(prov)
                if not slots:
                    providers_str = ", ".join(all_providers())
                    pi(f"[red]Provider '{prov}' no tiene schema predefinido.[/red]\n"
                       f"  Disponibles: {providers_str}")
                else:
                    from rich.table import Table
                    t = Table(title=f"🪦 Schema tumba — [bold]{prov}[/bold]",
                              box=box.ROUNDED, show_lines=True)
                    t.add_column("Clave tumba", style="bold cyan", no_wrap=True)
                    t.add_column("Env var", style="dim")
                    t.add_column("Req.", justify="center")
                    t.add_column("Formato", style="yellow")
                    t.add_column("Descripción")
                    for s in slots:
                        req = "[green]✓[/green]" if s["required"] else "[dim]opt[/dim]"
                        env = s["env"] or "[dim]—[/dim]"
                        t.add_row(s["name"], env, req, s["format"], s["desc"])
                    console.print(t)
                    keys = tumba_list()
                    miss = missing_slots(prov, keys)
                    if miss:
                        req_miss = [m for m in miss if m["required"]]
                        opt_miss = [m for m in miss if not m["required"]]
                        if req_miss:
                            console.print(
                                f"\n  [red]⚠  Faltan {len(req_miss)} slots requeridos:[/red] "
                                + ", ".join(f"[bold]{m['name']}[/bold]" for m in req_miss)
                            )
                        if opt_miss:
                            console.print(
                                f"  [dim]Opcionales sin llenar: "
                                + ", ".join(m["name"] for m in opt_miss) + "[/dim]"
                            )
                    else:
                        console.print(
                            f"\n  [green]✓ Todos los slots de {prov} están en la tumba.[/green]"
                        )
            else:
                # Mostrar catálogo completo por grupos
                by_group = all_by_group()
                _GROUP_LABELS = {
                    "llm":       "🤖 LLM / IA",
                    "repo":      "📦 Repositorios",
                    "cloud":     "☁️  Cloud/Storage",
                    "messaging": "💬 Mensajería/Bots",
                    "payments":  "💳 Pagos",
                    "infra":     "🏗️  Infraestructura",
                    "database":  "🗄️  Bases de datos",
                    "email":     "📧 Email/SMS",
                    "devops":    "🔧 DevOps",
                    "pm":        "📋 Gestión de proyectos",
                }
                pi("[bold]🪦 Providers con schema tumba predefinido:[/bold]")
                for group, members in by_group.items():
                    label = _GROUP_LABELS.get(group, group)
                    prov_list = "  ".join(f"[cyan]{p}[/cyan]" for p in members)
                    console.print(f"  {label}:  {prov_list}")
                console.print(
                    "\n  [dim]/tumba schema <provider>  — ver slots detallados[/dim]\n"
                    "  [dim]/tumba fill <provider>    — rellenar slots en modo tumba[/dim]"
                )

        elif sub == "fill":
            # /tumba fill <provider>  — activa tumba y guía slot por slot
            if not sub_arg:
                pi("[red]Uso: /tumba fill <provider>  (ej: /tumba fill telegram)[/red]")
            else:
                prov = sub_arg.lower()
                slots = get_slots(prov)
                if not slots:
                    pi(f"[red]Provider '{prov}' no tiene schema. Usa /tumba schema para ver disponibles.[/red]")
                else:
                    try:
                        from prompt_toolkit import prompt as pt_prompt
                    except ModuleNotFoundError:
                        from .ui import _stdin_prompt as pt_prompt
                    keys = tumba_list()
                    miss = missing_slots(prov, keys)
                    if not miss:
                        pi(f"[green]✓ Todos los slots de [bold]{prov}[/bold] ya están en la tumba.[/green]")
                    else:
                        console.print(Panel(
                            f"[bold yellow]🪦 TUMBA FILL — {prov.upper()}[/bold yellow]\n\n"
                            f"  Rellenando [bold]{len(miss)}[/bold] slots.\n"
                            f"  Los valores se copian directamente — el LLM NO los verá nunca.\n\n"
                            f"  [dim]Pulsa Enter sin valor para saltar un slot.[/dim]",
                            title=f"[bold red]🪦 FILL: {prov}[/bold red]",
                            border_style="red",
                            expand=False,
                        ))
                        saved = 0
                        for slot in miss:
                            req_label = "[red]*[/red]" if slot["required"] else "[dim]opt[/dim]"
                            console.print(
                                f"\n  {req_label} [bold cyan]{slot['name']}[/bold cyan]\n"
                                f"     [dim]{slot['desc']}[/dim]\n"
                                f"     [dim]Formato: {slot['format']}[/dim]"
                                + (f"\n     [dim]Obtener en: {slot['url']}[/dim]" if slot["url"] else "")
                            )
                            try:
                                val = pt_prompt(
                                    f"  {slot['name']}: ",
                                    is_password=True,
                                ).strip()
                            except (KeyboardInterrupt, EOFError):
                                pi("\n[dim]Fill cancelado.[/dim]")
                                break
                            if not val:
                                console.print("  [dim]→ Saltado[/dim]")
                                continue
                            line = f"{slot['name']}: {val}"
                            ok, name, msg = tumba_add(line)
                            console.print(msg)
                            if ok:
                                saved += 1
                        console.print(
                            f"\n  [green]✓ {saved} slots guardados para [bold]{prov}[/bold].[/green]\n"
                            f"  [dim]Usa {{{{slot name}}}} en tus mensajes para insertar el valor.[/dim]"
                        )

        elif sub == "check":
            # /tumba check <provider>  — estado rápido de slots
            if not sub_arg:
                pi("[red]Uso: /tumba check <provider>[/red]")
            else:
                prov = sub_arg.lower()
                slots = get_slots(prov)
                if not slots:
                    pi(f"[red]Provider '{prov}' no tiene schema predefinido.[/red]")
                else:
                    keys = set(tumba_list())
                    pi(f"[bold]🪦 Estado tumba — {prov}:[/bold]")
                    for slot in slots:
                        present = slot["name"] in keys
                        status = "[green]✓ guardado[/green]" if present else (
                            "[red]✗ FALTA[/red]" if slot["required"] else "[dim]— opcional[/dim]"
                        )
                        console.print(f"  {status}  [cyan]{slot['name']}[/cyan]")

        else:
            # Toggle del modo tumba
            session.tumba_mode = not session.tumba_mode
            if session.tumba_mode:
                console.print(Panel(
                    "[bold yellow]🪦 MODO TUMBA ACTIVADO[/bold yellow]\n\n"
                    "  Lo que escribas [bold]NO[/bold] se enviará al LLM.\n"
                    "  En su lugar se copia al archivo de secretos.\n\n"
                    "  [bold]Formato:[/bold]  [cyan]Nombre clave: valor secreto[/cyan]\n"
                    "  [bold]Ejemplo:[/bold]  [cyan]Telegram Bot Token: 1234567:ABCxyz...[/cyan]\n\n"
                    "  Para usar el valor en un mensaje normal:\n"
                    "    [cyan]Configura el bot con el {{Telegram Bot Token}}[/cyan]\n\n"
                    "  [dim]Subcomandos disponibles:[/dim]\n"
                    "  [dim]  /tumba list              — ver claves guardadas[/dim]\n"
                    "  [dim]  /tumba fill <provider>   — rellenar slots de un provider[/dim]\n"
                    "  [dim]  /tumba schema [provider] — ver slots predefinidos[/dim]\n"
                    "  [dim]  /tumba check <provider>  — estado de slots por provider[/dim]\n"
                    "  [dim]  /tumba del <nombre>      — eliminar una clave[/dim]\n"
                    "  [dim]  /tumba                   — desactivar modo tumba[/dim]",
                    title="[bold red]🪦 TUMBA[/bold red]",
                    border_style="red",
                    expand=False,
                ))
            else:
                pi("🪦 Modo TUMBA [dim]DESACTIVADO[/dim] — volviendo al chat normal.")


    # ── Bots de mensajeria ─────────────────────────────────────────────────────
    elif v == "/bot":
        parts = a.split(None, 1) if a else []
        bot_name = parts[0].lower() if parts else ""
        bot_arg = parts[1].strip() if len(parts) > 1 else ""

        if not bot_name:
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
        elif bot_name == "telegram":
            import subprocess, sys as _sys2
            if bot_arg == "start":
                token = session.creds.get("telegram", {}).get("token", "") or _sys2.environ.get("TELEGRAM_BOT_TOKEN", "")
                if not token:
                    pe("No hay token de Telegram. Guardalo con /tumba o exporta TELEGRAM_BOT_TOKEN")
                else:
                    env = dict(_sys2.environ, TELEGRAM_BOT_TOKEN=token)
                    proc = subprocess.Popen(
                        [_sys2.executable, "-m", "bago.api.services.telegram_bot"],
                        cwd=str(Path(__file__).resolve().parents[2]),
                        env=env,
                        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if _sys2.platform == "win32" else 0,
                    )
                    console.print(f"  [green]Telegram bot arrancado[/green] (PID {proc.pid})")
                    console.print("  [dim]Busca tu bot en Telegram y envia /start[/dim]")
            elif bot_arg == "stop":
                console.print("  [yellow]Para detener el bot, busca el PID y mata el proceso.[/yellow]")
            elif bot_arg == "status":
                try:
                    import urllib.request
                    req = urllib.request.Request("http://127.0.0.1:11439/", method="GET")
                    with urllib.request.urlopen(req, timeout=2) as resp:
                        data = resp.read()
                        console.print("  [green]Telegram bot: ONLINE[/green]")
                except Exception:
                    console.print("  [red]Telegram bot: OFFLINE[/red]")
            else:
                pi("Uso: /bot telegram start|stop|status")
        elif bot_name == "utopia":
            import subprocess, sys as _sys2
            if bot_arg == "start":
                proc = subprocess.Popen(
                    [_sys2.executable, "-m", "bago.api.services.utopia_bot"],
                    cwd=str(Path(__file__).resolve().parents[2]),
                    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if _sys2.platform == "win32" else 0,
                )
                console.print(f"  [green]Utopia bot arrancado[/green] (PID {proc.pid})")
            elif bot_arg == "stop":
                console.print("  [yellow]Para detener el bot, busca el PID y mata el proceso.[/yellow]")
            elif bot_arg == "status":
                console.print("  [dim]Verificando conexion Utopia...[/dim]")
                try:
                    import urllib.request, json as _json
                    req = urllib.request.Request(f"http://127.0.0.1:22824/api/1.0/getSystemInformation", method="POST")
                    with urllib.request.urlopen(req, timeout=3) as resp:
                        _json.loads(resp.read())
                        console.print("  [green]Utopia client: ONLINE[/green]")
                except Exception:
                    console.print("  [red]Utopia client: OFFLINE o no accesible[/red]")
            else:
                pi("Uso: /bot utopia start|stop|status")
        else:
            pe(f"Bot desconocido: {bot_name}. Usa telegram o utopia")

    # ── Informes por bot ───────────────────────────────────────────────────────
    elif v == "/informe":
        if not a.strip():
            pi("Uso: /informe <asunto> — Genera un informe y lo envia por el bot activo")
            pi("Ejemplo: /informe resumen de actividad de hoy")
        else:
            from .api.bridge import api_chat
            console.print("  [dim]Generando informe...[/dim]")
            try:
                result = api_chat(
                    messages=[{"role": "user", "content": f"Genera un informe detallado sobre: {a.strip()}"}],
                    system="Eres un asistente de reportes. Genera informes claros, estructurados y concisos.",
                )
                informe = result.get("content", "")
                console.print(Panel(informe, title="[bold]Informe BAGO[/bold]", border_style="green", expand=False))
                console.print("  [dim]Para enviar por Telegram o Utopia, copia el texto.[/dim]")
            except Exception as e:
                pe(f"Error generando informe: {e}")

    # ── API server ──────────────────────────────────────────────────────────────
    elif v == "/serve":
        import subprocess, sys as _sys
        port = a.strip() if a.strip() else "11435"
        try:
            port_int = int(port)
        except ValueError:
            pe(f"Puerto invalido: {port}")
            return True
        pi(f"[cyan]Arrancando BAGO API en puerto {port_int}...[/cyan]")
        try:
            proc = subprocess.Popen(
                [_sys.executable, "-m", "bago.api.server", "--port", str(port_int)],
                cwd=str(Path(__file__).resolve().parents[2]),
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if _sys.platform == "win32" else 0,
            )
            console.print(f"  [green]BAGO API arrancado[/green] (PID {proc.pid}, puerto {port_int})")
            console.print(f"  [dim]Endpoints: http://127.0.0.1:{port_int}/docs[/dim]")
            console.print(f"  [dim]Usa /api on para enrutar chat via API[/dim]")
        except Exception as exc:
            pe(f"Error arrancando API: {exc}")
    elif v == "/api":
        from .api.bridge import set_mode, get_mode, detect_mode, api_health
        if not a.strip():
            mode = get_mode()
            h = api_health()
            score = h.get("score", 0)
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
        elif a.strip().lower() == "on":
            set_mode("api")
            pi("Modo API: [green]ACTIVADO[/green] — chat via HTTP API")
        elif a.strip().lower() == "off":
            set_mode("direct")
            pi("Modo API: [yellow]DESACTIVADO[/yellow] — chat directo")
        elif a.strip().lower() == "hybrid":
            set_mode("hybrid")
            pi("Modo API: [cyan]HIBRIDO[/cyan] — intenta API primero, cae a directo")
        elif a.strip().lower() == "status":
            from .api.bridge import api_health, api_tags, api_services
            h = api_health()
            t = api_tags()
            s = api_services()
            providers_list = ""
            for svc, info in s.items():
                avail = "[green]OK[/green]" if info.get("available") else "[red]DOWN[/red]"
                providers_list += f"\n    {svc}: {avail} (:{info.get('port', '?')})"
            models_count = len(t.get("models", []))
            console.print(Panel(
                "[bold]Estado API BAGO[/bold]\n\n"
                f"  Health score: {h.get('score', 0)}\n"
                f"  Modelos disponibles: {models_count}\n"
                f"  Servicios:{providers_list or ' (sin datos)'}",
                title="BAGO API Status",
                border_style="cyan",
                expand=False,
            ))
        else:
            pi(f"Opcion desconocida: {a.strip()}. Usa on|off|hybrid|status")

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

    # Comandos del sistema BAGO (desde menu / con !)
    elif v.startswith("!"):
        import subprocess, sys as _sys2, shlex
        sys_cmd = v[1:] + (" " + a if a else "")
        sys_cmd_norm = sys_cmd.replace("git-dirty", "git dirty")
        console.print(f"  [dim]ejecutando: bago {sys_cmd_norm}[/dim]")
        bago_root = Path(__file__).resolve().parents[3]
        try:
            proc = subprocess.run(
                [_sys2.executable, str(bago_root / "bago")] + shlex.split(sys_cmd_norm),
                capture_output=True, text=True, cwd=str(bago_root),
                timeout=30, encoding="utf-8", errors="replace",
            )
            if proc.stdout:
                console.print(proc.stdout)
            if proc.stderr:
                console.print(f"[red]{proc.stderr}[/red]")
            if proc.returncode != 0:
                console.print(f"[red]rc={proc.returncode}[/red]")
        except subprocess.TimeoutExpired:
            console.print("  [red]Timeout (30s). Comando abortado.[/red]")
        except Exception as exc:
            pe(f"Error ejecutando bago {sys_cmd_norm}: {exc}")

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



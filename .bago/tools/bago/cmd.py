
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
from .routing_runtime import apply_preset, clear_contract, load_presets, set_contract
from .commands.provider import cmd_provider as _cmd_provider
from .commands.status import cmd_status as _cmd_status
from .commands.tumba import cmd_tumba as _cmd_tumba
from .commands.bot import cmd_bot as _cmd_bot
from .commands.api import cmd_api as _cmd_api, cmd_serve as _cmd_serve


def _paths() -> tuple[Path, Path, Path]:
    here = Path(__file__).resolve()
    tools_dir = here.parents[1]
    bago_dir = here.parents[2]
    root_dir = here.parents[3]
    return root_dir, bago_dir, tools_dir


def _launcher_args(command_line: str) -> list[str]:
    import shlex
    import sys as _sys

    root_dir, _, _ = _paths()
    py_launcher = root_dir / "bago"
    core_launcher = root_dir / "bago_core" / "launcher.py"
    args = shlex.split(command_line)
    if py_launcher.exists():
        return [_sys.executable, str(py_launcher)] + args
    if core_launcher.exists():
        return [_sys.executable, str(core_launcher)] + args
    cmd_launcher = root_dir / "bago.cmd"
    return [str(cmd_launcher)] + args


def _registry_path() -> Path:
    _, _, tools_dir = _paths()
    return tools_dir / "tool_registry.py"


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
    elif v in ("/provider", "/providers"):
        _cmd_provider(session, a)
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
        _cmd_status(session)

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

    elif v == "/create":
        layer = a.strip() if a else ""
        tools_dir = _paths()[2]
        studio = tools_dir / "creation_studio.py"
        if studio.exists():
            cmdline = [sys.executable, str(studio)]
            if layer:
                cmdline += ["--layer", layer]
            console.print("  [dim]abriendo BAGO Creation Studio...[/dim]")
            subprocess.run(cmdline, cwd=str(_paths()[0]))
        else:
            pe("creation_studio.py no encontrado")

    # ── Modo Tumba ────────────────────────────────────────────────────────────
    elif v == "/tumba":
        _cmd_tumba(session, a)

    # ── Bots de mensajeria ─────────────────────────────────────────────────────
    elif v == "/bot":
        _cmd_bot(session, a)

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
        _cmd_serve(a)
    elif v == "/api":
        _cmd_api(a)

    # ── Sincronizacion + repliegue/letargo ────────────────────────────────────
    elif v == "/sync":
        _cmd_sync(session)

    # ── Memoria y conocimiento ────────────────────────────────────────────────
    elif v == "/memory":
        _cmd_memory(session)

    elif v == "/restart":
        import subprocess, sys as _sys2
        bago_chat = Path(__file__).resolve().parents[2] / "bago_chat.py"
        subprocess.Popen([_sys2.executable, str(bago_chat)], cwd=str(Path(__file__).resolve().parents[3]), creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if _sys2.platform == "win32" else 0)
        pi("Reiniciando BAGO...")
        return False

    elif v == "/contract":
        sub_parts = a.split(None, 1) if a else []
        sub = sub_parts[0].lower() if sub_parts else "show"
        sub_arg = sub_parts[1] if len(sub_parts) > 1 else ""
        if sub in ("show", "status"):
            text = getattr(session, "output_contract", "") or "(sin contrato activo)"
            console.print(Panel(text, title="Contrato activo", border_style="cyan", expand=False))
        elif sub in ("set", "usar"):
            if not sub_arg:
                pe("Uso: /contract set <texto del contrato>")
            else:
                set_contract(sub_arg, source="explicit")
                session.refresh_runtime()
                pi("Contrato activo actualizado.")
        elif sub in ("clear", "off"):
            clear_contract()
            session.refresh_runtime()
            pi("Contrato activo eliminado.")
        else:
            pe("Uso: /contract show | /contract set <texto> | /contract clear")

    elif v == "/preset":
        sub_parts = a.split(None, 1) if a else []
        sub = sub_parts[0].lower() if sub_parts else "show"
        sub_arg = sub_parts[1].strip() if len(sub_parts) > 1 else ""
        presets = load_presets()
        if sub in ("show", "status"):
            current = getattr(session, "routing_preset", "balanced")
            info = presets.get(current, {})
            console.print(Panel(f"Preset: {current}\n\n{info.get('description', '')}", title="Preset activo", border_style="cyan", expand=False))
        elif sub == "list":
            for name, info in presets.items():
                console.print(f"  [cyan]{name}[/cyan]  [dim]{info.get('description', '')}[/dim]")
        elif sub in ("apply", "use"):
            if not sub_arg:
                pe("Uso: /preset apply <nombre>")
            else:
                try:
                    apply_preset(sub_arg)
                except KeyError:
                    pe(f"Preset desconocido: {sub_arg}")
                else:
                    session.refresh_runtime()
                    pi(f"Preset activo: {sub_arg}")
        else:
            pe("Uso: /preset show | /preset list | /preset apply <nombre>")
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

    elif v == "/portable":
        tools_dir = _paths()[2]
        portable = tools_dir / "bago_portable.py"
        if portable.exists():
            console.print("  [dim]abriendo BAGO Portable...[/dim]")
            subprocess.run([sys.executable, str(portable)], cwd=str(_paths()[0]))
        else:
            pe("bago_portable.py no encontrado")

    # Comandos del sistema BAGO (desde menu / con !)
    elif v.startswith("!"):
        import subprocess
        sys_cmd = v[1:] + (" " + a if a else "")
        sys_cmd_norm = sys_cmd.replace("git-dirty", "git dirty")
        console.print(f"  [dim]ejecutando: bago {sys_cmd_norm}[/dim]")
        try:
            proc = subprocess.run(
                _launcher_args(sys_cmd_norm),
                capture_output=True, text=True, cwd=str(_paths()[0]),
                timeout=30, encoding="utf-8", errors="replace",
            )
            if proc.stdout:
                console.print(proc.stdout)
            if proc.stderr:
                console.print(f"[red]{proc.stderr}[/red]")
            if proc.returncode != 0:
                console.print(f"[red]rc={proc.returncode}[/red]")
            elif not proc.stdout.strip() and not proc.stderr.strip():
                console.print("  [dim]completado sin salida[/dim]")
        except subprocess.TimeoutExpired:
            console.print("  [red]Timeout (30s). Comando abortado.[/red]")
        except Exception as exc:
            pe(f"Error ejecutando bago {sys_cmd_norm}: {exc}")

    else:
        if v.startswith("/"):
            reg_cmd = v[1:]
            try:
                import importlib.util, subprocess, sys as _sys2
                reg_path = _registry_path()
                if reg_path.exists():
                    spec = importlib.util.spec_from_file_location("_bago_repl_registry", str(reg_path))
                    mod = importlib.util.module_from_spec(spec)
                    _sys2.modules[spec.name] = mod
                    spec.loader.exec_module(mod)
                    registry = getattr(mod, "REGISTRY", {})
                    if reg_cmd in registry:
                        sys_cmd_norm = reg_cmd + (" " + a if a else "")
                        console.print(f"  [dim]ejecutando: bago {sys_cmd_norm}[/dim]")
                        proc = subprocess.run(
                            _launcher_args(sys_cmd_norm),
                            capture_output=True, text=True, cwd=str(_paths()[0]),
                            timeout=30, encoding="utf-8", errors="replace",
                        )
                        if proc.stdout:
                            console.print(proc.stdout)
                        if proc.stderr:
                            console.print(f"[red]{proc.stderr}[/red]")
                        if proc.returncode != 0:
                            console.print(f"[red]rc={proc.returncode}[/red]")
                        elif not proc.stdout.strip() and not proc.stderr.strip():
                            console.print("  [dim]completado sin salida[/dim]")
                        return True
            except Exception as exc:
                pe(f"Error ejecutando {v}: {exc}")
                return True
        # ── Atajos de agente (/code /debug /arch /sprint /refactor /git …) ────
        _agents_file = _paths()[1] / "state" / "agents_registry.json"
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




